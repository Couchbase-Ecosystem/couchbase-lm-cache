# SPDX-License-Identifier: Apache-2.0
"""Time-to-first-token with and without the Couchbase KV-cache tier.

Uses one LMCache server + vLLM pair from ``docker/compose.yaml`` (``b`` by
default) and measures what a restart costs with and without Couchbase:

1. Send ``--prompts`` unique long prompts cold and record TTFT; LMCache writes
   their KV cache to Couchbase.
2. Recreate the LMCache server and vLLM containers, wiping GPU and CPU caches,
   and send one short warm-up request.
3. Send the same prompts again (their KV cache can only come from Couchbase)
   and the same number of new prompts (cold, same warmed-up server).

Example with a larger model on GPU 1::

    MODEL=Qwen/Qwen3-8B GPU_MEMORY_UTILIZATION=0.85 \\
      docker compose -f docker/compose.yaml up -d --force-recreate lmcache-b vllm-b
    MODEL=Qwen/Qwen3-8B GPU_MEMORY_UTILIZATION=0.85 \\
      python examples/ttft_benchmark.py --prompts 5

Results go to ``evidence/ttft-<timestamp>/`` as ``results.json`` and
``report.md``. Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from vllm_e2e_demo import (
    COMPOSE,
    ROOT,
    Couchbase,
    answer,
    build_prompt,
    container_logs,
    http_json,
    l2_hits,
    log,
    stream_completion,
    wait_healthy,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pair", choices=["a", "b"], default="b")
    parser.add_argument("--prompts", type=int, default=5)
    parser.add_argument("--facts", type=int, default=330, help="prompt length knob")
    parser.add_argument("--max-tokens", type=int, default=24)
    parser.add_argument("--couchbase", default="http://localhost:9091")
    parser.add_argument("--couchbase-auth", default="Administrator:password")
    parser.add_argument("--bucket", default="lmcache")
    parser.add_argument("--out", type=Path, default=ROOT / "evidence")
    args = parser.parse_args()

    url = {"a": "http://localhost:8100", "b": "http://localhost:8200"}[args.pair]
    lmcache, vllm = f"lmcache-{args.pair}", f"vllm-{args.pair}"
    run_dir = args.out / f"ttft-{datetime.now():%Y%m%d-%H%M%S}"
    run_dir.mkdir(parents=True)
    couchbase = Couchbase(args.couchbase, args.couchbase_auth, args.bucket)
    wait_healthy(url)
    model = http_json(url + "/v1/models")["data"][0]["id"]
    log(f"Model: {model} on {vllm}; evidence -> {run_dir}")
    stream_completion(url, model, "Warm-up: say hello.", 4)

    def cold_request(seed: str, label: str) -> dict:
        # Let the previous prompt's background writes to Couchbase finish so
        # they do not compete with this prefill.
        before = couchbase.stats()["item_count"]
        prompt, expected = build_prompt(seed, args.facts)
        response = stream_completion(url, model, prompt, args.max_tokens)
        couchbase.wait_for_writes(before)
        log(
            f"{label} {response['prompt_tokens']} tokens: "
            f"TTFT {response['ttft_s'] * 1000:6.0f} ms  answer {answer(response)!r}"
        )
        return {"seed": seed, "expected": expected, **response}

    seeds = [uuid.uuid4().hex[:12] for _ in range(args.prompts)]
    cold = [cold_request(seed, "cold     ") for seed in seeds]
    stats = couchbase.stats()
    log(f"Couchbase: {stats}")

    log(f"Recreating {lmcache} and {vllm} (wipes GPU and CPU KV caches)")
    subprocess.run(
        COMPOSE + ["up", "-d", "--force-recreate", lmcache, vllm],
        check=True,
        capture_output=True,
    )
    wait_healthy(url)
    stream_completion(url, model, "Warm-up: say hello.", 4)
    since = datetime.now(timezone.utc).isoformat()

    warm, fresh = [], []
    for item in cold:
        prompt, _ = build_prompt(item["seed"], args.facts)
        response = stream_completion(url, model, prompt, args.max_tokens)
        warm.append({"seed": item["seed"], "expected": item["expected"], **response})
        log(
            f"couchbase {response['prompt_tokens']} tokens: "
            f"TTFT {response['ttft_s'] * 1000:6.0f} ms  answer {answer(response)!r}"
        )
    for _ in seeds:
        fresh.append(cold_request(uuid.uuid4().hex[:12], "cold (new)"))
    lmcache_log = container_logs(lmcache, since)

    def median_ms(rows: list[dict]) -> float:
        return round(statistics.median(r["ttft_s"] for r in rows) * 1000, 1)

    summary = {
        "model": model,
        "prompts": args.prompts,
        "median_prompt_tokens": statistics.median(r["prompt_tokens"] for r in cold),
        "median_ttft_ms_cold_before_restart": median_ms(cold),
        "median_ttft_ms_cold_after_restart": median_ms(fresh),
        "median_ttft_ms_from_couchbase_after_restart": median_ms(warm),
        "speedup_vs_cold_after_restart": round(median_ms(fresh) / median_ms(warm), 2),
        "chunks_loaded_from_couchbase": l2_hits(lmcache_log),
        "all_answers_correct": all(
            r["expected"] in r["text"] for r in cold + warm + fresh
        ),
        "answers_match_cold_run": all(
            answer(w) == answer(c) for w, c in zip(warm, cold, strict=True)
        ),
        "max_first_token_logprob_delta": round(
            max(
                abs(w["first_token_logprob"] - c["first_token_logprob"])
                for w, c in zip(warm, cold, strict=True)
            ),
            4,
        ),
    }
    results = {
        "started_at": since,
        "summary": summary,
        "cold_before_restart": cold,
        "from_couchbase_after_restart": warm,
        "cold_after_restart": fresh,
        "couchbase": stats,
        "lmcache_log": lmcache_log,
    }
    (run_dir / "results.json").write_text(json.dumps(results, indent=2))
    (run_dir / "report.md").write_text(render_report(results))
    log("Summary: " + json.dumps(summary, indent=2))
    return 0 if summary["all_answers_correct"] else 1


def render_report(results: dict) -> str:
    summary = results["summary"]
    lines = [
        "# Time to first token: recompute vs. Couchbase KV-cache tier",
        "",
        f"- Model: `{summary['model']}`",
        f"- Prompts: {summary['prompts']} unique prompts of "
        f"~{summary['median_prompt_tokens']:.0f} tokens",
        "",
        "| Prompt | Cold TTFT | TTFT after restart, KV from Couchbase | "
        "Cold TTFT after restart (new prompt) | Answer (cold / Couchbase) |",
        "| --- | --- | --- | --- | --- |",
    ]
    rows = zip(
        results["cold_before_restart"],
        results["from_couchbase_after_restart"],
        results["cold_after_restart"],
        strict=True,
    )
    for index, (cold, warm, fresh) in enumerate(rows, start=1):
        lines.append(
            f"| {index} | {cold['ttft_s'] * 1000:.0f} ms "
            f"| {warm['ttft_s'] * 1000:.0f} ms | {fresh['ttft_s'] * 1000:.0f} ms "
            f"| `{answer(cold)}` / `{answer(warm)}` |"
        )
    lines += ["", "## Summary", "", "```json", json.dumps(summary, indent=2), "```", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())

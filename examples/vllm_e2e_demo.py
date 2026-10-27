# SPDX-License-Identifier: Apache-2.0
"""End-to-end demo: two vLLM servers share a KV cache through Couchbase.

Run against the stack in ``docker/compose.yaml`` (LMCache multiprocess mode
with the Couchbase L2 adapter)::

    docker compose -f docker/compose.yaml up -d --build
    python examples/vllm_e2e_demo.py

Per trial, a never-seen-before long prompt is sent to:

1. vLLM A (GPU 0): cold prefill; its LMCache server stores the KV cache in
   Couchbase.
2. vLLM B (GPU 1): a separate server whose LMCache server never saw the
   prompt; it loads the KV cache from Couchbase instead of recomputing it.

Then LMCache server A and vLLM A are restarted (wiping their GPU and CPU
caches) and asked again, so the KV cache can only come from Couchbase. Every
step records time to first token (TTFT), the answer, the first-token
log-probability, LMCache log lines and Couchbase bucket stats. Results are
written to ``evidence/e2e-<timestamp>/`` as ``results.json`` and ``report.md``.

Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import base64
import json
import random
import re
import statistics
import subprocess
import sys
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ["docker", "compose", "-f", str(ROOT / "docker" / "compose.yaml")]
LMCACHE_LOG = re.compile(
    r"Prefetch request completed|Retrieved \d+ tokens|Stored \d+ tokens|"
    r"Couchbase L2 adapter ready"
)
L2_HITS = re.compile(r"retained keys \((\d+) L1, (\d+) L2\)")
COLORS = ["amber", "cobalt", "crimson", "emerald", "indigo", "ivory", "jade", "onyx"]
CITIES = ["Lisbon", "Oslo", "Austin", "Osaka", "Recife", "Krakow", "Perth", "Quito"]


def log(message: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


def http_json(url: str, payload: dict | None = None, auth: str | None = None):
    request = urllib.request.Request(url)
    if payload is not None:
        request.data = json.dumps(payload).encode()
        request.add_header("Content-Type", "application/json")
    if auth:
        request.add_header(
            "Authorization", "Basic " + base64.b64encode(auth.encode()).decode()
        )
    with urllib.request.urlopen(request, timeout=600) as response:
        return json.loads(response.read())


def build_prompt(seed: str, facts: int) -> tuple[str, str]:
    """Return (prompt, expected answer) for a unique long needle-in-a-haystack."""

    rng = random.Random(seed)
    code = f"{rng.randint(1000, 9999)}-{rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}"
    needle_at = rng.randrange(facts // 4, 3 * facts // 4)
    lines = [f"Operations ledger {seed}.", ""]
    for number in range(1, facts + 1):
        if number == needle_at:
            lines.append(f"Note: the master access code for the ledger is {code}.")
        lines.append(
            f"Entry {number}: vault {number} is in {rng.choice(CITIES)}, has a "
            f"{rng.choice(COLORS)} door and was last audited on day "
            f"{rng.randint(1, 365)}."
        )
    lines += ["", "Question: what is the master access code for the ledger?", "Answer:"]
    return "\n".join(lines), code


def stream_completion(base_url: str, model: str, prompt: str, max_tokens: int) -> dict:
    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": 0,
        "logprobs": 1,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    request = urllib.request.Request(
        base_url + "/v1/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    start = time.perf_counter()
    ttft = None
    first_logprob = None
    text = []
    usage = {}
    with urllib.request.urlopen(request, timeout=600) as response:
        for raw in response:
            line = raw.decode().strip()
            if not line.startswith("data:") or line == "data: [DONE]":
                continue
            chunk = json.loads(line[5:])
            if chunk.get("usage"):
                usage = chunk["usage"]
            for choice in chunk.get("choices", []):
                if choice.get("text"):
                    if ttft is None:
                        ttft = time.perf_counter() - start
                        logprobs = (choice.get("logprobs") or {}).get("token_logprobs")
                        first_logprob = logprobs[0] if logprobs else None
                    text.append(choice["text"])
    return {
        "ttft_s": ttft,
        "total_s": time.perf_counter() - start,
        "text": "".join(text),
        "first_token_logprob": first_logprob,
        "prompt_tokens": usage.get("prompt_tokens"),
    }


class Couchbase:
    def __init__(self, url: str, auth: str, bucket: str):
        self.url, self.auth, self.bucket = url, auth, bucket

    def stats(self) -> dict:
        info = http_json(
            f"{self.url}/pools/default/buckets/{self.bucket}", auth=self.auth
        )
        basic = info["basicStats"]
        return {
            "item_count": basic["itemCount"],
            "mem_used_mb": round(basic["memUsed"] / 2**20, 1),
            "data_used_mb": round(basic.get("dataUsed", 0) / 2**20, 1),
        }

    def wait_for_writes(
        self, baseline: int, quiet_s: float = 6.0, timeout_s: float = 300.0
    ) -> dict:
        """Wait for LMCache's asynchronous writes to finish landing.

        LMCache writes to Couchbase in the background after a request, and the
        bucket item count is refreshed with a small lag, so wait until the count
        has grown past ``baseline`` and then stayed unchanged for ``quiet_s``.
        """

        deadline = time.time() + timeout_s
        last = self.stats()
        stable_since = time.time()
        while time.time() < deadline:
            time.sleep(1)
            current = self.stats()
            if current["item_count"] != last["item_count"]:
                last, stable_since = current, time.time()
            elif (
                current["item_count"] > baseline
                and time.time() - stable_since >= quiet_s
            ):
                return current
        return last

    def sample_documents(self, limit: int = 8) -> list[dict]:
        url = (
            f"{self.url}/pools/default/buckets/{self.bucket}/scopes/_default/"
            f"collections/_default/docs?include_docs=false&limit={limit}"
        )
        try:
            rows = http_json(url, auth=self.auth).get("rows", [])
        except Exception as exc:  # noqa: BLE001 - evidence helper only
            return [{"error": str(exc)}]
        return [{"id": row.get("id")} for row in rows]


def container_logs(service: str, since: str) -> list[str]:
    output = subprocess.run(
        COMPOSE + ["logs", "--no-color", "--no-log-prefix", "--since", since, service],
        capture_output=True,
        text=True,
        check=False,
    )
    return [line for line in output.stdout.splitlines() if LMCACHE_LOG.search(line)]


def wait_healthy(base_url: str, timeout_s: float = 900) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base_url + "/health", timeout=5):
                return
        except Exception:  # noqa: BLE001 - server still starting
            time.sleep(3)
    raise TimeoutError(f"{base_url} did not become healthy")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--vllm-a", default="http://localhost:8100")
    parser.add_argument("--vllm-b", default="http://localhost:8200")
    parser.add_argument("--couchbase", default="http://localhost:9091")
    parser.add_argument("--couchbase-auth", default="Administrator:password")
    parser.add_argument("--bucket", default="lmcache")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--facts", type=int, default=220, help="prompt length knob")
    parser.add_argument("--max-tokens", type=int, default=24)
    parser.add_argument("--skip-restart", action="store_true")
    parser.add_argument("--out", type=Path, default=ROOT / "evidence")
    args = parser.parse_args()

    run_dir = args.out / f"e2e-{datetime.now():%Y%m%d-%H%M%S}"
    run_dir.mkdir(parents=True)
    couchbase = Couchbase(args.couchbase, args.couchbase_auth, args.bucket)
    for url in (args.vllm_a, args.vllm_b):
        wait_healthy(url)
    model = http_json(args.vllm_a + "/v1/models")["data"][0]["id"]
    log(f"Model: {model}; evidence -> {run_dir}")
    results: dict = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "couchbase_before": couchbase.stats(),
        "trials": [],
    }
    log(f"Couchbase before: {results['couchbase_before']}")

    for trial in range(1, args.trials + 1):
        seed = uuid.uuid4().hex[:12]
        prompt, expected = build_prompt(seed, args.facts)
        since = datetime.now(timezone.utc).isoformat()
        before = couchbase.stats()["item_count"]

        log(f"Trial {trial}: cold request to vLLM A (prompt never seen before)")
        cold = stream_completion(args.vllm_a, model, prompt, args.max_tokens)
        log(
            f"  A cold: TTFT {cold['ttft_s'] * 1000:.0f} ms over "
            f"{cold['prompt_tokens']} prompt tokens; answer {answer(cold)!r}"
        )
        stats_after_cold = couchbase.wait_for_writes(before)
        log(
            f"  Couchbase now holds {stats_after_cold['item_count']} documents "
            f"(+{stats_after_cold['item_count'] - before}), "
            f"{stats_after_cold['mem_used_mb']} MB in memory"
        )

        log("  Same prompt to vLLM B (other GPU, other LMCache server)")
        shared = stream_completion(args.vllm_b, model, prompt, args.max_tokens)
        log(
            f"  B with KV cache from Couchbase: TTFT {shared['ttft_s'] * 1000:.0f} ms; "
            f"answer {answer(shared)!r}"
        )
        b_log = container_logs("lmcache-b", since)

        baseline_prompt, _ = build_prompt(uuid.uuid4().hex[:12], args.facts)
        before = couchbase.stats()["item_count"]
        baseline = stream_completion(
            args.vllm_b, model, baseline_prompt, args.max_tokens
        )
        couchbase.wait_for_writes(before)
        log(
            "  B cold baseline (different prompt): "
            f"TTFT {baseline['ttft_s'] * 1000:.0f} ms"
        )

        results["trials"].append(
            {
                "trial": trial,
                "seed": seed,
                "expected_answer": expected,
                "vllm_a_cold": cold,
                "vllm_b_from_couchbase": shared,
                "vllm_b_cold_baseline": baseline,
                "answer_correct_a": expected in cold["text"],
                "answer_correct_b": expected in shared["text"],
                "couchbase_l2_chunks_loaded_by_b": l2_hits(b_log),
                "couchbase_after_cold": stats_after_cold,
                "lmcache_a_log": container_logs("lmcache-a", since),
                "lmcache_b_log": b_log,
            }
        )

    if not args.skip_restart:
        first = results["trials"][0]
        prompt, expected = build_prompt(first["seed"], args.facts)
        log("Restarting LMCache server A and vLLM A (wipes GPU and CPU caches)")
        # Recreate rather than restart: vllm-a shares lmcache-a's network
        # namespace, so it must rejoin the new container's namespace.
        subprocess.run(
            COMPOSE + ["up", "-d", "--force-recreate", "lmcache-a", "vllm-a"],
            check=True,
            capture_output=True,
        )
        wait_healthy(args.vllm_a)
        # The first request after a restart pays one-time warm-up costs (CUDA
        # graphs, kernel JIT); use a short unrelated prompt for that.
        stream_completion(args.vllm_a, model, "Warm-up: say hello.", 4)
        since = datetime.now(timezone.utc).isoformat()
        restarted = stream_completion(args.vllm_a, model, prompt, args.max_tokens)
        a_log = container_logs("lmcache-a", since)
        log(
            "  A after restart, trial-1 prompt: "
            f"TTFT {restarted['ttft_s'] * 1000:.0f} ms; answer {answer(restarted)!r}"
        )
        results["restart"] = {
            "vllm_a_after_restart": restarted,
            "answer_correct": expected in restarted["text"],
            "couchbase_l2_chunks_loaded": l2_hits(a_log),
            "lmcache_a_log": a_log,
        }

    results["couchbase_after"] = couchbase.stats()
    results["couchbase_sample_documents"] = couchbase.sample_documents()
    results["finished_at"] = datetime.now(timezone.utc).isoformat()
    results["summary"] = summarize(results)

    (run_dir / "results.json").write_text(json.dumps(results, indent=2))
    (run_dir / "report.md").write_text(render_report(results))
    log("Summary: " + json.dumps(results["summary"], indent=2))
    log(f"Saved {run_dir / 'results.json'} and {run_dir / 'report.md'}")
    return 0 if results["summary"]["passed"] else 1


def answer(response: dict) -> str:
    return response["text"].strip().splitlines()[0] if response["text"].strip() else ""


def l2_hits(lines: list[str]) -> int:
    """Number of chunks LMCache reported loading from the Couchbase L2 tier."""

    return sum(int(match.group(2)) for line in lines if (match := L2_HITS.search(line)))


def summarize(results: dict) -> dict:
    trials = results["trials"]

    def median_ms(field: str) -> float:
        return round(statistics.median(t[field]["ttft_s"] for t in trials) * 1000, 1)

    summary = {
        "trials": len(trials),
        "median_ttft_ms_vllm_a_cold": median_ms("vllm_a_cold"),
        "median_ttft_ms_vllm_b_cold": median_ms("vllm_b_cold_baseline"),
        "median_ttft_ms_vllm_b_from_couchbase": median_ms("vllm_b_from_couchbase"),
        "all_answers_correct": all(
            t["answer_correct_a"] and t["answer_correct_b"] for t in trials
        ),
        "every_trial_loaded_from_couchbase": all(
            t["couchbase_l2_chunks_loaded_by_b"] > 0 for t in trials
        ),
        "max_first_token_logprob_delta": round(
            max(
                abs(
                    t["vllm_a_cold"]["first_token_logprob"]
                    - t["vllm_b_from_couchbase"]["first_token_logprob"]
                )
                for t in trials
            ),
            4,
        ),
        "couchbase_documents_added": results["couchbase_after"]["item_count"]
        - results["couchbase_before"]["item_count"],
    }
    passed = (
        summary["all_answers_correct"] and summary["every_trial_loaded_from_couchbase"]
    )
    if "restart" in results:
        restart = results["restart"]
        summary["ttft_ms_vllm_a_after_restart"] = round(
            restart["vllm_a_after_restart"]["ttft_s"] * 1000, 1
        )
        summary["restart_answer_correct"] = restart["answer_correct"]
        summary["restart_loaded_from_couchbase"] = (
            restart["couchbase_l2_chunks_loaded"] > 0
        )
        passed = (
            passed
            and restart["answer_correct"]
            and summary["restart_loaded_from_couchbase"]
        )
    summary["passed"] = passed
    return summary


def render_report(results: dict) -> str:
    summary = results["summary"]
    lines = [
        "# vLLM + LMCache + Couchbase end-to-end run",
        "",
        f"- Model: `{results['model']}`",
        f"- Started: {results['started_at']}",
        f"- Result: **{'PASS' if summary['passed'] else 'FAIL'}**",
        "",
        "| Trial | Prompt tokens | A cold TTFT | B from Couchbase TTFT | "
        "B cold TTFT | Chunks from Couchbase | Expected | A answer | B answer |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for t in results["trials"]:
        lines.append(
            f"| {t['trial']} | {t['vllm_a_cold']['prompt_tokens']} "
            f"| {t['vllm_a_cold']['ttft_s'] * 1000:.0f} ms "
            f"| {t['vllm_b_from_couchbase']['ttft_s'] * 1000:.0f} ms "
            f"| {t['vllm_b_cold_baseline']['ttft_s'] * 1000:.0f} ms "
            f"| {t['couchbase_l2_chunks_loaded_by_b']} "
            f"| `{t['expected_answer']}` | `{answer(t['vllm_a_cold'])}` "
            f"| `{answer(t['vllm_b_from_couchbase'])}` |"
        )
    if "restart" in results:
        restart = results["restart"]
        lines += [
            "",
            "After restarting LMCache server A and vLLM A, the trial-1 prompt was "
            f"answered `{answer(restart['vllm_a_after_restart'])}` with TTFT "
            f"{restart['vllm_a_after_restart']['ttft_s'] * 1000:.0f} ms, loading "
            f"{restart['couchbase_l2_chunks_loaded']} chunks from Couchbase.",
        ]
    lines += [
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(summary, indent=2),
        "```",
        "",
        f"Couchbase before: `{results['couchbase_before']}`  ",
        f"Couchbase after: `{results['couchbase_after']}`",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())

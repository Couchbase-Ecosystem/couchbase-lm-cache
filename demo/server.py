# SPDX-License-Identifier: Apache-2.0
"""Backend for the explainer demo UI (``demo/static/index.html``).

Runs next to the stack in ``docker/compose.yaml`` and exposes, as server-sent
events, everything the UI visualizes -- all of it live, nothing scripted:

- ``/api/complete?server=a|b&doc=main|other``: proxies one real streaming
  ``/v1/completions`` call to vLLM A or B and reports when it was sent, the time
  to first token and the generated text.
- ``/api/events``: Couchbase bucket stats (polled every 500 ms) and LMCache
  server log events (Couchbase lookups, stores and loads, prefetches), tailed
  from ``docker compose logs``.
- ``/api/docs``: the two demo documents (a preview, token counts, answers).

    python demo/server.py            # then open http://localhost:8711

Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import base64
import json
import queue
import re
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))
from vllm_e2e_demo import build_prompt  # noqa: E402

STATIC = Path(__file__).resolve().parent / "static"
COMPOSE = ["docker", "compose", "-f", str(ROOT / "docker" / "compose.yaml")]
SERVERS = {"a": "http://localhost:8100", "b": "http://localhost:8200"}
# End the answer after its first sentence so the clip shows just the answer.
STOP = ["\n", ". "]

LOG_EVENTS = [
    (
        "lookup",
        re.compile(r"Couchbase L2 lookup: (?P<found>\d+) of (?P<total>\d+) chunks"),
    ),
    (
        "stored",
        re.compile(
            r"Couchbase L2 stored (?P<chunks>\d+) chunks \((?P<mb>[\d.]+) MB\) "
            r"in (?P<ms>\d+) ms"
        ),
    ),
    (
        "loaded",
        re.compile(
            r"Couchbase L2 loaded (?P<chunks>\d+) chunks \((?P<mb>[\d.]+) MB\) "
            r"in (?P<ms>\d+) ms"
        ),
    ),
    (
        "prefetch",
        re.compile(
            r"retained keys \((?P<l1>\d+) L1, (?P<l2>\d+) L2\) in (?P<ms>[\d.]+) ms"
        ),
    ),
    ("to_gpu", re.compile(r"Retrieved (?P<tokens>\d+) tokens in (?P<s>[\d.]+) sec")),
    ("from_gpu", re.compile(r"Stored (?P<tokens>\d+) tokens in (?P<s>[\d.]+) sec")),
]


class Hub:
    """Fans events out to every connected ``/api/events`` client."""

    def __init__(self) -> None:
        self._subscribers: list[queue.Queue] = []
        self._lock = threading.Lock()

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            self._subscribers.remove(q)

    def publish(self, event: dict) -> None:
        event.setdefault("t", time.time())
        with self._lock:
            for q in self._subscribers:
                q.put(event)


ANSI = re.compile(r"\x1b\[[0-9;]*m")
LOG_PREFIX = re.compile(r"^.*?\| \[[\d-]+ (?P<time>[\d:]+),\d+\] LMCache \w+: ")
LOG_SOURCE = re.compile(r" \([\w./]+:\d+:[\w.]+\)\s*$")


def clean_log_line(line: str) -> str:
    """``HH:MM:SS message`` from a raw ``docker compose logs`` LMCache line."""

    line = ANSI.sub("", line).rstrip()
    match = LOG_PREFIX.match(line)
    message = LOG_SOURCE.sub("", line[match.end() :] if match else line)
    return f"{match.group('time')} {message}" if match else message


def tail_lmcache_logs(hub: Hub) -> None:
    process = subprocess.Popen(
        [
            *COMPOSE,
            "logs",
            "-f",
            "--no-color",
            "--since",
            "1s",
            "lmcache-a",
            "lmcache-b",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    assert process.stdout is not None
    for line in process.stdout:
        service = "a" if line.startswith("lmcache-a") else "b"
        for kind, pattern in LOG_EVENTS:
            if match := pattern.search(line):
                hub.publish(
                    {
                        "type": kind,
                        "server": service,
                        "line": clean_log_line(line),
                        **match.groupdict(),
                    }
                )
                break


def poll_couchbase(hub: Hub, url: str, auth: str, bucket: str) -> None:
    header = "Basic " + base64.b64encode(auth.encode()).decode()
    while True:
        try:
            request = urllib.request.Request(
                f"{url}/pools/default/buckets/{bucket}",
                headers={"Authorization": header},
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                stats = json.loads(response.read())["basicStats"]
            hub.publish(
                {
                    "type": "couchbase",
                    "items": stats["itemCount"],
                    "mem_mb": round(stats["memUsed"] / 2**20),
                }
            )
        except Exception as exc:  # noqa: BLE001 - keep polling
            hub.publish({"type": "couchbase_error", "error": str(exc)})
        time.sleep(0.5)


def count_tokens(base_url: str, model: str, prompt: str) -> int:
    request = urllib.request.Request(
        base_url + "/tokenize",
        data=json.dumps({"model": model, "prompt": prompt}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return int(json.loads(response.read())["count"])


class DemoState:
    def __init__(self, facts: int) -> None:
        with urllib.request.urlopen(SERVERS["a"] + "/v1/models", timeout=10) as r:
            self.model = json.loads(r.read())["data"][0]["id"]
        self.docs = {}
        for name in ("main", "other"):
            seed = uuid.uuid4().hex[:12]
            prompt, answer = build_prompt(seed, facts)
            self.docs[name] = {
                "prompt": prompt,
                "answer": answer,
                "tokens": count_tokens(SERVERS["a"], self.model, prompt),
            }


def make_handler(hub: Hub, state: DemoState, max_tokens: int):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(STATIC), **kwargs)

        def log_message(self, *args) -> None:
            pass

        def _sse_start(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()

        def _sse(self, event: dict) -> None:
            self.wfile.write(f"data: {json.dumps(event)}\n\n".encode())
            self.wfile.flush()

        def do_GET(self) -> None:  # noqa: N802 - http.server API
            url = urlparse(self.path)
            if url.path == "/api/docs":
                body = json.dumps(
                    {
                        "model": state.model,
                        "max_tokens": max_tokens,
                        "stop": STOP,
                        "docs": {
                            name: {
                                "head": doc["prompt"][:420],
                                "tail": doc["prompt"][-140:],
                                "chars": len(doc["prompt"]),
                                "tokens": doc["tokens"],
                                "answer": doc["answer"],
                            }
                            for name, doc in state.docs.items()
                        },
                    }
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            elif url.path == "/api/events":
                self._sse_start()
                q = hub.subscribe()
                try:
                    while True:
                        self._sse(q.get())
                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    hub.unsubscribe(q)
            elif url.path == "/api/complete":
                params = parse_qs(url.query)
                self._complete(params["server"][0], params["doc"][0])
            else:
                super().do_GET()

        def _complete(self, server: str, doc_name: str) -> None:
            self._sse_start()
            payload = {
                "model": state.model,
                "prompt": state.docs[doc_name]["prompt"],
                "max_tokens": max_tokens,
                "temperature": 0,
                "stop": STOP,
                "stream": True,
            }
            request = urllib.request.Request(
                SERVERS[server] + "/v1/completions",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            start = time.perf_counter()
            self._sse({"type": "sent", "server": server})
            hub.publish({"type": "request", "server": server, "doc": doc_name})
            first = None
            with urllib.request.urlopen(request, timeout=600) as response:
                for raw in response:
                    line = raw.decode().strip()
                    if not line.startswith("data:") or line == "data: [DONE]":
                        continue
                    for choice in json.loads(line[5:]).get("choices", []):
                        text = choice.get("text")
                        if not text:
                            continue
                        if first is None:
                            first = time.perf_counter() - start
                            self._sse({"type": "first_token", "ttft": first})
                            hub.publish(
                                {"type": "first_token", "server": server, "ttft": first}
                            )
                        self._sse({"type": "token", "text": text})
            self._sse({"type": "done", "ttft": first})

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8711)
    parser.add_argument("--facts", type=int, default=330, help="document length knob")
    parser.add_argument("--max-tokens", type=int, default=32)
    parser.add_argument("--couchbase", default="http://localhost:9091")
    parser.add_argument("--couchbase-auth", default="Administrator:password")
    parser.add_argument("--bucket", default="lmcache")
    args = parser.parse_args()

    hub = Hub()
    state = DemoState(args.facts)
    threading.Thread(target=tail_lmcache_logs, args=(hub,), daemon=True).start()
    threading.Thread(
        target=poll_couchbase,
        args=(hub, args.couchbase, args.couchbase_auth, args.bucket),
        daemon=True,
    ).start()
    server = ThreadingHTTPServer(
        ("127.0.0.1", args.port), make_handler(hub, state, args.max_tokens)
    )
    print(f"Demo UI on http://localhost:{args.port} (model {state.model})", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())

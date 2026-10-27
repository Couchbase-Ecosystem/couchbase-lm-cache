# Evidence: Couchbase as an LMCache KV-cache tier for vLLM

Recorded on 2026-10-26 on one workstation: 2x NVIDIA RTX 3090, 24 cores,
121 GB RAM. Stack: `lmcache/vllm-openai:v0.5.6` (LMCache 0.5.6, vLLM 0.31.0)
plus this package (0.2.0), Couchbase Server 8.0.2 Enterprise in Docker (single
node), Couchbase Python SDK 4.6.3. LMCache runs in multiprocess (MP) mode with
the Couchbase L2 adapter (`docker/compose.yaml`).

Every prompt is a unique ~10k-token (8B) or ~7k-token (0.6B) ledger with one
hidden access code, so each answer can be checked.

| Path | What it shows |
| --- | --- |
| `recordings/01-demo.mp4` | 62 s, 1080p, one live run with no narration. Three columns: server A gets document X (10,288 tokens) and its LMCache log shows `Couchbase L2 lookup: 0 of 40 chunks found`, then the KV cache being stored to Couchbase while the GPU computes (time to first token **2.71 s**); server B gets the same request, finds `40 of 40 chunks`, loads them (1.5 GB in 0.83 s) and answers in **1.17 s** with the same answer (6692-J); server B then gets a different document Y and computes it (**2.65 s**). Bottom strip: live Couchbase bucket document count (0 → 1,480 → 2,960). Every request, timing and log line on screen is real. |
| `recordings/02-couchbase-buckets.mp4` | The Couchbase web console's bucket list recorded during the same run (same timeline as `01-demo.mp4`): items going from 0 to 1,480 to 2,960, 100% resident. |
| `recordings/03-couchbase-documents.mp4` | 38 s in the Couchbase console after the run: the `lmcache` documents, a KV-cache chunk's JSON manifest (`{"lmcache_shards": 36, "bytes": 37748736}`), its binary 1 MiB shard documents, and the manifest's metadata. |
| `recordings/markers.json` | When each request, first token and step happened, in seconds from the start of `01-demo.mp4` / `02-couchbase-buckets.mp4`, with the measured times. |
| `ttft-20261026-191832/` | Restart benchmark, Qwen3-8B, 5 prompts: after recreating the LMCache and vLLM containers (GPU and CPU caches wiped), median time to first token is **1.14 s from Couchbase vs 2.69 s recomputed (2.35x)**; 15/15 answers correct and identical to the cold run. The first two loads after the restart took 3.0 s and 3.5 s, with the bucket at its memory high-water mark (13.8 of 16 GB). |
| `e2e-20261026-180055/` | Functional end-to-end run with Qwen3-0.6B on both GPUs: 3 trials of server-to-server sharing plus a restart, all answers correct, every trial loaded from Couchbase. With a model this small, recomputing (0.25 s) is faster than loading (about 1 s). |
| `ttft-20261026-183124-host-cpu-saturated/` | The same 8B restart benchmark while unrelated jobs saturated the CPU (load average ~35 on 24 cores): answers still correct, but loading from Couchbase (3.5-3.9 s) lost to recomputation. Couchbase reads need CPU headroom. |
| `01-pytest-live-lmcache-couchbase.txt`, `pytest-live.xml` | 48 tests passing inside the LMCache image against live Couchbase: unit tests, the in-process connector through LMCache's `RemoteBackend`, and the MP-mode L2 adapter through LMCache's adapter registry, including 25 MiB payloads above Couchbase's 20 MiB document limit. |

Re-run everything with the commands below; [docs/demo.md](../docs/demo.md)
explains every step, including setting up GPU access for Docker:

```bash
export MODEL=Qwen/Qwen3-8B GPU_MEMORY_UTILIZATION=0.85 LMCACHE_L1_SIZE_GB=16
export COUCHBASE_RAM_MB=18432 COUCHBASE_BUCKET_RAM_MB=16384
docker compose -f docker/compose.yaml up -d --build
python demo/server.py &                 # evidence page on http://localhost:8711
python demo/record.py                   # records evidence/recordings (needs playwright + Chrome)
python examples/ttft_benchmark.py       # restart benchmark
python examples/vllm_e2e_demo.py        # sharing + restart, 3 trials
```

## Why MP mode

LMCache 0.5.6's in-process `LMCacheConnectorV1` loads cached KV
non-deterministically with vLLM 0.31's packed KV layout, on every storage
backend including LMCache's own CPU tier
([LMCache#4463](https://github.com/LMCache/LMCache/issues/4463)). We confirmed it
on this machine with first-token log-probability probes (same prompt, greedy):

| Setup | Cold | Load 1 | Load 2 | Load 3 |
| --- | --- | --- | --- | --- |
| vLLM prefix cache only (no LMCache) | -0.4776 | -0.5367 | -0.5367 | -0.5367 |
| In-process LMCache, CPU tier | -0.6467 | -0.4270 | -0.5028 | n/a |
| In-process LMCache, built-in `fs` connector | -0.3600 | -0.0754 | -0.1196 | n/a |
| In-process LMCache, Couchbase connector | -0.3690 | -0.0647 | -0.0621 | n/a |
| **LMCache MP mode, CPU tier** | -0.3889 | -0.3920 | -0.3920 | -0.3920 |

Each row used its own prompt, so compare loads within a row. Loads should
repeat exactly, as vLLM's prefix cache and MP mode do. In-process loads change
from load to load on every backend. Separately, the KV chunks the Couchbase
connector stored from two separate processes were byte-identical (26 of 26).

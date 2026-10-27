# Browser demo

A live view of two vLLM servers sharing a KV cache through Couchbase: the
requests, time to first token, LMCache log lines and the bucket's document
count, all from the running stack.

- `server.py`: backend on http://localhost:8711 (standard library only).
- `static/index.html`: the page; press Space or open `/?autoplay` to run it.
- `record.py`, `cursor.js`: record the page and the Couchbase console as 1080p
  clips (needs Playwright, Google Chrome and ffmpeg).

Setup, from GPU access for Docker to recording:
[docs/demo.md](../docs/demo.md).

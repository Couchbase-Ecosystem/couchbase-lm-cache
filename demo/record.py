# SPDX-License-Identifier: Apache-2.0
"""Record the explainer demo and the Couchbase console as 1080p video clips.

Needs ``pip install playwright`` and Google Chrome (used through Playwright's
``chrome`` channel), the stack from ``docker/compose.yaml`` and the demo
backend (``python demo/server.py``). Produces, in ``--out``:

- ``01-demo.mp4``: the evidence page (requests, timings, LMCache logs, bucket
  stats), one continuous live run.
- ``02-couchbase-buckets.mp4``: the Couchbase console's bucket list recorded at
  the same time, showing the document count grow and stay put.
- ``03-couchbase-documents.mp4``: the Couchbase console opening the KV-cache
  documents (a chunk manifest and its binary shards).
- ``markers.json``: when each scene and request happened in ``01-demo.mp4``
  (seconds from the start of the clip), for editing.

Frames come from Chrome's screencast and are encoded at a constant 30 fps.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import shutil
import subprocess
from pathlib import Path

from playwright.async_api import Page, async_playwright

CURSOR_JS = (Path(__file__).resolve().parent / "cursor.js").read_text()


class Screencast:
    """Collects Chrome screencast frames for one page and encodes them."""

    def __init__(self, page: Page, frames_dir: Path, width: int, height: int):
        self.page, self.dir, self.width, self.height = page, frames_dir, width, height
        self.frames: list[tuple[float, Path]] = []
        self.started_wall: float | None = None

    async def start(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.cdp = await self.page.context.new_cdp_session(self.page)
        self.cdp.on("Page.screencastFrame", self._on_frame)
        await self.cdp.send(
            "Page.startScreencast",
            {
                "format": "jpeg",
                "quality": 95,
                "maxWidth": self.width,
                "maxHeight": self.height,
                "everyNthFrame": 1,
            },
        )

    def _on_frame(self, params: dict) -> None:
        stamp = params["metadata"]["timestamp"]
        if self.started_wall is None:
            self.started_wall = stamp
        path = self.dir / f"{len(self.frames):06d}.jpg"
        path.write_bytes(base64.b64decode(params["data"]))
        self.frames.append((stamp, path))
        asyncio.ensure_future(
            self.cdp.send("Page.screencastFrameAck", {"sessionId": params["sessionId"]})
        )

    async def stop(self, hold_last: float = 1.0) -> None:
        await self.cdp.send("Page.stopScreencast")
        self.hold_last = hold_last

    def trim_before(self, wall: float) -> None:
        """Drop frames captured before ``wall`` (keeping the last one before it)."""

        earlier = [f for f in self.frames if f[0] < wall]
        self.frames = earlier[-1:] + [f for f in self.frames if f[0] >= wall]

    def encode(self, output: Path, fps: int = 30) -> None:
        listing = self.dir / "frames.txt"
        lines = []
        for (stamp, path), nxt in zip(
            self.frames, self.frames[1:] + [None], strict=True
        ):
            duration = (nxt[0] - stamp) if nxt else self.hold_last
            lines += [f"file '{path.name}'", f"duration {max(duration, 0.001):.4f}"]
        lines.append(f"file '{self.frames[-1][1].name}'")
        listing.write_text("\n".join(lines) + "\n")
        subprocess.run(
            [
                "ffmpeg",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(listing),
                "-vf",
                f"fps={fps},scale={self.width}:{self.height}:flags=lanczos,format=yuv420p",
                "-c:v",
                "libx264",
                "-preset",
                "slow",
                "-crf",
                "14",
                "-movflags",
                "+faststart",
                str(output),
            ],
            check=True,
        )


async def couchbase_login(page: Page, url: str, user: str, password: str) -> None:
    await page.goto(f"{url}/ui/index.html")
    await page.fill("#auth-username-input", user)
    await page.fill("#auth-password-input", password)
    await page.keyboard.press("Enter")
    await page.wait_for_selector("a[href^='#/buckets']")


async def glide_click(page: Page, selector: str, pause: float = 0.6) -> None:
    """Move the visible cursor onto an element, then click it."""

    target = page.locator(selector).first
    box = await target.bounding_box()
    assert box, f"{selector} not visible"
    x, y = box["x"] + min(60, box["width"] / 2), box["y"] + 12
    await page.mouse.move(x, y, steps=30)
    await asyncio.sleep(pause)
    await target.click()


def save_live_clips(
    demo_cast: Screencast,
    buckets_cast: Screencast,
    markers: list[dict],
    page_start: float,
    out: Path,
) -> None:
    """Encode the two live clips; they share one timeline from the page start."""

    demo_cast.trim_before(page_start)
    buckets_cast.trim_before(page_start)
    clip_start = demo_cast.frames[0][0]
    for marker in markers:
        marker["video_s"] = round(marker.pop("wall") - clip_start, 2)
    demo_cast.encode(out / "01-demo.mp4")
    buckets_cast.encode(out / "02-couchbase-buckets.mp4")
    (out / "markers.json").write_text(
        json.dumps(
            {
                "note": "video_s = seconds from the start of 01-demo.mp4 "
                "and 02-couchbase-buckets.mp4 (same timeline)",
                "markers": markers,
            },
            indent=2,
        )
    )


async def show_documents(console: Page) -> None:
    """Open the KV-cache documents in the Couchbase console, at a viewer's pace."""

    await asyncio.sleep(1.5)
    await glide_click(console, "a[href^='#/docs']")
    await console.wait_for_selector("text=Retrieve Docs")
    await asyncio.sleep(1.5)
    await glide_click(console, "button:has-text('Retrieve Docs')")
    await console.wait_for_selector("text=lmcache_shards")
    await asyncio.sleep(3.0)
    box = await console.locator("text=lmcache_shards").first.bounding_box()
    assert box
    await console.mouse.move(box["x"] - 30, box["y"] + box["height"] + 18, steps=35)
    await asyncio.sleep(3.0)
    await console.mouse.wheel(0, 420)
    await asyncio.sleep(3.0)
    await console.mouse.wheel(0, -420)
    await asyncio.sleep(1.5)
    await glide_click(console, "a:has-text('lmcache:Qwen')")
    await console.wait_for_selector("text=Edit Document")
    await asyncio.sleep(4.0)
    await glide_click(console, "text=Metadata >> visible=true")
    await asyncio.sleep(4.0)
    await glide_click(console, "text=Data >> visible=true")
    await asyncio.sleep(1.5)
    await glide_click(console, "text=Cancel >> visible=true")
    await asyncio.sleep(1.5)
    await glide_click(console, "a[href^='#/buckets']")
    await asyncio.sleep(3.0)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--demo-url", default="http://localhost:8711/?autoplay")
    parser.add_argument("--couchbase", default="http://localhost:9091")
    parser.add_argument("--user", default="Administrator")
    parser.add_argument("--password", default="password")
    parser.add_argument("--out", type=Path, default=Path("evidence/recordings"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    work = args.out / "frames"
    shutil.rmtree(work, ignore_errors=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", headless=True)
        demo_ctx = await browser.new_context(viewport={"width": 1920, "height": 1080})
        console_ctx = await browser.new_context(
            viewport={"width": 1280, "height": 720}, device_scale_factor=1.5
        )
        await console_ctx.add_init_script(CURSOR_JS)

        # Couchbase console on the bucket list, recorded alongside the demo.
        console = await console_ctx.new_page()
        await couchbase_login(console, args.couchbase, args.user, args.password)
        await console.click("a[href^='#/buckets']")
        await console.wait_for_selector("text=lmcache")
        await console.mouse.move(640, 600)

        demo = await demo_ctx.new_page()
        demo_cast = Screencast(demo, work / "demo", 1920, 1080)
        buckets_cast = Screencast(console, work / "buckets", 1920, 1080)
        await buckets_cast.start()
        await demo_cast.start()
        await demo.goto(args.demo_url)
        page_start = await demo.evaluate("window.__t0_wall")
        await demo.wait_for_function("window.__done === true", timeout=15 * 60 * 1000)
        markers = await demo.evaluate("window.__markers")
        await demo_cast.stop(hold_last=1.5)
        await buckets_cast.stop()
        save_live_clips(demo_cast, buckets_cast, markers, page_start, args.out)

        # The KV-cache documents in the Couchbase console.
        docs_cast = Screencast(console, work / "documents", 1920, 1080)
        await docs_cast.start()
        try:
            await show_documents(console)
        finally:
            await docs_cast.stop(hold_last=1.0)
            await browser.close()
            docs_cast.encode(args.out / "03-couchbase-documents.mp4")

    shutil.rmtree(work, ignore_errors=True)
    print(f"Saved clips and markers to {args.out}")


if __name__ == "__main__":
    asyncio.run(main())

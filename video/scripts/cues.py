#!/usr/bin/env python3
"""Record when each word is spoken in every voice-over clip.

Transcribes public/vo/<Scene>-<n>.mp3 with Whisper (word timestamps) and
writes src/explainer/vo-words.json, which `cue()` in src/explainer/timeline.ts
uses to start an animation on a word in the middle of a line. Run it after
tts.py / pick_voice.py.

    python3 scripts/cues.py
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NARRATION = ROOT / "src" / "explainer" / "narration.json"
WORDS = ROOT / "src" / "explainer" / "vo-words.json"
VO = ROOT / "public" / "vo"


def main() -> None:
    narration = json.loads(NARRATION.read_text())
    ids = [
        f"{scene}-{i}"
        for scene, spec in narration.items()
        for i in range(len(spec["segments"]))
    ]
    with tempfile.TemporaryDirectory() as workdir:
        subprocess.run(
            ["whisper", *(str(VO / f"{i}.mp3") for i in ids), "--model", "small.en",
             "--language", "en", "--word_timestamps", "True", "--output_format",
             "json", "--output_dir", workdir, "--fp16", "False"],
            check=True,
            capture_output=True,
        )
        words = {}
        for i in ids:
            data = json.loads((Path(workdir) / f"{i}.json").read_text())
            words[i] = [
                [re.sub(r"[^a-z0-9]", "", w["word"].lower()), round(w["start"], 2)]
                for segment in data["segments"]
                for w in segment.get("words", [])
            ]
    WORDS.write_text(json.dumps(words, indent=0) + "\n")
    print(f"word timings for {len(words)} clips")


if __name__ == "__main__":
    main()

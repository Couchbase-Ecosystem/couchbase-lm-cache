#!/usr/bin/env python3
"""Pick, for every narration line, the take whose voice matches best.

Reads public/vo/takes/candidates.json (written by `tts.py --engine gemini
--takes N`), embeds every candidate clip with a speaker-verification model
(Resemblyzer), builds one reference voice from the clips that agree with each
other, and copies the closest clip of each line to public/vo/<Scene>-<n>.mp3.
Candidates whose transcript doesn't match the line are skipped. Lengths go to
src/explainer/vo-durations.json.

    pip install resemblyzer webrtcvad-wheels   # plus torch
    python3 scripts/pick_voice.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
from resemblyzer import VoiceEncoder, preprocess_wav

ROOT = Path(__file__).resolve().parent.parent
TAKES = ROOT / "public" / "vo" / "takes"
OUT = ROOT / "public" / "vo"
DURATIONS = ROOT / "src" / "explainer" / "vo-durations.json"
NARRATION = ROOT / "src" / "explainer" / "narration.json"
MIN_MATCH = 0.6  # transcript similarity; numbers spelled out lower it, so keep it loose
LONG_CLIP = 2.5  # seconds; shorter clips give noisier voice embeddings


def load(path: Path) -> np.ndarray:
    raw = subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-f",
            "f32le",
            "-",
        ],
        check=True,
        capture_output=True,
    ).stdout
    return np.frombuffer(raw, np.float32)


def sentences(lines: list[str]) -> list[list[str]]:
    """Group consecutive lines of a scene that belong to one sentence."""

    narration = json.loads(NARRATION.read_text())
    text = {
        f"{scene}-{i}": segment["text"]
        for scene, spec in narration.items()
        for i, segment in enumerate(spec["segments"])
    }
    groups: list[list[str]] = []
    for line in lines:
        previous = groups[-1][-1] if groups else None
        same_scene = previous and previous.rsplit("-", 1)[0] == line.rsplit("-", 1)[0]
        if same_scene and not text[previous].rstrip().endswith((".", "?", "!")):
            groups[-1].append(line)
        else:
            groups.append([line])
    return groups


def main() -> None:
    candidates = json.loads((TAKES / "candidates.json").read_text())
    encoder = VoiceEncoder("cpu", verbose=False)
    for clips in candidates.values():
        for clip in clips:
            clip["embedding"] = encoder.embed_utterance(
                preprocess_wav(load(ROOT / clip["path"]), source_sr=16000)
            )

    # Reference voice: centroid of the long clips, refined twice on the clips
    # closest to it, so drifted stretches don't pull it toward themselves.
    long_clips = [
        c for clips in candidates.values() for c in clips if c["seconds"] >= LONG_CLIP
    ]
    pool = np.array([c["embedding"] for c in long_clips])
    reference = np.median(pool, axis=0)
    for _ in range(2):
        reference /= np.linalg.norm(reference)
        similarity = pool @ reference
        reference = pool[similarity >= np.percentile(similarity, 30)].mean(axis=0)
    reference /= np.linalg.norm(reference)

    # Lines that continue one sentence ("We'll cover the problem," / "the
    # solution,") come from the same take, so a sentence is never stitched from
    # different recordings.
    for clips in candidates.values():
        for clip in clips:
            clip["voice"] = float(clip["embedding"] @ reference)
    chosen, report = {}, {}
    for group in sentences(list(candidates)):
        takes = sorted({c["take"] for c in candidates[group[0]]})

        def score(take: int, group: list[str] = group) -> tuple[bool, bool, float]:
            clips = [next(c for c in candidates[line] if c["take"] == take) for line in group]
            return (
                all(c.get("clean", True) for c in clips),
                all(c["match"] >= MIN_MATCH for c in clips),
                float(np.mean([c["voice"] for c in clips])),
            )

        best_take = max(takes, key=score)
        for line in group:
            best = next(c for c in candidates[line] if c["take"] == best_take)
            chosen[line] = best
            report[line] = {
                "take": best_take,
                "voice": round(best["voice"], 3),
                "seconds": best["seconds"],
                "sentence": group,
                "all": [(c["take"], round(c["voice"], 3), c["match"]) for c in candidates[line]],
            }

    long_scores = [c["voice"] for c in chosen.values() if c["seconds"] >= LONG_CLIP]
    floor = float(np.median(long_scores)) - 0.04
    flagged = [
        line
        for line, c in chosen.items()
        if c["seconds"] >= LONG_CLIP and c["voice"] < floor
    ]

    durations = {}
    for line, clip in chosen.items():
        shutil.copyfile(ROOT / clip["path"], OUT / f"{line}.mp3")
        durations[line] = clip["seconds"]
    DURATIONS.write_text(json.dumps(durations, indent=1) + "\n")
    (TAKES / "choice.json").write_text(json.dumps(report, indent=1) + "\n")

    takes = {}
    for c in chosen.values():
        takes[c["take"]] = takes.get(c["take"], 0) + 1
    print(
        f"chose {len(chosen)} lines from takes {dict(sorted(takes.items()))}; "
        f"voice match median {np.median([c['voice'] for c in chosen.values()]):.3f}"
    )
    for line in flagged:
        print(f"  still off ({chosen[line]['voice']:.3f}): {line}")


if __name__ == "__main__":
    main()

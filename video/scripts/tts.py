#!/usr/bin/env python3
"""Synthesize the explainer voice-over with Google text-to-speech.

Two engines, both writing public/vo/<Scene>-<n>.mp3 for every line of
src/explainer/narration.json and the clip lengths to
src/explainer/vo-durations.json, which drives the scene timing:

- chirp (default): Google Cloud Text-to-Speech, Chirp 3 HD preset voice. Each
  line is synthesized on its own; a preset voice sounds the same on every line.
  Unchanged lines are not re-synthesized.

      GOOGLE_TTS_API_KEY=... python3 scripts/tts.py

- gemini: Gemini text-to-speech. Generative, so the voice drifts between
  requests; the whole narration is generated as one take, transcribed with
  Whisper (word timestamps), aligned to the script and cut at the pauses.
  Requires the `whisper` CLI. --resplit re-cuts the existing take.

      GEMINI_API_KEY=... python3 scripts/tts.py --engine gemini

  With --takes 3, three takes are recorded as candidates and
  scripts/pick_voice.py keeps, per line, the clip whose voice best matches the
  others (speaker embeddings), so a take that drifts doesn't reach the video.

Requires ffmpeg. API keys are read from the environment (or --key-file) and
never written.
"""

from __future__ import annotations

import argparse
import base64
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NARRATION = ROOT / "src" / "explainer" / "narration.json"
DURATIONS = ROOT / "src" / "explainer" / "vo-durations.json"
OUT = ROOT / "public" / "vo"
TAKE = OUT / "take.wav"
TAKE_HASH = OUT / "take.sha256"
ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
CLOUD_TTS = "https://texttospeech.googleapis.com/v1/text:synthesize"

# Style notes go in the prompt; the model speaks only the TRANSCRIPT section.
PROMPT = """# AUDIO PROFILE: Narrator
## THE SCENE: A technical explainer video for software developers, recorded in one take.
### DIRECTOR'S NOTES
Style: friendly developer advocate, calm, warm and conversational. One narrator only: keep exactly the same voice, pitch, energy and pace from start to finish. Never change voice, accent or character, and never act out what other people said. Read every paragraph, in order, and nothing else. Leave a clear pause of about one second between paragraphs.
#### TRANSCRIPT
{text}"""

EDGE_TRIM = (
    "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.03,areverse,"
    "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.03,areverse,"
    "afade=t=in:d=0.01,areverse,afade=t=in:d=0.02,areverse"
)


# ---- synthesis --------------------------------------------------------------


def synthesize(text: str, model: str, voice: str, key: str) -> bytes:
    body = {
        "contents": [{"role": "user", "parts": [{"text": PROMPT.format(text=text)}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}
            },
        },
    }
    request = urllib.request.Request(
        ENDPOINT.format(model=model),
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=900) as response:
                data = json.load(response)
            candidate = data["candidates"][0]
            if candidate.get("finishReason") != "STOP":
                raise KeyError(candidate.get("finishReason"))
            return base64.b64decode(
                candidate["content"]["parts"][0]["inlineData"]["data"]
            )
        except urllib.error.HTTPError as error:
            message = (
                json.loads(error.read() or b"{}").get("error", {}).get("message", "")
            )
            if error.code in (500, 503) and attempt < 3:
                print(f"  {error.code}, retrying: {message[:120]}")
                time.sleep(20 * (attempt + 1))
                continue
            sys.exit(f"Text-to-speech request failed ({error.code}): {message}")
        except (KeyError, IndexError) as error:
            if attempt < 3:
                print(f"  incomplete audio ({error}), retrying")
                continue
            sys.exit("Text-to-speech response had no complete audio")
    raise AssertionError("unreachable")


def synthesize_chirp(text: str, voice: str, key: str) -> bytes:
    body = {
        "input": {"text": text},
        "voice": {"languageCode": voice[:5], "name": voice},
        "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 24000},
    }
    request = urllib.request.Request(
        CLOUD_TTS,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "X-Goog-Api-Key": key},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return base64.b64decode(json.load(response)["audioContent"])
    except urllib.error.HTTPError as error:
        message = json.loads(error.read() or b"{}").get("error", {}).get("message", "")
        sys.exit(f"Cloud Text-to-Speech request failed ({error.code}): {message}")


# ---- alignment ----------------------------------------------------------------

ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
TENS = ["_", "_", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def number_words(n: int) -> list[str]:
    if n < 20:
        return [ONES[n]]
    if n < 100:
        return [TENS[n // 10]] + (number_words(n % 10) if n % 10 else [])
    for size, name in (
        (10**9, "billion"),
        (10**6, "million"),
        (1000, "thousand"),
        (100, "hundred"),
    ):
        if n >= size:
            rest = number_words(n % size) if n % size else []
            return number_words(n // size) + [name] + rest
    raise AssertionError(n)


def tokens(text: str) -> list[str]:
    """Normalize script and transcript text to comparable lowercase words."""

    text = re.sub(
        r"\b(?:[A-Z] )+[A-Z](?:s)?\b", lambda m: m.group(0).replace(" ", ""), text
    )
    text = re.sub(r"(\d),(\d{3})", r"\1\2", text)
    text = re.sub(r"(\d)([A-Za-z])", r"\1 \2", text)
    out: list[str] = []
    for word in re.findall(r"\d+\.\d+|\d+|[a-zA-Z']+", text):
        if re.fullmatch(r"\d+\.\d+", word):
            whole, frac = word.split(".")
            out += number_words(int(whole)) + ["point"] + [ONES[int(d)] for d in frac]
        elif word.isdigit():
            out += number_words(int(word))
        else:
            out.append(word.lower().strip("'"))
    return [t for t in out if t not in ("and", "a", "")]


def transcribe(take: Path, workdir: Path) -> list[dict]:
    subprocess.run(
        [
            "whisper",
            str(take),
            "--model",
            "small.en",
            "--language",
            "en",
            "--word_timestamps",
            "True",
            "--output_format",
            "json",
            "--output_dir",
            str(workdir),
            "--fp16",
            "False",
        ],
        check=True,
        capture_output=True,
    )
    data = json.loads((workdir / f"{take.stem}.json").read_text())
    words = []
    for segment in data["segments"]:
        for w in segment.get("words", []):
            for t in tokens(w["word"]):
                words.append({"token": t, "start": w["start"], "end": w["end"]})
    return words


def silences(take: Path) -> list[tuple[float, float]]:
    log = subprocess.run(
        [
            "ffmpeg",
            "-i",
            str(take),
            "-af",
            "silencedetect=noise=-40dB:d=0.12",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    ).stderr
    marks = [float(v) for v in re.findall(r"silence_(?:start|end): ([0-9.]+)", log)]
    return list(zip(marks[0::2], marks[1::2]))


def cut_points(
    texts: list[str], words: list[dict], gaps: list[tuple[float, float]]
) -> list[float]:
    """Return the time where each line after the first starts in the take."""

    script: list[str] = []
    first_token = []
    for text in texts:
        first_token.append(len(script))
        script += tokens(text)
    # Snap misheard words ("entropic", "quen") to the closest script word.
    vocabulary = set(script)
    heard = [
        w["token"]
        if w["token"] in vocabulary
        else next(
            iter(difflib.get_close_matches(w["token"], vocabulary, n=1, cutoff=0.74)),
            w["token"],
        )
        for w in words
    ]
    matcher = difflib.SequenceMatcher(None, script, heard, autojunk=False)
    to_heard: dict[int, int] = {}
    for block in matcher.get_matching_blocks():
        for k in range(block.size):
            to_heard[block.a + k] = block.b + k

    # Heard words matched to each line; the cut is the longest pause between the
    # last matched word of one line and the first matched word of the next, so
    # words transcribed differently (e.g. "L M Cache" vs "LMCache") don't shift it.
    bounds = first_token + [len(script)]
    matched = [
        [to_heard[j] for j in range(bounds[line], bounds[line + 1]) if j in to_heard]
        for line in range(len(texts))
    ]
    if not matched[0] or not matched[-1]:
        sys.exit("Could not find the first or last line in the take")

    def midpoint(g: tuple[float, float], lo: float, hi: float) -> float:
        return (max(g[0], lo) + min(g[1], hi)) / 2

    # Lines with no matched word (rare) are cut at the longest pauses between
    # their matched neighbours.
    cuts: list[float] = []
    line = 1
    while line < len(texts):
        unmatched = 0
        while not matched[line + unmatched]:
            unmatched += 1
        last, first = (
            words[max(matched[line - 1])],
            words[min(matched[line + unmatched])],
        )
        lo, hi = last["end"] - 0.05, first["start"] + 0.05
        candidates = sorted(
            (g for g in gaps if g[1] > lo and g[0] < hi),
            key=lambda g: g[1] - g[0],
            reverse=True,
        )
        needed = unmatched + 1
        if not unmatched and not candidates:
            # The narrator ran two lines together: cut between the two words.
            cuts.append((last["end"] + first["start"]) / 2)
            line += 1
            continue
        if len(candidates) < needed:
            sys.exit(f"Could not place line {line} in the take: {texts[line]!r}")
        if unmatched:
            print(f"  placed {unmatched} unmatched line(s) at pauses: {texts[line]!r}")
        cuts += sorted(midpoint(g, lo, hi) for g in candidates[:needed])
        line += needed
    return cuts


def check(
    texts: list[str], words: list[dict], bounds: list[tuple[float, float]]
) -> list[float]:
    """Compare what was heard in each clip with its line; print clips to review."""

    ratios = []
    for text, (start, end) in zip(texts, bounds):
        heard = [
            w["token"] for w in words if start <= (w["start"] + w["end"]) / 2 < end
        ]
        ratio = difflib.SequenceMatcher(
            None, tokens(text), heard, autojunk=False
        ).ratio()
        ratios.append(round(ratio, 3))
        if ratio < 0.7:
            print(f"  CHECK ({ratio:.2f}) {text!r}\n        heard: {' '.join(heard)!r}")
    return ratios


# ---- output -------------------------------------------------------------------


def duration_seconds(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return round(float(result.stdout.strip()), 3)


def api_key(args: argparse.Namespace, *names: str) -> str:
    key = (
        args.key_file.read_text().strip()
        if args.key_file
        else next((os.environ[n] for n in names if os.environ.get(n)), "")
    )
    if not key:
        sys.exit(f"Set {' or '.join(names)} or pass --key-file")
    return key


def chirp(
    args: argparse.Namespace, ids: list[str], texts: list[str]
) -> dict[str, float]:
    """One request per line with a fixed preset voice; unchanged lines are kept."""

    voice = args.voice or "en-US-Chirp3-HD-Charon"
    hashes_path = OUT / "hashes.json"
    hashes = json.loads(hashes_path.read_text()) if hashes_path.exists() else {}
    key = None
    durations = {}
    for segment_id, text in zip(ids, texts):
        path = OUT / f"{segment_id}.mp3"
        digest = hashlib.sha256(f"chirp|{voice}|{text}".encode()).hexdigest()
        if hashes.get(segment_id) != digest or not path.exists():
            key = key or api_key(args, "GOOGLE_TTS_API_KEY")
            with tempfile.NamedTemporaryFile(suffix=".wav") as source:
                source.write(synthesize_chirp(text, voice, key))
                source.flush()
                subprocess.run(
                    [
                        "ffmpeg",
                        "-loglevel",
                        "error",
                        "-y",
                        "-i",
                        source.name,
                        "-af",
                        EDGE_TRIM + ",loudnorm=I=-16:TP=-1.5:LRA=11",
                        "-ar",
                        "48000",
                        "-ac",
                        "1",
                        "-b:a",
                        "160k",
                        str(path),
                    ],
                    check=True,
                )
            hashes[segment_id] = digest
            hashes_path.write_text(json.dumps(hashes, indent=1))
            print(f"synthesized {segment_id}", flush=True)
        durations[segment_id] = duration_seconds(path)
    for stale in OUT.glob("*.mp3"):
        if stale.stem not in durations:
            stale.unlink()
    hashes_path.write_text(
        json.dumps({k: v for k, v in hashes.items() if k in durations}, indent=1)
    )
    return durations


def gemini_take(
    args: argparse.Namespace, texts: list[str], take: Path
) -> list[tuple[float, float, float]]:
    """Make sure `take` holds one recording of the script; return (start, end, ratio) per line."""

    voice = args.voice or "Charon"
    script = "\n\n".join(texts)
    digest_path = take.with_suffix(".sha256")
    digest = hashlib.sha256(
        f"{args.model}|{voice}|{PROMPT}|{script}|{take.name}".encode()
    ).hexdigest()
    if not args.resplit and (
        not take.exists()
        or not digest_path.exists()
        or digest_path.read_text() != digest
    ):
        key = api_key(args, "GEMINI_API_KEY", "GOOGLE_API_KEY")
        print(f"synthesizing {take.name} ({len(texts)} lines)…", flush=True)
        raw = synthesize(script, args.model, voice, key)
        with tempfile.NamedTemporaryFile(suffix=".wav") as source:
            source.write(raw)
            source.flush()
            subprocess.run(
                [
                    "ffmpeg",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    source.name,
                    "-af",
                    "loudnorm=I=-16:TP=-1.5:LRA=11",
                    "-ar",
                    "48000",
                    "-ac",
                    "1",
                    str(take),
                ],
                check=True,
            )
        digest_path.write_text(digest)

    with tempfile.TemporaryDirectory() as workdir:
        words = transcribe(take, Path(workdir))
    cuts = cut_points(texts, words, silences(take))
    bounds = list(zip([0.0] + cuts, cuts + [duration_seconds(take)]))
    ratios = check(texts, words, bounds)
    return [(start, end, ratio) for (start, end), ratio in zip(bounds, ratios)]


def cut(take: Path, start: float, end: float, path: Path) -> float:
    subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{start:.3f}",
            "-to",
            f"{end:.3f}",
            "-i",
            str(take),
            "-af",
            EDGE_TRIM,
            "-b:a",
            "160k",
            str(path),
        ],
        check=True,
    )
    return duration_seconds(path)


def gemini(
    args: argparse.Namespace, ids: list[str], texts: list[str]
) -> dict[str, float] | None:
    """One take of the whole script, cut into lines at the pauses.

    With --takes N > 1, N takes are cut into candidates under public/vo/takes/
    (with each line's transcript match in candidates.json) for
    scripts/pick_voice.py to choose from; nothing in public/vo is replaced.
    """

    if args.takes == 1:
        lines = gemini_take(args, texts, TAKE)
        for stale in OUT.glob("*.mp3"):
            stale.unlink()
        return {
            i: cut(TAKE, start, end, OUT / f"{i}.mp3")
            for i, (start, end, _) in zip(ids, lines)
        }

    takes_dir = OUT / "takes"
    takes_dir.mkdir(exist_ok=True)
    candidates: dict[str, list[dict]] = {i: [] for i in ids}
    for n in range(args.takes):
        take = takes_dir / f"take{n}.wav"
        clip_dir = takes_dir / str(n)
        clip_dir.mkdir(exist_ok=True)
        for i, (start, end, ratio) in zip(ids, gemini_take(args, texts, take)):
            path = clip_dir / f"{i}.mp3"
            candidates[i].append(
                {
                    "take": n,
                    "path": str(path.relative_to(ROOT)),
                    "seconds": cut(take, start, end, path),
                    "match": ratio,
                }
            )
    (takes_dir / "candidates.json").write_text(json.dumps(candidates, indent=1) + "\n")
    print(f"{args.takes} takes cut into candidates; choose with scripts/pick_voice.py")
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--engine", choices=["chirp", "gemini"], default="chirp")
    parser.add_argument(
        "--voice", help="default: en-US-Chirp3-HD-Charon (chirp), Charon (gemini)"
    )
    parser.add_argument(
        "--model", default="gemini-3.8-flash-tts", help="gemini engine only"
    )
    parser.add_argument("--key-file", type=Path, help="file holding the API key")
    parser.add_argument(
        "--resplit", action="store_true", help="gemini: re-cut the existing take(s)"
    )
    parser.add_argument(
        "--takes",
        type=int,
        default=1,
        help="gemini: record N takes as candidates for pick_voice.py",
    )
    args = parser.parse_args()

    narration = json.loads(NARRATION.read_text())
    ids, texts = [], []
    for scene, spec in narration.items():
        for index, segment in enumerate(spec["segments"]):
            ids.append(f"{scene}-{index}")
            texts.append(segment["text"])

    OUT.mkdir(parents=True, exist_ok=True)
    durations = (chirp if args.engine == "chirp" else gemini)(args, ids, texts)
    if durations is None:
        return
    DURATIONS.write_text(json.dumps(durations, indent=1) + "\n")
    print(f"{len(durations)} lines, {sum(durations.values()):.0f} s of speech")


if __name__ == "__main__":
    main()

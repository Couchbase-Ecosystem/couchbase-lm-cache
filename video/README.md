# Explainer video

Remotion project for a ~5:20 narrated explainer of the Couchbase KV-cache tier for vLLM +
LMCache, aimed at developers new to LLM inference: an intro (what an LLM call
does), the KV-cache memory problem (prefill, why a 10k-token prompt needs 1.5
GB, why GPU memory loses it), where it hurts (many questions about one long
document), the solution, how chunks become Couchbase documents, how another
server reuses them, and proof from the real recordings in
[`../evidence/recordings`](../evidence/recordings) (copied into `public/`).

```bash
npm i
npx remotion studio          # preview and edit; each scene is also its own composition
npx remotion render Explainer out/couchbase-lmcache-explainer.mp4
```

- `src/explainer/Explainer.tsx`: scene order and durations.
- `src/explainer/scenes/`: one file per scene.
- `src/explainer/theme.ts`: fonts, colors, and the measured numbers shown on screen.
- Spotlight coordinates and clip times in `ProofRun.tsx` / `ProofConsole.tsx`
  refer to the 1920×1080 recordings and `../evidence/recordings/markers.json`;
  update them if the recordings are re-made.

## Voice-over and sources

- `src/explainer/narration.json`: the narration, one entry per line, by scene.
  Each line starts at `at` seconds into its scene or `gap` seconds after the
  previous line; animations, captions and footage spotlights follow these
  beats (`src/explainer/timeline.ts`), and footage freezes while narration
  outlasts a recorded moment.
- `scripts/tts.py` and `scripts/pick_voice.py`: the voice-over. The current
  audio was made with Gemini text-to-speech (voice Charon). Gemini is
  generative, so its voice drifts within and between recordings; to keep one
  voice, record several full takes, then let a speaker-verification model
  keep, for every line, the clip closest to one reference voice:

  ```bash
  GEMINI_API_KEY=... python3 scripts/tts.py --engine gemini --takes 5
  python3 scripts/pick_voice.py      # needs: pip install torch resemblyzer webrtcvad-wheels
  python3 scripts/cues.py           # word timings, for animations keyed to a word
  ```

  Lines that continue one sentence are always taken from the same take. Cuts
  are placed in the quietest stretch between two lines, so quiet word endings
  are kept. `cue(scene, line, ["minimax"])` in `src/explainer/timeline.ts`
  returns the frame at which a line says a word, from `src/explainer/vo-words.json`.

  `tts.py` transcribes each take with Whisper, aligns it to the script and cuts
  it into lines; candidates go to `public/vo/takes/` (not committed) and the
  picks to `public/vo/<Scene>-<n>.mp3` and `src/explainer/vo-durations.json`.
  Unchanged takes are reused. With Cloud Text-to-Speech enabled,
  `GOOGLE_TTS_API_KEY=... python3 scripts/tts.py` uses a fixed Chirp 3 HD
  voice instead and needs no picking. Keys are never written to the repo.

- `SOURCES.md`: the quoted articles and docs, with links.


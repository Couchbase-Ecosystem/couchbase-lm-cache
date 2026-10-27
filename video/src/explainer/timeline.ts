import narration from "./narration.json";
import spoken from "./vo-durations.json";
import spokenWords from "./vo-words.json";

/**
 * Scene timing driven by the voice-over. Each narration segment starts at
 * `at` seconds into its scene, or `gap` seconds after the previous segment
 * ends, whichever is later. Durations come from vo-durations.json (written by
 * scripts/tts.py); without audio they are estimated from the word count.
 */
export const FPS = 30;
export const TRANSITION_FRAMES = 15;
const WORDS_PER_SECOND = 2.7;
// Clips keep ~120 ms of silence at each end (scripts/tts.py), so lines need
// little extra gap.
const DEFAULT_GAP = 0.05;
const DEFAULT_TAIL = 1;

type Segment = { text: string; at?: number; gap?: number };
type SceneNarration = { min: number; tail?: number; segments: Segment[] };

const scenes = narration as Record<string, SceneNarration>;
const durations = spoken as Record<string, number>;
const words = spokenWords as unknown as Record<string, [string, number][]>;

export type Beat = { start: number; end: number };

export const segmentId = (scene: string, index: number) => `${scene}-${index}`;

export const hasAudio = (scene: string, index: number) =>
  durations[segmentId(scene, index)] !== undefined;

/** Start and end frame of every narration segment in a scene. */
export const sceneBeats = (scene: string): Beat[] => {
  let previousEnd = 0;
  return scenes[scene].segments.map((segment, index) => {
    const seconds =
      durations[segmentId(scene, index)] ??
      segment.text.split(/\s+/).length / WORDS_PER_SECOND;
    const start = Math.max(segment.at ?? 0, previousEnd + (segment.gap ?? DEFAULT_GAP));
    previousEnd = start + seconds;
    return { start: Math.round(start * FPS), end: Math.round(previousEnd * FPS) };
  });
};

export const sceneDuration = (scene: string) => {
  const beats = sceneBeats(scene);
  const tail = Math.round((scenes[scene].tail ?? DEFAULT_TAIL) * FPS);
  return Math.max(scenes[scene].min, beats[beats.length - 1].end + tail);
};


/**
 * Frame at which a line says one of `starts` (lowercase word prefixes, e.g.
 * ["minimax"]), from vo-words.json (scripts/cues.py). Falls back to
 * `fallbackSeconds` into the line when the word isn't found.
 */
export const cue = (scene: string, index: number, starts: string[], fallbackSeconds = 0) => {
  const beat = sceneBeats(scene)[index];
  const hit = (words[segmentId(scene, index)] ?? []).find(([w]) =>
    starts.some((s) => w.startsWith(s)),
  );
  return beat.start + Math.round((hit ? hit[1] : fallbackSeconds) * FPS);
};

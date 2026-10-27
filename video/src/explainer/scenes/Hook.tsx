import React from "react";
import { Easing, Interactive, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { SceneBackground } from "../components";
import { sceneBeats } from "../timeline";
import { colors, run } from "../theme";

const fadeIn = (frame: number, start: number, end: number) =>
  interpolate(frame, [start, end], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

/** Opening statement: LLM inference has a memory problem. */
export const Hook: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const beats = sceneBeats("Hook");
  const title = fadeIn(frame, 0, 0.6 * fps);
  return (
    <SceneBackground>
      <Interactive.Div
        name="Statement"
        style={{
          position: "absolute",
          left: 100,
          right: 100,
          top: 320,
          fontSize: 104,
          fontWeight: 800,
          letterSpacing: -3,
          textAlign: "center",
          opacity: title,
          translate: `0px ${(1 - title) * 30}px`,
        }}
      >
        LLMs have a <span style={{ color: colors.red }}>memory problem</span>
      </Interactive.Div>
      <Interactive.Div
        name="Fact"
        style={{
          position: "absolute",
          left: 100,
          right: 100,
          top: 500,
          fontSize: 50,
          fontWeight: 600,
          textAlign: "center",
          opacity: fadeIn(frame, beats[1].start - 4, beats[1].start + 14),
        }}
      >
        In Qwen3-8B, every token it reads takes{" "}
        <span style={{ color: colors.blue }}>{run.kbPerToken} KB</span> of GPU memory
      </Interactive.Div>
      <Interactive.Div
        name="Consequence"
        style={{
          position: "absolute",
          left: 100,
          right: 100,
          top: 600,
          fontSize: 44,
          fontWeight: 500,
          color: colors.muted,
          textAlign: "center",
          opacity: fadeIn(frame, beats[2].start - 4, beats[2].start + 14),
        }}
      >
        GPUs can’t hold much of it, so it’s thrown away and computed again.
      </Interactive.Div>
    </SceneBackground>
  );
};

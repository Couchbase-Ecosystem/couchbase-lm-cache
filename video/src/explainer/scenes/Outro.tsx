import React from "react";
import { Easing, Interactive, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { SceneBackground } from "../components";
import { mono } from "../theme";
import { sceneBeats } from "../timeline";

export const Outro: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const beats = sceneBeats("Outro");
  return (
    <SceneBackground>
      <Interactive.Div
        name="Closing line"
        style={{
          position: "absolute",
          left: 160,
          right: 160,
          top: 340,
          textAlign: "center",
          fontSize: 92,
          fontWeight: 800,
          letterSpacing: -2,
          lineHeight: 1.1,
          opacity: interpolate(frame, [0, 0.6 * fps], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          }),
        }}
      >
        Compute the prompt once.
        <br />
        <span style={{ color: "#ea2328" }}>Reuse it from Couchbase.</span>
      </Interactive.Div>
      <Interactive.Div
        name="Stack"
        style={{
          position: "absolute",
          left: 160,
          right: 160,
          top: 640,
          textAlign: "center",
          fontSize: 44,
          color: "#97a1b5",
          opacity: interpolate(frame, [0.8 * fps, 1.4 * fps], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        vLLM · LMCache · Couchbase
      </Interactive.Div>
      <Interactive.Div
        name="Repository"
        style={{
          position: "absolute",
          left: 160,
          right: 160,
          top: 730,
          textAlign: "center",
          fontSize: 40,
          fontFamily: mono,
          color: "#eef1f7",
          opacity: interpolate(frame, [beats[1].start - 4, beats[1].start + 14], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        github.com/Couchbase-Ecosystem/couchbase-lm-cache
      </Interactive.Div>
    </SceneBackground>
  );
};

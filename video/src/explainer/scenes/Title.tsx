import React from "react";
import { Interactive, useCurrentFrame, useVideoConfig } from "remotion";
import { SceneBackground, progress } from "../components";
import { colors } from "../theme";

/** Opening title: what this video is about. */
export const Title: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const title = progress(frame, 0.2 * fps, 0.9 * fps);
  const sub = progress(frame, 1.3 * fps, 1.9 * fps);
  return (
    <SceneBackground>
      <Interactive.Div
        name="Stack"
        style={{
          position: "absolute",
          left: 100,
          right: 100,
          top: 300,
          textAlign: "center",
          fontSize: 36,
          fontWeight: 700,
          letterSpacing: 5,
          textTransform: "uppercase",
          color: colors.red,
          opacity: title,
        }}
      >
        vLLM · LMCache · Couchbase
      </Interactive.Div>
      <Interactive.Div
        name="Title"
        style={{
          position: "absolute",
          left: 100,
          right: 100,
          top: 370,
          textAlign: "center",
          fontSize: 100,
          fontWeight: 800,
          letterSpacing: -2.5,
          lineHeight: 1.08,
          opacity: title,
          translate: `0px ${(1 - title) * 30}px`,
        }}
      >
        A shared KV cache
        <br />
        for LLM inference
      </Interactive.Div>
      <Interactive.Div
        name="Subtitle"
        style={{
          position: "absolute",
          left: 100,
          right: 100,
          top: 640,
          textAlign: "center",
          fontSize: 40,
          fontWeight: 500,
          color: colors.muted,
          opacity: sub,
        }}
      >
        Storing the model’s working memory in Couchbase, so every GPU server can reuse it
      </Interactive.Div>
    </SceneBackground>
  );
};

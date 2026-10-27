import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { Arrow, Box, Em, SceneBackground, SceneTitle, progress } from "../components";
import { sceneBeats } from "../timeline";
import { colors } from "../theme";

const steps = [
  <>Your app sends a <Em color={colors.blue}>prompt</Em>: instructions, documents, chat history</>,
  <>The model <Em color={colors.amber}>reads the whole prompt</Em> on the GPU</>,
  <>Then it writes the answer, <Em color={colors.green}>one word at a time</Em></>,
];

/** How an LLM request works, for viewers with no inference background. */
export const Context: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const beats = sceneBeats("Context");
  const boxes = [
    { x: 140, title: "Your app", detail: "chatbot, agent, …", color: colors.line, at: 0.5 },
    { x: 770, title: "LLM server", detail: "vLLM on a GPU", color: colors.amber, at: 1.1 },
    { x: 1400, title: "Answer", detail: "streamed back", color: colors.green, at: 1.7 },
  ];
  return (
    <SceneBackground>
      <SceneTitle kicker="First, some context" title="What happens when you call an LLM" />
      {boxes.map((b) => {
        const p = progress(frame, b.at * fps, (b.at + 0.5) * fps);
        return (
          <div key={b.title} style={{ opacity: p }}>
            <Box x={b.x} y={320} w={380} h={170} border={b.color}>
              <div style={{ padding: "30px 34px" }}>
                <div style={{ fontSize: 46, fontWeight: 800 }}>{b.title}</div>
                <div style={{ fontSize: 30, color: colors.muted, marginTop: 8 }}>{b.detail}</div>
              </div>
            </Box>
          </div>
        );
      })}
      <Arrow x1={540} y1={405} x2={750} y2={405} color={colors.blue} from={1 * fps} to={1.4 * fps} label="prompt" labelOffset={[0, -46]} />
      <Arrow x1={1170} y1={405} x2={1380} y2={405} color={colors.green} from={1.6 * fps} to={2 * fps} label="words" labelOffset={[0, -46]} />
      {steps.map((s, i) => {
        const p = progress(frame, beats[i + 1].start - 4, beats[i + 1].start + 12);
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: 140,
              right: 140,
              top: 580 + i * 110,
              display: "flex",
              alignItems: "center",
              gap: 30,
              fontSize: 46,
              fontWeight: 600,
              opacity: p,
              translate: `${(1 - p) * 30}px 0px`,
            }}
          >
            <div
              style={{
                flex: "0 0 auto",
                width: 70,
                height: 70,
                borderRadius: 35,
                border: `3px solid ${colors.line}`,
                fontSize: 36,
                fontWeight: 800,
                textAlign: "center",
                lineHeight: "64px",
              }}
            >
              {i + 1}
            </div>
            <div>{s}</div>
          </div>
        );
      })}
    </SceneBackground>
  );
};

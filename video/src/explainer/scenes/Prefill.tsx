import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { Box, Em, Explain, SceneBackground, SceneTitle, progress } from "../components";
import { sceneBeats } from "../timeline";
import { colors, mono, run } from "../theme";

/** The model reads the whole prompt (prefill) and builds the KV cache. */
export const Prefill: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const beats = sceneBeats("Prefill");
  const start = beats[0].start + 10;
  const end = start + 3.2 * fps;
  const p = progress(frame, start, end);
  const tokens = Math.round(p * run.tokens);
  const gb = (p * run.kvGB).toFixed(1);
  const firstWord = progress(frame, end, end + 10);

  return (
    <SceneBackground>
      <SceneTitle kicker="1 · The problem" title="Step 2, up close: reading the prompt" />

      {/* The prompt */}
      <Box x={140} y={330} w={500} h={430}>
        <div style={{ padding: 32 }}>
          <div style={{ fontSize: 36, fontWeight: 700 }}>Your prompt</div>
          <div style={{ fontSize: 30, color: colors.muted, marginTop: 6 }}>
            a long context + a question
          </div>
          {Array.from({ length: 7 }).map((_, i) => (
            <div
              key={i}
              style={{
                height: 16,
                marginTop: 20,
                width: `${[92, 80, 88, 70, 95, 60, 84][i]}%`,
                borderRadius: 8,
                background:
                  p * 7 > i ? "rgba(90,169,255,0.75)" : "rgba(151,161,181,0.25)",
              }}
            />
          ))}
          <div style={{ fontSize: 40, fontWeight: 800, marginTop: 30, fontVariantNumeric: "tabular-nums" }}>
            {tokens.toLocaleString("en-US")} <span style={{ fontSize: 30, color: colors.muted, fontWeight: 500 }}>tokens read</span>
          </div>
        </div>
      </Box>

      {/* The GPU */}
      <Box x={760} y={380} w={400} h={330} border={p > 0 && p < 1 ? colors.amber : colors.line}>
        <div style={{ padding: 32, textAlign: "center" }}>
          <div style={{ fontSize: 44, fontWeight: 800 }}>GPU</div>
          <div style={{ fontSize: 30, color: colors.muted, marginTop: 4 }}>{run.model}</div>
          <div
            style={{
              fontSize: 96,
              fontWeight: 800,
              marginTop: 30,
              color: p < 1 ? colors.amber : colors.text,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {Math.round(p * 100)}%
          </div>
          <div style={{ fontSize: 30, color: colors.muted }}>{p < 1 ? "reading…" : "done reading"}</div>
        </div>
      </Box>

      {/* The KV cache */}
      <Box x={1280} y={330} w={500} h={430} border={colors.blue}>
        <div style={{ padding: 32 }}>
          <div style={{ fontSize: 36, fontWeight: 700 }}>KV cache</div>
          <div style={{ fontSize: 30, color: colors.muted, marginTop: 6 }}>
            keys + values for every token
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 24 }}>
            {Array.from({ length: 40 }).map((_, i) => (
              <div
                key={i}
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: 6,
                  background: p * 40 > i ? colors.blue : "rgba(90,169,255,0.12)",
                }}
              />
            ))}
          </div>
          <div style={{ fontSize: 40, fontWeight: 800, marginTop: 24, fontVariantNumeric: "tabular-nums" }}>
            {gb} GB
          </div>
        </div>
      </Box>

      <div
        style={{
          position: "absolute",
          left: 760,
          top: 740,
          width: 400,
          textAlign: "center",
          fontFamily: mono,
          fontSize: 34,
          color: colors.green,
          opacity: firstWord,
        }}
      >
        → “The master…”
      </div>

      <Explain from={beats[0].start} to={beats[1].start - 12}>
        To answer, the model first turns <Em color={colors.blue}>every token</Em> of the prompt into
        keys and values: the <Em color={colors.blue}>KV cache</Em>.
      </Explain>
      <Explain from={beats[1].start}>
        This step is called <Em color={colors.amber}>prefill</Em>, and the answer can’t start until
        it’s done. Only then does the first word come out.
      </Explain>
    </SceneBackground>
  );
};

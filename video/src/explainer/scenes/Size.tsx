import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { Em, Explain, SceneBackground, SceneTitle, progress } from "../components";
import { sceneBeats } from "../timeline";
import { colors, mono, run } from "../theme";

const CELL_W = 24;
const CELL_GAP = 4;
const GRID_X = 560;

/** Why a 28 KB document turns into 1.4 GB of KV cache. */
export const Size: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const beats = sceneBeats("Size");
  const [intro, perBox, perTokenBeat, document] = beats;
  const token = progress(frame, intro.start, intro.start + 15);
  const grid = progress(frame, intro.start + 0.8 * fps, intro.start + 2.6 * fps);
  const cell = progress(frame, perBox.start, perBox.start + 18);
  const formula = progress(frame, perTokenBeat.start, perTokenBeat.start + 18);
  const perToken = progress(frame, perTokenBeat.end - 1.2 * fps, perTokenBeat.end - 0.6 * fps);
  const total = progress(frame, document.start, document.start + 18);
  const count = progress(frame, document.start + 6, document.start + 1.6 * fps);
  const gridWidth = run.layers * (CELL_W + CELL_GAP) - CELL_GAP;
  const kb = (run.headDim * run.kvHeads * run.bytesPerNumber) / 1024;

  return (
    <SceneBackground>
      <SceneTitle kicker="1 · The problem" title={`${run.promptKB} KB of text, ${run.kvGB} GB of KV cache`} />

      {/* One token */}
      <div
        style={{
          position: "absolute",
          left: 140,
          top: 345,
          opacity: token,
          display: "flex",
          alignItems: "center",
          gap: 30,
        }}
      >
        <div
          style={{
            padding: "18px 28px",
            borderRadius: 16,
            border: `3px solid ${colors.blue}`,
            background: colors.panel,
            fontFamily: mono,
            fontSize: 44,
          }}
        >
          “vault”
          <div style={{ fontFamily: "inherit", fontSize: 26, color: colors.muted, textAlign: "center" }}>1 token</div>
        </div>
        <div style={{ fontSize: 44, color: colors.muted }}>→</div>
      </div>

      {/* Key and value per layer */}
      {["key", "value"].map((label, row) => (
        <React.Fragment key={label}>
          <div
            style={{
              position: "absolute",
              left: GRID_X - 110,
              top: 330 + row * 54,
              width: 96,
              textAlign: "right",
              fontSize: 28,
              color: colors.muted,
              lineHeight: "44px",
              opacity: grid > 0 ? 1 : 0,
            }}
          >
            {label}
          </div>
          {Array.from({ length: run.layers }).map((_, i) => (
            <div
              key={i}
              style={{
                position: "absolute",
                left: GRID_X + i * (CELL_W + CELL_GAP),
                top: 330 + row * 54,
                width: CELL_W,
                height: 44,
                borderRadius: 5,
                background: grid * run.layers > i ? (row === 0 ? colors.blue : colors.amber) : "rgba(151,161,181,0.12)",
                outline: cell > 0 && i === 0 && row === 0 ? `3px solid ${colors.text}` : undefined,
              }}
            />
          ))}
        </React.Fragment>
      ))}
      <div
        style={{
          position: "absolute",
          left: GRID_X,
          top: 446,
          width: gridWidth,
          textAlign: "center",
          fontSize: 28,
          color: colors.muted,
          opacity: grid,
        }}
      >
        ← {run.layers} layers of {run.model} →
      </div>
      <div
        style={{
          position: "absolute",
          left: GRID_X,
          top: 494,
          width: gridWidth,
          textAlign: "center",
          fontSize: 32,
          opacity: cell,
        }}
      >
        each box: {run.kvHeads} heads × {run.headDim} numbers × {run.bytesPerNumber} bytes ={" "}
        <Em color={colors.text}>{kb} KB</Em>
      </div>

      {/* The arithmetic */}
      <div
        style={{
          position: "absolute",
          left: 140,
          right: 140,
          top: 590,
          fontFamily: mono,
          fontSize: 44,
          color: colors.muted,
          opacity: formula,
        }}
      >
        2 × {run.layers} layers × {kb} KB ={" "}
        <span style={{ color: colors.text, fontWeight: 600, opacity: perToken }}>{run.kbPerToken} KB per token</span>
      </div>
      <div
        style={{
          position: "absolute",
          left: 140,
          right: 140,
          top: 680,
          fontSize: 88,
          fontWeight: 800,
          letterSpacing: -1.5,
          opacity: total,
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {run.kbPerToken} KB × {Math.round(count * run.tokens).toLocaleString("en-US")} tokens ={" "}
        <span style={{ color: colors.blue }}>{(count * run.kvGB).toFixed(1)} GB</span>
      </div>

      <Explain from={intro.start} to={perTokenBeat.start - 12}>
        For <Em color={colors.blue}>every token</Em>, each of the model’s {run.layers} layers keeps a{" "}
        <Em color={colors.blue}>key</Em> and a <Em color={colors.amber}>value</Em>.
      </Explain>
      <Explain from={perTokenBeat.start} to={document.start - 12}>
        That’s {run.kbPerToken} KB of numbers for a single token.
      </Explain>
      <div
        style={{
          position: "absolute",
          left: 140,
          top: 790,
          fontSize: 26,
          color: colors.muted,
          opacity: total,
        }}
      >
        1 KB = 1,024 bytes, 1 GB = 1,024 MB
      </div>
      <Explain from={document.start}>
        So the {run.promptKB} KB document needs <Em color={colors.blue}>{run.kvGB} GB</Em> of GPU
        memory: about <Em color={colors.text}>54,000×</Em> the size of the text.
      </Explain>
    </SceneBackground>
  );
};

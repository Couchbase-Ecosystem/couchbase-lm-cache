import React from "react";
import { useCurrentFrame } from "remotion";
import { Explain, SceneBackground, SceneTitle, progress } from "../components";
import { architectures } from "../models";
import { colors } from "../theme";
import { sceneBeats } from "../timeline";

const BAR_X = 760;
const BAR_MAX = 700;

/** KV cache per token across 2025–2026 architectures. */
export const Architectures: React.FC = () => {
  const frame = useCurrentFrame();
  const beats = sceneBeats("Architectures");
  // Rows appear as the narration names them.
  const rowAt = [beats[1].start, beats[1].start + 45, beats[2].start, beats[3].start, beats[3].start + 60];
  const max = architectures[0].kb;
  return (
    <SceneBackground>
      <SceneTitle kicker="1 · The problem" title="It depends on the model architecture" />
      {architectures.map((a, i) => {
        const p = progress(frame, rowAt[i] - 4, rowAt[i] + 18);
        const top = 290 + i * 100;
        return (
          <div key={a.model} style={{ opacity: Math.min(1, p * 1.5) }}>
            <div style={{ position: "absolute", left: 140, top, width: 600, whiteSpace: "nowrap" }}>
              <div style={{ fontSize: 38, fontWeight: 800 }}>{a.model}</div>
              <div style={{ fontSize: 24, color: colors.muted }}>{a.year} · {a.why}</div>
            </div>
            <div
              style={{
                position: "absolute",
                left: BAR_X,
                top: top + 8,
                width: (a.kb / max) * BAR_MAX * p,
                height: 56,
                borderRadius: 10,
                background: i === 0 ? colors.blue : "rgba(90,169,255,0.55)",
              }}
            />
            <div
              style={{
                position: "absolute",
                left: BAR_X + (a.kb / max) * BAR_MAX + 24,
                top: top + 12,
                fontSize: 36,
                fontWeight: 700,
                whiteSpace: "nowrap",
                opacity: p,
              }}
            >
              {a.label}
            </div>
          </div>
        );
      })}
      <div style={{ position: "absolute", left: 140, top: 815, fontSize: 24, color: colors.muted }}>
        KV cache per token in 16-bit, computed from each model’s config.json. “Fixed state”: hybrid layers keep a
        constant-size state per request instead.
      </div>
      <Explain from={beats[4].start}>Newer architectures are designed to shrink this cost.</Explain>
    </SceneBackground>
  );
};

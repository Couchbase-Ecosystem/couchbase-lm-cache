import React from "react";
import { useCurrentFrame } from "remotion";
import { Em, Explain, SceneBackground, SceneTitle, progress } from "../components";
import { fullContext } from "../models";
import { colors } from "../theme";
import { sceneBeats } from "../timeline";

const BAR_X = 640;
const BAR_MAX = 1000;
const SCALE_GB = 125;
const GPU_GB = 80;

/** KV cache for one request at each model's full context window. */
export const ContextGrowth: React.FC = () => {
  const frame = useCurrentFrame();
  const beats = sceneBeats("ContextGrowth");
  const rowAt = [beats[1].start, beats[2].start, beats[3].start, beats[3].start + 75, beats[4].start];
  const gpu = progress(frame, beats[4].start + 30, beats[4].start + 50);
  const px = (gb: number) => (gb / SCALE_GB) * BAR_MAX;
  return (
    <SceneBackground>
      <SceneTitle kicker="1 · The problem" title="…and context windows keep growing" />
      <div style={{ position: "absolute", left: BAR_X, top: 280, fontSize: 26, color: colors.muted }}>
        KV cache for one request, at the model’s full context
      </div>
      {fullContext.map((c, i) => {
        const p = progress(frame, rowAt[i] - 4, rowAt[i] + 20);
        const top = 330 + i * 92;
        const over = c.gb > GPU_GB;
        return (
          <div key={c.model} style={{ opacity: Math.min(1, p * 1.5) }}>
            <div style={{ position: "absolute", left: 140, top, width: 470 }}>
              <div style={{ fontSize: 36, fontWeight: 800 }}>{c.model}</div>
              <div style={{ fontSize: 24, color: colors.muted }}>{c.context}</div>
            </div>
            <div
              style={{
                position: "absolute",
                left: BAR_X,
                top: top + 8,
                width: px(c.gb) * p,
                height: 52,
                borderRadius: 10,
                background: over ? colors.red : colors.amber,
              }}
            />
            <div
              style={{
                position: "absolute",
                left: BAR_X + px(c.gb) * p + 20,
                top: top + 10,
                fontSize: 34,
                fontWeight: 700,
                whiteSpace: "nowrap",
                opacity: p,
              }}
            >
              {c.label}
            </div>
          </div>
        );
      })}
      <div style={{ opacity: gpu }}>
        <div
          style={{
            position: "absolute",
            left: BAR_X + px(GPU_GB),
            top: 320,
            height: 470,
            borderLeft: `4px dashed ${colors.text}`,
          }}
        />
        <div
          style={{
            position: "absolute",
            left: BAR_X + px(GPU_GB) - 160,
            top: 792,
            width: 320,
            textAlign: "center",
            fontSize: 28,
            fontWeight: 700,
          }}
        >
          one 80 GB GPU
        </div>
      </div>
      <Explain from={beats[5].start}>
        Cheaper per token, but up to a <Em>million tokens</Em> per request, for every user being served.
      </Explain>
    </SceneBackground>
  );
};

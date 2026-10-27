import React from "react";
import { useCurrentFrame } from "remotion";
import { Box, Em, SceneBackground, SceneTitle, progress } from "../components";
import { sceneBeats } from "../timeline";
import { colors, run } from "../theme";

const benefits = [
  { title: "Shared by every server", detail: "Any server can reuse the KV cache" },
  { title: "Survives evictions and restarts", detail: "GPU memory is no longer the only copy" },
  { title: "Less repeated GPU work", detail: "A context is read once, not on every turn" },
];

/** What the use case gains, with the one number measured in the demo. */
export const Results: React.FC = () => {
  const frame = useCurrentFrame();
  const beats = sceneBeats("Results");
  const stat = progress(frame, beats[4].start - 6, beats[4].start + 14);
  const speedup = (run.ttftComputed / run.ttftFromCouchbase).toFixed(1);

  return (
    <SceneBackground>
      <SceneTitle kicker="3 · The result" title="Read once, reuse on any server" />
      {benefits.map((b, i) => {
        const p = progress(frame, beats[i + 1].start - 4, beats[i + 1].start + 12);
        return (
          <div key={b.title} style={{ opacity: p, translate: `${(1 - p) * 30}px 0px` }}>
            <Box x={140} y={300 + i * 170} w={900} h={145} border={colors.green}>
              <div style={{ padding: "22px 32px" }}>
                <div style={{ fontSize: 40, fontWeight: 700 }}>{b.title}</div>
                <div style={{ fontSize: 30, color: colors.muted, marginTop: 6 }}>{b.detail}</div>
              </div>
            </Box>
          </div>
        );
      })}

      <div style={{ opacity: stat, scale: `${0.94 + 0.06 * stat}` }}>
        <Box x={1120} y={300} w={660} h={485} border={colors.line}>
          <div style={{ padding: "48px 44px", textAlign: "center" }}>
            <div style={{ fontSize: 34, color: colors.muted }}>In this demo, the answer started</div>
            <div style={{ fontSize: 180, fontWeight: 800, letterSpacing: -4, color: colors.green, lineHeight: 1.1, marginTop: 16 }}>
              {speedup}×
            </div>
            <div style={{ fontSize: 44, fontWeight: 700 }}>sooner</div>
            <div style={{ fontSize: 30, color: colors.muted, marginTop: 26, lineHeight: 1.35 }}>
              {run.ttftComputed} s → {run.ttftFromCouchbase} s to the first word
              <br />
              <Em color={colors.text}>same answer</Em> · {run.model}
            </div>
          </div>
        </Box>
      </div>
    </SceneBackground>
  );
};

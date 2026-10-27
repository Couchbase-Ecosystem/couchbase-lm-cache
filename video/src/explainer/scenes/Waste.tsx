import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { Box, Em, Explain, SceneBackground, SceneTitle, progress } from "../components";
import { cue, sceneBeats } from "../timeline";
import { colors, run } from "../theme";

const BAR_X = 140;
const BAR_W = 1640;
const px = (gb: number) => (gb / run.gpuGB) * BAR_W;

const reasons = [
  { title: "Other sessions need the space", detail: "This KV cache is evicted to make room" },
  { title: "The next turn goes to another server", detail: "Its GPU never had this KV cache" },
  { title: "The server restarts", detail: "GPU memory is wiped" },
];

/** GPU memory only fits a couple of these, so the KV cache is lost and recomputed. */
export const Waste: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const beats = sceneBeats("Waste");
  const bar = progress(frame, beats[0].start, beats[0].start + 0.8 * fps);
  const docs = progress(frame, beats[1].start - 0.6 * fps, beats[1].start);
  const room = progress(frame, beats[1].start, beats[1].start + 18);
  const reasonAt = [cue("Waste", 2, ["other"], 1.2), beats[3].start, beats[4].start];
  const weightsW = px(run.weightsGB);
  const kvW = px(run.kvSpaceGB);

  return (
    <SceneBackground>
      <SceneTitle kicker="1 · The problem" title="GPU memory can’t keep it for long" />

      {/* GPU memory bar */}
      <div style={{ position: "absolute", left: BAR_X, top: 300, fontSize: 32, color: colors.muted, opacity: bar }}>
        GPU memory · {run.gpuGB} GB
      </div>
      <div
        style={{
          position: "absolute",
          left: BAR_X,
          top: 350,
          width: BAR_W * bar,
          height: 90,
          borderRadius: 14,
          overflow: "hidden",
          display: "flex",
          background: "#1b2130",
        }}
      >
        <div style={{ flex: `0 0 ${weightsW}px`, background: "#3a4255", fontSize: 32, fontWeight: 600, padding: "24px 26px", whiteSpace: "nowrap" }}>
          model weights · {run.weightsGB} GB
        </div>
        <div style={{ flex: `0 0 ${kvW}px`, display: "flex", gap: 4, padding: 6, boxSizing: "border-box", background: "rgba(90,169,255,0.18)" }}>
          {[0, 1].map((i) => (
            <div
              key={i}
              style={{
                flex: 1,
                borderRadius: 8,
                background: colors.blue,
                opacity: progress(frame, beats[1].start + i * 12, beats[1].start + 12 + i * 12),
              }}
            />
          ))}
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          left: BAR_X + weightsW,
          top: 452,
          width: 700,
          fontSize: 30,
          lineHeight: 1.3,
          opacity: docs,
        }}
      >
        <Em color={colors.blue}>{run.kvSpaceGB} GB</Em> for KV caches
        <div style={{ opacity: room }}>
          room for only <Em color={colors.text}>2 contexts</Em> like this
        </div>
      </div>

      {/* Why it gets lost */}
      {reasons.map((r, i) => {
        const p = progress(frame, reasonAt[i] - 4, reasonAt[i] + 12);
        return (
          <div key={r.title} style={{ opacity: p, translate: `0px ${(1 - p) * 20}px` }}>
            <Box x={140 + i * 560} y={590} w={520} h={215} border={colors.amber}>
              <div style={{ padding: "26px 30px" }}>
                <div style={{ fontSize: 36, fontWeight: 700, lineHeight: 1.2 }}>{r.title}</div>
                <div style={{ fontSize: 30, color: colors.muted, marginTop: 10 }}>{r.detail}</div>
              </div>
            </Box>
          </div>
        );
      })}

      <Explain from={beats[5].start}>
        Each time, the model has to <Em color={colors.amber}>read the whole document again</Em>: the
        same GPU work, repeated.
      </Explain>
    </SceneBackground>
  );
};

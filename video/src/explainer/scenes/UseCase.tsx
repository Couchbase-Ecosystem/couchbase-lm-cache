import React from "react";
import { useCurrentFrame } from "remotion";
import { Box, Em, Explain, SceneBackground, SceneTitle, progress } from "../components";
import { colors } from "../theme";
import { sceneBeats } from "../timeline";

const BAR_X = 330;
const turns = [
  { label: "Turn 1", old: 0, add: 360, note: "instructions + documents + question" },
  { label: "Turn 2", old: 360, add: 90, note: "+ answer + new message" },
  { label: "Turn 3", old: 450, add: 90, note: "+ answer + new message" },
  { label: "Turn 4", old: 540, add: 90, note: "+ answer + new message" },
];

/** Where it hurts: a long session resends its whole context on every turn. */
export const UseCase: React.FC = () => {
  const frame = useCurrentFrame();
  const beats = sceneBeats("UseCase");
  const lost = progress(frame, beats[2].start - 4, beats[2].start + 14);
  return (
    <SceneBackground>
      <SceneTitle kicker="1 · Where it hurts" title="A long session, re-read on every turn" />
      {turns.map((t, i) => {
        const at = i === 0 ? beats[0].start + 20 : beats[1].start + (i - 1) * 25;
        const p = progress(frame, at - 4, at + 14);
        const top = 320 + i * 105;
        const last = i === turns.length - 1;
        return (
          <div key={t.label} style={{ opacity: p, translate: `${(1 - p) * 30}px 0px` }}>
            <div style={{ position: "absolute", left: 140, top: top + 8, fontSize: 34, fontWeight: 700 }}>
              {t.label}
            </div>
            <div
              style={{
                position: "absolute",
                left: BAR_X,
                top,
                width: t.old,
                height: 60,
                borderRadius: "10px 0 0 10px",
                background: last && lost > 0 ? colors.red : "rgba(90,169,255,0.45)",
              }}
            />
            <div
              style={{
                position: "absolute",
                left: BAR_X + t.old,
                top,
                width: t.add,
                height: 60,
                borderRadius: t.old ? "0 10px 10px 0" : 10,
                background: i === 0 ? "rgba(90,169,255,0.45)" : colors.amber,
              }}
            />
            <div
              style={{
                position: "absolute",
                left: BAR_X + t.old + t.add + 22,
                top: top + 14,
                fontSize: 26,
                color: colors.muted,
                whiteSpace: "nowrap",
              }}
            >
              {t.note}
            </div>
          </div>
        );
      })}
      <div
        style={{
          position: "absolute",
          left: BAR_X,
          top: 742,
          fontSize: 28,
          color: colors.muted,
          opacity: progress(frame, beats[1].start, beats[1].start + 14),
        }}
      >
        <span style={{ color: "#8fc3ff" }}>■</span> everything sent before, sent again{"   "}
        <span style={{ color: colors.amber }}>■</span> new
      </div>
      <div style={{ opacity: lost }}>
        <Box x={1340} y={320} w={440} h={300} border={colors.red}>
          <div style={{ padding: "30px 34px" }}>
            <div style={{ fontSize: 38, fontWeight: 800 }}>Turn 4 → server B</div>
            <div style={{ fontSize: 30, color: colors.muted, marginTop: 14, lineHeight: 1.3 }}>
              or turn 4 after the GPU evicted the cache
            </div>
            <div style={{ fontSize: 32, fontWeight: 700, color: colors.red, marginTop: 22 }}>
              reads it all again
            </div>
          </div>
        </Box>
      </div>
      <Explain from={beats[2].start}>
        Chats and agents resend the <Em color={colors.blue}>whole context</Em> on every turn.
      </Explain>
    </SceneBackground>
  );
};

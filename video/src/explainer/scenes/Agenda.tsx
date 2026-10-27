import React from "react";
import { useCurrentFrame } from "remotion";
import { SceneBackground, SceneTitle, progress } from "../components";
import { sceneBeats } from "../timeline";
import { colors } from "../theme";

const items = [
  { n: "1", title: "The problem", detail: "Reading a long prompt builds gigabytes of GPU memory that gets thrown away" },
  { n: "2", title: "The solution", detail: "Store that memory in Couchbase so every server can reuse it" },
  { n: "3", title: "A real demo", detail: "Two GPU servers, one long context, one Couchbase bucket" },
];

/** What the rest of the video covers. */
export const Agenda: React.FC = () => {
  const frame = useCurrentFrame();
  const beats = sceneBeats("Agenda");
  return (
    <SceneBackground>
      <SceneTitle kicker="What we’ll cover" title="Step 2 is where the waste hides" />
      {items.map((it, i) => {
        const p = progress(frame, beats[i + 1].start - 4, beats[i + 1].start + 12);
        return (
          <div
            key={it.n}
            style={{
              position: "absolute",
              left: 140,
              right: 140,
              top: 320 + i * 170,
              display: "flex",
              gap: 36,
              alignItems: "flex-start",
              opacity: p,
              translate: `${(1 - p) * 30}px 0px`,
            }}
          >
            <div
              style={{
                flex: "0 0 auto",
                width: 90,
                height: 90,
                borderRadius: 45,
                background: colors.red,
                fontSize: 50,
                fontWeight: 800,
                textAlign: "center",
                lineHeight: "90px",
              }}
            >
              {it.n}
            </div>
            <div>
              <div style={{ fontSize: 54, fontWeight: 800 }}>{it.title}</div>
              <div style={{ fontSize: 36, color: colors.muted, marginTop: 6 }}>{it.detail}</div>
            </div>
          </div>
        );
      })}
    </SceneBackground>
  );
};

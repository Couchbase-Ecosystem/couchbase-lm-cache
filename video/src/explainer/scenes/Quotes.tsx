import React from "react";
import { useCurrentFrame } from "remotion";
import { SceneBackground, SceneTitle, progress } from "../components";
import { researchQuotes } from "../sources";
import { colors, mono } from "../theme";
import { sceneBeats } from "../timeline";

/** Published sources describing the same problem, one quote per beat. */
export const Quotes: React.FC = () => {
  const frame = useCurrentFrame();
  const beats = sceneBeats("Quotes");
  return (
    <SceneBackground>
      <SceneTitle kicker="1 · Not just us" title="A known problem in LLM serving" />
      {researchQuotes.map((q, i) => {
        const beat = beats[i + 1];
        const next = beats[i + 2]?.start ?? 1e6;
        const opacity = progress(frame, beat.start - 8, beat.start + 8) * (1 - progress(frame, next - 10, next));
        if (opacity <= 0) return null;
        return (
          <div
            key={q.url}
            style={{
              position: "absolute",
              left: 140,
              right: 140,
              top: 340,
              opacity,
              translate: `0px ${(1 - opacity) * 16}px`,
            }}
          >
            <div style={{ display: "flex", gap: 30 }}>
              <div style={{ fontSize: 180, lineHeight: 0.8, color: colors.red, fontWeight: 800 }}>“</div>
              <div>
                <div style={{ fontSize: 60, fontWeight: 700, lineHeight: 1.22, letterSpacing: -0.5 }}>{q.quote}</div>
                {q.extra ? (
                  <div style={{ fontSize: 40, fontWeight: 500, color: colors.muted, marginTop: 26, lineHeight: 1.3 }}>
                    “{q.extra}”
                  </div>
                ) : null}
                <div style={{ marginTop: 44, fontSize: 36, fontWeight: 700 }}>— {q.who}</div>
                <div style={{ fontSize: 30, color: colors.muted, marginTop: 8 }}>{q.where}</div>
                <div style={{ fontSize: 24, fontFamily: mono, color: colors.blue, marginTop: 10 }}>{q.url}</div>
              </div>
            </div>
          </div>
        );
      })}
    </SceneBackground>
  );
};

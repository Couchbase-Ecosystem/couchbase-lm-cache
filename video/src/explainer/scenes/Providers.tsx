import React from "react";
import { useCurrentFrame } from "remotion";
import { Box, Em, Explain, SceneBackground, SceneTitle, progress } from "../components";
import { providerQuotes } from "../sources";
import { colors, mono } from "../theme";
import { sceneBeats } from "../timeline";

/** Hosted AI APIs already cache prompts; self-hosted models need their own cache. */
export const Providers: React.FC = () => {
  const frame = useCurrentFrame();
  const beats = sceneBeats("Providers");
  return (
    <SceneBackground>
      <SceneTitle kicker="1 · Not just us" title="The big AI providers already cache prompts" />
      {providerQuotes.map((q, i) => {
        const p = progress(frame, beats[i + 1].start - 6, beats[i + 1].start + 10);
        return (
          <div key={q.url} style={{ opacity: p, translate: `0px ${(1 - p) * 20}px` }}>
            <Box x={140 + i * 840} y={300} w={800} h={470}>
              <div style={{ padding: "40px 44px" }}>
                <div style={{ fontSize: 120, lineHeight: 0.7, color: colors.red, fontWeight: 800 }}>“</div>
                <div style={{ fontSize: 44, fontWeight: 700, lineHeight: 1.25, marginTop: 4 }}>{q.quote}</div>
                <div style={{ fontSize: 32, fontWeight: 700, marginTop: 34 }}>— {q.who}, {q.where}</div>
                <div style={{ fontSize: 17, fontFamily: mono, color: colors.blue, marginTop: 10, whiteSpace: "nowrap" }}>{q.url}</div>
              </div>
            </Box>
          </div>
        );
      })}
      <Explain from={beats[3].start}>
        Those caches live inside their platforms. <Em>Running your own models?</Em> You need your own.
      </Explain>
    </SceneBackground>
  );
};

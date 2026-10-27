import React from "react";
import { useCurrentFrame } from "remotion";
import { Em, SceneBackground, SceneTitle, progress } from "../components";
import { sceneBeats } from "../timeline";
import { colors, run } from "../theme";

const Step: React.FC<{
  n: number;
  at: number;
  title: React.ReactNode;
  detail: React.ReactNode;
  top: number;
}> = ({ n, at, title, detail, top }) => {
  const frame = useCurrentFrame();
  const p = progress(frame, at, at + 14);
  return (
    <div
      style={{
        position: "absolute",
        left: 140,
        right: 140,
        top,
        display: "flex",
        gap: 34,
        alignItems: "flex-start",
        opacity: p,
        translate: `${(1 - p) * 30}px 0px`,
      }}
    >
      <div
        style={{
          flex: "0 0 auto",
          width: 76,
          height: 76,
          borderRadius: 38,
          background: colors.green,
          color: colors.bg,
          fontSize: 42,
          fontWeight: 800,
          textAlign: "center",
          lineHeight: "76px",
        }}
      >
        {n}
      </div>
      <div>
        <div style={{ fontSize: 50, fontWeight: 700 }}>{title}</div>
        <div style={{ fontSize: 34, color: colors.muted, marginTop: 6 }}>{detail}</div>
      </div>
    </div>
  );
};

/** How a second server finds and loads the chunks instead of computing them. */
export const Reuse: React.FC = () => {
  const beats = sceneBeats("Reuse");
  const leftover = run.tokens - run.chunks * run.chunkTokens;
  return (
    <SceneBackground>
      <SceneTitle kicker="2 · How it works: reusing" title="The next turn lands on server B" />
      <Step
        n={1}
        at={beats[0].start}
        top={300}
        title="It turns the context into 40 chunk keys"
        detail="Keys are hashes of the tokens: the same text always gives the same keys"
      />
      <Step
        n={2}
        at={beats[1].start}
        top={460}
        title={<>It asks Couchbase for them: <Em color={colors.green}>40 of 40 found</Em></>}
        detail="Server A already saved them"
      />
      <Step
        n={3}
        at={beats[2].start}
        top={620}
        title={<>It loads the {run.kvGB} GB KV cache <Em color={colors.green}>from Couchbase</Em></>}
        detail="Instead of reading the whole document on the GPU again"
      />
      <Step
        n={4}
        at={beats[3].start}
        top={780}
        title={<>The GPU only reads the last {leftover} tokens and starts answering</>}
        detail="Same answer as computing from scratch"
      />
    </SceneBackground>
  );
};

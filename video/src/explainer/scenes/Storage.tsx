import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { Box, Em, Explain, SceneBackground, SceneTitle, progress } from "../components";
import { cue, sceneBeats } from "../timeline";
import { colors, mono, run } from "../theme";

/** How one prompt's KV cache becomes 1,480 Couchbase documents. */
export const Storage: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const beats = sceneBeats("Storage");
  const splitAt = cue("Storage", 0, ["splits"], 1.5);
  const split = progress(frame, splitAt, splitAt + 1.2 * fps); // KV cache → 40 chunks
  const focus = progress(frame, beats[1].start - 6, beats[1].start + 18); // zoom on one chunk
  const shards = progress(frame, beats[2].start, beats[2].start + 1.6 * fps); // chunk → 36 × 1 MB + manifest
  const total = progress(frame, beats[3].start, beats[3].start + 24);

  return (
    <SceneBackground>
      <SceneTitle kicker="2 · How it works: saving" title="One context becomes 1,480 documents" />

      {/* Row 1: KV cache split into 40 chunks */}
      <div style={{ position: "absolute", left: 140, top: 300, fontSize: 34, color: colors.muted }}>
        KV cache of a {run.tokens.toLocaleString("en-US")}-token context ({run.kvGB} GB)
      </div>
      <div style={{ position: "absolute", left: 140, top: 356, display: "flex", gap: 4 + split * 6 }}>
        {Array.from({ length: run.chunks }).map((_, i) => (
          <div
            key={i}
            style={{
              width: 28,
              height: 70,
              borderRadius: split > 0.5 ? 6 : 0,
              background: i === 0 && focus > 0 ? colors.red : colors.blue,
              opacity: focus > 0 && i !== 0 ? 1 - 0.6 * focus : 1,
            }}
          />
        ))}
      </div>
      <div
        style={{
          position: "absolute",
          left: 140,
          top: 446,
          fontSize: 40,
          fontWeight: 700,
          opacity: progress(frame, splitAt + 0.9 * fps, splitAt + 1.5 * fps),
        }}
      >
        LMCache splits it into <Em color={colors.blue}>{run.chunks} chunks</Em> of {run.chunkTokens} tokens
      </div>

      {/* Row 2: one chunk → shards + manifest */}
      <div style={{ opacity: focus }}>
        <Box x={140} y={560} w={340} h={200} border={colors.red}>
          <div style={{ padding: "22px 16px", textAlign: "center" }}>
            <div style={{ fontSize: 28, color: colors.muted, whiteSpace: "nowrap" }}>
              1 chunk = {run.chunkTokens} × {run.kbPerToken} KB
            </div>
            <div style={{ fontSize: 76, fontWeight: 800 }}>{run.chunkMB} MB</div>
            <div style={{ fontSize: 24, color: colors.amber, whiteSpace: "nowrap" }}>split into 1 MB pieces</div>
          </div>
        </Box>
        <div style={{ position: "absolute", left: 506, top: 620, fontSize: 70, color: colors.muted }}>→</div>
      </div>
      <div style={{ opacity: shards }}>
        <div style={{ position: "absolute", left: 600, top: 560, width: 760, display: "flex", flexWrap: "wrap", gap: 8 }}>
          {Array.from({ length: 36 }).map((_, i) => (
            <div
              key={i}
              style={{
                width: 76,
                height: 40,
                borderRadius: 6,
                background: shards * 36 > i ? "rgba(234,35,40,0.75)" : "rgba(234,35,40,0.15)",
                fontSize: 20,
                fontFamily: mono,
                color: "white",
                textAlign: "center",
                lineHeight: "40px",
              }}
            >
              1 MB
            </div>
          ))}
        </div>
        <Box x={1400} y={560} w={380} h={200} border={colors.green}>
          <div style={{ padding: 22 }}>
            <div style={{ fontSize: 28, color: colors.muted }}>+ 1 manifest document</div>
            <div style={{ fontFamily: mono, fontSize: 24, marginTop: 14, color: colors.green, lineHeight: 1.45 }}>
              {"{"}"lmcache_shards": 36,
              <br />
              &nbsp;"bytes": 37748736{"}"}
            </div>
          </div>
        </Box>
      </div>

      {/* The equation */}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 800,
          textAlign: "center",
          fontSize: 72,
          fontWeight: 800,
          opacity: total,
          scale: `${0.92 + 0.08 * total}`,
        }}
      >
        <Em color={colors.blue}>{run.chunks} chunks</Em> × <Em>37 documents</Em> ={" "}
        <span style={{ color: colors.text }}>{run.documents.toLocaleString("en-US")} documents</span>
      </div>

      <Explain from={beats[1].start} to={beats[3].start - 12}>
        The connector stores each chunk as <Em>36 documents of 1 MB</Em> plus a small manifest, so
        servers can read them in parallel.
      </Explain>
    </SceneBackground>
  );
};

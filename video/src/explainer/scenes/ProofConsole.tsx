import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import { Em, Spotlight, Tag } from "../components";
import { colors } from "../theme";
import { sceneBeats, sceneDuration } from "../timeline";
import { Footage } from "./Footage";

/** The stored KV cache in the Couchbase web console (03-couchbase-documents.mp4). */
export const ProofConsole: React.FC = () => {
  const b = sceneBeats("ProofConsole");
  const manifest = b[1].end + 15;
  const end = sceneDuration("ProofConsole");
  return (
    <AbsoluteFill style={{ backgroundColor: colors.bg }}>
      <Sequence name="Document list" durationInFrames={manifest} layout="absolute-fill">
        <Footage src="03-couchbase-documents.mp4" trimBefore={6} holdAfter={4.8} />
        <Spotlight
          x={505} y={485} w={870} h={125} from={b[0].start} to={b[0].end + 6}
          label={<>Each chunk has <Em>1 manifest</Em> document…</>}
          labelX={1000} labelY={330} labelWidth={560}
        />
        <Spotlight
          x={505} y={620} w={1400} h={400} from={b[1].start - 4} to={manifest + 10}
          label={<>…and its <Em>1 MB binary shards</Em>: …::shard::0, …::shard::1, …</>}
          labelX={600} labelY={330} labelWidth={760}
        />
      </Sequence>
      <Sequence name="Manifest" from={manifest} durationInFrames={end - manifest} layout="absolute-fill">
        <Footage src="03-couchbase-documents.mp4" trimBefore={18.2} holdAfter={18} />
        <Spotlight
          x={500} y={160} w={560} h={150} from={b[2].start - manifest - 6} to={end - manifest}
          label={<>The manifest: <Em>36 shards</Em>, 37,748,736 bytes (36 MB)</>}
          labelX={500} labelY={420} labelWidth={760}
        />
      </Sequence>
      <Tag>Real recording · Couchbase web console</Tag>
    </AbsoluteFill>
  );
};

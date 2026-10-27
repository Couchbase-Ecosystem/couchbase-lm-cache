import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import { Em, Spotlight, Tag } from "../components";
import { colors } from "../theme";
import { sceneBeats, sceneDuration } from "../timeline";
import { Footage } from "./Footage";

const CLIP_PAD = 15;

/**
 * The live run from evidence/recordings/01-demo.mp4, cut to three moments.
 * Spotlight coordinates are in the recording's 1920×1080 pixels; clip times
 * come from evidence/recordings/markers.json. Each spotlight follows the
 * narration segment that describes it.
 */
export const ProofRun: React.FC = () => {
  const b = sceneBeats("ProofRun");
  const clipB = b[3].end + CLIP_PAD;
  const clipC = b[4].end + CLIP_PAD;
  const end = sceneDuration("ProofRun");
  // Spotlight window for beat i, relative to the clip that starts at `offset`.
  const span = (i: number, offset: number) => ({ from: b[i].start - offset, to: b[i].end - offset + 8 });

  return (
    <AbsoluteFill style={{ backgroundColor: colors.bg }}>
      {/* 1. Server A: nothing in Couchbase yet, computes and saves (request at 3.5 s) */}
      <Sequence name="Server A computes" durationInFrames={clipB} layout="absolute-fill">
        <Footage src="01-demo.mp4" trimBefore={1} holdAfter={14} />
        <Spotlight
          x={52} y={128} w={560} h={290} {...span(0, 0)}
          label={<>The request: the <Em color={colors.blue}>10,288-token ledger</Em> plus one question, sent to server A</>}
          labelX={660} labelY={180} labelWidth={680}
        />
        <Spotlight
          x={60} y={618} w={440} h={26} {...span(1, 0)}
          label={<>Couchbase has <Em>0 of 40</Em> chunks: the GPU must read everything</>}
          labelX={660} labelY={520}
        />
        <Spotlight
          x={60} y={645} w={500} h={125} {...span(2, 0)}
          label={<>As it reads, LMCache <Em>saves the KV cache</Em> to Couchbase, 8 chunks at a time</>}
          labelX={660} labelY={600}
        />
        <Spotlight
          x={52} y={440} w={560} h={130} {...span(3, 0)}
          color={colors.amber}
          label={<>Answer: <Em color={colors.amber}>6692-J</Em>, first word after 2.71 s</>}
          labelX={660} labelY={420} labelWidth={560}
        />
      </Sequence>

      {/* 2. The documents land in the bucket (server B's request comes at 8.6 s) */}
      <Sequence name="Documents in Couchbase" from={clipB} durationInFrames={clipC - clipB} layout="absolute-fill">
        <Footage src="01-demo.mp4" trimBefore={15.8} holdAfter={8} />
        <Spotlight
          x={445} y={975} w={225} h={60} {...span(4, clipB)}
          label={<><Em>1,480 documents</Em> now in Couchbase: 40 chunks × 37 documents</>}
          labelX={445} labelY={760} labelWidth={760}
        />
      </Sequence>

      {/* 3. Server B: everything found, loaded instead of computed (the demo moves to the next column after about 8 s) */}
      <Sequence name="Server B loads" from={clipC} durationInFrames={end - clipC} layout="absolute-fill">
        <Footage src="01-demo.mp4" trimBefore={23.8} holdAfter={7.2} />
        <Spotlight
          x={690} y={618} w={440} h={26} {...span(5, clipC)}
          color={colors.green}
          label={<>Server B finds <Em color={colors.green}>all 40 chunks</Em> in Couchbase</>}
          labelX={1300} labelY={520} labelWidth={560}
        />
        <Spotlight
          x={690} y={645} w={515} h={26} {...span(6, clipC)}
          color={colors.green}
          label={<>…and loads the whole KV cache <Em color={colors.green}>instead of computing it</Em></>}
          labelX={1300} labelY={600} labelWidth={560}
        />
        <Spotlight
          x={675} y={430} w={580} h={120} from={b[7].start - clipC} to={end - clipC}
          color={colors.green}
          label={<><Em color={colors.green}>Same answer</Em>, and the first word came 2.3× sooner (1.17 s)</>}
          labelX={1300} labelY={420} labelWidth={560}
        />
      </Sequence>

      <Tag>Real recording · Qwen3-8B · 2× RTX 3090</Tag>
    </AbsoluteFill>
  );
};

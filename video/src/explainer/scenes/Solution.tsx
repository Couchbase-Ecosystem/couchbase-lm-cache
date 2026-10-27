import React from "react";
import { Arrow, CouchbaseBucket, Em, Explain, SceneBackground, SceneTitle, Server } from "../components";
import { sceneBeats } from "../timeline";
import { colors } from "../theme";

/** LMCache moves the KV cache off the GPU; Couchbase makes it shared. */
export const Solution: React.FC = () => {
  const beats = sceneBeats("Solution");
  return (
    <SceneBackground>
      <SceneTitle kicker="2 · The solution" title="Keep the KV cache in Couchbase" />
      <Server
        x={100}
        y={265}
        name="Server A"
        gpu="GPU 0"
        status="computes the KV cache once"
        progressValue={1}
        barColor={colors.blue}
        lmcache
      />
      <Server
        x={1200}
        y={265}
        name="Server B"
        gpu="GPU 1"
        status="reuses it instead of computing"
        statusColor={colors.green}
        progressValue={1}
        barColor={colors.green}
        lmcache
      />
      <CouchbaseBucket x={610} y={655} w={700} />
      <Arrow x1={420} y1={640} x2={600} y2={740} color={colors.red} from={beats[1].start} to={beats[1].start + 24} label="save" labelOffset={[-80, 0]} />
      <Arrow x1={1320} y1={740} x2={1500} y2={640} color={colors.green} from={beats[2].start} to={beats[2].start + 24} label="load" labelOffset={[80, 0]} />
      <Explain from={beats[3].start}>
        <Em color={colors.amber}>LMCache</Em> takes the KV cache off the GPU, and the{" "}
        <Em>Couchbase connector</Em> stores it where every server can read it.
      </Explain>
    </SceneBackground>
  );
};

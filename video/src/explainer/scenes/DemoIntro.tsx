import React from "react";
import { CouchbaseBucket, Em, Explain, SceneBackground, SceneTitle, Server } from "../components";
import { sceneBeats } from "../timeline";
import { colors, run } from "../theme";

/** Sets up the recorded demo before the footage starts. */
export const DemoIntro: React.FC = () => {
  const beats = sceneBeats("DemoIntro");
  return (
    <SceneBackground>
      <SceneTitle kicker="3 · The demo" title="Two GPU servers, one Couchbase bucket" />
      <Server x={100} y={265} name="Server A" gpu="GPU 0" status="gets the request first" lmcache />
      <Server x={1200} y={265} name="Server B" gpu="GPU 1" status="then gets the same context" lmcache />
      <CouchbaseBucket x={610} y={655} w={700} />
      <Explain from={beats[1].start}>
        A {run.tokens.toLocaleString("en-US")}-token context goes to server A, then to server B, like a
        session’s next turn. <Em color={colors.text}>Watch what server B finds.</Em>
      </Explain>
    </SceneBackground>
  );
};

import React from "react";
import { Composition, Folder } from "remotion";
import { Explainer, explainerDuration, NarratedScene, SCENES } from "./explainer/Explainer";
import { FPS, sceneDuration } from "./explainer/timeline";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Folder name="Explainer-Scenes">
        {SCENES.map((scene) => (
          <Composition
            key={scene.name}
            id={scene.name}
            component={() => <NarratedScene {...scene} />}
            durationInFrames={sceneDuration(scene.name)}
            fps={FPS}
            width={1920}
            height={1080}
          />
        ))}
      </Folder>
      <Composition
        id="Explainer"
        component={Explainer}
        durationInFrames={explainerDuration()}
        fps={FPS}
        width={1920}
        height={1080}
      />
    </>
  );
};

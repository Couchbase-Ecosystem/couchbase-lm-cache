import React from "react";
import { Audio } from "@remotion/media";
import { Sequence, staticFile } from "remotion";
import { hasAudio, sceneBeats, segmentId } from "./timeline";

/** Plays a scene's voice-over segments at their beats. */
export const Narration: React.FC<{ scene: string }> = ({ scene }) => (
  <>
    {sceneBeats(scene).map((beat, index) =>
      hasAudio(scene, index) ? (
        <Sequence
          key={index}
          from={beat.start}
          durationInFrames={beat.end - beat.start + 15}
          layout="none"
          name={`Voice ${index}`}
        >
          <Audio src={staticFile(`vo/${segmentId(scene, index)}.mp3`)} />
        </Sequence>
      ) : null,
    )}
  </>
);

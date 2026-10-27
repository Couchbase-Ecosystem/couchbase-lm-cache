import React from "react";
import { Video } from "@remotion/media";
import { Freeze, staticFile, useVideoConfig } from "remotion";

/**
 * A recording starting at `trimBefore` seconds. After `holdAfter` seconds the
 * frame freezes, so narration can run longer than the recorded moment without
 * the footage moving on to the next step.
 */
export const Footage: React.FC<{ src: string; trimBefore: number; holdAfter: number }> = ({
  src,
  trimBefore,
  holdAfter,
}) => {
  const { fps } = useVideoConfig();
  const hold = Math.round(holdAfter * fps);
  return (
    <Freeze frame={hold} active={(f) => f > hold}>
      <Video src={staticFile(src)} trimBefore={trimBefore * fps} muted />
    </Freeze>
  );
};

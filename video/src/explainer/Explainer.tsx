import React from "react";
import { linearTiming, TransitionSeries } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { Narration } from "./Narration";
import { sceneDuration, TRANSITION_FRAMES } from "./timeline";
import { Title } from "./scenes/Title";
import { Context } from "./scenes/Context";
import { Agenda } from "./scenes/Agenda";
import { Prefill } from "./scenes/Prefill";
import { Hook } from "./scenes/Hook";
import { Size } from "./scenes/Size";
import { Architectures } from "./scenes/Architectures";
import { ContextGrowth } from "./scenes/ContextGrowth";
import { Waste } from "./scenes/Waste";
import { Quotes } from "./scenes/Quotes";
import { Providers } from "./scenes/Providers";
import { UseCase } from "./scenes/UseCase";
import { Solution } from "./scenes/Solution";
import { Storage } from "./scenes/Storage";
import { Reuse } from "./scenes/Reuse";
import { DemoIntro } from "./scenes/DemoIntro";
import { ProofRun } from "./scenes/ProofRun";
import { ProofConsole } from "./scenes/ProofConsole";
import { Results } from "./scenes/Results";
import { Outro } from "./scenes/Outro";

/** Intro → the KV-cache memory problem → where it hurts → Couchbase → demo → result. */
export const SCENES: { name: string; Component: React.FC }[] = [
  { name: "Title", Component: Title },
  { name: "Context", Component: Context },
  { name: "Agenda", Component: Agenda },
  { name: "Prefill", Component: Prefill },
  { name: "Hook", Component: Hook },
  { name: "Size", Component: Size },
  { name: "Architectures", Component: Architectures },
  { name: "ContextGrowth", Component: ContextGrowth },
  { name: "Waste", Component: Waste },
  { name: "Quotes", Component: Quotes },
  { name: "Providers", Component: Providers },
  { name: "UseCase", Component: UseCase },
  { name: "Solution", Component: Solution },
  { name: "Storage", Component: Storage },
  { name: "Reuse", Component: Reuse },
  { name: "DemoIntro", Component: DemoIntro },
  { name: "ProofRun", Component: ProofRun },
  { name: "ProofConsole", Component: ProofConsole },
  { name: "Results", Component: Results },
  { name: "Outro", Component: Outro },
];

/** A scene with its voice-over, as used in the full video and the per-scene compositions. */
export const NarratedScene: React.FC<{ name: string; Component: React.FC }> = ({ name, Component }) => (
  <>
    <Component />
    <Narration scene={name} />
  </>
);

export const explainerDuration = () =>
  SCENES.reduce((total, s) => total + sceneDuration(s.name), 0) - TRANSITION_FRAMES * (SCENES.length - 1);

export const Explainer: React.FC = () => {
  return (
    <TransitionSeries>
      {SCENES.map((scene, i) => (
        <React.Fragment key={scene.name}>
          {i > 0 ? (
            <TransitionSeries.Transition
              presentation={fade()}
              timing={linearTiming({ durationInFrames: TRANSITION_FRAMES })}
            />
          ) : null}
          <TransitionSeries.Sequence durationInFrames={sceneDuration(scene.name)} name={scene.name}>
            <NarratedScene {...scene} />
          </TransitionSeries.Sequence>
        </React.Fragment>
      ))}
    </TransitionSeries>
  );
};

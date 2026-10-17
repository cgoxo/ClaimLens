import React from "react";
import { Audio, Composition, Sequence, staticFile } from "remotion";
import { FPS, H, W } from "./theme";
import { SCENES, SceneId, VOICE } from "./timeline";
import { Hook } from "./scenes/Hook";
import { Problem } from "./scenes/Problem";
import { Upload } from "./scenes/Upload";
import { Results } from "./scenes/Results";
import { ProofGate } from "./scenes/ProofGate";
import { Agent } from "./scenes/Agent";
import { Cloud } from "./scenes/Cloud";
import { Engineering } from "./scenes/Engineering";
import { Close } from "./scenes/Close";

const VIEWS: Record<SceneId, React.FC> = {
  hook: Hook, problem: Problem, upload: Upload, results: Results, proof: ProofGate,
  agent: Agent, cloud: Cloud, engineering: Engineering, close: Close,
};

const TOTAL = SCENES.reduce((n, s) => n + Math.round(s.seconds * FPS), 0);

const Film: React.FC = () => {
  let at = 0;
  return (
    <>
      {SCENES.map((s) => {
        const from = at, len = Math.round(s.seconds * FPS);
        at += len;
        const View = VIEWS[s.id];
        return (
          <Sequence key={s.id} name={s.id} from={from} durationInFrames={len}>
            <View />
            {VOICE && <Audio src={staticFile(`voice/${s.id}.m4a`)} />}
          </Sequence>
        );
      })}
    </>
  );
};

export const Root: React.FC = () => (
  <>
    <Composition id="ClaimLensDemo" component={Film} durationInFrames={TOTAL} fps={FPS} width={W} height={H} />
    {SCENES.map((s) => (
      <Composition key={s.id} id={`scene-${s.id}`} component={VIEWS[s.id]} durationInFrames={Math.round(s.seconds * FPS)} fps={FPS} width={W} height={H} />
    ))}
  </>
);

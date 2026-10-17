import React from "react";
import { Audio, Composition, Sequence, staticFile } from "remotion";
import { FPS, H, W } from "./theme";
import { MUSIC, SCENES, SceneId, VOICE } from "./timeline";
import { VOICE_LINES } from "./voiceTiming";
import { Captions } from "./components/ui";
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

// scenes on a dark background show light captions
const DARK: Partial<Record<SceneId, (t: number) => boolean>> = { problem: (t) => t < 5.9, close: () => true };

// every narration line on the film's own clock, for ducking the music under the voice
const SPOKEN = (() => {
  let at = 0;
  return SCENES.flatMap((s) => {
    const start = at;
    at += s.seconds;
    return (VOICE_LINES[s.id] ?? []).map((l) => [start + l.from, start + l.to] as const);
  });
})();

function musicUnderVoice(frame: number) {
  const t = frame / FPS;
  // distance in seconds to the nearest spoken line: 0 while speaking
  const gap = Math.min(...SPOKEN.map(([a, b]) => (t < a ? a - t : t > b ? t - b : 0)));
  return 0.06 + 0.06 * Math.min(1, Math.max(0, (gap - 0.2) / 0.6));
}

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
            {VOICE && VOICE_LINES[s.id].map((l) => (
              <Sequence key={l.file} from={Math.round(l.from * FPS)} layout="none">
                <Audio src={staticFile(l.file)} />
              </Sequence>
            ))}
            {VOICE && <Captions narrated dark={DARK[s.id]} lines={VOICE_LINES[s.id].map((l, i, all) => ({
              from: l.from - 0.1, to: Math.min(l.to + 0.35, all[i + 1]?.from ?? Infinity), text: l.text }))} />}
          </Sequence>
        );
      })}
      {MUSIC && <Audio src={staticFile("music.wav")} volume={(f) => (VOICE ? musicUnderVoice(f) : 0.22)} />}
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

import React from "react";
import { AbsoluteFill, Sequence, useVideoConfig } from "remotion";
import { BrowserShot, Box, Key, Point } from "./BrowserShot";
import { prog, useT } from "./ui";

export type Shot = { src: string; from: number; to: number; keys?: Key[]; boxes?: Box[]; cursor?: Point[]; cropTop?: number };

/** Plays screenshots one after another in the same browser frame, crossfading between them.
 *  Times on each shot's keys, boxes and cursor are relative to that shot's start. */
export const Shots: React.FC<{ shots: Shot[] }> = ({ shots }) => {
  const { t } = useT();
  const { fps } = useVideoConfig();
  return (
    <>
      {shots.map((s, i) => {
        const fadeIn = i === 0 ? 1 : prog(t, s.from, 0.3);
        const last = i === shots.length - 1;
        const fadeOut = last ? 1 : 1 - prog(t, s.to, 0.3);
        return (
          <Sequence key={s.src + i} from={Math.round(s.from * fps)} durationInFrames={Math.round((s.to - s.from + 0.3) * fps)} layout="none">
            <AbsoluteFill style={{ opacity: Math.min(fadeIn, fadeOut) }}>
              <BrowserShot src={s.src} keys={s.keys} boxes={s.boxes} cursor={s.cursor} cropTop={s.cropTop} enterAt={i === 0 ? 0 : -10} />
            </AbsoluteFill>
          </Sequence>
        );
      })}
    </>
  );
};

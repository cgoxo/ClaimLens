import { VOICE_LINES } from "./voiceTiming";

/** About when `phrase` is spoken in a scene, in seconds from the scene's start: the line's start plus the phrase's
 *  share of the line. Visuals keyed to it land with the words, whatever the voice's pace. */
export function cue(scene: string, phrase: string, fallback = 0): number {
  for (const l of VOICE_LINES[scene] ?? []) {
    const i = l.text.indexOf(phrase);
    if (i >= 0) return l.from + (i / l.text.length) * (l.to - l.from);
  }
  return fallback;
}

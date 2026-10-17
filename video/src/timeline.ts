// Every scene's length, in seconds. Change a number here to retime the film; the total must stay <= 180.
export const SCENES = [
  { id: "hook", seconds: 12 },
  { id: "problem", seconds: 13 },
  { id: "upload", seconds: 24 },
  { id: "results", seconds: 32 },
  { id: "proof", seconds: 15 },
  { id: "agent", seconds: 33 },
  { id: "cloud", seconds: 28 },
  { id: "engineering", seconds: 14 },
  { id: "close", seconds: 9 },
] as const;

export type SceneId = (typeof SCENES)[number]["id"];

// Narration on: lines and timings come from src/voiceTiming.ts, written by voice.mjs from SCRIPT.md
export const VOICE = true;

// Quiet background bed (public/music.wav, made by music.mjs); its level drops when the voice is on
export const MUSIC = true;

export const LIVE_URL = "claimlens-api-538594533263.asia-south1.run.app";

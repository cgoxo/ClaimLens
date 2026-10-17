// Every scene's length, in seconds, matching SCRIPT.md. The total must stay between 3 and 5 minutes.
export const SCENES = [
  { id: "hook", seconds: 12 },
  { id: "why", seconds: 17 },
  { id: "problem", seconds: 16 },
  { id: "upload", seconds: 25 },
  { id: "results", seconds: 33 },
  { id: "proof", seconds: 15 },
  { id: "agent", seconds: 35 },
  { id: "cloud", seconds: 33 },
  { id: "features", seconds: 15 },
  { id: "close", seconds: 13 },
] as const;

export type SceneId = (typeof SCENES)[number]["id"];

// Narration on: lines and timings come from src/voiceTiming.ts, written by voice.mjs from SCRIPT.md
export const VOICE = true;

// Quiet background bed (public/music.wav, made by music.mjs); its level drops when the voice is on
export const MUSIC = false; // music is mixed in after rendering (see README), so a voice-only cut exists too

export const LIVE_URL = "claimlens-api-538594533263.asia-south1.run.app";

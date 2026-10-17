// Every scene's length, in seconds. Change a number here to retime the film; the total must stay <= 180.
export const SCENES = [
  { id: "hook", seconds: 12 },
  { id: "problem", seconds: 13 },
  { id: "upload", seconds: 24 },
  { id: "results", seconds: 32 },
  { id: "proof", seconds: 15 },
  { id: "agent", seconds: 32 },
  { id: "cloud", seconds: 28 },
  { id: "engineering", seconds: 14 },
  { id: "close", seconds: 10 },
] as const;

export type SceneId = (typeof SCENES)[number]["id"];

// Set to true once the voiceover is saved as one file per scene: public/voice/<scene id>.m4a (hook.m4a, problem.m4a, ...)
export const VOICE = false;

export const LIVE_URL = "claimlens-api-538594533263.asia-south1.run.app";

import { loadFont as loadNewsreader } from "@remotion/google-fonts/Newsreader";
import { loadFont as loadPlexSans } from "@remotion/google-fonts/IBMPlexSans";
import { loadFont as loadPlexMono } from "@remotion/google-fonts/IBMPlexMono";

// The app's own tokens (frontend/src/styles/tokens.css), so the film looks like the product
export const C = {
  paper: "#f4efe4",
  sheet: "#fbf8f1",
  ink: "#1e1c19",
  inkSoft: "#5b564d",
  rule: "#d9d1c1",
  stamp: "#b3261e",
  amber: "#b26a00",
  olive: "#4f6b2e",
  slate: "#44546a",
  night: "#14130f",
  // Google Cloud accents
  gBlue: "#4285F4",
  gRed: "#EA4335",
  gYellow: "#FBBC04",
  gGreen: "#34A853",
};

export const F = {
  display: loadNewsreader("normal", { weights: ["500", "600"] }).fontFamily,
  body: loadPlexSans("normal", { weights: ["400", "500", "600"] }).fontFamily,
  mono: loadPlexMono("normal", { weights: ["400", "500"] }).fontFamily,
};

export const FPS = 30;
export const W = 1920;
export const H = 1080;

// Renders review stills in one bundle: node stills.mjs 240 660 ...
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import path from "node:path";

const serveUrl = await bundle({ entryPoint: path.resolve("src/index.ts") });
const composition = await selectComposition({ serveUrl, id: "ClaimLensDemo" });
for (const f of process.argv.slice(2).map(Number)) {
  await renderStill({ serveUrl, composition, frame: f, output: `out/stills/f${String(f).padStart(4, "0")}.png`, scale: 0.5 });
  console.log("frame", f);
}

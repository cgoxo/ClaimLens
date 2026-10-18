// Review aid: tiles one frame per narrated line, six to a sheet, captioned with the line. node sheets.mjs
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import fs from "node:fs";
import path from "node:path";

const lines = fs.readFileSync("out/line-frames.txt", "utf8").trim().split("\n").map((l) => {
  const m = l.match(/^\s*(\d+) (\w+) f(\d+): (.*)$/);
  return { n: +m[1], scene: m[2], file: `linecheck/f${m[3].padStart(4, "0")}.png`, text: m[4] };
});
const serveUrl = await bundle({ entryPoint: path.resolve("src/sheets.tsx") });
for (let i = 0; i < lines.length; i += 6) {
  const inputProps = { items: lines.slice(i, i + 6) };
  const composition = await selectComposition({ serveUrl, id: "Sheet", inputProps });
  await renderStill({ serveUrl, composition, frame: 0, inputProps, output: `out/sheets/sheet-${i / 6 + 1}.png`, scale: 0.75 });
  console.log("sheet", i / 6 + 1);
}

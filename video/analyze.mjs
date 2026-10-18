// Checks the team's recordings: length against the scene, loudness, clipping, background noise,
// and how many spoken stretches the pauses split each take into (compared with the script's line count).
// node analyze.mjs
import fs from "node:fs";

const script = fs.readFileSync("SCRIPT.md", "utf8");
const scenes = [...script.matchAll(/## \d+\. `(\w+)\.m4a` \((\d+) s\)\n\n((?:> .*\n)+)/g)]
  .map(([, id, seconds, body]) => ({ id, seconds: Number(seconds), lines: body.trim().split("\n").length }));

const db = (x) => (20 * Math.log10(x + 1e-12)).toFixed(1);

export function load(file) {
  const b = fs.readFileSync(file);
  let pos = 12, rate = 44100, data = null;
  while (pos < b.length - 8) {
    const id = b.toString("ascii", pos, pos + 4), size = b.readUInt32LE(pos + 4);
    if (id === "fmt ") rate = b.readUInt32LE(pos + 12);
    if (id === "data") { data = b.subarray(pos + 8, pos + 8 + size); break; }
    pos += 8 + size + (size % 2);
  }
  const x = new Float32Array(data.length / 2);
  for (let i = 0; i < x.length; i++) x[i] = data.readInt16LE(i * 2) / 32768;
  return { x, rate };
}

/** RMS in 20 ms windows */
export function frames(x, rate, ms = 20) {
  const n = Math.floor((rate * ms) / 1000), out = [];
  for (let i = 0; i + n <= x.length; i += n) {
    let s = 0;
    for (let j = i; j < i + n; j++) s += x[j] * x[j];
    out.push(Math.sqrt(s / n));
  }
  return out;
}

/** Spoken stretches separated by pauses of at least `minGap` seconds */
export function segments(env, ms, threshold, minGap = 0.55, minLen = 0.25) {
  const step = ms / 1000, segs = [];
  let start = -1, lastLoud = -1;
  env.forEach((v, i) => {
    const t = i * step;
    if (v > threshold) {
      if (start < 0) start = t;
      else if (t - lastLoud > minGap) { segs.push([start, lastLoud + step]); start = t; }
      lastLoud = t;
    }
  });
  if (start >= 0) segs.push([start, lastLoud + step]);
  return segs.filter(([a, b]) => b - a >= minLen);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  for (const s of scenes) {
    const { x, rate } = load(`recordings/wav/${s.id}.wav`);
    const env = frames(x, rate);
    const sorted = [...env].sort((a, b) => a - b);
    const noise = sorted[Math.floor(sorted.length * 0.1)];
    const speech = sorted[Math.floor(sorted.length * 0.9)];
    let peak = 0, clipped = 0;
    for (const v of x) { peak = Math.max(peak, Math.abs(v)); if (Math.abs(v) > 0.99) clipped++; }
    const threshold = Math.max(noise * 4, speech * 0.12);
    const segs = segments(env, 20, threshold);
    const spoken = segs.length ? segs.at(-1)[1] - segs[0][0] : 0;
    console.log(`${s.id.padEnd(9)} file ${(x.length / rate).toFixed(1).padStart(5)}s | speech ${spoken.toFixed(1).padStart(5)}s of ${String(s.seconds).padStart(2)}s` +
      ` | ${String(segs.length).padStart(2)} parts / ${s.lines} lines | speech ${db(speech)} dB, noise ${db(noise)} dB, SNR ${(20 * Math.log10(speech / noise)).toFixed(0)} dB` +
      ` | peak ${db(peak)} dB${clipped ? `, CLIPPED ${clipped}` : ""}`);
    console.log("          parts: " + segs.map(([a, b]) => `${a.toFixed(1)}-${b.toFixed(1)}`).join("  "));
  }
}

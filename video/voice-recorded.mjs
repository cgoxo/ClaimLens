// Uses the team's own recordings (recordings/wav/<scene>.wav, one take per scene) instead of a synthetic voice.
// Each take is cut into its script lines at the pauses that best match each line's share of the words; a line
// break with no pause is cut at the quietest moment near where it should be. Each line is then placed like
// voice.mjs places them: at its [n] start time if it has one, else after the previous line.
// Writes public/voice/<scene>/<n>.wav and src/voiceTiming.ts, and prints how long each scene needs to be.
// node voice-recorded.mjs
import fs from "node:fs";
import { frames, load, segments } from "./analyze.mjs";

const LEAD = 0.45, GAP = 0.45, MS = 20, STEP = MS / 1000;
const PAD_IN = 0.08, PAD_OUT = 0.14; // keep breaths and word endings

const script = fs.readFileSync("SCRIPT.md", "utf8");
const scenes = [...script.matchAll(/## \d+\. `(\w+)\.m4a` \((\d+) s\)\n\n((?:> .*\n)+)/g)].map(([, id, seconds, body]) => ({
  id, seconds: Number(seconds),
  lines: body.trim().split("\n").map((l) => {
    const raw = l.replace(/^> /, "").trim();
    const m = raw.match(/^\[(\d+(?:\.\d+)?)\]\s*/);
    return { at: m ? Number(m[1]) : null, text: raw.slice(m ? m[0].length : 0) };
  }),
}));

// rough syllables: vowel groups per word; an all-caps acronym (OCR, AI) is spelled out, one per letter
const words = (s) => s.split(/\s+/).filter(Boolean).reduce((n, w) => {
  const bare = w.replace(/[^A-Za-z]/g, "");
  if (bare.length > 1 && bare === bare.toUpperCase()) return n + bare.length;
  return n + Math.max(1, (bare.toLowerCase().replace(/e$/, "").match(/[aeiouy]+/g) ?? []).length);
}, 0);

/** Times to cut a take into `lines.length` parts */
function cuts(env, segs, lines) {
  const start = segs[0][0], end = segs.at(-1)[1];
  // speaking time only, so pauses don't skew where each line should fall
  const speakingBefore = (t) => segs.reduce((n, [a, b]) => n + Math.max(0, Math.min(b, t) - a), 0);
  const total = speakingBefore(end);
  const totalWords = lines.reduce((n, l) => n + words(l.text), 0);
  let acc = 0;
  const want = lines.slice(0, -1).map((l) => (acc += words(l.text)) / totalWords); // share of speaking time before each cut

  // candidates: every pause (preferred), and quiet moments inside speech (a small penalty)
  const cand = [];
  // the readers paused about a second between lines, so a long pause is more likely a line break than a comma
  for (let i = 1; i < segs.length; i++) {
    const len = segs[i][0] - segs[i - 1][1];
    cand.push({ t: (segs[i - 1][1] + segs[i][0]) / 2, penalty: 0.006 * Math.max(0, 1 - len / 1.2) });
  }
  segs.forEach(([a, b]) => {
    for (let t = a + 0.4; t < b - 0.4; t += STEP) {
      const i = Math.round(t / STEP);
      if (env[i] <= Math.min(env[i - 1], env[i + 1]) && env[i] < env[i - 3] && env[i] < env[i + 3]) cand.push({ t, penalty: 0.012 });
    }
  });
  cand.sort((x, y) => x.t - y.t);
  cand.forEach((c) => (c.share = speakingBefore(c.t) / total));

  // choose one increasing candidate per cut, keeping each close to where its line should end
  const K = want.length, n = cand.length;
  const best = Array.from({ length: K }, () => new Array(n).fill(Infinity));
  const from = Array.from({ length: K }, () => new Array(n).fill(-1));
  const cost = (k, j) => (cand[j].share - want[k]) ** 2 + cand[j].penalty;
  for (let j = 0; j < n; j++) best[0][j] = cost(0, j);
  for (let k = 1; k < K; k++)
    for (let j = 0; j < n; j++) {
      for (let i = 0; i < j; i++) if (cand[j].t - cand[i].t > 0.6 && best[k - 1][i] + cost(k, j) < best[k][j]) {
        best[k][j] = best[k - 1][i] + cost(k, j);
        from[k][j] = i;
      }
    }
  let j = best[K - 1].indexOf(Math.min(...best[K - 1]));
  const out = [];
  for (let k = K - 1; k >= 0; k--) { out.unshift(cand[j].t); j = from[k][j]; }
  return [start, ...out, end];
}

function writeWav(file, x, rate) {
  const buf = Buffer.alloc(44 + x.length * 2);
  buf.write("RIFF", 0); buf.writeUInt32LE(36 + x.length * 2, 4); buf.write("WAVE", 8);
  buf.write("fmt ", 12); buf.writeUInt32LE(16, 16); buf.writeUInt16LE(1, 20); buf.writeUInt16LE(1, 22);
  buf.writeUInt32LE(rate, 24); buf.writeUInt32LE(rate * 2, 28); buf.writeUInt16LE(2, 32); buf.writeUInt16LE(16, 34);
  buf.write("data", 36); buf.writeUInt32LE(x.length * 2, 40);
  x.forEach((v, i) => buf.writeInt16LE(Math.max(-32768, Math.min(32767, Math.round(v * 32767))), 44 + i * 2));
  fs.writeFileSync(file, buf);
}

fs.rmSync("public/voice", { recursive: true, force: true });
const timing = {}, needed = {};
for (const s of scenes) {
  const { x, rate } = load(`recordings/wav/${s.id}.wav`);
  const env = frames(x, rate, MS);
  const sorted = [...env].sort((a, b) => a - b);
  const threshold = Math.max(sorted[Math.floor(sorted.length * 0.1)] * 4, sorted[Math.floor(sorted.length * 0.9)] * 0.12);
  const segs = segments(env, MS, threshold);
  const edges = cuts(env, segs, s.lines);
  // trim each piece to its own speech, so silence at a cut isn't counted as part of a line
  const speechIn = (a, b) => {
    const inside = segs.map(([p, q]) => [Math.max(p, a), Math.min(q, b)]).filter(([p, q]) => q - p > 0.05);
    return inside.length ? [inside[0][0], inside.at(-1)[1]] : [a, b];
  };

  fs.mkdirSync(`public/voice/${s.id}`, { recursive: true });
  let at = LEAD;
  timing[s.id] = s.lines.map((l, i) => {
    const [a, b] = speechIn(edges[i], edges[i + 1]);
    const from = Math.max(0, Math.round((a - PAD_IN) * rate)), to = Math.min(x.length, Math.round((b + PAD_OUT) * rate));
    const clip = x.slice(from, to);
    const fade = Math.round(0.012 * rate);
    for (let k = 0; k < fade; k++) { clip[k] *= k / fade; clip[clip.length - 1 - k] *= k / fade; }
    const file = `voice/${s.id}/${i}.wav`;
    writeWav(`public/${file}`, clip, rate);
    if (l.at !== null) at = Math.max(at, l.at);
    const dur = clip.length / rate;
    const line = { text: l.text, file, from: +at.toFixed(2), to: +(at + dur).toFixed(2) };
    at += dur + GAP;
    return line;
  });
  const end = timing[s.id].at(-1).to;
  needed[s.id] = Math.max(s.seconds, Math.ceil(end + 1.2));
  console.log(`${s.id.padEnd(9)} ${end.toFixed(1)}s, scene ${s.seconds}s${needed[s.id] > s.seconds ? ` -> needs ${needed[s.id]}s` : ""}`);
  timing[s.id].forEach((l) => console.log(`            ${l.from.toFixed(1).padStart(5)}-${l.to.toFixed(1).padStart(5)}  ${l.text.slice(0, 70)}`));
}

fs.writeFileSync("src/voiceTiming.ts",
  "// Written by voice-recorded.mjs from the team's recordings: every narration line, its clip and when it plays\n" +
  "export type VoiceLine = { text: string; file: string; from: number; to: number };\n" +
  `export const VOICE_LINES: Record<string, VoiceLine[]> = ${JSON.stringify(timing, null, 2)};\n`);
fs.writeFileSync("recordings/needed.json", JSON.stringify(needed, null, 2));

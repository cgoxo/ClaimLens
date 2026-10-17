// Writes public/music.wav: a light, bright bed made in code (no samples, no copyright).
// Short plucked notes over a major I-V-vi-IV loop at a relaxed 92 bpm, with a soft bass on each chord.
// It already dips under the narration (read from src/voiceTiming.ts), so it is mixed in at a fixed level.
import fs from "node:fs";

const RATE = 44100;
const scenes = [...fs.readFileSync("src/timeline.ts", "utf8").matchAll(/id: "(\w+)", seconds: (\d+)/g)].map(([, id, s]) => ({ id, seconds: Number(s) }));
const SECONDS = scenes.reduce((n, s) => n + s.seconds, 0);
const N = RATE * SECONDS;

const vt = fs.readFileSync("src/voiceTiming.ts", "utf8");
const lines = JSON.parse(vt.slice(vt.indexOf("> = {") + 4).replace(/;\s*$/, ""));
const spoken = [];
let at = 0;
for (const s of scenes) {
  for (const l of lines[s.id] ?? []) spoken.push([at + l.from, at + l.to]);
  at += s.seconds;
}

const BPM = 92, BEAT = 60 / BPM, STEP = BEAT / 2; // eighth notes
const hz = (m) => 440 * 2 ** ((m - 69) / 12);
// C major: C, G, Am, F; arpeggio notes per chord (an octave above middle C) and a bass root
const CHORDS = [
  { bass: 36, notes: [72, 76, 79, 84, 79, 76, 74, 76] },
  { bass: 43, notes: [71, 74, 79, 83, 79, 74, 71, 74] },
  { bass: 45, notes: [72, 76, 81, 84, 81, 76, 72, 76] },
  { bass: 41, notes: [72, 77, 81, 84, 81, 77, 76, 77] },
];
const BAR = STEP * 8;

const L = new Float32Array(N), R = new Float32Array(N);
function pluck(start, freq, amp, decay, pan) {
  const from = Math.floor(start * RATE), len = Math.floor(decay * 5 * RATE);
  for (let i = 0; i < len && from + i < N; i++) {
    const t = i / RATE;
    const env = Math.min(1, t / 0.004) * Math.exp(-t / decay);
    // a soft mallet: fundamental plus a quickly fading fourth partial
    const v = Math.sin(2 * Math.PI * freq * t) + 0.35 * Math.exp(-t / 0.05) * Math.sin(2 * Math.PI * freq * 4 * t);
    L[from + i] += v * env * amp * (1 - pan);
    R[from + i] += v * env * amp * pan;
  }
}

for (let bar = 0; bar * BAR < SECONDS; bar++) {
  const c = CHORDS[bar % 4], t0 = bar * BAR;
  pluck(t0, hz(c.bass), 0.5, 0.55, 0.5);
  pluck(t0 + BEAT * 2, hz(c.bass), 0.3, 0.4, 0.5);
  c.notes.forEach((m, k) => pluck(t0 + k * STEP, hz(m), k % 4 === 0 ? 0.22 : 0.15, 0.22, k % 2 ? 0.65 : 0.35));
}

// level: lower under speech, a little up in the gaps; fade in and out
const level = (t) => {
  const gap = Math.min(...spoken.map(([a, b]) => (t < a ? a - t : t > b ? t - b : 0)));
  return 0.45 + 0.55 * Math.min(1, Math.max(0, (gap - 0.25) / 0.6));
};
let peak = 0;
for (let i = 0; i < N; i += 1) peak = Math.max(peak, Math.abs(L[i]), Math.abs(R[i]));
const buf = Buffer.alloc(44 + N * 4);
buf.write("RIFF", 0); buf.writeUInt32LE(36 + N * 4, 4); buf.write("WAVE", 8);
buf.write("fmt ", 12); buf.writeUInt32LE(16, 16); buf.writeUInt16LE(1, 20); buf.writeUInt16LE(2, 22);
buf.writeUInt32LE(RATE, 24); buf.writeUInt32LE(RATE * 4, 28); buf.writeUInt16LE(4, 32); buf.writeUInt16LE(16, 34);
buf.write("data", 36); buf.writeUInt32LE(N * 4, 40);
let lv = 0;
for (let i = 0; i < N; i++) {
  const t = i / RATE;
  if (i % 441 === 0) lv = level(t); // the envelope moves slowly: work it out every 10 ms
  const g = (0.7 / peak) * lv * Math.min(1, t / 2, (SECONDS - t) / 3);
  buf.writeInt16LE(Math.round(L[i] * g * 32767), 44 + i * 4);
  buf.writeInt16LE(Math.round(R[i] * g * 32767), 46 + i * 4);
}
fs.writeFileSync("public/music.wav", buf);
console.log(`public/music.wav ${SECONDS}s, ${spoken.length} spoken lines ducked`);

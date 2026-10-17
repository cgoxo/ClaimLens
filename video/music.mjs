// Writes public/music.wav: a quiet ambient bed made in code (no samples, no copyright).
// Soft sine pads over a slow four-chord loop, with gentle attack and release so nothing pulses.
import fs from "node:fs";

const RATE = 44100, SECONDS = 180, N = RATE * SECONDS;
const BAR = 8; // seconds per chord

const note = (n) => 440 * 2 ** ((n - 69) / 12); // MIDI note to Hz
// D major family, calm and open: Dmaj9, Bm7, Gmaj7, Aadd9 (bass + three upper notes)
const CHORDS = [
  [38, 62, 66, 69, 76],
  [35, 62, 66, 69, 74],
  [31, 62, 66, 71, 74],
  [33, 61, 64, 69, 71],
];

const left = new Float32Array(N), right = new Float32Array(N);
for (let i = 0; i < N; i++) {
  const t = i / RATE;
  const bar = Math.floor(t / BAR), pos = t - bar * BAR;
  // crossfade each chord into the next over two seconds
  const parts = [[CHORDS[bar % 4], 1]];
  if (pos > BAR - 2) parts.push([CHORDS[(bar + 1) % 4], (pos - (BAR - 2)) / 2]);
  if (pos > BAR - 2) parts[0][1] = 1 - (pos - (BAR - 2)) / 2;
  if (bar > 0 && pos < 0) parts.length = 1;
  let l = 0, r = 0;
  for (const [chord, w] of parts) {
    chord.forEach((m, k) => {
      const f = note(m);
      const amp = (k === 0 ? 0.20 : 0.075) * w;
      const wobble = 1 + 0.0015 * Math.sin(2 * Math.PI * (0.11 + k * 0.03) * t);
      const v = Math.sin(2 * Math.PI * f * wobble * t) + 0.25 * Math.sin(2 * Math.PI * f * 2 * t);
      const pan = k % 2 ? 0.62 : 0.38;
      l += v * amp * (1 - pan);
      r += v * amp * pan;
    });
  }
  const breathe = 0.85 + 0.15 * Math.sin(2 * Math.PI * t / 16);
  const fade = Math.min(1, t / 3, (SECONDS - t) / 5);
  left[i] = l * breathe * fade;
  right[i] = r * breathe * fade;
}

let peak = 0;
for (let i = 0; i < N; i++) peak = Math.max(peak, Math.abs(left[i]), Math.abs(right[i]));
const gain = 0.7 / peak;
const buf = Buffer.alloc(44 + N * 4);
buf.write("RIFF", 0); buf.writeUInt32LE(36 + N * 4, 4); buf.write("WAVE", 8);
buf.write("fmt ", 12); buf.writeUInt32LE(16, 16); buf.writeUInt16LE(1, 20); buf.writeUInt16LE(2, 22);
buf.writeUInt32LE(RATE, 24); buf.writeUInt32LE(RATE * 4, 28); buf.writeUInt16LE(4, 32); buf.writeUInt16LE(16, 34);
buf.write("data", 36); buf.writeUInt32LE(N * 4, 40);
for (let i = 0; i < N; i++) {
  buf.writeInt16LE(Math.round(left[i] * gain * 32767), 44 + i * 4);
  buf.writeInt16LE(Math.round(right[i] * gain * 32767), 46 + i * 4);
}
fs.writeFileSync("public/music.wav", buf);
console.log("public/music.wav", (buf.length / 1e6).toFixed(1), "MB");

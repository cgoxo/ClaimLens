// Speaks SCRIPT.md one line at a time with a macOS voice, measures every clip, and writes src/voiceTiming.ts
// so the narration and the captions land on exactly the same frames.
// node voice.mjs "Tara (English (India))"
import { execFileSync } from "node:child_process";
import fs from "node:fs";

const voice = process.argv[2];
if (!voice) throw new Error('usage: node voice.mjs "<voice name>"');
const LEAD = 0.45;  // seconds of quiet at the start of a scene whose first line has no start time
const GAP = 0.45;   // pause between lines
const TEMPO = 0.88; // slower than the voice's own pace, without changing its pitch: calmer, easier to follow

const script = fs.readFileSync("SCRIPT.md", "utf8");
const scenes = [...script.matchAll(/## \d+\. `(\w+)\.m4a` \((\d+) s\)\n\n((?:> .*\n)+)/g)]
  .map(([, id, seconds, body]) => ({ id, seconds: Number(seconds), lines: body.trim().split("\n").map((l) => l.replace(/^> /, "").trim()) }));

/** Length of a PCM WAV in seconds, from its fmt and data chunks */
function wavSeconds(file) {
  const b = fs.readFileSync(file);
  let pos = 12, rate = 0, block = 0;
  while (pos < b.length - 8) {
    const id = b.toString("ascii", pos, pos + 4), size = b.readUInt32LE(pos + 4);
    if (id === "fmt ") { rate = b.readUInt32LE(pos + 12); block = b.readUInt16LE(pos + 20); }
    if (id === "data") return size / (rate * block);
    pos += 8 + size + (size % 2);
  }
  throw new Error(`no data chunk in ${file}`);
}

fs.rmSync("public/voice", { recursive: true, force: true });
const timing = {};
for (const s of scenes) {
  fs.mkdirSync(`public/voice/${s.id}`, { recursive: true });
  let at = LEAD;
  timing[s.id] = s.lines.map((raw, i) => {
    const m = raw.match(/^\[(\d+(?:\.\d+)?)\]\s*/);
    if (m) at = Math.max(at, Number(m[1]));
    const text = raw.slice(m ? m[0].length : 0);
    const file = `voice/${s.id}/${i}.wav`;
    const spoken = `public/voice/${s.id}/${i}.raw.wav`;
    execFileSync("say", ["-v", voice, "--file-format=WAVE", "--data-format=LEI16@44100", "-o", spoken, text]);
    execFileSync("npx", ["remotion", "ffmpeg", "-v", "error", "-y", "-i", spoken, "-af", `atempo=${TEMPO}`, "-c:a", "pcm_s16le", `public/${file}`]);
    fs.rmSync(spoken);
    const dur = wavSeconds(`public/${file}`);
    const line = { text, file, from: +at.toFixed(2), to: +(at + dur).toFixed(2) };
    at += dur + GAP;
    return line;
  });
  const end = timing[s.id].at(-1).to;
  console.log(`${s.id.padEnd(12)} ${end.toFixed(1)}s of ${s.seconds}s${end > s.seconds - 0.4 ? "   TOO LONG" : ""}`);
}

fs.writeFileSync("src/voiceTiming.ts",
  "// Written by voice.mjs: every narration line, its clip and when it plays (seconds from the scene's start)\n" +
  "export type VoiceLine = { text: string; file: string; from: number; to: number };\n" +
  `export const VOICE_LINES: Record<string, VoiceLine[]> = ${JSON.stringify(timing, null, 2)};\n`);

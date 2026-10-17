# ClaimLens demo video

A 3-minute submission video, made with [Remotion](https://www.remotion.dev) (React to MP4). Design:
`docs/superpowers/specs/2026-10-17-claimlens-demo-video-design.md`.

```bash
npm install
npm run studio          # preview in the browser, scrub the timeline
npm run render          # writes out/claimlens-demo.mp4
node stills.mjs 240 960 # renders review frames to out/stills/
```

| Path | What |
| --- | --- |
| `src/timeline.ts` | Scene order and lengths; `VOICE` switches the voiceover on |
| `src/scenes/` | One file per scene: Hook, Problem, Upload, Results, ProofGate, Agent, Cloud, Engineering, Close |
| `src/components/BrowserShot.tsx` | A screenshot in a browser frame, with camera moves, highlight boxes and a cursor |
| `public/shots/` | Full-resolution captures of the live app (sample claim), taken with `cap.sh` |
| `SCRIPT.md` | The voiceover, one file per scene in `public/voice/` |

Positions in scenes (camera keys, boxes, cursor) are in the page's CSS pixels: the captured viewport is 1470 x 745.

## Sound

```bash
node voice.mjs "Tara (English (India))" # narration from SCRIPT.md: one clip per line, slowed to 88%, and src/voiceTiming.ts
node music.mjs                          # public/music.wav: a light plucked bed that already dips under every line
npm run render                          # out/claimlens-demo.mp4, voice only
npx remotion ffmpeg -i out/claimlens-demo.mp4 -c:v copy -af "loudnorm=I=-16:TP=-1.5:LRA=11" -ar 48000 -c:a aac -b:a 192k out/claimlens-demo-voice-only.mp4
npx remotion ffmpeg -i out/claimlens-demo.mp4 -i public/music.wav -filter_complex "[1:a]volume=0.16[m];[0:a][m]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[a]" -map 0:v -map "[a]" -c:v copy -ar 48000 -c:a aac -b:a 192k out/claimlens-demo-with-music.mp4
```

Run `music.mjs` after `voice.mjs`: it reads the narration timing. Both finals are levelled to -16 LUFS, the usual
loudness for online video.

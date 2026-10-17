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

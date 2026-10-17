# ClaimLens demo video: design

## Goal

A 3-minute submission video for the Google Cloud APAC AI builder hackathon. A judge should come away knowing
what ClaimLens does, why it can be trusted (Gemini reads, code decides, every quote is proved), that it has an
agentic edge (the chat agent uses tools, a human applies), how much of Google Cloud it uses, and that it is
engineered properly.

## Constraints

- At most 3:00. 1920x1080, 30 fps, MP4 (H.264).
- Works muted: bold burned-in captions carry the story; the user's recorded voiceover is laid in on top.
- The app is not touched: everything lives in `video/` on branch `feat/demo-video`.
- Every number on screen is taken from the repo or `docs/eval/`, never invented.
- Footage is real: screenshots of the deployed app, captured through Claude in Chrome in the user's signed-in
  Chrome, in a new tab.

## How it is made

1. **Capture.** Claude drives the live app (sample claim) and saves full-resolution screenshots to
   `video/public/shots/`, one per shot in the shot list below.
2. **Edit.** Remotion (React to video). One component per scene in `video/src/scenes/`, timings in one file
   (`video/src/timeline.ts`). Motion is code: pans and zooms on screenshots, a drawn cursor, typed text,
   highlight boxes, animated diagrams. Previewed with `npx remotion studio`.
3. **Voice.** `video/SCRIPT.md` holds the narration per scene with its length. The user records it; the audio
   goes in `video/public/voice.m4a` (one file, or one per scene). Scene lengths are adjusted to the voice.
4. **Render.** `npx remotion render` writes `video/out/claimlens-demo.mp4`.

## Storyboard

| Time | Scene | Content |
| --- | --- | --- |
| 0:00-0:12 | Hook | A bill; one amount changes 12,000 to 42,000. "Health-insurance fraud is often one edited number." |
| 0:12-0:25 | Why it's hard | An AI that makes things up can't judge claims. Title: "Gemini reads. Code decides. Every claim proved." |
| 0:25-0:50 | Upload (real) | Sign-in, Claim and Policy forms, Try the sample claim, live progress labels |
| 0:50-1:20 | Results (real) | Risk stamp, findings, a finding's box on the page, facts with page links, settlement and recommendation |
| 1:20-1:35 | Proof gate (animation) | Quotes checked against the page; a made-up one is dropped; "covered" never matches "not covered" |
| 1:35-2:05 | Agentic edge (real + overlay) | Chat question, tool calls shown as chips, cited answer, Ask about an area, proposal waiting for Apply |
| 2:05-2:35 | Built on Google Cloud (animation) | Firebase Auth, Cloud Run, Cloud Storage, Cloud Tasks (retry), Document AI, Vertex AI Gemini 2.5 Flash, Firestore; Artifact Registry, Secret Manager, Cloud Logging, Workload Identity, Terraform |
| 2:35-2:50 | Engineering | Test counts, CI/CD on push to main, keyless deploy, jobs that run once, measured evaluation (CAT-Net dropped at AUC 0.40; risk files 4/4 live) |
| 2:50-3:00 | Close | Logo, live URL, "It flags. A human decides." |

## Shot list (captured from the live app)

1. Signed-in upload page, empty
2. Upload page with the sample claim loaded (both forms filled)
3. Case page during analysis, progress label visible (two or three moments)
4. Finished case: risk stamp and recommendation
5. Findings list
6. A critical finding selected, its box on the page
7. Facts panel with page links
8. Settlement
9. Chat: a question and its cited answer
10. Ask about an area: a box selected on the bill, and the answer
11. A proposal waiting for Apply

## Look

Product scenes use the app's paper-and-ink palette. Google Cloud scenes use Google's blue, red, yellow and
green as accents on the same paper. Display type: Bricolage Grotesque; body: IBM Plex Sans (both Google Fonts,
loaded by Remotion). Service tiles are text labels, not trademarked logos.

## Risks

- A chat answer comes back weak or unverified: ask again or rephrase before capturing.
- The live analysis takes about 40 seconds: progress is captured as stills and played back faster.
- Voice longer than a scene: lengthen the scene in `timeline.ts`, keeping the total at 3:00 or less.

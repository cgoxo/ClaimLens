# ClaimLens demo: narration

Total 3:00. Each `>` line is spoken as one clip and shown as one caption. `[n]` makes a line start no earlier than
n seconds into its scene, so it lands on its visual; lines without one follow the previous line.

Generate the voice (macOS voice "Tara", English India) and its timing:

```bash
node voice.mjs "Tara (English (India))"
```

That writes `public/voice/<scene>/<n>.wav` and `src/voiceTiming.ts`, and warns if a scene's narration runs too long.
To use your own recordings instead, record each line as its own file at the same paths and rerun the timing step.

---

## 1. `hook.m4a` (12 s)

> [0.5] This is a hospital bill.
> [2.3] Someone hid the real total under a white box,
> and typed a bigger one on top, in a different font.
> [7.6] Would a reviewer catch it? Would an AI?

## 2. `problem.m4a` (13 s)

> [0.3] AI reads documents brilliantly. It also makes things up.
> In insurance, that hurts honest families.
> [6.0] So we built ClaimLens.
> [7.1] Gemini reads. Code decides. Every claim is proved.

## 3. `upload.m4a` (24 s)

> [0.3] A reviewer signs in with Google, through Firebase.
> [3.6] They upload the claim and its policy. Here, our sample claim.
> [9.1] The case goes onto a Cloud Tasks queue, and runs in the background.
> [14.0] Every page is read. Photos go through Document AI.
> Gemini pulls out the facts.
> [19.0] In under a minute, the case is ready.

## 4. `results.m4a` (32 s)

> [0.4] Risk: one hundred out of one hundred. Investigate.
> [5.0] Gemini writes the summary, but plain code sets the score.
> [9.2] Every finding is marked on its own page.
> This total's font doesn't match any other amount.
> [15.7] This pharmacy invoice was already used in another claim, even on a photo.
> [21.7] The policy becomes a rulebook. Cataract is still in its waiting period.
> [27.2] So the settlement, worked out line by line in code, is zero.

## 5. `proof.m4a` (15 s)

> [0.4] This is what makes it trustworthy.
> Every fact Gemini returns must quote its page.
> [5.2] Code looks for that quote. If it isn't there, it's dropped.
> [9.8] Typos are fine. A different number, or a missing not, never is.

## 6. `agent.m4a` (33 s)

> [0.3] On a finished case, the reviewer can question a Gemini agent.
> [4.3] It calls read-only tools over the case.
> [7.6] And its answers pass the same proof gate.
> [13.1] Draw a box on any page, and ask about just that area.
> [17.2] It adds up the lines itself. The total doesn't fit.
> [23.2] It can suggest a change, but only as a proposal.
> [28.2] The agent investigates. Code verifies. A human decides.

## 7. `cloud.m4a` (28 s)

> [0.5] It all runs on Google Cloud. Firebase signs reviewers in.
> [4.3] One Cloud Run service runs the app, the API and the agent.
> [8.3] Files go to Cloud Storage, cases to Firestore.
> [12.3] Cloud Tasks runs each analysis, retried if it fails, never twice.
> [17.3] Document AI reads the scans. Gemini on Vertex AI reads the meaning.
> [22.1] Every push is tested and deployed automatically, with no stored keys.

## 8. `engineering.m4a` (14 s)

> [0.5] More than six hundred automated tests run before anything ships.
> [6.9] And we measure. A forgery model that couldn't beat a coin flip on our photos?
> We cut it.

## 9. `close.m4a` (9 s)

> [0.6] ClaimLens.
> [1.6] It flags. A human decides.

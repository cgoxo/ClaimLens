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

> [0.5] Look at this hospital bill.
> [2.4] The real total is hidden under a white box,
> and a bigger one is typed on top.
> [7.8] Would you catch it?

## 2. `problem.m4a` (13 s)

> [0.3] AI reads documents brilliantly.
> [2.2] But it also makes things up.
> [6.0] So we built ClaimLens.
> [7.3] Gemini reads. Code decides. Every claim is proved.

## 3. `upload.m4a` (24 s)

> [0.3] A reviewer signs in with Google,
> [3.6] and uploads the claim and the policy.
> [9.1] Cloud Tasks runs the analysis in the background.
> [14.0] Every page is read, and Gemini pulls out the facts.
> [19.0] In under a minute, it's ready.

## 4. `results.m4a` (32 s)

> [0.4] Risk: one hundred out of one hundred.
> [5.0] Gemini writes the summary. Code sets the score.
> [9.2] Every finding is marked on its page.
> This total uses a different font.
> [15.7] This invoice was already used in another claim.
> [21.7] And cataract is still in its waiting period,
> [27.2] so the payable amount is zero.

## 5. `proof.m4a` (15 s)

> [0.4] Here's why you can trust it.
> Every fact must quote its page.
> [5.4] If the quote isn't there, it's dropped.
> [9.8] A different number, or a missing "not", never passes.

## 6. `agent.m4a` (34 s)

> [0.3] Now, the agent.
> Reviewers can question Gemini about the case.
> [4.3] It uses read-only tools,
> [7.6] and every answer passes the same proof check.
> [13.1] Draw a box on the bill, and ask about just that area.
> [17.2] It adds up the lines, and the total doesn't fit.
> [23.2] It can suggest changes, but only a human can apply them.
> [28.3] The agent investigates. Code verifies. A human decides.

## 7. `cloud.m4a` (28 s)

> [0.5] All of it runs on Google Cloud.
> [4.3] One Cloud Run service hosts everything.
> [8.3] Files in Cloud Storage. Cases in Firestore.
> [12.3] Cloud Tasks retries failures, and never runs a job twice.
> [17.3] Document AI reads the scans. Gemini, on Vertex AI, reads the meaning.
> [22.1] And every push is tested and deployed automatically.

## 8. `engineering.m4a` (14 s)

> [0.5] Over six hundred tests run before anything ships.
> [6.9] And when a forgery model failed our tests, we cut it.

## 9. `close.m4a` (8 s)

> [0.6] ClaimLens.
> [1.8] It flags. A human decides.

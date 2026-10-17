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
> [2.4] The real total is hidden under a white box, and a bigger one is typed on top.
> [7.8] Would your team catch it?

## 2. `why.m4a` (17 s)

> [0.4] In India alone, health insurers lose up to ten thousand crore rupees a year to fraud, waste and abuse.
> That's across more than three crore claims a year.
> And with AI, faking a bill gets easier every day.

## 3. `problem.m4a` (16 s)

> [0.3] Across Asia-Pacific, claims arrive as PDFs, scans and phone photos.
> No reviewer can check every page.
> So we built ClaimLens.
> Gemini reads. Code decides. Every claim is proved.

## 4. `upload.m4a` (25 s)

> [0.3] Sign in with Google, and drop in the claim and the policy.
> [9.1] ClaimLens reads every page, and runs OCR on photos with Document AI.
> [13.1] It confirms these are real insurance documents, then Gemini extracts the facts.
> [19.0] In under a minute, the case file is ready.

## 5. `results.m4a` (33 s)

> [0.4] Risk: one hundred out of one hundred. Recommendation: investigate.
> [5.3] Every fact links back to the page it came from.
> [9.7] Every problem is marked on the document: an amount in a different font, the real total hidden underneath,
> an invoice already used in another claim, even on a phone photo.
> The policy becomes a rulebook. A waiting period applies, line by line.
> Payable: zero.

## 6. `proof.m4a` (15 s)

> [0.4] AI can make things up. So every fact must quote its page.
> [5.4] No quote, no finding.
> [9.8] A different number, or a missing "not", never passes.

## 7. `agent.m4a` (35 s)

> [0.3] And this is where it becomes agentic.
> Reviewers question a Gemini agent that investigates the case with its own tools.
> [8.6] Every answer is checked against the documents.
> [14.1] Draw a box on any page, and ask about just that area.
> [18.2] It does the maths, and spots the total that doesn't fit.
> [24.2] It even proposes changes, but nothing happens until a human approves.
> [29.3] The agent investigates. Code verifies. A human decides.

## 8. `cloud.m4a` (33 s)

> [0.4] ClaimLens runs entirely on Google Cloud, in the Mumbai region.
> Firebase signs reviewers in.
> One Cloud Run service hosts the app, the pipeline and the agent, and scales to zero when idle.
> Cloud Tasks runs every analysis reliably. Firestore and Cloud Storage keep the case file.
> Document AI reads the scans. Gemini on Vertex AI reads the meaning.
> Every release ships automatically, with no stored keys.

## 9. `features.m4a` (15 s)

> [0.4] Edited files. Hidden text. Totals that don't add up.
> Reused invoices. Missing pages. Policy limits.
> One case file. Every problem, on its page.

## 10. `close.m4a` (13 s)

> [0.5] ClaimLens. AI that shows its work.
> Every page read. Every rupee proved.
> Built by Himanshi, Chitresh and Priyanshu.

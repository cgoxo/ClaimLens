# ClaimLens demo: voiceover script

Total 3:00. Record **one file per scene**, named exactly as below (e.g. `hook.m4a`), and put them in
`video/public/voice/`. Then set `VOICE = true` in `src/timeline.ts`.

How to record:
- Quiet room, phone or laptop about 20 cm from your mouth. iPhone Voice Memos or QuickTime (File → New Audio Recording) is fine.
- Calm, confident, slightly slower than normal. Smile a little: it shows in the voice.
- Start each file about half a second after you press record. Stay under the time given; shorter is fine.
- If a take goes wrong, just re-record that one scene.

The word counts fit the times at a relaxed pace (about 2.3 words a second).

---

## 1. `hook.m4a` (12 s)

> A hospital bill. Someone hid the real total under a white box,
> and typed a bigger one on top.
> Would a reviewer catch it? Would an AI?

## 2. `problem.m4a` (13 s)

> AI reads documents brilliantly. It also makes things up,
> and in insurance that can hurt an honest family.
> So in ClaimLens, Gemini reads, code decides, and every claim is proved.

## 3. `upload.m4a` (24 s)

> A reviewer signs in with Google, through Firebase,
> and uploads a claim and its policy. We'll use the sample claim.
> The case goes onto a Cloud Tasks queue, so the analysis runs in the background.
> Every page is read. Photos go through Document AI. Gemini pulls out the facts.
> Under a minute later, it's ready.

## 4. `results.m4a` (32 s)

> Risk: one hundred out of one hundred. Recommendation: investigate.
> Gemini writes this summary, but plain code sets the score.
> Every finding is marked on its page. This total's font doesn't match the others.
> This pharmacy invoice was already used in another claim, caught on a phone photo.
> The policy is read into a rulebook. Cataract is still in its twenty-four-month waiting period,
> so the settlement, worked out line by line in code, is zero.

## 5. `proof.m4a` (15 s)

> This is what makes it trustworthy. Every fact Gemini returns must quote its page.
> Code looks for that quote. If it isn't there, it's dropped.
> Typos are fine. A different number, or a missing "not", never is.

## 6. `agent.m4a` (32 s)

> On a finished case, the reviewer can question a Gemini agent.
> It answers by calling read-only tools over the case, and its answers pass the same proof gate.
> You can draw a box on any page and ask about just that area. Here it adds up the lines itself:
> forty-five thousand five hundred. The total doesn't fit.
> It can suggest changes, like dismissing a typo, but only as a proposal.
> The agent investigates. Code verifies. A human decides.

## 7. `cloud.m4a` (28 s)

> It all runs on Google Cloud. Firebase signs reviewers in.
> One Cloud Run service serves the app, the API, the pipeline and the agent.
> Files go to Cloud Storage, cases to Firestore.
> Cloud Tasks runs each analysis: retried if it fails, never run twice.
> Document AI reads the scans. Gemini 2.5 Flash on Vertex AI reads the meaning.
> And every push ships through CI, with keyless deploys.

## 8. `engineering.m4a` (14 s)

> More than six hundred automated tests run before anything deploys.
> And we measure. A forgery model that couldn't beat a coin flip on our photos? We cut it.

## 9. `close.m4a` (10 s)

> ClaimLens. It flags. A human decides.

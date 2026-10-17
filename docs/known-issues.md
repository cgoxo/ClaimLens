# Known issues (to fix later)

Collected on 2026-10-17. Each issue has a test case in part E (extensive testing) that shows it, so a later fix can be measured. Issues are grouped by area.

## Policy, settlement and recommendation (PR #1)

| # | Issue | Seen in | Effect |
| --- | --- | --- | --- |
| P1 | Gemini's exclusion check repeats a rule that code already applies (co-pay, non-payable items) | Live scenario seeds 70047, 70079, 70088 | The amount is deducted twice; payable is too low |
| P2 | Gemini reads "if a costlier room is chosen, the excess is not payable" as a proportionate-deduction clause | Seeds 70058, 70077 | Doctor, surgery and test charges are cut too |
| P3 | The test generator's planted "Spa and massage package" is legitimately excludable as cosmetic | Seed 70097 | A false miss in the scenario report (generator fault) |
| P4 | The bill-against-treatment check is only 39% precise | Live run | It ships off (`BILL_STORY=off`) |
| P5 | OCR missed a policy-number mismatch on a photo | Seed 70080 | One missed finding |
| P6 | Payable and recommendation scored 93.6% live; the target is 95% | Live run | Mostly caused by P1, P2 and P4 |
| P7 | No backend test checks that "RoomLimit not verified" is dropped when the legacy limit is proved | Final review | An unguarded display list |

## Chat (PR #2)

| # | Issue | Effect |
| --- | --- | --- |
| C1 | After a correction shifts a positional finding id, a second correction re-adds the replacement finding and drops its review | Rare; a review can be lost; nothing changes without Apply |
| C2 | The final status write after a successful Apply is outside the error handling | If that write fails, the proposal stays "Applying…" |
| C3 | A severity override is carried through a correction only if it is the latest version | A dismissal after a severity change loses the severity |
| C4 | Figures written in words can pass the "proposal-only, no digits" verified exception | Rare unverified figure shown as verified |
| C5 | Two corrections to the same fact have no stale check; concurrent corrections are last-write-wins on `corrections` | Older correction can overwrite a newer one |
| C6 | A correction can produce a code coverage finding next to Gemini's matching `not_covered` finding | Possible double deduction (not yet confirmed in `settle`) |
| C7 | The daily chat limit can be overshot slightly by parallel requests; failed answers don't use quota | Minor |
| C8 | `findings_count` is not updated after a correction removes findings | The case list shows the old count |

## Not yet verified (needs deploy or a real device)

| # | Item | How |
| --- | --- | --- |
| V1 | Firestore paths: finding versions, chat storage, `claim_proposal`, the chat index | After `terraform apply`, one real ask → apply → new chat, plus a dismiss → restore with history |
| V2 | Box positions on an EXIF-rotated phone photo (`view_region`, `check_region`, area selection) | One real rotated photo |
| V3 | Font edits on printed-then-scanned bills: the font check needs a digital PDF; ELA fails after print-and-scan | Part E print-then-scan test set |

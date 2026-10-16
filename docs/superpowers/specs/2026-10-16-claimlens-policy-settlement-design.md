# ClaimLens policy and bill understanding: design

Date: 2026-10-16 · Status: approved in chat, awaiting written-spec review

Runs before sub-project **D (chat)**. Pixel forensics (C) Phase 2, putting ELA in the pipeline, is postponed, not dropped.

## 1. Goal

Today Gemini pulls only four things from the policy (start date, sum insured, room-rent limit, waiting periods), and nothing checks whether the bill fits the illness. The payable amount is the claimed amount minus a few deductions.

After this work, ClaimLens:

1. **Studies the whole policy** into a **rulebook**: every rule that changes the payout, each with its clause, page and exact sentence, and each proved against the page.
2. **Understands the bill**: every line item gets a category (room, ICU, surgery, medicines, consumables and so on).
3. **Checks the bill against the medical story**: room days against the stay, and charges that don't fit the diagnosis or treatment.
4. **Works out the settlement in code**: an item-by-item sheet in which every deduction names its rule and quotes its clause, ending in the payable amount.
5. **Makes a recommendation in code**: Approve, Approve in part, Not payable, Query or Investigate, with reasons. Gemini only explains it in plain words. A human decides.
6. **Recalculates after review**: dismissing or restoring a finding updates the score, risk, settlement and recommendation. The original analysis stays visible next to the result after review.

**Principle, unchanged:** Gemini reads, and its every statement must quote the page. Code makes every decision with a right answer, including every rupee.

**Success criteria** (measured with the extended scenario suite, §9):
- The payable amount is within ₹1 of the truth on at least 95% of generated claims, with real Gemini and Document AI.
- The recommendation matches the truth on at least 95%.
- Every policy rule in the generated policies is found and proved on at least 95% of policies.
- The bill-against-story check flags at least 80% of planted unrelated charges, and at least 95% of its flags are correct. If it misses that bar, it ships switched off (§10).

## 2. Out of scope

- Network or non-network hospital rules, cashless pre-authorisation, multiple policies on one claim, top-up policies, renewals and cumulative bonus.
- Age-based premium rules. Age is used only for an age-based co-pay.
- Medical coding (ICD or procedure codes).
- Chat (D), and ELA in the pipeline (C Phase 2).

## 3. The rulebook

A new model, `PolicyRulebook`, replaces `PolicyFacts`. Older cases keep reading as before (§11). Every rule carries `clause`, `page` and `quote`. A rule whose quote isn't on its page is **not applied** and is listed under "rules not verified".

| Rule | Fields | Example |
|---|---|---|
| Identity | insurer, policy number, start date, insured persons with ages if printed | as today |
| Sum insured | amount | ₹3,00,000 |
| Co-pay | list of `{percent, applies: all \| age_over \| other, age, condition_text}` | 10% on every claim; 20% if the insured is over 60 |
| Deductible | `{amount, per: claim \| year}` | first ₹25,000 per claim |
| Room rent limit | `{amount \| percent_of_si, per_day, room_type_text}` | 1% of SI per day; "single private room" |
| ICU limit | `{amount \| percent_of_si, per_day}` | 2% of SI per day |
| Proportionate deduction | present or not, quote | "if a higher room is chosen, all associated charges are paid in the same proportion" |
| Sub-limits | list of `{applies_to, amount \| percent_of_si, per: claim \| eye \| year}` | Cataract: ₹40,000 per eye |
| Waiting periods | initial days, pre-existing months, specific list (as today) | 30 days; 48 months; hernia 24 months |
| Exclusions | list of `{what}` | cosmetic, dental unless accidental |
| Non-payable items | list of items, or "standard list" when the policy refers to the regulator's list | gloves, admission kit, attendant |
| Pre- and post-hospitalisation | days before and after | 30 and 60 days |

Percentages are turned into rupees by code from the sum insured, never by Gemini. If the sum insured isn't found, percentage limits can't be applied, and each gets a note.

**Standard non-payable list.** When the policy refers to the regulator's list instead of listing items, code uses a built-in list of common non-payable items (gloves, masks, admission and registration charges, attendant charges, toiletries, food for attendants and similar). It is kept in one data file and cited as "standard list, referred to in clause X".

## 4. Understanding the bill

`extract_facts` adds to each line item:

- `category`: room, icu, surgery (OT, surgeon, anaesthetist), doctor (visits, consultation), nursing, investigations (lab, imaging), medicines, consumables, implants, ambulance, pre_hospitalisation, post_hospitalisation, other.
- `days` and `rate` when the line shows them (room and ICU).

It also extracts the patient's age, if printed, and the room type.

The category is Gemini's reading, so code double-checks the ones money depends on. A line labelled room or ICU must have a rate or a number of days, or it falls back to `other`. Pre- and post-hospitalisation are decided by code from the bill date against the stay, not by Gemini's label.

## 5. Bill against the story

**Code checks (exact):**

| Code | Rule | Severity |
|---|---|---|
| `room_days_exceed_stay` | Room plus ICU days billed are more than the nights between admission and discharge, plus one | high |
| `duplicate_charge` | The same description and amount appear twice on the same day, across or within bills | medium |
| `bill_outside_cover_window` | A bill is dated before the pre-hospitalisation window or after the post-hospitalisation window | medium (the money is handled by the settlement) |

**Gemini check (judgement), new call `judge_bill_story`.**
- Input: the diagnosis, the procedures, the discharge summary pages, and the bill line items with their categories.
- Output per item: `fits | unusual | unrelated`, a reason, a quote of the bill line, and a quote from the story that it is judged against.
- Code keeps only items whose bill quote passes Prove:
  - `unrelated` becomes `charge_unrelated_to_treatment`, medium.
  - `unusual` becomes `charge_unusual_for_treatment`, low.
- The detail always says this is a judgement to check, for example "Chemotherapy charges on an appendicitis claim. Check with the hospital."
- These findings never change the payable amount by themselves. The reviewer decides, and dismissing them is how a reviewer clears them.
- This check is **advisory and fails open**: if the call fails, the case gets a low note ("the bill-against-treatment check couldn't run") and goes on.

## 6. Settlement in code

New module `pipeline/settlement.py`, a pure function of the rulebook, the claim facts, the coverage verdicts and the kept findings:

```
settle(rulebook, facts, coverage, findings) -> Settlement
```

It works line by line, in this order. Each deduction records its amount, its reason and the rule it came from (clause, page, quote):

1. **Waiting period or exclusion of the main treatment**: the whole claim is not payable (as today). Stop.
2. **Item not covered or partly covered** (from `judge_coverage`, proved): that amount is deducted.
3. **Non-payable items**: a consumables or other line matching the policy's list, or the standard list, is deducted in full.
4. **Room and ICU limits**: (rate − limit) × days is deducted.
5. **Proportionate deduction**, only if the policy has the clause and the room rate is above the limit. Associated lines (doctor, nursing, surgery, investigations) are paid in the ratio limit ÷ rate. Medicines, consumables and implants are not reduced. *Assumption to confirm: this follows common Indian practice; the list of reduced categories is one constant.*
6. **Outside the pre- or post-hospitalisation window**: that bill is deducted.
7. **Sub-limit**: if the treatment matches a sub-limit, the admissible total for it is capped.
8. **Deductible**, then **co-pay** on what remains, then the **sum insured** cap.

*Assumption to confirm: order 8 (deductible before co-pay) is the common reading; it is one function, easy to change.*

**Output:** for each line, the claimed amount, the deductions and the payable amount. Then the subtotal, the sub-limit, the deductible, the co-pay, the final payable amount, and **notes** for rules that couldn't be applied, with the reason (for example "co-pay applies to insured over 60; age not found").

The settlement becomes the single source of the case's `payable`. Coverage findings keep their `amount_not_payable` for display, but money is counted once, in the settlement. A bill-against-story finding never moves money.

## 7. Recommendation in code

Taken in this order, first match wins:

| Recommendation | When |
|---|---|
| **Investigate** | Risk band high, or any critical finding (tamper, duplicate invoice) not dismissed |
| **Query** | Risk band is review, or something needed is missing: no claimed amount, no sum insured, an unreadable file, an inpatient claim with no discharge summary, or a rule that couldn't be applied and would change the amount |
| **Not payable** | Final payable is 0 because of an exclusion or waiting period |
| **Approve in part** | Risk is low and payable is less than claimed |
| **Approve** | Risk is low and payable equals claimed (within ₹1) |

Every case lands in exactly one row: anything high-risk is caught by the first row, anything review-risk by the second, so the last three only see low-risk cases.

Each recommendation lists its reasons, each linked to a finding, a deduction or a note. Gemini's summary is given the recommendation, the settlement totals and the findings, and explains them in 3 to 4 sentences. It may not change them.

## 8. Recalculating after review

- `POST /findings/{fid}/review` already saves accept or dismiss. After saving, the API now recomputes the score, risk, settlement and recommendation from the stored inputs and the findings that aren't dismissed. It is a pure, fast function with no Gemini call.
- Inputs saved for this: the rulebook, the facts and the coverage verdicts, stored on the case after the analysis.
- New review action `restore` undoes a dismiss.
- The case keeps `analysis` (the original score, risk, payable and recommendation) and `current` (after review). The case page shows "Analysis: HIGH · 70 → After review: REVIEW · 30" when they differ.
- Each review change saves a version of the finding in a new `finding_versions` subcollection of the case: the finding id, a version number assigned in a transaction, the full finding as it was, who, when, the action and the note. The pipeline's own output is version 1. This is the first part of the finding history that chat (D) will extend.

## 9. Testing

**Unit tests.**
- The settlement: each rule alone, the order of rules, the proportionate deduction, co-pay with and without age, the deductible, sub-limits, the sum insured cap, rounding, and missing inputs giving notes instead of guesses.
- The recommendation table.
- The rulebook grounding: a rule with a wrong quote is not applied.
- The new code checks.
- Recalculation after a dismiss and a restore.
- The fallback for older cases.

**Scenario suite, extended** (`backend/eval/scenarios`):
- **Policy variants:**
  - co-pay 0, 10 or 20%, or 20% for over 60
  - deductible 0 or ₹25,000
  - a cataract sub-limit
  - an ICU limit
  - with and without the proportionate-deduction clause
  - an explicit non-payable list, or a reference to the standard list
  - pre- and post-hospitalisation windows
- **Claim variants:**
  - consumables lines
  - an ICU stay
  - a pharmacy bill before or after the stay
  - extra room days
  - an unrelated charge (for example chemotherapy on a fracture claim)
  - a duplicated line
- `truth.py` computes the expected settlement, payable and recommendation from the recipe, independently of the product code.
- **Report metrics:**
  - payable within ₹1
  - recommendation accuracy
  - per-rule found and proved
  - per-code precision and recall, including the bill-against-story check
- Run with FakeAi in CI. Run live with real Gemini and Document AI before merging, as was done for the 97/100 run.

## 10. Rollout

- A setting `BILL_STORY=on|off` (default on), so the Gemini judgement can be switched off without a deploy if its live precision is below 95%.
- The settlement and recommendation are not behind a flag. They replace the payable calculation once the live scenario run meets §1.

## 11. Older cases and storage

- **Cases analysed before this change** have no rulebook. They keep their stored payable and show no settlement sheet or recommendation. Recalculation after review only updates the score and risk for them.
- **New case fields:**
  - `rulebook`
  - `settlement`
  - `recommendation`
  - `analysis` and `current` snapshots
  - `review_inputs` (facts and coverage verdicts for recalculation)
- These sit on the case document or in a `results` subdocument if size requires. Firestore's limit is 1 MB per document, and a rulebook plus settlement for 80 pages is well under that.

## 12. Gemini calls after this change

| Call | Change |
|---|---|
| classify_documents | unchanged |
| extract_facts | adds line-item category, days and rate, patient age, room type |
| extract_policy | returns the full rulebook (§3) |
| judge_coverage | also gets item categories; unchanged otherwise |
| judge_bill_story | **new**, advisory, fails open |
| summarise | also gets the recommendation and settlement totals |

That is one more call per case. The policy call's answer is larger, but the input is the same text.

## 13. User interface

The case page gets two new panels and a changed header:

- **Header:** the recommendation badge (Approve, Approve in part, Not payable, Query, Investigate) next to the risk stamp, with its reasons. It shows "Analysis → After review" when the two differ.
- **Settlement panel:** a table of bill lines, each with its category, claimed amount, deductions and payable amount. Each deduction has a clause chip that opens the policy page with the sentence boxed. The totals rows show the sub-limit, deductible, co-pay and final payable. Notes list rules that couldn't be applied.
- **Policy rulebook panel:** each rule found, with a clause chip, plus "rules not verified".
- **Findings:** the new codes appear like the others. A dismissed finding gets a Restore button.

## 14. Failure paths

| Situation | What happens |
|---|---|
| The policy has no readable text | The rulebook is empty. The settlement uses only the coverage verdicts. The recommendation is Query ("the policy couldn't be read"). |
| A rule's quote isn't on its page | Not applied; listed under "rules not verified" |
| Percentage limit but no sum insured | Not applied; note; recommendation Query |
| Gemini labels a room line without days or rate | Treated as `other`; no room deduction from it |
| `extract_policy` or `extract_facts` fails | Case FAILED at CHECKING, as today |
| `judge_bill_story` fails | Low note; the case goes on (fails open) |
| Settlement code raises | Case FAILED with the step "settlement" (a bug, caught by tests) |
| Recalculation after review raises | The review is still saved; the API logs the error and returns the finding with the previous numbers |

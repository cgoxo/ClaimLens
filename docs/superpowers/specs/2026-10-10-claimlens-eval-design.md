# ClaimLens evaluation suite: design

Date: 2026-10-10 · Status: approved in chat, awaiting written-spec review

Goal: measure, with ground truth, how well ClaimLens catches forged and inconsistent claims. The suite runs locally (in-process) and against the live deployment (API), and produces a report a person can read.

## 1. Success criteria

1. `python -m eval.run --suite synthetic --n 200 --target local` finishes and writes `report.md` + `results.jsonl` with per-check precision and recall, risk-band accuracy, payable accuracy and the worst cases.
2. The same command with `--target live --base-url <run url>` runs through the deployed API as the test user, without hitting the daily limit.
3. `--suite policies` scores coverage extraction against ≥ 5 real insurer policy wordings, downloaded from the insurers' official sites, with hand-checked ground truth.
4. `--suite findit` scores case-level tamper detection, and marker/region overlap, on all 163 forged receipts plus 163 authentic ones from Find-It-Again (OCR on).
5. Offline unit tests cover the generator (each forgery produces its expected codes when run through the pipeline with a fake AI that returns the generator's ground-truth facts), the metrics maths and the report.
6. Browser spot-check: the 3 worst live cases from a run are opened in Chrome and their findings are compared with the report.

Out of scope: image forensics (ELA, copy-move). The Find-It-Again result is expected to show that gap. Fixing it is a separate feature.

## 2. Layout

```
backend/eval/
  __init__.py
  recipe.py        # random claim recipe (dataclass) + seeded RNG
  forge.py         # recipe -> claim.pdf, policy.pdf (+ scanned variants), applies forgeries, returns Truth
  forgeries.py     # one function per forgery: mutates recipe or the rendered PDF; declares expected codes
  truth.py         # Truth model: expected codes (multiset), risk band, payable, facts (for FakeAi)
  targets.py       # LocalTarget (in-process run_pipeline) and LiveTarget (HTTP API) -> CaseResult
  metrics.py       # per-code TP/FP/FN, precision, recall; band and payable accuracy
  report.py        # results.jsonl -> report.md
  policies.yaml    # insurer, product, UIN, official URL, sha256, ground truth (filled after reading)
  fetch_policies.py
  findit.py        # download/unzip, sample, map receipts -> cases, region overlap
  run.py           # CLI
backend/tests/eval/  # offline tests for the above
```

Data goes to `backend/data/eval/` (gitignored): generated PDFs, downloaded policies, Find-It-Again files and run outputs (`runs/<timestamp>-<suite>-<target>/`).

## 3. Synthetic suite

**Recipe** (seeded): patient name, age, hospital, policy number and start date; admission and discharge dates (2–6 days); a procedure from a list with a condition (cataract, hernia, appendicitis, knee replacement, fracture, dengue, and so on); a hospital bill with 3–6 line items including room charges (`days × rate`); 0–2 pharmacy bills; and a claim date. Policy terms: sum insured, room-rent limit (1% of the sum insured, or none), and waiting periods (24 months for a fixed list of conditions).

Invoice numbers carry the run id (`INV-<run>-<n>`), so runs never collide with each other or with real users.

**Forgeries.** Each case applies 0–3, chosen at random. 25% of cases are clean controls.

| Forgery | How | Expected codes |
| --- | --- | --- |
| `retype_total` | White box over the bill total and a new total in Times-Roman | `font_outlier`, `hidden_text`, `sum_mismatch`, plus `editing_tool` (the save sets producer `iLovePDF`) |
| `retype_line` | Same, on one line item; the total is left alone | `font_outlier`, `hidden_text`, `sum_mismatch`, `editing_tool` |
| `editor_resave` | Re-save with producer from the editing-tool list | `editing_tool` |
| `late_edit` | modDate − creationDate = 5 days, neutral producer | `late_edit` |
| `incremental_save` | Append an incremental save | `multiple_saves` |
| `pharmacy_after_discharge` | Inpatient pharmacy bill dated 1–3 days after discharge | `inpatient_outside_stay` |
| `admit_after_discharge` | Swap admission and discharge dates | `date_order` |
| `name_typo` | One-letter change in one document's name | `name_mismatch` (low) |
| `different_name` | Another person's name on one document | `name_mismatch` (high) |
| `claimed_mismatch` | Claim-form amount = bills + 10–30% | `claimed_amount_mismatch` |
| `reused_invoice` | Bill invoice number pre-registered to another case | `duplicate_invoice` |
| `waiting_period` | Policy start under 24 months before treatment, condition on the list | `waiting_period` |
| `room_over_limit` | Room rate above the limit | `room_rent_limit` |

Forgeries that conflict (for example, `retype_total` and `claimed_mismatch`) are not combined. The generator computes the final expected codes from the recipe, not from the forgery list, so overlaps stay correct.

**Scanned variants** (10% of cases, local target only, `OCR=docai`):
- `scanned`: every page rasterised to an image-only PDF. Expected codes: the story, duplicate and coverage codes. PDF-structure codes are not expected.
- `scanned_with_text`: rasterised, plus an invisible text layer in which one amount is changed. Expected: `ocr_layer_mismatch`.

**Ground truth (`Truth`):** the expected code multiset, the expected risk band (computed with the product's weights from the expected severities), the expected payable, and the true facts (ClaimFacts/PolicyFacts with exact quotes) so offline tests can run with a FakeAi.

**Scoring per case:** expected vs found code multisets give TP / FP / FN per code. A case passes when there are no missed findings and no extra non-low findings.

## 4. Real policies suite

- `policies.yaml` lists at least 5 official wordings: insurer, product, UIN, URL on the insurer's own domain, and sha256. `fetch_policies.py` downloads them and checks the hash.
- **Ground truth** per policy, written after reading the PDF and stored in `policies.yaml`:
  - initial waiting days;
  - specific-disease waiting months, and whether cataract is on the list;
  - pre-existing disease months;
  - room-rent limit (per-day amount, % of sum insured, or none), with page numbers.
- **Cases:** for each policy, 4 generated claims:
  - cataract surgery inside the waiting period;
  - cataract surgery after the waiting period;
  - room rate above the limit, where the policy has one;
  - a clean case.
- **Scored:** policy facts extracted (months, limit), coverage findings present or absent as expected, and payable.

## 5. Find-It-Again suite

- Download `findit2.zip` from the dataset page into `data/eval/findit/` and unzip it. It is not redistributed, and the report cites the ICDAR 2023 paper.
- **Sample:** all forged receipts across train, val and test (163) plus 163 authentic, using a seeded random choice.
- **Each receipt** is uploaded as the claim (PNG) with a fixed one-page stub policy. It needs `OCR=docai`.
- **Scored:**
  - case level: forged means at least one tamper finding (`font_outlier`, `hidden_text`, `ocr_layer_mismatch`, `editing_tool`, `late_edit`, `multiple_saves`); authentic means none. Precision, recall and F1.
  - localisation: for forged receipts, the share whose markers overlap an annotated modified region with IoU ≥ 0.1.

## 6. Targets

- **`LocalTarget`:** builds `Deps` with `STORAGE=local`, `DB=local` (`data/eval/runs/<id>/db`), the real Vertex Gemini and `DocAiOcr` when the suite needs OCR, then calls `run_pipeline` directly. Concurrency is set by `--workers` (default 4).
- **`LiveTarget`:** signs in the test user through Identity Toolkit `signInWithPassword` (API key from `frontend/.env.production`, password from `backend/data/.tester_password`), then uses `POST /api/cases` and polls `GET /api/cases/{id}`. The token is refreshed after 50 minutes. Concurrency defaults to 3. Seeding duplicates live is not possible from the client, so `reused_invoice` is achieved by submitting the "earlier" case first in the same run.
- **Backend change:** a new setting `NO_LIMIT_EMAILS` (comma or semicolon separated, empty by default). The daily-limit check is skipped for those emails. The Makefile and CI set it to `claimlens-tester@example.com`.

## 7. Metrics and report

`results.jsonl` holds one line per case: id, suite, target, variant, expected codes, found codes (with severities), risk expected/found, payable expected/found, status, error, seconds.

`report.md` contains:
- a header (suite, target, n, date, git sha);
- a per-code table (TP, FP, FN, precision, recall);
- case pass rate;
- risk-band confusion (3×3);
- payable accuracy (exact match within ₹1);
- failures by type (pipeline FAILED, timeouts);
- the 10 worst cases (expected vs found, with case id and live URL);
- time and an approximate Gemini/Document AI call count.

## 8. Testing (offline)

- **Generator:** for each forgery alone, the generated claim run through `run_pipeline` with `FakeAi(truth.facts)` yields exactly the expected codes. Clean recipes yield no codes. Same seed means byte-identical PDFs.
- **Metrics:** hand-made expected/found pairs give known TP/FP/FN, and precision/recall when the denominator is 0.
- **Report:** a small results fixture renders the expected tables.
- **Find-It-Again mapping:** the annotation parser on a fixture record gives the boxes, and the IoU maths is checked.
- **LiveTarget:** an HTTP mock covers sign-in, upload, polling to READY, and a 429 that is retried after 5 s.

## 9. Browser use (Claude in Chrome)

- **Policies:** navigate to each insurer's official policy-wording page, find the product's PDF link, and record the URL in `policies.yaml`. Each download is named to the user before it happens.
- **Spot-check:** after a live run, take the 3 worst cases' PDFs (saved in the run folder) and upload them through the live UI, signed in as the user with Google. Compare what the reviewer sees (stamp, findings, markers) with the report. This also exercises the real upload path. Eval cases owned by the test user are not opened in the browser.

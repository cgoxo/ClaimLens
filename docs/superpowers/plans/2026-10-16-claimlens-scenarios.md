# ClaimLens scenario suite implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove how ClaimLens behaves beyond the 100%-risk sample:
- clean claims;
- coverage-only claims;
- each single problem;
- combinations of problems;
- rejections;
- photo formats.

Results are checked exactly offline, and measured with real Gemini and Document AI.

**Architecture:** this is the **synthetic suite** of `docs/superpowers/specs/2026-10-10-claimlens-eval-design.md` §3, brought up to date with B:
- uploads use the two forms (claim, policy) and several files;
- the document check, REJECTED and `unreadable_file` are covered;
- `duplicate_page_image`, `incomplete_bill` and `policy_number_mismatch` are covered.

`backend/eval/scenarios/` generates recipes into PDF and photo files plus a `Truth`, runs them through a target and scores them. The policies suite, Find-It-Again and the live API target stay in sub-project E.

**Tech Stack:** Python 3.12, reportlab, PyMuPDF, Pillow, pytest; real Vertex Gemini plus `DocAiOcr` for the live run.

**Spec:** `docs/superpowers/specs/2026-10-10-claimlens-eval-design.md` (§3, §7, §8), with the changes listed under Architecture.

## Global Constraints

- **Files:** generated files go to `backend/data/eval/scenarios/<run>/` (gitignored); reports go to `docs/eval/scenarios-<target>-<date>.md` (committed).
- **Invoice numbers** carry the run id (`INV-<run>-<n>`), so runs never collide.
- **Expected results** are computed from the **final recipe**, never from the list of forgeries applied:
  - codes, as a multiset;
  - risk band from the product's weights (critical 40, high 20, medium 10, low 5, coverage 0; low < 30, review < 60, high ≥ 60);
  - payable;
  - status (READY or REJECTED).
- **Mix:** 25% of cases are clean controls. Each case applies 0–3 forgeries, and conflicting ones are never combined:
  - `retype_total` with `claimed_mismatch`;
  - `admit_after_discharge` with `pharmacy_after_discharge`;
  - any rejection with anything else.
- **Offline target:** `FakeAi(truth.facts)` with exact quotes. **Every case must pass exactly** (no missing codes, no extra non-low codes).
- **Live target:** `LocalTarget` with real Vertex Gemini and `DocAiOcr` (prod processor, ADC), local storage and DB in `data/eval/scenarios/<run>/db`, 4 workers. **No prod writes, so no daily limit.**
- **Test baselines:** backend `.venv/bin/pytest -q` stays green.
- **Commits** end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Forgeries that change what's expected.** `retype_total` also changes the claimed amount; `waiting_period` also makes the payable ₹0. Expectations must come from the final recipe. Pinned in Task 1.
2. **`reused_invoice` across runs.** The earlier invoice is registered inside the run's own DB only. Pinned in Task 2.
3. **Photo variants offline.** With OCR off, photo pages are unreadable, so their expected result is "unreadable_file, and the facts on those pages are missing". The offline run expects that; the live run (OCR on) expects the full codes. Pinned in Task 1.
4. **The document check offline.** `FakeAi.classify_documents` must return the truth labels per file, including the non-insurance file. Pinned in Task 2.
5. **Coverage findings count for nothing in the band, but do change the payable.** Pinned in Task 1.

---

### Task 1: Recipe, forgeries, truth

**Files:**
- Create: `backend/eval/scenarios/{__init__,recipe,render,forgeries,truth}.py`
- Test: `backend/tests/eval/test_scenarios_truth.py`

**Interfaces:**
- **`Recipe`** (dataclass, from a seeded RNG): patient, age, hospital, policy number, start date, admission, discharge, procedure (from a list of conditions), hospital bill items (including `room = days × rate`), 0–2 pharmacy bills, claimed amount, claim date, sum insured, room limit (1% of sum insured or none), waiting periods (24 months for a fixed list).
- **`make_recipe(seed: int, run: str) -> Recipe`**
- **`FORGERIES: dict[str, Forgery]`.** Each forgery has `apply(recipe) -> Recipe`, `post(files) -> files` (PDF and image edits), `codes: list[str]` and `conflicts: set[str]`. The forgeries:
  - `retype_total`, `retype_line`, `editor_resave`, `late_edit`, `incremental_save`
  - `pharmacy_after_discharge`, `admit_after_discharge`
  - `name_typo`, `different_name`, `claimed_mismatch`, `reused_invoice`, `wrong_policy_number`
  - `waiting_period`, `room_over_limit`
  - `duplicate_page`, `missing_page`
  - `cv_in_claim`, `bill_in_policy`, `policy_in_claim`
- **`Format`:** `one_pdf`, `split_files` or `photos`. With `photos`, each claim page is a JPEG (via `eval.forensics.photo.to_photo`).
- **`render(recipe, forgeries, fmt) -> list[(card_id, name, bytes)]`**
- **`Truth`** (dataclass): `codes: Counter`, `status`, `band`, `payable`, `facts: ClaimFacts`, `policy: PolicyFacts`, `documents: list[DocLabel]`. Quotes are exact.
- **`truth_of(recipe, forgeries, fmt, ocr: bool) -> Truth`**

- [ ] **Step 1: Write failing tests:**
  - **Clean:** a clean recipe's truth has no codes, band `low`, payable = claimed.
  - **Waiting period:** gives `{"waiting_period"}`, band `low`, payable `0`.
  - **Retyped total:** `retype_total` gives `{"font_outlier", "hidden_text", "sum_mismatch", "editing_tool"}`, with the band computed from 40+40+20+20 = 120, so `high`.
  - **Name typo:** `name_typo` gives `name_mismatch` with severity low; `different_name` gives it with severity high.
  - **Rejections:** `cv_in_claim` gives status `REJECTED` and no codes.
  - **Photos with OCR off:** `photos` with `ocr=False` gives `unreadable_file` × the number of claim pages, and no codes that depend on those pages.
  - **Conflicts:** conflicting pairs are never chosen together by `pick(rng)`.
- [ ] **Step 2:** `.venv/bin/pytest tests/eval/test_scenarios_truth.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement. Severities come from the product. `truth_of` reuses `claimlens.pipeline.report.WEIGHTS` and `risk_band`, so the expectations can't drift from the product.
- [ ] **Step 4:** `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(eval): scenario recipes, forgeries and truth`.

### Task 2: Offline target: every scenario exactly

**Files:**
- Create: `backend/eval/scenarios/targets.py`, `backend/eval/scenarios/fake_ai.py`
- Test: `backend/tests/eval/test_scenarios_offline.py`

**Interfaces:**
- **`TruthAi(truth)`:** an `Ai` that returns `truth.facts`, `truth.policy`, `truth.documents`, coverage items derived from the recipe, and a fixed summary.
- **`LocalTarget(settings_overrides, ai_factory)`:** `.run(files, truth) -> CaseResult(status, codes: Counter, band, payable, error, seconds, case_id)`.
  - It uploads through the real API in-process (`TestClient` with `JOBS=inline`), so the upload, the document check and Prove are all exercised.
  - `reused_invoice` registers the earlier invoice in this target's DB first.

- [ ] **Step 1: Write the failing test.** `test_every_single_scenario_offline` is parametrised over every forgery alone × `one_pdf` and `split_files`, plus the clean case. The result must match the truth **exactly**: codes, status, band, and payable within ₹1.
- [ ] **Step 2:** Run. Expected: FAIL, then iterate. **When a mismatch is a product bug, fix it test-first in the product, and ledger it.**
- [ ] **Step 3:** Add `test_combinations_offline`: 30 seeded cases with 2–3 forgeries, all exact.
- [ ] **Step 4:** Add `test_photos_offline`: `photos` with OCR off gives `unreadable_file` notes and status READY, and never crashes.
- [ ] **Step 5:** `.venv/bin/pytest -q`. Expected: green. **Commit** `test(eval): every scenario through the real pipeline offline`.

### Task 3: Live run and report

**Files:**
- Create: `backend/eval/scenarios/run.py`, `backend/eval/scenarios/report.py`
- Test: `backend/tests/eval/test_scenarios_report.py`
- Output: `docs/eval/scenarios-live-2026-10-16.md`

**Interfaces:**
- **`python -m eval.scenarios.run --n 100 --target live --formats one_pdf,split_files,photos --seed 7`:** `LocalTarget` with the real Vertex Gemini and `OCR=docai`, writing `results.jsonl` (§7 of the eval spec plus `status_expected`/`status_found`).
- **`report.py`:**
  - per code: TP, FP, FN, precision, recall;
  - case pass rate;
  - band confusion (3×3);
  - payable accuracy;
  - REJECTED accuracy;
  - accuracy per format;
  - the 10 worst cases with their local case ids;
  - time;
  - the approximate number of Gemini and Document AI calls.

- [ ] **Step 1: Write failing tests:**
  - **Precision and recall:** hand-made results give known TP/FP/FN, including a denominator of 0 (reported as "n/a").
  - **Band matrix:** the confusion matrix sums to n.
  - **Worst cases:** sorted by (status wrong, number of missing codes, number of extra codes).
- [ ] **Step 2:** Run. Expected: FAIL. **Step 3:** Implement. **Step 4:** green.
- [ ] **Step 5:** Run live with `--n 100` (≈ $1–2 of Gemini and Document AI), then generate the report.
- [ ] **Step 6: Commit** the report as `docs: scenario suite live report`. Share it with the user together with the forensics report.

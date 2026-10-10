# ClaimLens Evaluation Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A repeatable evaluation suite (synthetic forgeries, real insurer policies, Find-It-Again) that runs locally or against the live app and writes a per-check precision/recall report.

**Architecture:** `backend/eval/` package. A seeded recipe is rendered to claim and policy PDFs, forgeries mutate the recipe or the PDF, and `Truth` records the expected codes. Targets run cases in-process (`LocalTarget`) or over HTTP (`LiveTarget`). Metrics and the report are computed from `results.jsonl`.

**Tech Stack:** Python 3.12, reportlab + PyMuPDF (generation), httpx (live), PyYAML, existing `claimlens` pipeline; Claude in Chrome for policy discovery and spot-checks.

**Spec:** `docs/superpowers/specs/2026-10-10-claimlens-eval-design.md`

## Global Constraints

- Eval code lives in `backend/eval/`, tests in `backend/tests/eval/`. All data goes under `backend/data/eval/` (gitignored). Nothing downloaded is committed.
- Invoice numbers are `INV-<run>-<n>`, where `<run>` is the run id.
- Clean controls make up 25% of synthetic cases; scanned variants 10% (local target only).
- Tamper codes for Find-It-Again: `font_outlier, hidden_text, ocr_layer_mismatch, editing_tool, late_edit, multiple_saves`. Localisation IoU threshold is 0.1.
- Live concurrency defaults to 3, local to 4. Re-sign in after 50 minutes. Retry a 429 after 5 s.
- `NO_LIMIT_EMAILS` defaults to empty; the Makefile and CI set it to `claimlens-tester@example.com`.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. A case where the pipeline FAILs or the live API times out must be recorded as `status=error` and counted in the report. It must not crash the run. Test in Task 6.
2. Overlapping forgeries (for example `retype_total` with `reused_invoice` and `name_typo`) must give the exact union of expected codes. Test in Task 3.
3. An interrupted run must resume with `--resume <run dir>`, skipping case ids already in `results.jsonl`. Test in Task 7.
4. Find-It-Again annotations with no regions, or with only "original area" regions, must give zero ground-truth boxes, not a crash. Test in Task 9.
5. Precision and recall with a zero denominator must show as `n/a`, not a division error or `0`. Test in Task 5.

---

### Task 1: `NO_LIMIT_EMAILS` setting

**Files:** Modify `backend/claimlens/settings.py`, `backend/claimlens/api.py`, `backend/Makefile`, `.github/workflows/ci-deploy.yml`, `backend/README.md`. Test: `backend/tests/test_api.py`.

**Interfaces:**
- Produces: `Settings.no_limit_emails: list[str]`, split on `,` or `;` and lower-cased (`Annotated[list[str], NoDecode]` with a before-validator). `create_case` skips the daily-limit check when the user's email is in that list.

- [ ] **Step 1:** Write the failing test `test_no_limit_email_skips_daily_limit`: with `daily_case_limit=1` and `no_limit_emails=["a@x.com"]`, two uploads as `a@x.com` both return 201, and a second upload as `b@x.com` returns 429.
- [ ] **Step 2:** Run `cd backend && .venv/bin/pytest tests/test_api.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement it. Add `##NO_LIMIT_EMAILS=claimlens-tester@example.com` to the deploy env-vars line in both the Makefile and the workflow. Add a README line.
- [ ] **Step 4:** Run `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5:** Commit `feat: NO_LIMIT_EMAILS for the eval account`.

### Task 2: Recipe, truth, clean rendering

**Files:** Create `backend/eval/{__init__,recipe,truth,forge}.py`, `backend/tests/eval/{__init__,test_forge}.py`. Modify `backend/.gitignore` if needed (`data/` is already ignored).

**Interfaces:**
- Produces:
  - `@dataclass Recipe` with: patient, age, hospital, policy_no, policy_start: date, admit: date, discharge: date, claim_date: date, condition: str, procedure: str, procedure_date: date, room_rate: int, room_days: int, line_items: list[tuple[str,int]], pharmacy: list[dict(no, date, amount, inpatient)], invoice_no, sum_insured, room_limit: int|None, waiting: dict[str,int], names_by_page: dict[int,str], claimed: int, producer: str, created/modified: datetime.
  - `make_recipe(rng: random.Random, run_id: str, n: int) -> Recipe`. Conditions come from: cataract, hernia, appendicitis, knee replacement, fracture, dengue. `waiting = {cataract:24, hernia:24, knee replacement:24}`.
  - `class Truth(BaseModel)`: `case_id, codes: list[str], severities: dict[str,str], risk: str, payable: float | None, variant: str ("digital"|"scanned"|"scanned_with_text"), forgeries: list[str], prior_invoice: str | None, facts: ClaimFacts, policy: PolicyFacts`.
  - `expected_truth(r: Recipe, applied: list[str], variant: str) -> Truth`. It computes codes from the recipe state, mirroring the product rules (sum mismatch, date order, inpatient outside the stay, name ratio 85–99 → low, claimed vs bills, waiting months, room limit), plus the PDF-level codes for the applied PDF forgeries. Risk and payable use the product weights (`claimlens.pipeline.report.WEIGHTS`, `risk_band`).
  - `render(r: Recipe, out_dir: Path) -> tuple[Path, Path]` writes `claim.pdf` (claim form, discharge summary, hospital bill, pharmacy bills) and `policy.pdf` (schedule with room-rent clause; waiting-period page) with reportlab, in the same layout style as `samples/make_example.py`. It sets producer and creation/mod dates from the recipe.

- [ ] **Step 1:** Write the failing tests:
  - `test_same_seed_same_bytes` (two renders with seed 7 give identical sha256, with a fixed reportlab `invariant=1`);
  - `test_clean_recipe_has_no_codes` (`expected_truth(r, [], "digital").codes == []`, `risk == "low"`);
  - `test_clean_case_through_pipeline_finds_nothing`: run `run_pipeline` on the rendered PDFs with `TruthAi(truth)` (Task 3 helper, defined here in `truth.py`) and get READY with zero findings.
- [ ] **Step 2:** Run `.venv/bin/pytest tests/eval -q`. Expected: FAIL.
- [ ] **Step 3:** Implement. `TruthAi(truth)` returns `truth.facts`, `truth.policy`, coverage `[]` and summary `"eval"`. The facts' quotes must be the exact strings the renderer prints, so build facts and text from the same values.
- [ ] **Step 4:** Run the same command. Expected: PASS.
- [ ] **Step 5:** Commit `feat(eval): recipe, truth and clean claim rendering`.

### Task 3: Forgeries

**Files:** Create `backend/eval/forgeries.py`, `backend/tests/eval/test_forgeries.py`.

**Interfaces:**
- Produces:
  - `FORGERIES: dict[str, Forgery]`, where `Forgery` has `kind: "recipe"|"pdf"`, `apply(...)` and `conflicts: set[str]`. The 13 names are exactly as in the spec §3 table.
    - Recipe forgeries take `(r: Recipe, rng) -> None`.
    - PDF forgeries take `(claim_pdf: Path, r: Recipe, rng) -> None` and mutate in place. `retype_total` and `retype_line` use the white-box + Times-Roman + producer `iLovePDF` method from `make_example.tamper`. `incremental_save` uses `doc.save(..., incremental=True)`.
  - `build_case(seed: int, run_id: str, n: int, out_dir: Path) -> Truth`:
    1. Draw 0–3 compatible forgeries (25% clean).
    2. Apply the recipe ones, render, apply the PDF ones.
    3. Return `expected_truth`.
  - `reused_invoice` is expressed as `Truth.prior_invoice: str | None`; the target registers it before running.

- [ ] **Step 1:** Write the failing tests:
  - Parametrised `test_single_forgery_yields_expected_codes[name]` for all 13: build with only that forgery, run the pipeline with `TruthAi`, and the found code multiset equals `truth.codes`.
  - `test_overlapping_forgeries_union`: `retype_total + reused_invoice + name_typo` gives codes = font_outlier, hidden_text, sum_mismatch, editing_tool, duplicate_invoice, name_mismatch.
  - `test_conflicts_never_combined`: over 500 seeds, no case has both `retype_total` and `claimed_mismatch`.
- [ ] **Step 2:** Run `.venv/bin/pytest tests/eval/test_forgeries.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement. Where the product's real behaviour differs from the spec's expected codes, fix `expected_truth` only if the product is right, and record it as a ruling. A real product bug gets its own failing test in `backend/tests/` and a fix.
- [ ] **Step 4:** Run `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5:** Commit `feat(eval): 13 forgeries with expected codes`.

### Task 4: Scanned variants

**Files:** Modify `backend/eval/forge.py`. Create `backend/tests/eval/test_scanned.py`.

**Interfaces:**
- Produces: `rasterise(pdf: Path, out: Path, with_text_layer: bool, change_amount: str | None) -> None`. Each page is rendered at 150 dpi and inserted as a full-page image. With a text layer, the original text is written invisibly (`render_mode=3`) and one amount is changed. `build_case(..., variant=...)` uses it.
- Test helper `SpanOcr(original_pdf)`: an `Ocr` returning the original digital spans for that page (stands in for Document AI offline).

- [ ] **Step 1:** Write the failing tests:
  - `test_scanned_variant_is_image_only` (read gives kind `scanned` with `NoOcr`, `unreadable`);
  - `test_scanned_with_text_flags_ocr_layer_mismatch` (with `SpanOcr`, the codes include `ocr_layer_mismatch`).
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `.venv/bin/pytest -q`. Expected: PASS.
- [ ] **Step 5:** Commit `feat(eval): scanned variants`.

### Task 5: Metrics and report

**Files:** Create `backend/eval/{metrics,report}.py`, `backend/tests/eval/test_metrics_report.py`.

**Interfaces:**
- Produces:
  - `@dataclass CaseResult`: `id, suite, target, variant, status ("ok"|"error"), error, expected: list[str], found: list[tuple[code, severity]], risk_expected, risk_found, payable_expected, payable_found, seconds, url: str | None`.
  - `score(results) -> Scores`, with `per_code[code] = {tp, fp, fn, precision, recall}` (`None` when the denominator is 0), `case_pass_rate`, `risk_confusion`, `payable_accuracy` and `errors`.
  - `render_report(scores, results, meta) -> str` (markdown per spec §7; `None` renders as `n/a`).

- [ ] **Step 1:** Write the failing tests:
  - a known pair with expected `[a, a, b]` and found `[a, c]` gives a: tp1 fn1; b: fn1; c: fp1;
  - zero-denominator values render as `n/a`;
  - an error case is counted in `errors` and excluded from code scoring;
  - the report contains the per-code table header and a "Worst cases" section.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit `feat(eval): metrics and markdown report`.

### Task 6: Targets

**Files:** Create `backend/eval/targets.py`, `backend/tests/eval/test_targets.py`.

**Interfaces:**
- Produces:
  - `class LocalTarget(ai: Ai | None, ocr: Ocr, data_dir)`. `.run(case_id, claim: Path, policy: Path, prior_invoice: str | None) -> CaseResult` registers the prior invoice, creates the case, runs `run_pipeline` synchronously and maps the result. `ai=None` means Vertex.
  - `class LiveTarget(base_url, api_key, email, password)`. Same `.run`; `prior_invoice` is handled by the runner submitting the "earlier" case first.
    - Signs in via `signInWithPassword` and re-signs in after 50 minutes.
    - Polls every 3 s up to 300 s.
    - On 429: waits 5 s and retries up to 3 times.
    - Any exception becomes `status="error"`.

- [ ] **Step 1:** Write the failing tests:
  - `LocalTarget` with `TruthAi` on a built case gives `status ok` and the expected codes;
  - a `LocalTarget` whose AI raises gives `status error` with the message (the pipeline FAILED);
  - `LiveTarget` with `httpx.MockTransport`: sign-in, upload, polling (CHECKING then READY) and the mapped result;
  - a 429 followed by 201 is retried;
  - a poll timeout gives `status error`, `"timeout"`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement (`LiveTarget` takes an optional `transport` for tests).
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit `feat(eval): local and live targets`.

### Task 7: Runner CLI and the first synthetic run

**Files:** Create `backend/eval/run.py`, `backend/tests/eval/test_run.py`. Modify `backend/Makefile` (targets `eval-synthetic`, `eval-live`).

**Interfaces:**
- Produces: `python -m eval.run --suite synthetic|policies|findit --target local|live [--n 200] [--seed 1] [--workers N] [--resume DIR] [--base-url URL]`.
  - Creates `data/eval/runs/<ts>-<suite>-<target>/`, builds the cases, runs them in a thread pool, and appends each result to `results.jsonl` as it finishes.
  - Writes `report.md` and prints its path.

- [ ] **Step 1:** Write the failing tests:
  - `test_run_synthetic_local_fake` (`--n 6 --ai fake-truth`; there is a hidden `--ai` flag for tests that uses `TruthAi`): the report exists and 6 lines are written;
  - `test_resume_skips_done`: pre-write 3 result lines and resume; only 3 new cases run.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `.venv/bin/pytest -q`. Expected: PASS.
- [ ] **Step 5:** **Real run:** `.venv/bin/python -m eval.run --suite synthetic --n 200 --target local` (Vertex; scanned variants use `DocAiOcr`). Expected: a report is written. Read it. Every missed or extra code gets classified as a product bug (failing test plus fix), a generator or truth bug (fix it), or a known limitation (ledger). Re-run until it is explained.
- [ ] **Step 6:** Commit `feat(eval): runner; first synthetic report` (the report is copied to `docs/eval/<date>-synthetic-local.md`).

### Task 8: Real insurer policies

**Files:** Create `backend/eval/policies.yaml`, `backend/eval/fetch_policies.py`. Modify `backend/eval/run.py` (policies suite). Test: `backend/tests/eval/test_policies.py`.

**Interfaces:**
- Produces:
  - `policies.yaml` entries `{id, insurer, product, uin, url, sha256, truth: {initial_days, specific_months, cataract_listed, ped_months, room_limit: {type: "amount"|"percent"|"none", value, page}}}`.
  - `load_policies() -> list[PolicySpec]`.
  - `fetch(spec) -> Path` (verifies sha256; downloads to `data/eval/policies/<id>.pdf`).
  - `policy_cases(spec, path, rng) -> list[(Truth, claim_pdf, policy_pdf)]`: the 4 cases from spec §4, with claims generated against that policy's real terms.

- [ ] **Step 1:** **Browser:** use Claude in Chrome on each insurer's official site (Star Health, HDFC ERGO, ICICI Lombard, Niva Bupa, Care Health) to find one retail health product's policy-wording PDF. Record the URL, product and UIN, and tell the user each filename and source before downloading.
- [ ] **Step 2:** Run `fetch_policies.py`, then read each PDF's text and fill in the `truth` block (with page numbers). Record the sha256.
- [ ] **Step 3:** Write the failing tests:
  - `test_yaml_schema` (all 5 entries are complete);
  - `test_policy_cases_expectations` (cataract-inside gives `waiting_period` iff `cataract_listed`; cataract-after gives none; room-over gives `room_rent_limit` iff the limit is not `none`).
- [ ] **Step 4:** Implement the suite in `run.py`. Run `--suite policies --target local`. Expected: a report. Review the wrong extractions: product issues go to the ledger or get fixed; ground-truth errors are re-checked in the PDF.
- [ ] **Step 5:** Commit `feat(eval): real policy suite and report`.

### Task 9: Find-It-Again

**Files:** Create `backend/eval/findit.py`, `backend/tests/eval/test_findit.py`, `backend/tests/eval/fixtures/findit_annotation.json`. Modify `backend/eval/run.py`.

**Interfaces:**
- Produces:
  - `download() -> Path` (`findit2.zip` into `data/eval/findit/`, unzipped once).
  - `load_labels(root) -> list[Receipt(id, path, forged: bool, boxes: list[(x,y,w,h)])]`. Boxes come only from regions whose "Original area" is not "yes".
  - `sample(receipts, rng) -> list[Receipt]` (all forged plus the same number authentic).
  - `iou(a, b) -> float`.
  - `findit_result(receipt, case_result, page_size) -> CaseResult` (expected = `["tamper"]` if forged else `[]`; found collapses tamper codes to `"tamper"`; adds `localised: bool`).

- [ ] **Step 1:** Write the failing tests:
  - the annotation fixture parses into 2 boxes and skips the "original area" one;
  - a record with no regions gives `[]`;
  - `iou` on identical boxes is 1, disjoint is 0, half overlap ≈ 0.333;
  - `sample` is balanced and deterministic.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement. Tell the user before downloading (`findit2.zip` from l3i-share.univ-lr.fr, the size printed by a HEAD request).
- [ ] **Step 4:** Run `--suite findit --target local` (OCR=docai, Vertex). Expected: a report with case-level P/R/F1 and the localisation rate. Copy it to `docs/eval/`.
- [ ] **Step 5:** Commit `feat(eval): Find-It-Again suite and report`.

### Task 10: Live runs and browser spot-check

**Files:** Modify `backend/README.md` (an "Evaluation" section), `docs/eval/README.md` (a summary of all reports).

- [ ] **Step 1:** Push to `main` so CI deploys `NO_LIMIT_EMAILS`, then confirm the env var is on the service.
- [ ] **Step 2:** Run `--suite synthetic --n 60 --target live --base-url <url>` (digital variants only). Expected: a report comparable to the local one.
- [ ] **Step 3:** **Browser:** upload the 3 worst live cases' PDFs through the live UI, signed in as the user. Compare the stamp, findings and markers with the report, and record a GIF `claimlens_eval_spotcheck.gif`.
- [ ] **Step 4:** Write `docs/eval/README.md` with the headline numbers per suite and known limitations, and link it from the root README.
- [ ] **Step 5:** Commit `docs(eval): live results and summary` and push.

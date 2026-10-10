# ClaimLens Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A FastAPI backend that turns a claim PDF + policy PDF into a cited case file (tamper, story, duplicate, coverage findings). It runs locally and on Cloud Run.

**Architecture:** One FastAPI app. Uploads create a case, and a background thread runs `run_pipeline` (Read → Extract → Checks → Prove → Report). Storage, DB, AI and OCR are Protocols with local/fake and GCP implementations, picked by settings. GCP resources are managed by Terraform; Cloud Run is deployed with `gcloud`.

**Tech Stack:** Python 3.12, FastAPI, uvicorn, pydantic v2 + pydantic-settings, PyMuPDF, rapidfuzz, python-dateutil, google-genai, google-cloud-storage, google-cloud-firestore, google-cloud-documentai, firebase-admin, pytest, httpx, Terraform (google provider ≥ 6), Postman.

**Spec:** `docs/superpowers/specs/2026-10-10-claimlens-backend-design.md`

## Global Constraints

- All backend code lives under `backend/`; package name `claimlens`; venv `backend/.venv` created with `python3.12`.
- Health route is `GET /health`. Never use paths ending in `z` (Cloud Run reserves them).
- GCP project `social-pulse-510513`, region `asia-south1`, Firestore database `claimlens`, bucket `social-pulse-510513-claimlens`, Document AI location `us`, Vertex location `global`, model `gemini-2.5-flash`.
- Terraform: every `google_project_service` has `disable_on_destroy = false`. State is local and git-ignored. Never touch SocialPulse resources.
- Severity weights: critical 40, high 20, medium 10, low 5, coverage 0. Risk bands: below 30 `low`, 30–59 `review`, 60+ `high`.
- Prove thresholds: `partial_ratio ≥ 90` (digital), `≥ 80` (any other page kind).
- Limits defaults: `MAX_FILE_MB=20`, `MAX_PAGES=60`, `DAILY_CASE_LIMIT=20`.
- Status values: `QUEUED, READING, CHECKING, PROVING, READY, FAILED`.
- Default pytest run is offline (`-m 'not live'`), with `AI=fake`.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. A file that is named `.pdf` but is corrupt, encrypted or not a PDF should return **400** with a clear message, not 500 or a FAILED case. Test in Task 10.
2. Gemini returns facts with missing fields (no bills, no room, null dates). The pipeline should still reach `READY` with fewer findings, without crashing. Test in Task 9.
3. Gemini returns dates in other formats (`13/03/2026`, `13-Mar-2026`, `2026-03-13`). They should parse to the same date, and unparseable dates should be skipped. Test in Task 4.
4. A claim uploaded as a JPG photo with `OCR=off` should reach `READY`, with the page listed as `unreadable`. Test in Task 9.
5. Two uploads at once on `LocalDb` must not corrupt each other's files, and a FAILED case must show `step` and `error` through `GET /api/cases/{id}`. Tests in Tasks 2 and 9.

---

## File structure

```
backend/
  pyproject.toml  Makefile  Dockerfile  .dockerignore  .gitignore  .env.example  README.md
  claimlens/
    __init__.py settings.py models.py deps.py main.py api.py auth.py
    storage.py db.py ai.py ocr.py runner.py
    pipeline/__init__.py run.py context.py read.py extract.py text.py prove.py report.py
    pipeline/checks/__init__.py tamper.py story.py duplicate.py coverage.py
  tests/
    conftest.py
    fixtures/ai/sample/{facts,policy,coverage,summary}.json
    test_settings.py test_storage_db.py test_read.py test_extract.py test_tamper.py
    test_story_duplicate.py test_coverage.py test_prove_report.py test_pipeline.py
    test_api.py test_live.py
  samples/  claim.pdf policy.pdf claim_clean.pdf make_example.py
  scripts/  build_postman.py seed_invoices.py create_test_user.py smoke_test.py
  postman/  ClaimLens.postman_collection.json ClaimLens-local.postman_environment.json ClaimLens-cloud.postman_environment.json
  infra/    versions.tf variables.tf apis.tf firestore.tf storage.tf docai.tf registry.tf iam.tf outputs.tf terraform.tfvars.example
frontend/README.md
```

`pipeline/context.py` holds `Ctx`, the in-memory bundle passed to checks. `pipeline/text.py` holds `normalise`, `parse_date` and `money_re`, shared by extract, checks and prove.

---

### Task 1: Scaffold, settings, models, samples

**Files:**
- Create: `backend/pyproject.toml`, `backend/Makefile`, `backend/.gitignore`, `backend/.env.example`, `backend/claimlens/{__init__,settings,models,deps,main}.py`, `backend/samples/*`, `frontend/README.md`
- Test: `backend/tests/conftest.py`, `backend/tests/test_settings.py`

**Interfaces:**
- Produces:
  - `Settings` (pydantic-settings, env vars exactly as in spec §7, lower-case attrs: `app_env, storage, db, ai, ocr, auth_mode, data_dir: Path, gcp_project, bucket, firestore_db, gemini_model, vertex_location, docai_location, docai_processor, allowed_emails: list[str], max_file_mb, max_pages, daily_case_limit, fake_ai_dir: Path = tests/fixtures/ai/sample`). Its validator raises `ValueError` for: `storage=gcs` without bucket; `ocr=docai` without processor; `auth_mode=dev` with `app_env=prod`. `allowed_emails` parses a string split on `,` or `;`, lower-cased.
  - `models.py`: pydantic models `Span, PageInfo, FileInfo, Citation, Finding, Case, Fact, Procedure, Room, LineItem, Bill, ClaimFacts, WaitingPeriod, PolicyFacts, CoverageItem` with the fields in spec §4. `Fact.value: str | float | None`; dates stay strings in facts. `Severity` and `Status` are `Literal`s. `SEVERITY_ORDER = ["critical","high","medium","low","coverage"]`.
  - `deps.py`: `@dataclass Deps(settings, storage, db, ai, ocr)` and `build_deps(settings) -> Deps`. Implementations are imported lazily, so GCP libraries load only when chosen.
  - `main.py`: `create_app(settings: Settings | None = None, deps: Deps | None = None) -> FastAPI` with `GET /health → {"ok": true}`.

- [ ] **Step 1:** Write `pyproject.toml`, the same shape as SocialPulse:
  - hatchling, `requires-python = ">=3.12,<3.13"`, the dependencies from Tech Stack, plus `python-multipart` and `python-dateutil`.
  - `dev` extra: `pytest>=8`, `httpx`, `reportlab`.
  - pytest config: `markers = ["live: hits real GCP"]`, `addopts = "-m 'not live'"`, `testpaths = ["tests"]`.
  - Makefile targets: `venv` (`python3.12 -m venv .venv && .venv/bin/pip install -e '.[dev]'`), `test`, `run` (`.venv/bin/uvicorn claimlens.main:create_app --factory --reload --port 8080`), `samples`.
  - `.gitignore`: `.venv/ data/ .env __pycache__/ .pytest_cache/ infra/.terraform/ infra/*.tfstate* infra/terraform.tfvars infra/tfplan*`.
- [ ] **Step 2:** Copy `make_example.py` from `/Users/chitresh/Documents/Obsidian Vault/Hackiii/ClaimLens example/` into `backend/samples/`. Add a `--clean` flag that also writes `claim_clean.pdf` (the untampered claim with metadata producer `SunriseHMS v4.2` and no modDate change). Run `make samples` to produce `claim.pdf`, `policy.pdf` and `claim_clean.pdf`.
- [ ] **Step 3:** Write the failing tests in `tests/test_settings.py`:
  - `test_defaults_are_local` (storage, db = `local`; auth_mode = `dev`)
  - `test_gcs_requires_bucket` (raises)
  - `test_dev_auth_refused_in_prod` (raises)
  - `test_allowed_emails_parsing`: `"A@x.com; b@y.com"` gives `["a@x.com","b@y.com"]`
  - `test_health`: `TestClient(create_app(...)).get("/health").json() == {"ok": True}`

  `conftest.py` provides a `settings` fixture with `data_dir=tmp_path`, `ai="fake"`.
- [ ] **Step 4:** Run `cd backend && make venv && .venv/bin/pytest tests/test_settings.py -q`. Expected: FAIL (imports missing).
- [ ] **Step 5:** Implement `settings.py`, `models.py`, `deps.py` (with stub implementations raising `NotImplementedError` until Task 2) and `main.py`. Write `frontend/README.md` ("Frontend: next phase").
- [ ] **Step 6:** Run `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 7:** Commit `chore: scaffold backend, settings, models, samples`.

### Task 2: Local storage and DB

**Files:**
- Create: `backend/claimlens/storage.py`, `backend/claimlens/db.py`
- Test: `backend/tests/test_storage_db.py`

**Interfaces:**
- Produces:
  - `class Storage(Protocol)`: `put(key: str, data: bytes, content_type: str) -> None`, `get(key) -> bytes` (raises `KeyError`), `exists(key) -> bool`. `LocalStorage(root: Path)`.
  - `class Db(Protocol)`:
    - `create_case(case: Case) -> None`, `get_case(id) -> Case | None`, `update_case(id, **fields) -> Case` (always sets `updated_at`)
    - `list_cases(owner: str) -> list[Case]` (newest first), `count_cases_since(owner, since: datetime) -> int`
    - `put_findings(case_id, findings: list[Finding])` (replaces all), `get_findings(case_id) -> list[Finding]`, `update_finding(case_id, fid, **fields) -> Finding | None`
    - `put_pages(case_id, pages: list[PageInfo])`, `get_pages(case_id) -> list[PageInfo]`
    - `get_invoice(key) -> dict | None`, `put_invoice(key, doc: dict)`
  - `LocalDb(root: Path)` writes one JSON file per document under `root/<collection>/…`, guarded by a single `threading.Lock`, and writes atomically (write a temp file, then `os.replace`).
  - `build_deps` wires `LocalStorage(data_dir/"files")` and `LocalDb(data_dir/"db")`.

- [ ] **Step 1:** Write the failing tests:
  - storage put/get/exists round trip, and `get` on a missing key raises `KeyError`
  - case create/get/update/list ordering; `count_cases_since`
  - findings replace and update; invoice get/put
  - `test_concurrent_updates`: 20 threads each call `update_case(id, step=str(i))`, then the file parses as valid JSON
- [ ] **Step 2:** Run `.venv/bin/pytest tests/test_storage_db.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement `storage.py` (Protocol + `LocalStorage`) and `db.py` (Protocol + `LocalDb`). Wire them in `build_deps`.
- [ ] **Step 4:** Run the same command. Expected: PASS.
- [ ] **Step 5:** Commit `feat: local storage and JSON db`.

### Task 3: Read step

**Files:**
- Create: `backend/claimlens/pipeline/{__init__,context,read}.py`, `backend/claimlens/ocr.py` (Protocol + `NoOcr` only)
- Test: `backend/tests/test_read.py`

**Interfaces:**
- Consumes: `Storage`, `Ocr`.
- Produces:
  - `class Ocr(Protocol)`: `read_page(png: bytes, doc: str, page: int, width: float, height: float) -> list[Span]`. `NoOcr.read_page` returns `[]`.
  - `@dataclass Drawing(doc, page, rect: tuple, fill: tuple | None, seqno: int)`
  - `@dataclass ReadResult(pages: list[PageInfo], spans: list[Span], hidden_layer: list[Span], drawings: list[Drawing], files: list[FileInfo])`
  - `read_document(doc: str, data: bytes, filename: str, case_id: str, storage: Storage, ocr: Ocr) -> ReadResult`, which stores PNGs at `cases/{case_id}/pages/{doc}/{n}.png` (110 dpi).
  - `Ctx` (in `context.py`): `case_id, read: ReadResult, claim_facts: ClaimFacts | None, policy_facts: PolicyFacts | None, deps`, plus helpers `page_text(doc, page) -> str`, `page_kind(doc, page) -> str`, `spans_on(doc, page) -> list[Span]`.

- [ ] **Step 1:** Write the failing tests, using `samples/claim.pdf`:
  - `test_claim_pages_digital`: 4 pages, all `digital`.
  - `test_spans_have_fonts`: a span with text `"Rs 48,500"` on page 3 has `font == "Times-Roman"`, and a span containing `"Rs 45,500"` has font `"Helvetica"`.
  - `test_white_rect_detected`: a drawing on page 3 has fill ≈ (1,1,1), and its seqno is greater than the `"Rs 45,500"` span's seqno and less than the `"Rs 48,500"` span's.
  - `test_file_info`: producer `"iLovePDF"`, created `"D:20260313…"`, modified `"D:20260320…"`.
  - `test_png_stored`: `storage.exists("cases/c1/pages/claim/3.png")`.
  - `test_jpg_upload_unreadable_with_no_ocr`: a 200×200 JPG made with PyMuPDF/Pillow gives 1 page of kind `unreadable`.
- [ ] **Step 2:** Run `.venv/bin/pytest tests/test_read.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement `read.py`:
  - Wrap images as PDFs: `pymupdf.open(stream=data, filetype=ext).convert_to_pdf()`.
  - Spans and seqno: take spans from `page.get_texttrace()` and group consecutive chars with the same `seqno` into one span (text, font, size, bbox = union of char bboxes). Texttrace `type == 3` (invisible) goes to `hidden_layer`.
  - Drawings: `page.get_drawings()` items with `fill` set and a `rect`, keeping `seqno`.
  - Page kind: as in spec §5.1. A full-page image means `page.get_image_info()` has a bbox covering ≥ 90% of the page area.
  - Non-digital pages call `ocr.read_page`. If it returns nothing, the kind becomes `unreadable`.
  - First confirm in a REPL that `get_texttrace()` items carry `seqno` and `get_drawings()` items carry `seqno` (PyMuPDF ≥ 1.23). If drawings lack it, fall back to `get_drawings(extended=True)`.
- [ ] **Step 4:** Run the same command. Expected: PASS.
- [ ] **Step 5:** Commit `feat: read step with spans, drawings, file info, page images`.

### Task 4: Text helpers, AI protocol, fake AI, extract + grounding

**Files:**
- Create: `backend/claimlens/pipeline/text.py`, `backend/claimlens/ai.py` (Protocol + `FakeAi`), `backend/claimlens/pipeline/extract.py`, `backend/tests/fixtures/ai/sample/{facts,policy,coverage,summary}.json`
- Test: `backend/tests/test_extract.py`

**Interfaces:**
- Produces:
  - `text.py`:
    - `normalise(s: str) -> str` (spec §5.4 rules)
    - `parse_date(s: str | None) -> date | None` (`dateutil.parser.parse(s, dayfirst=True)`; returns `None` on failure)
    - `parse_money(v) -> float | None` (strips `Rs`, `₹`, `INR` and commas)
    - `MONEY_RE` (the spec regex)
  - `class Ai(Protocol)`:
    - `extract_facts(claim_text: str) -> ClaimFacts`
    - `extract_policy(policy_text: str) -> PolicyFacts`
    - `judge_coverage(policy_text: str, facts: ClaimFacts) -> list[CoverageItem]`
    - `summarise(findings: list[Finding]) -> str`
  - `FakeAi(dir: Path)`: each method loads `{dir}/{facts|policy|coverage|summary}.json` and validates it into the model. The summary file is `{"text": "..."}`. The input is ignored.
  - `labelled_text(read: ReadResult, doc: str) -> str`: pages joined as `=== {doc} page N ===\n{text}`.
  - `ground(ctx: Ctx, doc: str, fact: Fact | None) -> Fact | None`: on a digital page, `bbox` = the first rect from `pymupdf` `page.search_for(fact.quote)` (open the PDF from storage). Otherwise use the best span by `partial_ratio ≥ 90`. Returns `None` if not found.
  - `extract(ctx: Ctx) -> None`: fills `ctx.claim_facts` and `ctx.policy_facts`, with every `Fact` grounded. Ungrounded facts become `None` or are removed from their list.

- [ ] **Step 1:** Write the fixtures by hand to match the sample text. Each quote is copied from the page text, which `make samples` prints with `python -c "import pymupdf;…get_text()"`.
  - `facts.json`:
    - claimant `"Rahul Verma"` p1
    - names: p1 `"Rahul Verma"`, p2 `"Rahul Varma"`, p3 `"Rahul Verma"`, p4 `"Rahul Verma"`
    - admission `"10-Mar-2026"` p1, discharge `"13-Mar-2026"` p1, claim date `"22-Mar-2026"` p1, amount claimed `51500` p1 (quote `"Rs 51,500"`)
    - diagnosis `"Senile cataract, right eye"` p2
    - procedure `"Phacoemulsification with IOL implant"`, date `"11-Mar-2026"` p2
    - room rate `4500`, days `3` p3 (quote `"3 days x Rs 4,500"`)
    - bills:
      - p3 hospital, invoice `"INV-SEH-2026-0412"`, date `"13-Mar-2026"`, inpatient true, 4 line items (13500, 22000, 8000, 2000), total `48500` (quote `"Rs 48,500"`)
      - p4 pharmacy, invoice `"PH-7781"`, date `"15-Mar-2026"` (quote `"Date: 15-Mar-2026"`), inpatient true, 1 item 3000, total 3000
  - `policy.json`:
    - policy number `EH-2025-778812` p1, start `"01-Jan-2026"` p1, sum insured `300000` p1
    - room limit `3000` p1 (quote `"Room rent is payable up to 1% of the sum insured per day"`)
    - waiting periods: `{condition:"Cataract", months:24, clause:"3.2", page:2, quote:"not payable until 24 months"}`
  - `coverage.json`:
    - `[{item:"Cataract surgery", verdict:"not_covered", clause:"3.2", page:2, quote:"not payable until 24 months", amount_not_payable:0, reason:"…"}`
    - `{item:"Room rent", verdict:"partly_covered", clause:"2.1", page:1, quote:"Room rent is payable up to 1% of the sum insured per day", amount_not_payable:4500, reason:"…"}]`
  - `summary.json`: `{"text":"High risk: the bill total was edited and the invoice was used in an earlier claim. Cataract is in its 24-month waiting period."}`
- [ ] **Step 2:** Write the failing tests:
  - `test_parse_date_formats`: `"13/03/2026"`, `"13-Mar-2026"` and `"2026-03-13"` all give `date(2026,3,13)`; `"soon"` gives None.
  - `test_normalise`: `"₹ 48,500"` and `"Rs. 48,500"` normalise equal.
  - `test_extract_grounds_bill_total`: after `extract`, `bill.total.bbox` is not None and lies inside page 3.
  - `test_ungrounded_fact_dropped`: a FakeAi whose facts have the claimant quote `"Imaginary Person"` gives `claimant_name is None`.
- [ ] **Step 3:** Run `.venv/bin/pytest tests/test_extract.py -q`. Expected: FAIL.
- [ ] **Step 4:** Implement `text.py`, `ai.py` (Protocol + FakeAi) and `extract.py`. Wire `ai="fake"` in `build_deps`.
- [ ] **Step 5:** Run the same command. Expected: PASS.
- [ ] **Step 6:** Commit `feat: extract facts with quote grounding; fake AI fixtures`.

### Task 5: Tamper checks

**Files:**
- Create: `backend/claimlens/pipeline/checks/{__init__,tamper}.py`
- Test: `backend/tests/test_tamper.py`

**Interfaces:**
- Consumes: `Ctx`, `MONEY_RE`.
- Produces:
  - `check_tamper(ctx: Ctx) -> list[Finding]`, using the codes and severities in spec §5.3.
  - File-level findings (`editing_tool`, `late_edit`, `multiple_saves`) cite page 1 of the document, with the quote set to the text of the first span on that page.
  - `Finding.id` = `f"{code}-{doc}-{page}-{n}"`.
  - `checks/__init__.py` exports `ALL_CHECKS = [check_tamper, check_story, check_duplicate, check_coverage]`. Later tasks append their checks.

- [ ] **Step 1:** Write the failing tests, using a ctx built from read + extract on the samples (a fixture in conftest):
  - `test_font_outlier`: exactly 1 `font_outlier`, citing claim p3 `"Rs 48,500"`, critical.
  - `test_hidden_text`: 1 `hidden_text`, citing claim p3 with a quote containing `"Rs 45,500"`, critical.
  - `test_editing_tool`: 1 `editing_tool` on claim, high, detail mentions `iLovePDF`; no `late_edit` for claim.
  - `test_clean_claim_has_no_tamper`: `claim_clean.pdf` gives `[]`.
  - `test_policy_has_no_tamper`: no findings with `doc == "policy"`.
- [ ] **Step 2:** Run `.venv/bin/pytest tests/test_tamper.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement `check_tamper`:
  - The editing-tool list is copied verbatim from the spec.
  - The `ocr_layer_mismatch` rule extracts `\d[\d,./-]*` tokens from `hidden_layer` spans and from the OCR spans for that page. Flag tokens present in the hidden layer but absent from OCR.
- [ ] **Step 4:** Run the same command. Expected: PASS.
- [ ] **Step 5:** Commit `feat: tamper checks`.

### Task 6: Story and duplicate checks

**Files:**
- Create: `backend/claimlens/pipeline/checks/story.py`, `backend/claimlens/pipeline/checks/duplicate.py`
- Test: `backend/tests/test_story_duplicate.py`

**Interfaces:**
- Produces:
  - `check_story(ctx) -> list[Finding]`
  - `check_duplicate(ctx) -> list[Finding]`
  - `invoice_key(no: str) -> str` (upper-case, only A–Z and 0–9)
  - `register_invoices(ctx) -> None` (called by run.py after READY; stores `{invoice_no, amount, case_id, created_at}`)

- [ ] **Step 1:** Write the failing tests:
  - `test_sum_mismatch`: 1 finding, high, citing claim p3 `"Rs 48,500"`.
  - `test_inpatient_outside_stay`: 1 finding, high, citing claim p4 `"Date: 15-Mar-2026"`.
  - `test_name_mismatch_low`: 1 finding, low, quote `"Rahul Varma"`.
  - `test_no_claimed_amount_mismatch` (51,500 = 48,500 + 3,000).
  - `test_no_date_order_finding`.
  - `test_missing_fields_no_crash`: a `ClaimFacts` with every field None and empty lists gives `[]`.
  - `test_invoice_key`: `"INV-SEH-2026-0412"` gives `"INVSEH20260412"`.
  - `test_duplicate_found`: seed the db with key `INVSEH20260412 → {case_id:"CLM-1043"}`, giving 1 critical finding whose detail mentions `CLM-1043`.
  - `test_duplicate_same_case_ignored`.
- [ ] **Step 2:** Run `.venv/bin/pytest tests/test_story_duplicate.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement both modules, using `parse_date` and `parse_money` everywhere. Skip a rule when its inputs are None.
- [ ] **Step 4:** Run the same command. Expected: PASS.
- [ ] **Step 5:** Commit `feat: story and duplicate checks`.

### Task 7: Coverage check

**Files:**
- Create: `backend/claimlens/pipeline/checks/coverage.py`
- Test: `backend/tests/test_coverage.py`

**Interfaces:**
- Produces: `check_coverage(ctx) -> list[Finding]` (severity `coverage`, `amount_not_payable` set, citations on `doc="policy"`). It also exposes `months_between(a: date, b: date) -> int`.

- [ ] **Step 1:** Write the failing tests:
  - `test_waiting_period_not_covered`: 1 finding mentioning `3.2`, citing policy p2 `"not payable until 24 months"`.
  - `test_room_rent_excess`: 1 finding with `amount_not_payable == 4500`, citing policy p1.
  - `test_override_when_ai_says_covered`: a FakeAi coverage file where cataract is `covered` still gives a waiting-period finding, because of the code override.
  - `test_months_between`: 2026-01-01 → 2026-03-11 gives 2.
- [ ] **Step 2:** Run `.venv/bin/pytest tests/test_coverage.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement it:
  - Call `ai.judge_coverage(labelled policy text, facts)`.
  - Apply the waiting-period override: `partial_ratio(condition.lower(), diagnosis/procedure.lower()) ≥ 80`. Apply the room-rent override as in spec §5.3.
  - Remove duplicate items by `clause`. Code-derived items replace AI items with the same clause.
- [ ] **Step 4:** Run the same command. Expected: PASS.
- [ ] **Step 5:** Commit `feat: coverage check with deterministic overrides`.

### Task 8: Prove and report

**Files:**
- Create: `backend/claimlens/pipeline/prove.py`, `backend/claimlens/pipeline/report.py`
- Test: `backend/tests/test_prove_report.py`

**Interfaces:**
- Produces:
  - `prove(ctx, findings: list[Finding]) -> tuple[list[Finding], list[dict]]`, returning (kept with `verified=True`, dropped `[{title, reason}]`).
  - `score(findings) -> int`, `risk_band(score) -> str`
  - `payable(ctx, findings) -> float | None`
  - `summarise(ctx, findings) -> str` (falls back to `f"{n} problems found: " + "; ".join(titles)` if the AI raises)
  - `sort_findings(findings)` (by `SEVERITY_ORDER`)

- [ ] **Step 1:** Write the failing tests:
  - `test_prove_keeps_real_quote` (`"Rs 48,500"` on claim p3)
  - `test_prove_drops_invented_quote` (`"patient has diabetes"` p2 is dropped, with a reason)
  - `test_prove_ocr_threshold`: one character changed in the quote on an `image` page is kept; the same quote on a digital page at ratio 85 is dropped.
  - `test_score_caps_at_100`, `test_risk_bands` (29 → low, 30 → review, 60 → high)
  - `test_payable_zero_when_main_procedure_not_covered`
  - `test_payable_subtracts_room_excess_when_covered` (51500 − 4500 = 47000, using a coverage fixture without the cataract item)
  - `test_summary_fallback` (an AI that raises gives text starting `"7 problems found"` for 7 findings)
- [ ] **Step 2:** Run `.venv/bin/pytest tests/test_prove_report.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement both modules.
- [ ] **Step 4:** Run the same command. Expected: PASS.
- [ ] **Step 5:** Commit `feat: prove step and report scoring`.

### Task 9: Pipeline orchestration and background runner

**Files:**
- Create: `backend/claimlens/pipeline/run.py`, `backend/claimlens/runner.py`
- Test: `backend/tests/test_pipeline.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `run_pipeline(case_id: str, deps: Deps) -> None`:
    - Loads the case and reads `files.claim` / `files.policy` keys from storage.
    - Statuses: `READING` (read both + `put_pages`), `CHECKING` (extract + `ALL_CHECKS`), `PROVING` (prove), then report.
    - Sets `READY` with `score, risk, payable, summary, dropped_findings`, then calls `register_invoices`.
    - Any exception: `update_case(status="FAILED", step=<current status>, error=str(e))`.
  - `start(case_id, deps) -> None` runs it in `threading.Thread(daemon=True)`. Tests call `run_pipeline` directly.

- [ ] **Step 1:** Write the failing tests:
  - `test_sample_end_to_end`: after seeding the invoice, the case is `READY`.
    - Finding codes, as a multiset, equal `{font_outlier, hidden_text, editing_tool, sum_mismatch, inpatient_outside_stay, name_mismatch, duplicate_invoice}` plus 2 coverage findings.
    - score 100, risk `high`, payable 0.
    - The invoice is registered under this case id.
  - `test_failure_recorded`: an AI whose `extract_facts` raises `RuntimeError("boom")` gives `FAILED`, step `CHECKING`, error `"boom"`.
  - `test_empty_facts_still_ready`: a FakeAi with empty facts and coverage gives `READY`.
  - `test_jpg_claim_ready_with_unreadable_page`.
- [ ] **Step 2:** Run `.venv/bin/pytest tests/test_pipeline.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement `run.py` and `runner.py`. Cache `ReadResult` as JSON at `cases/{id}/read.json`.
- [ ] **Step 4:** Run `.venv/bin/pytest -q`. Expected: all PASS.
- [ ] **Step 5:** Commit `feat: pipeline orchestration and background runner`.

### Task 10: Auth and API

**Files:**
- Create: `backend/claimlens/auth.py`, `backend/claimlens/api.py`; Modify: `backend/claimlens/main.py`
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Produces:
  - `current_user(request) -> str` (email), as a FastAPI dependency following spec §6.
  - Firebase mode calls `firebase_admin.auth.verify_id_token(token)`, after initialising the app once with `options={"projectId": settings.gcp_project}`.
  - Routes exactly as in spec §6.
  - `create_app` mounts `api.router` and stores `deps` on `app.state`. The upload route calls `runner.start` (tests override `app.state.start` with a synchronous call to `run_pipeline`).

- [ ] **Step 1:** Write the failing tests (TestClient, `AUTH_MODE=dev`, tmp data dir, fake AI, synchronous start):
  - `test_requires_dev_header` → 401
  - `test_upload_and_get_ready`: POST the sample files → 201 `QUEUED`; GET → `READY` with 9 findings sorted critical first and a `pages` list of 7 entries.
  - `test_page_png`: GET claim page 3 → 200 `image/png`.
  - `test_review_finding`: accept → `review.action == "accept"`.
  - `test_other_users_case_404`: header `b@x.com` → 404.
  - `test_list_cases_only_mine`
  - `test_bad_file_400`: text bytes named `claim.pdf` → 400.
  - `test_encrypted_pdf_400`: PyMuPDF save with `encryption=PDF_ENCRYPT_AES_256, user_pw="x"` → 400.
  - `test_too_many_pages_400` with `MAX_PAGES=2`.
  - `test_daily_limit_429` with `DAILY_CASE_LIMIT=1`.
  - `test_firebase_mode_rejects_non_allowlisted`: monkeypatch `verify_id_token` to return `{"email":"x@y.com"}` and set `ALLOWED_EMAILS=a@b.com` → 403; with no token → 401.
- [ ] **Step 2:** Run `.venv/bin/pytest tests/test_api.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement the routes.
  - Validation opens each file with PyMuPDF inside try/except. Not openable, `doc.needs_pass`, or page count over the limit → 400. Size is checked before opening.
  - The case id is `uuid4().hex[:12]`.
- [ ] **Step 4:** Run `.venv/bin/pytest -q`. Expected: all PASS.
- [ ] **Step 5:** Commit `feat: auth and REST API`.

### Task 11: GCP adapters

**Files:**
- Modify: `backend/claimlens/storage.py` (`GcsStorage`), `backend/claimlens/db.py` (`FirestoreDb`), `backend/claimlens/ai.py` (`VertexGemini`), `backend/claimlens/ocr.py` (`DocAiOcr`), `backend/claimlens/deps.py`
- Test: `backend/tests/test_live.py` (all `@pytest.mark.live`)

**Interfaces:**
- Produces:
  - `GcsStorage(bucket: str)`
  - `FirestoreDb(project: str, database: str)`, using the same collections as spec §4. Findings and pages are stored as subcollections. `count_cases_since` uses `where owner_email == x and created_at >= ts`.
  - `VertexGemini(project, location, model)`, built on `genai.Client(vertexai=True, …)`. Each method sends a system prompt plus the labelled text, with `response_mime_type="application/json"` and `response_schema=<pydantic model>`, `temperature=0`.
    - The prompts require copying exact quotes from the given page and give dates as written.
    - The coverage prompt carries spec §5.3's instruction verbatim: *"For each item, decide covered / not_covered / partly_covered. Cite the clause, the policy page, and copy the exact sentence you relied on. If the policy doesn't say, answer unknown. Do not guess."*
    - `summarise` returns 3–4 sentences built only from the findings it is given.
  - `DocAiOcr(project, location, processor)`: `process_document` on the PNG gives tokens. Each token becomes a `Span` with `font="ocr"`, a bbox (normalised vertices × page width/height), confidence, and seqno = token index.

- [ ] **Step 1:** Write the live tests:
  - `test_vertex_extract_grounds` (real Gemini on the samples: claimant grounded, bill total 48500 grounded on p3)
  - `test_vertex_pipeline_codes` (`run_pipeline` with real AI and local storage/db gives the same code multiset as Task 9)
  - `test_gcs_roundtrip`, `test_firestore_roundtrip` (both skipped unless `BUCKET` is set and Firestore exists)
- [ ] **Step 2:** Implement the four adapters and wire them in `build_deps`.
- [ ] **Step 3:** Run `.venv/bin/pytest -q`. Expected: offline suite still passes.
- [ ] **Step 4:** Run `gcloud auth application-default login` if ADC is missing, then `.venv/bin/pytest -m live -k vertex -q`. Expected: PASS. If grounding fails, tune the prompt, not the thresholds.
- [ ] **Step 5:** Commit `feat: GCS, Firestore, Vertex Gemini and Document AI adapters`.

### Task 12: Dev tooling: scripts, Postman, Docker, README

**Files:**
- Create: `backend/scripts/{seed_invoices,create_test_user,smoke_test,build_postman}.py`, `backend/postman/*.json`, `backend/Dockerfile`, `backend/.dockerignore`, `backend/README.md`; Modify: `backend/Makefile`, `backend/.env.example`

**Interfaces:**
- Produces:
  - `seed_invoices.py`: uses `build_deps(Settings())` and puts `INVSEH20260412 → {invoice_no:"INV-SEH-2026-0412", amount:45500, case_id:"CLM-1043"}`.
  - `create_test_user.py --email claimlens-tester@example.com --password …`: uses the firebase-admin `auth.get_user_by_email`, else `create_user`.
  - `smoke_test.py --base-url … (--dev-user … | --token …)`: uploads the samples, polls every 2 s for up to 180 s, and asserts READY and the code superset from Task 9. Exit code 0 or 1.
  - `build_postman.py` writes the 3 Postman files per spec §11. The file `src` is the absolute path of `backend/samples/*.pdf`.
  - Make targets: `seed`, `postman`, `smoke-local`, `docker-build`.

- [ ] **Step 1:** Write the scripts and the Postman builder. Run `make postman`, then check that `python -m json.tool` parses all 3 files.
- [ ] **Step 2:** Dockerfile: `python:3.12-slim`, `pip install .`, `CMD uvicorn claimlens.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8080}`. `.dockerignore` excludes `.venv data tests infra postman`.
- [ ] **Step 3:** Local verification:
  - `make seed && make run` (in the background), then `make smoke-local`. Expected: `READY` and the codes match (real Gemini, local storage/db).
  - `docker build -t claimlens-api .` succeeds.
- [ ] **Step 4:** Write `backend/README.md`: the quick start (venv, `.env` from the example, ADC login, seed, run, Postman import, test commands) and the GCP deploy steps (Task 13).
- [ ] **Step 5:** Commit `chore: scripts, Postman collection, Dockerfile, README`.

### Task 13: Terraform infrastructure and Cloud Run deploy

**Files:**
- Create: `backend/infra/*.tf`, `backend/infra/terraform.tfvars.example`; Modify: `backend/Makefile` (targets `infra-plan`, `infra-apply`, `deploy`, `smoke-cloud`)

**Interfaces:**
- Produces: the resources and outputs in spec §8 (`bucket`, `docai_processor_id`, `service_account_email`, `registry`). `make deploy` reads these outputs with `terraform output -raw`.

- [ ] **Step 1:** Write the Terraform files per spec §8.
  - Provider `google` with `project`/`region` variables; `user_project_override = true` and `billing_project = var.project` (needed for the Firestore and Document AI APIs with user ADC).
  - Grant the bucket role with `google_storage_bucket_iam_member`.
- [ ] **Step 2:** Run `make infra-plan` (`terraform init && terraform plan -out tfplan`). Expected: only `claimlens` resources and API enablements; no destroy/replace of anything existing. **Show the plan summary to the user and wait for approval.**
- [ ] **Step 3:** Run `make infra-apply`. Expected: apply succeeds; outputs are printed.
- [ ] **Step 4:** Firebase email/password: run `create_test_user.py`. If it reports the provider is disabled, enable "Email/Password" in Firebase console → Authentication → Sign-in method (browser; ask the user first), then re-run.
- [ ] **Step 5:** Run `make deploy` (`gcloud builds submit` + `gcloud run deploy` with the env vars from spec §8, `ALLOWED_EMAILS` = the user's email and the tester email, `BUCKET` / `DOCAI_PROCESSOR` from outputs). Then run `make seed` against Firestore (`DB=firestore`).
- [ ] **Step 6:** Verification:
  - `curl $URL/health` → `{"ok":true}`
  - `make smoke-cloud` (gets a token via `signInWithPassword` with the Firebase web API key) → exit 0
  - `curl $URL/api/me` without a token → 401
- [ ] **Step 7:** Regenerate Postman with the cloud URL and web API key (`make postman URL=… API_KEY=…`).
- [ ] **Step 8:** Commit `infra: Terraform for ClaimLens GCP resources; deploy targets`.

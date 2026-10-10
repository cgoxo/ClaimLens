# ClaimLens backend: design

Date: 2026-10-10 · Status: approved in chat, awaiting written-spec review

Source design: Obsidian note *ClaimLens - Insurance Claim Fraud Investigator README* (sections 8–10). This spec makes that design concrete for the backend. The frontend is a later, separate spec.

## 1. Goal and success criteria

ClaimLens takes a claim PDF and a policy PDF and returns a case file. The case file lists tamper, story, duplicate and coverage findings, each citing a document, page, quote and box.

The backend is done when:

1. `pytest` passes offline (no network). With the fake AI, the sample `claim.pdf` + `policy.pdf` produce exactly the 9 findings in §9 (7 risk findings + 2 coverage findings).
2. Running locally (`make run`, local storage and DB, real Gemini) and uploading the samples through the Postman **local** environment reaches `READY` with the same findings.
3. After `make infra` + `make deploy`, the same Postman requests against the **cloud** environment reach `READY` with the same findings, stored in Firestore DB `claimlens` and the GCS bucket.
4. Requests without a valid login get `401`. A signed-in email that isn't on the allow-list gets `403`.

Out of scope: frontend, queues, BigQuery, PDF export of the report, image-forensics (ELA/copy-move), photo EXIF checks, the WhatsApp channel.

## 2. Repository layout

```
ClaimLens/                       (git repo)
├── backend/
│   ├── claimlens/               python package
│   │   ├── main.py              create_app(): FastAPI app factory
│   │   ├── settings.py          pydantic-settings, all env vars (§7)
│   │   ├── models.py            Span, PageInfo, Citation, Finding, Case, facts models
│   │   ├── api.py               /api routes
│   │   ├── auth.py              current_user dependency (dev | firebase)
│   │   ├── storage.py           Storage protocol: LocalStorage, GcsStorage
│   │   ├── db.py                Db protocol: LocalDb (JSON files), FirestoreDb
│   │   ├── ai.py                Ai protocol: VertexGemini, FakeAi
│   │   ├── ocr.py               Ocr protocol: NoOcr, DocAiOcr
│   │   ├── runner.py            start(case_id): background thread → run_pipeline
│   │   └── pipeline/
│   │       ├── run.py           run_pipeline(case_id, deps): steps + status updates
│   │       ├── read.py          PDFs/images → pages, spans, drawings, metadata, PNGs
│   │       ├── extract.py       Gemini facts + quote→bbox grounding
│   │       ├── checks/tamper.py
│   │       ├── checks/story.py
│   │       ├── checks/duplicate.py
│   │       ├── checks/coverage.py
│   │       ├── prove.py
│   │       └── report.py        score, risk band, payable, summary
│   ├── tests/                   unit tests + fixtures (fake AI responses for samples)
│   ├── samples/                 claim.pdf, policy.pdf, make_example.py
│   ├── postman/                 collection + local and cloud environments
│   ├── scripts/                 seed_invoices.py, create_test_user.py, smoke_test.py
│   ├── infra/                   Terraform (§8)
│   ├── Dockerfile, Makefile, pyproject.toml, .env.example, README.md
├── frontend/                    README placeholder only (next phase)
└── docs/superpowers/{specs,plans}/
```

Python 3.12, FastAPI, PyMuPDF, rapidfuzz, google-genai, google-cloud-firestore, google-cloud-storage, google-cloud-documentai, firebase-admin, pydantic-settings. Virtual env at `backend/.venv`.

## 3. Swappable dependencies

Each dependency is a small Protocol with two implementations, chosen by settings. `run_pipeline` and the API receive a `Deps` object (`storage, db, ai, ocr, settings`), so tests inject fakes.

| Protocol | Methods | Local / test | GCP |
| --- | --- | --- | --- |
| `Storage` | `put(key, bytes, content_type)`, `get(key) -> bytes`, `exists(key)` | `LocalStorage(DATA_DIR/files)` | `GcsStorage(BUCKET)` |
| `Db` | `create_case`, `get_case`, `update_case(id, **fields)`, `list_cases(owner)`, `count_cases_since(owner, ts)`, `put_findings(case_id, list)`, `get_findings`, `update_finding`, `get_invoice(key)`, `put_invoice(key, doc)` | `LocalDb(DATA_DIR/db)`: one JSON file per document, guarded by a lock | `FirestoreDb(database=FIRESTORE_DB)` |
| `Ai` | `extract_facts(claim_pages) -> ClaimFacts`, `extract_policy(policy_pages) -> PolicyFacts`, `judge_coverage(policy_pages, facts) -> list[CoverageItem]`, `summarise(findings) -> str` | `FakeAi(fixtures dir)`: returns canned JSON keyed by the SHA-256 of the input files | `VertexGemini(model, project, location)` using structured output (`response_schema`) |
| `Ocr` | `read_page(png_bytes) -> list[Span]` (with `confidence`) | `NoOcr` (page marked `unreadable`) | `DocAiOcr(processor)` |

## 4. Data model

```python
Span:      doc, page, text, font, size, bbox(x0,y0,x1,y1 PDF pts), seqno, confidence=1.0
PageInfo:  doc, page, kind("digital"|"scanned"|"scanned_with_text"|"image"|"unreadable"),
           text, width, height, png_key
FileInfo:  doc, producer, creator, created, modified, eof_count
Citation:  doc, page, quote, bbox | None
Finding:   id, check("tamper"|"story"|"duplicate"|"coverage"), code (e.g. "font_outlier"),
           severity("critical"|"high"|"medium"|"low"|"coverage"),
           title, detail, citations[], amount_not_payable: float = 0,
           verified: bool, review: {action, note, by, at} | None
Case:      id, owner_email, status, step, error, created_at, updated_at,
           files{claim, policy}, score, risk("low"|"review"|"high"), payable,
           summary, dropped_findings: list[{title, reason}]
```

**Facts.** Every scalar is `Fact{value, page, quote, bbox?}`.

```python
ClaimFacts: policy_number, claimant_name, admission_date, discharge_date, claim_date,
            amount_claimed, diagnosis, names: list[Fact], procedures: list[{name: Fact, date: Fact}],
            room: {rate_per_day: Fact, days: Fact} | None,
            bills: list[{page, kind("hospital"|"pharmacy"|"other"), invoice_no: Fact, date: Fact,
                         inpatient: bool, line_items: list[{desc, amount: Fact}], total: Fact}]
PolicyFacts: policy_number, start_date, sum_insured, room_rent_limit_per_day: Fact | None,
             waiting_periods: list[{condition, months, clause, page, quote}]
CoverageItem: item, verdict("covered"|"not_covered"|"partly_covered"|"unknown"),
              reason, clause, page, quote, amount_not_payable
```

**Firestore DB `claimlens`:** `cases/{id}`, `cases/{id}/findings/{fid}`, `cases/{id}/pages/{doc_page}` (PageInfo without text larger than 900 KB), `invoices/{normalised_no}`.

**Storage keys:** `cases/{id}/claim.pdf`, `cases/{id}/policy.pdf`, `cases/{id}/pages/{doc}/{n}.png`, `cases/{id}/read.json` (spans, drawings and file info cached between steps).

## 5. Pipeline

`run_pipeline(case_id, deps)` runs each step in order. Before each step it sets `status`. On any exception it sets `status=FAILED, step=<name>, error=<message>` and stops.

Statuses: `QUEUED → READING → CHECKING → PROVING → READY | FAILED`.

### 5.1 Read (`read.py`)
For each document (claim, policy). An image upload is wrapped as a one-page PDF first.
- Classify each page:
  - `digital`: it has text spans and no full-page image.
  - `scanned_with_text`: an image covers ≥ 90% of the page and its text is invisible (texttrace type 3) or in `GlyphLessFont`.
  - `scanned`: a full-page image and no text.
  - `image`: an uploaded photo.
- Spans:
  - `digital` pages: spans come from `page.get_texttrace()` merged with `get_text("dict")`, giving text, font, size, bbox and seqno.
  - Other kinds: spans come from `Ocr.read_page`. With `NoOcr`, the page is `unreadable`.
  - `scanned_with_text`: also keep the original invisible spans, for the OCR-layer comparison.
- Drawings: filled rectangles from `page.get_drawings()` (fill colour, rect, seqno).
- File info: `doc.metadata` and `raw_bytes.count(b"%%EOF")`.
- Render each page to PNG at 110 dpi and store it.

### 5.2 Extract (`extract.py`)
- `Ai.extract_facts` gets the claim page texts labelled `=== claim page N ===`. `Ai.extract_policy` gets the policy text the same way.
- **Grounding:** for each `Fact`, normalise its `quote` (§5.4) and find it in the spans of `Fact.page`. Set `bbox` to the union of the matched spans. A fact that can't be grounded becomes `None` (or is removed from its list).

### 5.3 Checks
Each check is a pure function `(ctx) -> list[Finding]`, where `ctx` holds pages, spans, drawings, file info, facts, policy facts and deps. The checks run one after another (fast enough).

**Tamper (`checks/tamper.py`):**

| Code | Rule | Severity |
| --- | --- | --- |
| `font_outlier` | On each `digital` page, take money spans (regex `(Rs\.?\|₹\|INR)\s*[\d,]+(\.\d+)?`) and their most common font. A money span whose font differs, or whose size differs by more than 0.5 pt, is flagged | critical |
| `hidden_text` | A span is ≥ 50% covered by a near-white filled rect (all fill channels ≥ 0.95) whose seqno is greater than the span's | critical |
| `ocr_layer_mismatch` | On a `scanned_with_text` page, a number or date in the invisible layer has no match in the OCR spans | critical |
| `editing_tool` | Producer or creator contains one of: ilovepdf, smallpdf, sejda, pdfescape, photoshop, canva, pdf-xchange, foxit phantompdf, sodapdf. The detail includes created and modified dates | high |
| `late_edit` | `modified − created > 1 day` and no `editing_tool` finding for that doc | medium |
| `multiple_saves` | `eof_count > 1` | medium |

**Story (`checks/story.py`):**

| Code | Rule | Severity |
| --- | --- | --- |
| `sum_mismatch` | For each bill, `|Σ line_items − total| > 1` | high |
| `date_order` | Any break in policy start ≤ admission ≤ each procedure ≤ discharge ≤ claim date (skip missing dates) | high |
| `inpatient_outside_stay` | A bill with `inpatient=true` dated outside [admission, discharge] | high |
| `name_mismatch` | For each name compared with `claimant_name`, `rapidfuzz.fuzz.ratio`: 85–99 is low ("possible typo"); below 85 is high | low / high |
| `claimed_amount_mismatch` | `|amount_claimed − Σ bill totals| > 1` | medium |

**Duplicate (`checks/duplicate.py`):** normalise `invoice_no` (upper-case, strip everything that isn't A–Z or 0–9). If `db.get_invoice(key)` exists with a different `case_id`, raise `duplicate_invoice` (critical). After `READY`, `run.py` stores this case's invoices.

**Coverage (`checks/coverage.py`):** `Ai.judge_coverage` returns items. Code then overrides two things deterministically:
- **Waiting periods:** for each `waiting_period` whose condition fuzzily matches (partial_ratio ≥ 80) the diagnosis or a procedure name, if the months between `start_date` and the procedure date are fewer than `months`, the verdict becomes `not_covered`.
- **Room rent:** if `room.rate_per_day > room_rent_limit_per_day`, then `amount_not_payable = (rate − limit) × days`.

Each `not_covered` or `partly_covered` item becomes a finding with severity `coverage`, citing the policy page and quote.

### 5.4 Prove (`prove.py`)
`normalise(s)`: lower-case; `₹`, `rs.` and `inr` all become `rs`; whitespace collapsed; leading and trailing punctuation stripped.

A citation is kept if its normalised quote is a substring of the normalised page text, or if `fuzz.partial_ratio ≥ 90` (≥ 80 when the page kind isn't `digital`).

A finding with no kept citation is moved to `case.dropped_findings` with a reason. Kept findings get `verified=True`. This applies to every finding, whichever check made it.

### 5.5 Report (`report.py`)
- **Score:** critical 40, high 20, medium 10, low 5, coverage 0. `score = min(100, Σ)`. `risk`: below 30 is `low`, 30–59 is `review`, 60 and above is `high`.
- **Payable:** `amount_claimed − Σ amount_not_payable`. It is 0 if any `not_covered` item matches the main diagnosis or procedure, and is capped at `sum_insured`. It is `None` if `amount_claimed` is missing.
- **Summary:** `Ai.summarise(verified findings)`. If that fails, use a template ("N problems found: …").

## 6. API

All `/api/*` routes need `current_user`. Errors return `{"detail": str}`.

| Method | Path | Request | Response |
| --- | --- | --- | --- |
| GET | `/health` | none | `{"ok": true}` (no auth; Cloud Run reserves paths ending in `z`) |
| GET | `/api/me` | none | `{"email"}` |
| POST | `/api/cases` | multipart: `claim` (pdf/jpg/png), `policy` (pdf) | `201 {"case_id","status":"QUEUED"}` |
| GET | `/api/cases` | none | `[{id,status,risk,score,created_at}]`, the caller's cases, newest first |
| GET | `/api/cases/{id}` | none | Case + findings (sorted by severity) + pages `[{doc,page,kind,width,height}]` |
| GET | `/api/cases/{id}/pages/{doc}/{n}.png` | none | `image/png` |
| POST | `/api/cases/{id}/findings/{fid}/review` | `{"action":"accept"\|"dismiss","note"?}` | updated finding |

**Validation on `POST /api/cases`:**
- 400 for a bad type, more than `MAX_FILE_MB`, more than `MAX_PAGES` pages, or a file that isn't a valid PDF.
- 429 if the caller has created `DAILY_CASE_LIMIT` cases in the last 24 h.

**Access:** another user's case returns 404. A finding id that doesn't exist returns 404.

**Auth (`auth.py`):**
- `AUTH_MODE=dev`: the `X-Dev-User: <email>` header is required (401 if missing). Startup is refused when `APP_ENV=prod`.
- `AUTH_MODE=firebase`: `Authorization: Bearer <Firebase ID token>`, verified with `firebase-admin` against `GCP_PROJECT`. 401 if the token is missing or invalid; 403 if the email isn't in `ALLOWED_EMAILS` (comma or semicolon separated, case-insensitive).

## 7. Settings (env vars)

| Var | Default | Notes |
| --- | --- | --- |
| `APP_ENV` | `local` | `local` or `prod` |
| `STORAGE` | `local` | `local` or `gcs` |
| `DB` | `local` | `local` or `firestore` |
| `AI` | `vertex` | `vertex` or `fake` (tests set `fake`) |
| `OCR` | `off` | `off` or `docai` |
| `AUTH_MODE` | `dev` | `dev` or `firebase` |
| `DATA_DIR` | `./data` | local storage and DB |
| `GCP_PROJECT` | `social-pulse-510513` | |
| `BUCKET` | none | required when `STORAGE=gcs` |
| `FIRESTORE_DB` | `claimlens` | |
| `GEMINI_MODEL` | `gemini-2.5-flash` | |
| `VERTEX_LOCATION` | `global` | |
| `DOCAI_LOCATION` / `DOCAI_PROCESSOR` | `us` / none | required when `OCR=docai` |
| `ALLOWED_EMAILS` | empty | |
| `MAX_FILE_MB` / `MAX_PAGES` / `DAILY_CASE_LIMIT` | 20 / 60 / 20 | |

## 8. GCP infrastructure (Terraform, `backend/infra/`)

Project `social-pulse-510513`, region `asia-south1`. Terraform state is local and git-ignored, separate from SocialPulse. Every `google_project_service` uses `disable_on_destroy = false`, so destroying ClaimLens never turns off APIs that SocialPulse uses.

| Resource | Details |
| --- | --- |
| APIs | firestore, aiplatform, documentai, storage, run, cloudbuild, artifactregistry, identitytoolkit, firebase |
| `google_firestore_database` | name `claimlens`, `FIRESTORE_NATIVE`, asia-south1, `delete_protection_state = DELETE_PROTECTION_DISABLED` |
| `google_storage_bucket` | `<project>-claimlens`, asia-south1, uniform access, public access prevented, delete objects after 30 days |
| `google_document_ai_processor` | `claimlens-ocr`, type `OCR_PROCESSOR`, location `us` |
| `google_artifact_registry_repository` | `claimlens`, docker, asia-south1 |
| Service account `claimlens-api` | roles: `aiplatform.user`, `datastore.user`, `documentai.apiUser`, `firebaseauth.viewer`; `storage.objectAdmin` on the bucket only |
| Outputs | bucket, processor id, service account email, registry path |

Cloud Run is **not** managed by Terraform. `make deploy` runs:
1. `gcloud builds submit --tag <registry>/claimlens-api:<git sha>`
2. `gcloud run deploy claimlens-api --image … --service-account … --allow-unauthenticated --cpu 1 --memory 1Gi --timeout 300 --no-cpu-throttling --min-instances 0 --max-instances 2 --set-env-vars APP_ENV=prod,STORAGE=gcs,DB=firestore,AI=vertex,OCR=docai,AUTH_MODE=firebase,…`

Firebase Auth already exists in the project. `scripts/create_test_user.py` creates (if missing) the email/password user `claimlens-tester@example.com` with a password passed as an argument, using the Admin SDK. If the email/password provider is disabled, it says so and stops. You add that email to `ALLOWED_EMAILS`.

## 9. Expected result for the samples

Inputs: `samples/claim.pdf` and `samples/policy.pdf`, plus the seeded invoice `INVSEH20260412 → case CLM-1043`.

| # | code | severity | citation |
| --- | --- | --- | --- |
| 1 | font_outlier | critical | claim p.3 "Rs 48,500" |
| 2 | hidden_text | critical | claim p.3 "Rs 45,500" |
| 3 | editing_tool | high | claim p.1 (file info: producer iLovePDF, created 13-Mar, modified 20-Mar). Citation quote is the claim-form title "Claim Form" |
| 4 | sum_mismatch | high | claim p.3 "Rs 48,500" |
| 5 | inpatient_outside_stay | high | claim p.4 "Date: 15-Mar-2026" |
| 6 | name_mismatch | low | claim p.2 "Rahul Varma" |
| 7 | duplicate_invoice | critical | claim p.3 "INV-SEH-2026-0412" |
| 8 | coverage: waiting period | coverage | policy p.2 "not payable until 24 months" |
| 9 | coverage: room rent | coverage, ₹4,500 not payable | policy p.1 "Room rent is payable up to 1% of the sum insured per day" |

`late_edit` does not fire because `editing_tool` already covers it, and `claimed_amount_mismatch` does not fire (₹48,500 + ₹3,000 = ₹51,500 claimed). So there are 7 risk findings and 2 coverage findings. Score: critical 3 × 40 + high 3 × 20 + low 5 = 185, capped at **100**; risk `high`; payable **₹0** (cataract is not covered).

## 10. Testing

- **Unit (offline, `AI=fake`):** read (page kinds, spans with fonts, white rect detected); each tamper, story and duplicate rule against the sample, plus a negative case built from an unedited copy (`make_example.py --clean`); prove (keeps real quotes, drops an invented one); report (score, band, payable); API through `TestClient` with `AUTH_MODE=dev` and an in-memory local DB in a tmp dir. This covers upload, then poll until `READY`, then the expected findings, then review, then 401, 403, 404, 400 and 429 cases.
- **Fake AI fixtures:** `tests/fixtures/ai/<sha>/{facts,policy,coverage,summary}.json`. They are written once by hand to match §9.
- **Live (`-m live`, skipped by default):** `VertexGemini` on the samples returns facts that ground and produce findings 1–9.
- **Smoke:** `scripts/smoke_test.py --base-url … --token …` uploads the samples and asserts that `READY` and finding codes ⊇ §9.

## 11. Postman (`backend/postman/`)

Generated by `scripts/build_postman.py`, the same approach as SocialPulse.

- **Environments:**
  - `local`: `baseUrl=http://localhost:8080`, `devUser`
  - `cloud`: `baseUrl=<run url>`, `firebaseApiKey`, `testEmail`, `testPassword`, `idToken`
- **Requests:**
  - **Sign in test user:** calls Identity Toolkit `signInWithPassword`; a test script stores `idToken` (cloud only)
  - Health, Me
  - **Create case:** form-data files `samples/claim.pdf` and `samples/policy.pdf`; stores `caseId`
  - **Get case:** a test script shows status and the finding count
  - List cases, Page image (claim p.3)
  - **Review first finding:** uses the stored `findingId`
- **Auth:** at collection level, a pre-request script sends `X-Dev-User` when `devUser` is set, otherwise `Authorization: Bearer {{idToken}}`.

## 12. Error handling

- **Pipeline:** any step exception means `FAILED` with the step and message. A Gemini failure in `summarise` falls back to the template. A Gemini failure in extract or coverage fails the case, because findings would be unreliable without it.
- **OCR:** with `OCR=off`, unreadable pages are listed in the case as `unreadable` (shown later in the UI) and don't fail the case.
- **Startup:** fail fast on invalid settings (e.g. `STORAGE=gcs` without `BUCKET`; `AUTH_MODE=dev` with `APP_ENV=prod`).

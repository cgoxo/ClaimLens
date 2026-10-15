# ClaimLens multi-file cases and job queue implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A case is one claim made of user-grouped cards (claim form, bills, supporting documents, policy), each holding PDFs or images. It is uploaded one file per request, checked per bill and across cards, and analysed through a pluggable job queue (a thread locally, Cloud Tasks in prod).

**Architecture:**
- **Pages:** cards are tagged pages inside the existing two streams (`claim`, `policy`), so citations and existing checks don't change.
- **Jobs:** a `jobs` module on `Deps` hides how a job runs: `inline` (tests), `thread` (local) or `cloudtasks` (prod). An OIDC-verified `/internal/jobs/{kind}` endpoint runs them, behind a run-once guard.
- **Frontend:** the two upload trays become cards. The viewer groups thumbnails by card.

**Tech Stack:** Python 3.12, FastAPI, PyMuPDF, google-cloud-tasks, google-auth, Firestore · React 18, TypeScript, Vitest · Terraform.

**Spec:** `docs/superpowers/specs/2026-10-16-claimlens-multi-file-design.md`

## Global Constraints

- **Card roles:** `claim_form | bill | supporting | policy`.
- **Bill kinds:** `hospital | pharmacy | lab | other`.
- **Card counts:** exactly one policy card, at most one claim_form card, at most one supporting card, 0–10 bill cards.
- **Card ids:** match `^[a-z0-9-]{1,32}$` and are unique.
- **Limits:** 20 MB per file; 40 files and 80 pages per case. Settings: `max_files=40`, `max_pages=80`, `max_bill_cards=10`, `max_file_mb=20`.
- **File types:** every card accepts `pdf, jpg, jpeg, png`.
- **Claim-stream order:** claim_form, then bills in card order, then supporting. The policy stream is the policy card. Files keep their upload order within a card.
- **Card labels** (code only, never the AI): `Claim form`, `Bill <n> · <kind>` (n is 1-based among bill cards), `Supporting documents`, `Policy`.
- **Gemini page header:** `=== claim page 5 · Bill 2 (pharmacy) ===`. Old cases with no cards keep `=== claim page 5 ===`.
- **New finding codes:** `bill_split_across_cards` (high), `mixed_bill_in_card` (medium), `duplicate_page_image` (high), `incomplete_bill` (medium). All use check `"cards"`.
- **dHash:** 64-bit, from a 9×8 greyscale render. A page is a duplicate at Hamming distance ≤ 4.
- **Jobs:**
  - `JOBS` setting is `inline | thread | cloudtasks`, default `thread`.
  - Prod env: `JOBS=cloudtasks`, `TASKS_QUEUE=claimlens-jobs`, `TASKS_LOCATION=asia-south1`, `TASKS_SA`, `SERVICE_URL`.
  - Tasks use a 30 min `dispatch_deadline`. Cloud Run `--timeout 1800`.
- **Queue:** `claimlens-jobs`, `max_attempts=3`, `min_backoff=10s`, `max_concurrent_dispatches=10`.
- **Test baselines:** backend `cd backend && .venv/bin/pytest -q` (133 passed); frontend `cd frontend && npx vitest run` (84 passed) and `npm run build`.
- **Commits** end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **A JPG in a card used as a PDF.** `extract._pdf` used `filetype="pdf"` on raw bytes, and it must open images with `open_document`, or locating a quote on an image page can crash. Pinned in Task 4.
2. **A task delivered twice at the same moment** must run the pipeline once. `claim_run` has to be atomic: a Firestore transaction, or the LocalDb lock. Pinned in Task 2.
3. **Submitting a draft whose files are all in empty or removed cards** must give a 400, not an empty analysis. Pinned in Task 3.
4. **Upload retry after a failure on file 3** must not upload files 1–2 again; otherwise they are duplicated and flagged as `duplicate_page_image`. Pinned in Task 9.
5. **An old case opened after deploy** (no `cards`, only `files`) must render with two card groups and keep its findings' page numbers. Pinned in Tasks 4 and 10.

---

### Task 1: Card model, settings, `cards_of`

**Files:**
- Modify: `backend/claimlens/models.py`, `backend/claimlens/settings.py`
- Create: `backend/claimlens/cards.py`
- Test: `backend/tests/test_cards_model.py`

**Interfaces:**
- **Models:**
  - `CaseFile(BaseModel){key: str, name: str, content_type: str, pages: int}`
  - `Card(BaseModel){id: str, role: Literal[...], kind: Literal[...] | None = None, files: list[CaseFile] = []}`
- **Case:** gains `cards: list[Card] = []` and `run_attempt: int = -1`. `Status` gains `"DRAFT"`.
- **PageInfo:** gains `card_id: str | None = None`, `file_index: int = 0`, `file_page: int = 0`, `dhash: str | None = None`.
- **FileInfo:** gains `card_id: str | None = None`, `key: str = ""`, `first_page: int = 1`.
- **`cards.py`:**
  - `cards_of(case: Case) -> list[Card]`: an old `files` dict gives `[Card(id="claim", role="claim_form", files=[...]), Card(id="policy", role="policy", files=[...])]`, with `pages=0`.
  - `stream_of(card: Card) -> str`: `"policy"` for the policy card, `"claim"` otherwise.
  - `ordered(cards: list[Card], stream: str) -> list[Card]`: the stream order from Global Constraints.
  - `card_label(cards: list[Card], card_id: str) -> str`
  - `layout_error(cards: list[Card], settings) -> str | None`: the card-count, id and kind rules.
- **Settings:** `max_pages=80`, `max_files=40`, `max_bill_cards=10`, plus the `jobs` and `tasks_*` / `service_url` fields used by Task 2.

- [ ] **Step 1: Write failing tests:**
  - `test_cards_of_old_case`: a case with `files={"claim": "cases/x/claim.pdf", "policy": "cases/x/policy.pdf"}` gives two cards with roles `claim_form` and `policy`.
  - `test_ordered_claim_stream`: cards `[policy, supporting, bill b2, claim_form, bill b1]` (b2 created before b1) order as `claim_form, b2, b1, supporting` for `"claim"`.
  - `test_labels`: `Claim form`, `Bill 1 · hospital`, `Bill 2 · pharmacy`, `Supporting documents`, `Policy`.
  - `test_layout_errors`, parametrised:
    - two policy cards → `"exactly one policy card"`;
    - 11 bills → `"at most 10 bills"`;
    - a bill without a kind → `"bill b1 needs a kind"`;
    - id `"Bad Id"` → `"card id"`;
    - duplicate ids → `"duplicate card id"`;
    - a valid layout → `None`.
- [ ] **Step 2:** `.venv/bin/pytest tests/test_cards_model.py -q`. Expected: FAIL (import error).
- [ ] **Step 3: Implement.** Error messages contain the quoted fragments above.
- [ ] **Step 4:** `.venv/bin/pytest -q`. Expected: all pass (133 + new).
- [ ] **Step 5: Commit** `feat(backend): card model and stream ordering`.

### Task 2: Job queue and run-once guard

**Files:**
- Create: `backend/claimlens/jobs.py`
- Modify: `backend/claimlens/deps.py`, `backend/claimlens/main.py`, `backend/claimlens/db.py`, `backend/claimlens/settings.py`, `backend/pyproject.toml`
- Delete: `backend/claimlens/runner.py`
- Test: `backend/tests/test_jobs.py`

**Interfaces:**
- `jobs.py`:
  - `HANDLERS: dict[str, Callable[[dict, Deps, int], None]] = {"run_case": run_case_job}`
  - `run_case_job(payload: {"case_id": str}, deps, attempt: int) -> None`. Calls `deps.db.claim_run(case_id, attempt)`, and runs `run_pipeline` only if it returns True.
  - `InlineJobs(deps).enqueue(kind, payload)` runs now. `ThreadJobs(deps).enqueue` runs in a daemon thread. Both use `attempt=0`.
  - `CloudTasksJobs(settings, client=None).enqueue(kind, payload)` builds one HTTP task:
    - URL `f"{service_url}/internal/jobs/{kind}"`, method POST, JSON body;
    - `oidc_token{service_account_email: tasks_sa, audience: service_url}`;
    - `dispatch_deadline` 1800 s, on queue path `projects/{gcp_project}/locations/{tasks_location}/queues/{tasks_queue}`.
  - `verify_task_token(authorization: str, settings) -> bool`. Uses `google.oauth2.id_token.verify_oauth2_token(token, google.auth.transport.requests.Request(), audience=settings.service_url)`, then checks `claims["email"] == settings.tasks_sa`. Any exception → False. Module-level so tests can monkeypatch it.
- **`Deps`:** gains `jobs`. `build_deps` picks the class from `settings.jobs`.
- **`Db.claim_run(case_id: str, attempt: int) -> bool`:**
  - Logic: if the status is `QUEUED`, or the status is running and `attempt > run_attempt`, set `run_attempt=attempt` and return True; otherwise False.
  - LocalDb runs this under its lock. FirestoreDb runs it in `client.transaction()` with `@firestore.transactional`.
- **Endpoint:** `POST /internal/jobs/{kind}` lives in `main.py`, which logs it with `request.state.user = f"tasks:{kind}"`.
  - 404 unless `settings.jobs == "cloudtasks"`, and 404 for an unknown kind.
  - 403 unless `verify_task_token`.
  - `attempt = int(request.headers.get("X-CloudTasks-TaskExecutionCount", 0))`. Runs the handler synchronously in a threadpool (`run_in_threadpool`), then returns `{"ok": True}`.
- **Settings:** `jobs: Literal["inline","thread","cloudtasks"] = "thread"`, `tasks_queue = "claimlens-jobs"`, `tasks_location = "asia-south1"`, `tasks_sa: str | None`, `service_url: str | None`. The validator rejects `jobs="cloudtasks"` without `tasks_sa` and `service_url`.
- **`pyproject.toml`:** add `google-cloud-tasks>=2.16`.
- **`app.state.start` is removed.** Task 3's API calls `deps.jobs.enqueue("run_case", {"case_id": id})`. The `settings` fixture in `conftest.py` sets `jobs="inline"`.

- [ ] **Step 1: Write failing tests:**
  - `test_inline_runs_handler`
  - `test_claim_run_rules` (LocalDb):
    - QUEUED with attempt 0 → True; again with 0 → False;
    - running with attempt 1 → True;
    - READY → False.
  - `test_claim_run_is_atomic`: 8 threads call `claim_run(id, 0)` on one QUEUED case, and exactly one gets True.
  - `test_run_case_job_runs_once`: two calls with attempt 0 → `run_pipeline` is called once (monkeypatch it with a counter).
  - `test_cloudtasks_builds_task`: a fake client records `create_task(parent=..., task=...)`; assert the URL, the OIDC email and audience, `dispatch_deadline.seconds == 1800`, and the queue path.
  - `test_internal_endpoint_auth`, with the app in cloudtasks mode and `jobs.verify_task_token` monkeypatched:
    - False → 403;
    - True with kind `nope` → 404;
    - True with `run_case` → 200, and the handler is called with attempt 2 from the header.
  - `test_internal_endpoint_off_in_thread_mode` → 404.
  - `test_settings_cloudtasks_needs_sa_and_url` → `ValueError`.
- [ ] **Step 2:** `.venv/bin/pytest tests/test_jobs.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement. Install with `.venv/bin/pip install -q 'google-cloud-tasks>=2.16'`. The tasks client is imported lazily inside `CloudTasksJobs`.
- [ ] **Step 4:** `.venv/bin/pytest -q`. Expected: all pass. Existing API tests that relied on `app.state.start = run_pipeline` now run through `InlineJobs`; update `tests/test_api.py::_client` to drop that line.
- [ ] **Step 5: Commit** `feat(backend): pluggable job queue with Cloud Tasks and a run-once guard`.

### Task 3: Draft, file and submit upload API

**Files:**
- Modify: `backend/claimlens/api.py`, `backend/scripts/smoke_test.py`, `backend/tests/test_api.py`, `backend/tests/test_read.py`
- Test: `backend/tests/test_upload_api.py`

**Interfaces:**
- `POST /api/cases`, JSON `{"cards": [{"id", "role", "kind"}]}`:
  - 400 with `layout_error`, or 429 at the daily limit;
  - otherwise 201 `{"case_id", "status": "DRAFT"}`.
- `POST /api/cases/{id}/files`, multipart `card_id` + `file`:
  - 404 if not your case; 409 if not DRAFT; 400 for an unknown card or a bad file (reuse `_validated`, with every card allowing `pdf, jpg, jpeg, png`);
  - stores `cases/{id}/{card_id}/{n}.{ext}` and appends `CaseFile`;
  - returns 201 `{"card_id", "index", "pages"}`.
- `POST /api/cases/{id}/submit`:
  - 409 if not DRAFT;
  - drops empty cards, then returns 400 on: `"add the policy"` (no policy file), `"add the claim documents"` (no claim-side file), `"more than 40 files"`, `"more than 80 pages"`;
  - otherwise sets QUEUED, calls `deps.jobs.enqueue("run_case", {"case_id": id})` and returns 200 `{"case_id", "status": "QUEUED"}`.
- `GET /api/cases` skips DRAFT. `GET /api/cases/{id}` adds `"cards"` (each card: `id, role, kind, label, files: [{name, pages}]`).
- **Test helper `upload_case(client, headers=A, cards=None, files=None) -> Response`:** in `tests/conftest.py`. The default is a `claim_form` card with `samples/claim.pdf` and a policy card with `samples/policy.pdf`. It returns the first non-2xx response, or the submit response. `test_api._upload` now calls it, keeping its `claim=` and `claim_name=` arguments for the claim_form file.
- `scripts/smoke_test.py` uses the 3-step flow.

- [ ] **Step 1: Write failing tests** (`test_upload_api.py`):
  - `test_create_draft_and_layout_error`
  - `test_file_rules`:
    - a policy JPG → 201;
    - `card_id="zzz"` → 400;
    - 21 MB → 400;
    - after submit → 409.
  - `test_file_order_kept`: two files in `b1` give indexes 0 and 1, stored at `…/b1/0.pdf` and `…/b1/1.jpg`.
  - `test_submit_rules`:
    - no policy file → 400 `"add the policy"`;
    - only empty claim cards → 400 `"add the claim documents"`;
    - too many files (`max_files` patched to 2, then 3 files uploaded) → 400 `"more than 2 files"`;
    - a page-limit breach (with `max_pages` patched to 3) → 400;
    - a valid draft → 200 QUEUED, enqueued once (a recording fake `deps.jobs`);
    - a second submit → 409.
  - `test_drafts_hidden_from_list`
  - `test_case_has_cards`: after `upload_case`, `GET` shows `cards[0]["label"] == "Claim form"`.
- [ ] **Step 2:** `.venv/bin/pytest tests/test_upload_api.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Remove the old two-file form endpoint. Switch `test_api.py`, `test_read.py` and `test_logs.py` uploads to `upload_case`. Where an old test asserted 201 from the upload, it now expects 200 from submit.
- [ ] **Step 4:** `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(backend): upload a case one file per request (draft, files, submit)`.

### Task 4: Read and extract over cards

**Files:**
- Modify:
  - `backend/claimlens/pipeline/read.py`, `run.py`, `extract.py`, `context.py`
  - `backend/claimlens/ai.py` (`FACTS_PROMPT`)
- Test: `backend/tests/test_read_cards.py`

**Interfaces:**
- **`read_document`** gains `start_page: int = 1` and `card_id: str | None = None`.
  - Stream pages are numbered from `start_page`. Each `PageInfo` gets `card_id`, `file_index` and `file_page` (1-based in its file).
  - One `FileInfo` per call, with `card_id`, `key` and `first_page=start_page`.
  - `png_key` becomes `cases/{case_id}/pages/{doc}/{stream page}.png`, the same as today.
  - It also fills `PageInfo.dhash` (Task 5 uses it): render `page.get_pixmap(matrix=…, colorspace=GRAY)` scaled to 9×8.
  - `dhash_of(pix) -> str` (16 hex chars) lives in `read.py`.
- **`run_pipeline`:**
  - builds the streams with `cards_of(case)`, `ordered`, `stream_of`, then reads every file with a running `start_page` per stream;
  - progress labels become `Reading <card label>, page <file_page> (<n> of <total>)` (or `OCR on …`);
  - `Ctx.files` is replaced by `Ctx.cards: list[Card]`.
- **`extract._pdf(ctx, doc, page) -> tuple[pymupdf.Document | None, int]`:** finds the `PageInfo`, then the card file by `card_id`/`file_index`, and opens it with `open_document(data, name)`. It returns the doc and the 0-based local page index, and caches by file key. `locate` uses it.
- **`labelled_text`:** the header carries `· <card label>` when the page has a `card_id` and the case has cards. Pages listed in `ctx.skip_pages: set[tuple[str, int]]` are left out (Task 5 fills it).
- **`context_of`:** each bill dict gains `"card": <label of the card holding bill.page>`.
- **`FACTS_PROMPT`** adds: `` - A bill never spans two cards (see the page headers). Report each bill's first page as `page`. ``
- **`checks/tamper.py::_file_info`** cites each FileInfo's own first page (`info.first_page`) instead of page 1, and its ids use that page, so an edited file is flagged on its own pages.

- [ ] **Step 1: Write failing tests:**
  - `test_stream_numbering_and_tags`: cards `claim_form` (claim p1 as a 1-page PDF), `b1` (p3), `b2` (the pharmacy page as a JPG). The claim stream has pages 1..3 with `card_id`s `["claim_form", "b1", "b2"]`, and each page's `file_page` is 1.
  - `test_file_info_per_file`: 3 claim FileInfos with `first_page` 1, 2 and 3.
  - `test_pdf_maps_stream_page_to_file`: a card with two 2-page PDFs; `_pdf(ctx, "claim", 3)` returns the second file and index 0.
  - `test_locate_on_image_page_does_not_crash`: `locate` on a JPG page returns `(False, None)` with OCR off.
  - `test_labelled_text_has_card_headers`: contains `"=== claim page 2 · Bill 1 (hospital) ==="`.
  - `test_old_case_reads_as_before`: an old `files` case gives the same 7 pages, and the exact sample findings `Counter` (`tests/test_pipeline.py::EXPECTED`).
  - `test_context_bills_have_card_labels`
  - `test_editing_tool_cites_the_edited_files_first_page`: with the tampered hospital bill as card `b1` (stream page 2), `editing_tool` cites `claim p.2`.
- [ ] **Step 2:** `.venv/bin/pytest tests/test_read_cards.py -q`. Expected: FAIL. Build the card test files in a fixture by splitting `samples/claim.pdf` pages with PyMuPDF, and render the pharmacy page to JPG with `page.get_pixmap(dpi=150).tobytes("jpeg")`.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(backend): read and extract over cards with per-file metadata`.

### Task 5: Card checks

**Files:**
- Create: `backend/claimlens/pipeline/checks/cards.py`
- Modify: `backend/claimlens/pipeline/checks/__init__.py`, `backend/claimlens/models.py` (`Finding.check` gains `"cards"`), `backend/claimlens/pipeline/run.py`
- Test: `backend/tests/test_card_checks.py`

**Interfaces:**
- `duplicate_pages(read: ReadResult) -> list[tuple[PageInfo, PageInfo]]`: claim-stream pairs `(earlier, later)` with `dhash` Hamming distance ≤ 4.
- **`run.py`:** after Read, set `ctx.skip_pages = {("claim", later.page) for _, later in duplicate_pages(read)}`. It must be set before `extract`.
- `check_cards(ctx) -> list[Finding]`, appended to `ALL_CHECKS` after `check_duplicate`:
  - **`bill_split_across_cards`** (high): bills with the same `invoice_key` whose pages fall in different cards. Title `Invoice <no> appears in two cards (<label a>, <label b>)`. Cites both invoice facts.
  - **`mixed_bill_in_card`** (medium): a bill card whose bills have two or more different invoice keys. Title `<label> holds more than one bill (<no a>, <no b>)`.
  - **`duplicate_page_image`** (high): title `Claim page <later> is the same image as page <earlier>`.
    - Cites the later page, `source="page"`, quote = its first non-empty text line.
    - If the page has no text, `source="metadata"` and quote = `""`. `prove.citation_holds` then accepts it when `ctx.read.files` has that doc.
  - **`incomplete_bill`** (medium): in a bill card, `re.findall(r"page\s+(\d+)\s+of\s+(\d+)", text, re.I)` over the card's pages. If any `m` is seen and the set of `n` misses some of `1..m` → title `<label> is missing page(s) <list> of <m>`. Cites the card's first page and first line.
- These findings are skipped for old cases (no `cards`), except `duplicate_page_image`.

- [ ] **Step 1: Write failing tests** with hand-built `Ctx` / `ReadResult` and facts, as in `test_story_duplicate.py`:
  - **split:** high, cites 2 claim pages.
  - **mixed:** medium.
  - **duplicate:** the same JPG twice in `b2` → one high finding; `("claim", 4) in ctx.skip_pages` (or the later page number); `labelled_text` lacks `claim page 4`.
  - **incomplete:** pages showing `Page 1 of 3` and `Page 2 of 3` only → medium, missing `3`.
  - **clean:** the clean multi-card case gives `[]`.
  - **survives Prove:** `prove()` keeps the duplicate finding for a text page, and for an empty image page via `source="metadata"`.
- [ ] **Step 2:** `.venv/bin/pytest tests/test_card_checks.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** `.venv/bin/pytest -q`. Expected: all pass, and the sample `EXPECTED` is unchanged.
- [ ] **Step 5: Commit** `feat(backend): card checks for split, mixed, duplicate and incomplete bills`.

### Task 6: Multi-card sample and end to end

**Files:**
- Modify: `backend/samples/make_example.py`
- Create:
  - `backend/samples/cards/{claim-form.pdf, discharge-summary.pdf, hospital-bill.pdf, pharmacy-bill.jpg}` (generated, committed)
  - `frontend/public/samples/` copies of those four, plus the existing `policy.pdf`
- Test: `backend/tests/test_pipeline.py` (append)

**Interfaces:**
- `make_example.py --cards` writes the 4 files from the **tampered** `claim.pdf`:
  - pages 1, 2 and 3 are saved as single-page PDFs **keeping the doc's metadata**, so `editing_tool` and `late_edit` still fire on the hospital bill;
  - page 4 is rendered at 150 dpi to JPG.
- The card layout for tests and the frontend sample:
  - `claim_form`: claim-form.pdf;
  - `b1` (hospital): hospital-bill.pdf;
  - `b2` (pharmacy): pharmacy-bill.jpg;
  - `supporting`: discharge-summary.pdf;
  - `policy`: policy.pdf.

- [ ] **Step 1: Write the failing test** `test_multi_card_sample_end_to_end`:
  - upload through `upload_case` with that layout (inline jobs and FakeAi, with fixture page numbers adjusted by an override `facts` folder `tests/fixtures/ai/cards/` that reflects the new stream order: claim form p1, bill p2, pharmacy p3, discharge p4);
  - READY, and the finding codes are a superset of `{font_outlier, hidden_text, editing_tool, sum_mismatch, name_mismatch, waiting_period, room_rent_limit}`;
  - no card-check codes;
  - `editing_tool` cites `claim p.2`.
- [ ] **Step 2:** Run. Expected: FAIL (no sample files).
- [ ] **Step 3: Generate** with `cd backend/samples && ../.venv/bin/python make_example.py --cards`, then copy the files to `frontend/public/samples/`. Write `tests/fixtures/ai/cards/{facts,policy,coverage,summary}.json`, with facts re-paged from `sample/` (the pharmacy bill on the JPG page has no text with OCR off, so its facts are dropped by grounding; the test accepts that).
- [ ] **Step 4:** `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: multi-card sample claim (pharmacy bill as a photo)`.

### Task 7: Infrastructure, deploy and Postman

**Files:**
- Create: `backend/infra/tasks.tf`
- Modify:
  - `backend/infra/apis.tf` (`cloudtasks.googleapis.com`), `backend/infra/outputs.tf`
  - `.github/workflows/ci-deploy.yml`, `backend/Makefile`
  - `backend/scripts/build_postman.py` and the regenerated `backend/postman/*.json`
  - `backend/.env.example`

**Interfaces:**
- **Terraform resources:**
  - `google_cloud_tasks_queue.jobs` (name `claimlens-jobs`, location `var.region`, rate/retry per Global Constraints);
  - `google_service_account.tasks` (`claimlens-tasks`);
  - `google_cloud_tasks_queue_iam_member` with `roles/cloudtasks.enqueuer` for `claimlens-api`;
  - `google_service_account_iam_member` with `roles/iam.serviceAccountUser` on `tasks`, for `claimlens-api`;
  - `google_cloud_run_service_iam_member` with `roles/run.invoker` for `tasks`, on service `claimlens-api` in `var.region`.
- **Outputs:** `tasks_queue`, `tasks_sa_email`.
- **Deploy env** (workflow and Makefile): `JOBS=cloudtasks##TASKS_QUEUE=claimlens-jobs##TASKS_LOCATION=asia-south1##TASKS_SA=claimlens-tasks@social-pulse-510513.iam.gserviceaccount.com##SERVICE_URL=https://claimlens-api-538594533263.asia-south1.run.app`, and `--timeout 1800`.
- **Smoke step:** add `test "$(curl -s -o /dev/null -w '%{http_code}' -X POST "$URL/internal/jobs/run_case")" = 403`.
- **Postman:** create draft → upload file (claim form) → upload file (policy) → submit → get.

- [ ] **Step 1:** `terraform -chdir=backend/infra fmt -check && terraform -chdir=backend/infra validate`. Expected: success.
- [ ] **Step 2:** `cd backend && .venv/bin/python scripts/build_postman.py`, then `python -m json.tool backend/postman/ClaimLens.postman_collection.json > /dev/null`. Expected: valid JSON with the 3-step flow.
- [ ] **Step 3: Commit** `infra: Cloud Tasks queue, tasks service account, deploy env`.
- **Do not apply.** `make infra-plan` / `infra-apply` happen in Task 11, after the user confirms.

### Task 8: Frontend API client and upload rules

**Files:**
- Modify: `frontend/src/api/types.ts`, `frontend/src/api/client.ts`, `frontend/src/lib/upload.ts`, `frontend/src/test/sampleCase.ts`
- Test: `frontend/src/api/client.test.ts`, `frontend/src/lib/upload.test.ts`

**Interfaces:**
- **Types:**
  - `CardRole`, `BillKind`;
  - `CardSpec {id: string; role: CardRole; kind: BillKind | null}`;
  - `CaseCard extends CardSpec {label: string; files: {name: string; pages: number}[]}`.
  - `Case` gains `cards: CaseCard[]`. `PageMeta` gains `card_id: string | null`. `Status` gains `"DRAFT"`.
- **Client:**
  - `createDraft(cards: CardSpec[]): Promise<{case_id: string}>`
  - `uploadFile(caseId, cardId, file): Promise<{card_id: string; index: number; pages: number}>`
  - `submit(caseId): Promise<{case_id: string; status: Status}>`
  - `createCase` is removed.
- **`lib/upload.ts`:**
  - `checkFile(file): string | null`: every card accepts pdf/jpg/jpeg/png. Messages: `"Must be a PDF, JPG or PNG"`, `"File is larger than 20 MB"`.
  - `checkCards(cards: DraftCard[]): string | null`: the spec §3 totals, client-side, minus page counts. Messages `"Add the policy"`, `"Add the claim documents"`, `"At most 40 files"`, `"At most 10 bills"`.
  - `DraftCard = CardSpec & {files: File[]}`
- **`sampleCase`** gains `cards` (two default cards) and `card_id` on pages.

- [ ] **Step 1: Write failing tests:**
  - **client** (stubbed `fetch`):
    - `createDraft` posts JSON;
    - `uploadFile` posts FormData with `card_id`;
    - `submit` posts to `/submit`.
  - **upload:** each `checkFile` and `checkCards` message.
- [ ] **Step 2:** `npx vitest run src/api src/lib/upload.test.ts`. Expected: FAIL.
- [ ] **Step 3:** Implement. Fix the `tsc -b` errors from the removed `createCase` (UploadPage is updated in Task 9; give it a temporary stub only if needed to compile, and remove it in Task 9).
- [ ] **Step 4:** `npx vitest run && npx tsc -b`. Expected: pass.
- [ ] **Step 5: Commit** `feat(frontend): card upload client and rules`.

### Task 9: Card upload UI

**Files:**
- Create: `frontend/src/components/CaseCards.tsx`, `CaseCards.test.tsx`, `frontend/src/lib/submitCase.ts`, `submitCase.test.ts`
- Modify: `frontend/src/pages/UploadPage.tsx`, `UploadPage.test.tsx`, `frontend/src/styles/app.css`
- Delete: `frontend/src/components/UploadTrays.tsx`

**Interfaces:**
- **`CaseCards({cards, onChange, busy, errors})`:**
  - **Starting cards:** `[claim_form "claim-form", bill "b1" hospital, supporting "supporting", policy "policy"]`.
  - **Bill buttons:** **+ Add bill** gives the next id `b<n>` (disabled at 10). **Remove bill** is on bill cards only.
  - **File list:** ▲ ▼ ✕ per file, using accessible names `Move <file> up`, `Move <file> down` and `Remove <file>`.
  - **Bill kind:** a `<select>` labelled `Kind of Bill <n>`.
  - **Drop zones:** each card's zone takes multiple files (`input multiple`).
- **`submitCase(client, cards, state, onProgress) -> Promise<string>`** (returns the case id):
  - `state: {caseId?: string; uploaded: Set<File>}` is kept by `UploadPage` between attempts.
  - It creates the draft once, uploads only the files not yet in `uploaded` (in card order, then file order), then submits.
  - `onProgress(done, total)` is called as files finish.
  - On a failed file it throws `{file, message}`.
- **`UploadPage`:**
  - **Open case:** calls `askPermission()`, then `submitCase`. The button text is `Uploading <done> of <total>…`. On success it calls `track(id)` and navigates.
  - **On error:** shows the message under that file and keeps the state for a retry.
- **Try the sample:** fetches the 5 sample files into the card layout from Task 6, then uses the same flow.

- [ ] **Step 1: Write failing tests:**
  - `CaseCards`:
    - add bills up to 10, then the button is disabled;
    - remove Bill 2, and the labels renumber;
    - reorder and remove files;
    - the kind dropdown changes `kind`.
  - `submitCase`:
    - the call order is `createDraft`, uploads (in order), `submit`;
    - when `uploadFile` throws on file 3, a second call with the same `state` uploads only file 3 onward and does not call `createDraft` again.
  - `UploadPage`:
    - the sample puts 5 files in the right cards;
    - the progress text shows;
    - an error message appears under the failed file.
- [ ] **Step 2:** `npx vitest run src/components/CaseCards.test.tsx src/lib/submitCase.test.ts src/pages/UploadPage.test.tsx`. Expected: FAIL.
- [ ] **Step 3:** Implement. Card styling reuses the tray look (`.tray`) in a responsive grid; one column under 720 px.
- [ ] **Step 4:** `npx vitest run && npm run build`. Expected: pass.
- [ ] **Step 5: Commit** `feat(frontend): upload a claim as cards of files`.

### Task 10: Viewer grouped by card, bill labels in the context panel

**Files:**
- Modify: `frontend/src/components/PageViewer.tsx`, `frontend/src/components/CaseContext.tsx`, `frontend/src/pages/CasePage.tsx`, `frontend/src/styles/app.css`
- Test: `frontend/src/components/PageViewer.test.tsx` (create), `CaseContext.test.tsx`

**Interfaces:**
- **`PageViewer`** gains `cards: CaseCard[]`. Its thumbs are grouped under a small heading per card (`card.label`) for the current doc. Pages with `card_id=null` (old cases) are grouped under `Claim` / `Policy`.
- **`CaseContext`:** the bill line reads `<card label> ₹<total>` when the bill dict has `card`, and falls back to `kind`.

- [ ] **Step 1: Write failing tests:**
  - **grouping:** a 3-card claim stream renders the headings `Claim form`, `Bill 1 · hospital` and `Bill 2 · pharmacy`, with page buttons under each;
  - **old case:** a case without cards renders one `Claim` group;
  - **bill label:** the context bill line shows `Bill 2 · pharmacy ₹3,000`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** `npx vitest run && npm run build`. Expected: pass.
- [ ] **Step 5: Commit** `feat(frontend): page strip grouped by card`.

### Task 11: Verify locally, apply infra, deploy, verify on prod

- [ ] **Step 1:** Run both suites and the build. Expected: green.
- [ ] **Step 2: Local browser check** (`JOBS=thread`, real Gemini):
  - **Try the sample:** READY, with thumbs grouped by card.
  - **Duplicate photo:** add the pharmacy JPG twice in Bill 2 → `duplicate_page_image`.
  - **Retry:** a forced failure (rename a file to `.docx` after picking it) shows its error, and a retry uploads only the rest.
- [ ] **Step 3: Infra.** Ask the user, then run `make infra-plan`, show the plan summary, and `make infra-apply` on approval.
- [ ] **Step 4: Deploy.** Merge to main and push. Watch the run, including the new 403 smoke check.
- [ ] **Step 5: Prod check:**
  - **Sample:** the sample on prod reaches READY.
  - **Task route:** Cloud Logging shows `jsonPayload.user="tasks:run_case"` with a 200 on `/internal/jobs/run_case`.
  - **Old case:** an old case still opens.

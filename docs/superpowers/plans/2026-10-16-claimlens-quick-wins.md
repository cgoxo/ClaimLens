# ClaimLens quick wins implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Log who calls the API. Show the claim and policy context early. Show detailed progress. Notify the browser when a case finishes, and mark cases that finished while the user was away.

**Architecture:**
- **Backend:** a JSON request-log middleware. Three new case fields: `context` (saved right after Extract), `progress` (throttled writes from the pipeline) and `finished_at`/`seen_at`. One new story check.
- **Frontend:**
  - a `CaseContext` panel and a `Progress` component on the case page;
  - an app-wide `CaseWatcherProvider` that polls `/api/cases` while anything is running and fires browser notifications or toasts.

**Tech Stack:** Python 3.12, FastAPI, pydantic, pytest · React 18, TypeScript, Vite, Vitest, Testing Library.

**Spec:** `docs/superpowers/specs/2026-10-16-claimlens-quick-wins-design.md`

## Global Constraints

- Backend tests: `cd backend && .venv/bin/pytest -q`. The baseline is **98 passed**, and no existing test may break.
- Frontend tests: `cd frontend && npx vitest run`. The baseline is **48 passed**. `npm run build` must succeed (it runs `tsc -b`).
- The existing sample's expected findings (`tests/test_pipeline.py::EXPECTED`) do not change. The sample's policy numbers match, so `policy_number_mismatch` must not fire on it.
- Logged fields are exactly `severity, message, user, method, path, status, latency_ms, case_id`. `/health` and non-`/api/` paths are never logged.
- `severity` is `INFO` for status < 400, `WARNING` for 4xx and `ERROR` for 5xx.
- JSON log format only when `APP_ENV=prod`. Local runs keep plain text.
- Progress writes: at most **1 per second** within a step. A step change and the last page always write.
- Watcher poll: **5 s**, only while some case is `QUEUED|READING|CHECKING|PROVING`. The case page keeps its own 2 s poll.
- The "Still working. Large scans take longer." note appears after **60 s** without a change in `progress`.
- Toast lasts **6 s**.
- Notification text: `Case <id> ready: <RISK> risk, <n> findings` or `Case <id> failed`.
- Missing context value copy: `Not found in documents`.
- New finding: code `policy_number_mismatch`, check `story`, severity `high`, title `Claim names policy <X>, but the uploaded policy is <Y>`.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Policy numbers that differ only in formatting** (`EH-2025-778812` vs `EH 2025/778812`) must not be flagged. Pinned in Task 3.
2. **A case that fails mid-Read** must clear `progress` and set `finished_at`, or the UI shows a frozen bar forever. Pinned in Task 4.
3. **Re-opening a seen case** must not write to the DB on every 2 s poll. Pinned in Task 5.
4. **Notification permission denied, or the Notification API missing** (Safari private mode, jsdom) must not throw, and must fall back to a toast. Pinned in Task 8.
5. **Two cases finishing in the same poll** must give two notifications, and a case already READY on first load must give none. Pinned in Task 9.

---

### Task 1: Request and pipeline logging with the caller

**Files:**
- Create: `backend/claimlens/logs.py`
- Modify: `backend/claimlens/main.py`, `backend/claimlens/auth.py`, `backend/claimlens/pipeline/run.py`
- Test: `backend/tests/test_logs.py`

**Interfaces:**
- Produces:
  - `logs.setup(app_env: str) -> None`. In prod, it installs a `JsonFormatter` on the root logger. A record's `extra` keys `user, method, path, status, latency_ms, case_id` become top-level JSON fields, and `severity` comes from the level name.
  - `logs.case_logger(case_id: str, user: str | None) -> logging.LoggerAdapter`
  - `request.state.user: str`, set in `current_user()`.

- [ ] **Step 1: Write failing tests** in `tests/test_logs.py`, using the `client` fixture pattern from `test_api.py` and `caplog`:
  - `test_api_request_logged_with_user`: GET `/api/me` with `A`. Exactly one record from logger `claimlens.request` with `record.user == "a@x.com"`, `record.status == 200`, `record.path == "/api/me"`, `record.method == "GET"`, an int `latency_ms`, and `record.case_id is None`.
  - `test_case_id_extracted`: GET `/api/cases/nope` gives a record with `case_id == "nope"`, `status == 404` and level WARNING.
  - `test_unauthenticated_logs_null_user`: GET `/api/me` without a header gives `user is None` and `status == 401`.
  - `test_health_and_static_not_logged`: GET `/health` gives no `claimlens.request` records.
  - `test_json_formatter`: format a record with extras through `logs.JsonFormatter()`, then `json.loads` it. The keys `severity, message, user, status` are present, and `severity == "WARNING"` for a WARNING record.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_logs.py -v`. Expected: FAIL (`claimlens.logs` not found or no records).
- [ ] **Step 3: Implement.**
  - `logs.py` holds `JsonFormatter`, `setup` and `case_logger`.
  - `main.create_app` calls `logs.setup(settings.app_env)` in place of `logging.basicConfig`.
  - Add an `@app.middleware("http")`: skip unless `request.url.path.startswith("/api/")`. Time the call with `time.perf_counter`. Read `getattr(request.state, "user", None)`. Get `case_id` from the path with `re.match(r"/api/cases/([^/]+)", path)`. Log on `logging.getLogger("claimlens.request")` at the level for the status.
  - In `auth.current_user`, set `request.state.user = email` before both returns.
- [ ] **Step 4:** In `run.py`, replace the module `log` usage inside `run_pipeline` with `log = case_logger(case_id, case.owner_email if case else None)` after fetching the case. The existing `log.exception("case %s failed during %s", ...)` must still fire when `get_case` itself throws, so fall back to the module logger.
- [ ] **Step 5: Run** `.venv/bin/pytest -q`. Expected: all pass (98 + 5).
- [ ] **Step 6: Commit** `feat(backend): log calling user per API request as structured JSON`.

### Task 2: Case context (new facts, saved after Extract)

**Files:**
- Modify:
  - `backend/claimlens/models.py`
  - `backend/claimlens/ai.py` (`FACTS_PROMPT`, `POLICY_PROMPT`)
  - `backend/claimlens/pipeline/text.py`
  - `backend/claimlens/pipeline/checks/coverage.py`
  - `backend/claimlens/pipeline/run.py`
  - `backend/tests/fixtures/ai/sample/facts.json`, `policy.json`
- Test: `backend/tests/test_context.py`

**Interfaces:**
- Produces:
  - `ClaimFacts.hospital_name: Fact | None = None`
  - `PolicyFacts.insurer_name: Fact | None = None`
  - `text.months_between(a: date, b: date) -> int`, moved verbatim from `coverage.py`, which now imports it.
  - `Case.context: dict | None = None`
  - `pipeline.context_of(ctx: Ctx) -> dict`, which returns `{"claim": dict | None, "policy": dict | None, "policy_age_months": int | None}`. It lives in `run.py`.
  - The facts dicts are `model_dump(mode="json", exclude_none=True)`.

- [ ] **Step 1: Fixtures.**
  - `facts.json` gains `"hospital_name": {"value": "Sunrise Eye & General Hospital, Pune", "page": 1, "quote": "Sunrise Eye & General Hospital, Pune"}`.
  - `policy.json` gains `"insurer_name": {"value": "Example Health Insurance Co.", "page": 1, "quote": "Example Health Insurance Co."}`.
  - Both quotes are verified to be on page 1 of the sample PDFs.
- [ ] **Step 2: Write failing tests** in `tests/test_context.py`:
  - `test_new_facts_grounded(ctx)`: `ctx.claim_facts.hospital_name.value == "Sunrise Eye & General Hospital, Pune"` with a bbox that is not None. `ctx.policy_facts.insurer_name.page == 1`.
  - `test_fabricated_hospital_dropped(tmp_path)`: a FakeAi subclass whose `extract_facts` sets `hospital_name` with quote `"Apollo Hospital"`. After `extract`, `hospital_name is None`.
  - `test_context_of_sample(ctx)`:
    - `context_of(ctx)["policy_age_months"] == 2` (01-Jan-2026 to procedure 11-Mar-2026);
    - `["claim"]["policy_number"]["value"] == "EH-2025-778812"`;
    - `["policy"]["insurer_name"]["page"] == 1`.
  - `test_context_saved_before_checks(tmp_path, monkeypatch)`: monkeypatch `claimlens.pipeline.run.ALL_CHECKS` to `[spy]`, where `spy(ctx)` records `ctx.deps.db.get_case("c1").context` and returns `[]`. After `run_pipeline`, the recorded value is not None and has key `"claim"`. Reuse `_deps` and `_new_case` from `test_pipeline.py`.
  - `test_context_none_when_no_dates`: a `context_of` on a Ctx whose policy facts have no `start_date` gives `policy_age_months is None`.
- [ ] **Step 3: Run** `.venv/bin/pytest tests/test_context.py -v`. Expected: FAIL.
- [ ] **Step 4: Implement.**
  - Add the model fields.
  - Add one prompt line each:
    - `` - `hospital_name`: the hospital's name as printed. ``
    - `` - `insurer_name`: the insurance company's name as printed. ``
  - Move `months_between`.
  - Add `context_of`. The treated date uses the same rule as `_waiting_periods`: the first procedure date, else admission.
  - In `run_pipeline`, right after `extract(ctx)`, call `db.update_case(case_id, context=context_of(ctx))`.
- [ ] **Step 5: Run** `.venv/bin/pytest -q`. Expected: all pass. `test_sample_end_to_end` is unchanged.
- [ ] **Step 6: Commit** `feat(backend): extract hospital and insurer, save case context after Extract`.

### Task 3: `policy_number_mismatch` story check

**Files:**
- Modify: `backend/claimlens/pipeline/checks/story.py`
- Test: `backend/tests/test_story_duplicate.py` (append)

**Interfaces:**
- Consumes: `ctx.claim_facts.policy_number`, `ctx.policy_facts.policy_number` (both `Fact | None`).
- Produces: `_policy_number_mismatch(ctx) -> list[Finding]`, appended to `check_story`'s result.
  - The finding id is `policy_number_mismatch-claim-<claim page>-1`.
  - Citations are the claim fact via `_cite`, then `Citation(doc="policy", page=..., quote=..., bbox=...)`.

- [ ] **Step 1: Write failing tests.** Each builds facts by `model_copy` on the `ctx` fixture's grounded facts:
  - `test_policy_number_match_no_finding(ctx)`: the sample gives no `policy_number_mismatch`.
  - `test_policy_number_formatting_ignored(ctx)`: set the policy value to `"EH 2025/778812"`. No finding.
  - `test_policy_number_mismatch(ctx)`: set the policy value to `"EH-2024-000001"`. One finding with severity `high` and title `"Claim names policy EH-2025-778812, but the uploaded policy is EH-2024-000001"`. `[c.doc for c in citations] == ["claim", "policy"]`.
  - `test_policy_number_missing_skips(ctx)`: set `policy_facts.policy_number = None`. No finding.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_story_duplicate.py -v`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement.** Compare with `re.sub(r"[^A-Z0-9]", "", str(v).upper())`. Detail text: `"The claim form and the policy document carry different policy numbers."`
- [ ] **Step 4: Run** `.venv/bin/pytest -q`. Expected: all pass. `prove` keeps the finding because both quotes are real.
- [ ] **Step 5: Commit** `feat(backend): flag claim/policy policy-number mismatch`.

### Task 4: Progress and `finished_at`

**Files:**
- Modify: `backend/claimlens/models.py`, `backend/claimlens/pipeline/read.py`, `backend/claimlens/pipeline/run.py`, `backend/claimlens/api.py` (stale path)
- Test: `backend/tests/test_progress.py`

**Interfaces:**
- Produces:
  - `Case.progress: dict | None = None`
  - `Case.finished_at: datetime | None = None`
  - `read_document(..., on_page: Callable[[str, int, str], None] | None = None)`: called after each page with `(doc, n, kind)`.
  - `class Progress` in `run.py`, created as `Progress(db, case_id, clock=time.monotonic)` and used through:
    - `Progress.step(step: str, label: str, total: int = 0) -> None`: always writes, and resets `done` to 0.
    - `Progress.tick(label: str, done: int, force: bool = False) -> None`: writes only if `force` or at least 1.0 s since the last write.
    - It writes `progress={"step", "done", "total", "label"}`.

- [ ] **Step 1: Write failing tests** in `tests/test_progress.py`:
  - `test_throttle`: a fake clock returning 0.0, 0.2, 0.4, 1.5. With a recording fake db, `step(...)` plus three `tick`s gives writes at step, (skip), (skip), and tick@1.5. That's 2 writes total. `tick(..., force=True)` always writes.
  - `test_on_page_called_per_page(tmp_path)`: `read_document` on `samples/claim.pdf` with a list-appending callback gives `[("claim", 1, "digital"), ..., ("claim", 4, "digital")]`.
  - `test_progress_labels_and_cleared(tmp_path)`: wrap `LocalDb.update_case` to record every `progress` value during `run_pipeline` on the sample.
    - Labels include `"Reading claim page 1 (1 of 7)"`, `"Reading policy page 3 (7 of 7)"` (the last page is forced), `"Extracting facts with Gemini"`, `"Checking: tamper"` and `"Checking coverage with Gemini"`.
    - Final case: `progress is None` and `finished_at is not None`.
  - `test_failed_mid_read_clears_progress(tmp_path)`: an OCR or storage stub raising on the policy file gives `status == "FAILED"`, `progress is None` and `finished_at` set.
  - `test_stale_sets_finished_at` (api): create a case with status `READING` and `updated_at` 20 min ago, then GET it. The response has `status == "FAILED"` and a non-null `finished_at`.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_progress.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
  - **Read:** the total page count comes from opening each file with `open_document` once before reading. Read labels are `Reading <doc> page <p> (<n> of <total>)` for digital pages and `OCR on <doc> page <p> (<n> of <total>)` otherwise. `p` is the page within its file; `n` (also written as `done`) counts across both files.
  - **Check:** labels are `Extracting facts with Gemini`, then `Checking: <tamper|story|duplicate|coverage>` with `done/total=4`, where the coverage one is labelled `Checking coverage with Gemini`. Iterate `ALL_CHECKS` with `check.__name__.removeprefix("check_")`.
  - **Prove / Report:** `Proving findings`.
  - **Finish:** READY and FAILED updates pass `progress=None, finished_at=now()`. The stale path in `api.get_case` passes `finished_at=now()`.
- [ ] **Step 4: Run** `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(backend): per-page progress and finished_at on cases`.

### Task 5: Seen and unseen

**Files:**
- Modify: `backend/claimlens/models.py`, `backend/claimlens/api.py`
- Test: `backend/tests/test_api.py` (append)

**Interfaces:**
- Produces:
  - `Case.seen_at: datetime | None = None`
  - `Case.findings_count: int | None = None`, set by `run.py` in the READY update to `len(kept)`.
  - `GET /api/cases` rows gain `"unseen": bool`, plus `progress` and `findings_count`.
  - The rule is `unseen = status in {"READY","FAILED"} and finished_at is not None and (seen_at is None or seen_at < finished_at)`.
  - `GET /api/cases/{id}` sets `seen_at=now()` only when that rule is true at read time.

- [ ] **Step 1: Write failing tests:**
  - `test_unseen_until_opened(client)`: upload. The list shows `unseen is True`. GET the case, after which the list shows `unseen is False`.
  - `test_second_get_does_not_write(client, monkeypatch)`: after the first GET, wrap `deps.db.update_case` with a counter. A second GET makes 0 calls.
  - `test_list_has_findings_count(client)`: after the sample upload, the list row has `findings_count == 9`.
  - `test_running_case_not_unseen`: a case created with status `CHECKING` gives `unseen is False`, and a GET does not set `seen_at`.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_api.py -v`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement** a helper `_unseen(case: Case) -> bool` in `api.py`, used by both endpoints. The list `include` set gains `progress` and `findings_count`.
- [ ] **Step 4: Run** `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(backend): track seen cases and report unseen in the case list`.

### Task 6: Frontend types and the `Progress` component

**Files:**
- Modify: `frontend/src/api/types.ts`, `frontend/src/test/sampleCase.ts`, `frontend/src/pages/CasePage.tsx`
- Create: `frontend/src/components/Progress.tsx`, `frontend/src/components/Progress.test.tsx`

**Interfaces:**
- Produces:
  - `interface Fact { value: string | number | null; page: number; quote: string; bbox: BBox | null }`
  - `interface CaseProgress { step: Status; done: number; total: number; label: string }`
  - `interface CaseContextData { claim: Record<string, unknown> | null; policy: Record<string, unknown> | null; policy_age_months: number | null }`
  - `Case` gains `context: CaseContextData | null`, `progress: CaseProgress | null`, `finished_at: string | null` and `seen_at: string | null`.
  - `CaseSummary` gains `unseen: boolean`, `progress: CaseProgress | null` and `findings_count: number | null`.
  - `Progress({ status, progress }: { status: Status; progress: CaseProgress | null })`

- [ ] **Step 1:** Update the types. `sampleCase` gains a `context` built from the backend fixtures (hospital, insurer and the policy number included), plus `progress: null`, `finished_at` and `seen_at`. Update other fixtures until `npx tsc -b` passes.
- [ ] **Step 2: Write failing tests** in `Progress.test.tsx`:
  - **Label and bar:** given progress `{step:"READING",done:3,total:7,label:"Reading claim page 3 (3 of 7)"}`, the label text shows, and `role="progressbar"` has `aria-valuenow=3` and `aria-valuemax=7`.
  - **Indeterminate:** with `total: 0`, the progressbar has no `aria-valuenow`.
  - **Still-working note:** with `vi.useFakeTimers()`, render, then advance 60_000 ms. `"Still working. Large scans take longer."` is visible. Re-rendering with a different label hides it.
  - **Stepper:** still marks the current step with `aria-current="step"`.
- [ ] **Step 3: Run** `npx vitest run src/components/Progress.test.tsx`. Expected: FAIL.
- [ ] **Step 4: Implement.** Move the stepper out of `CasePage.tsx` into `Progress.tsx`, and pass `data.progress` from `CasePage`. Track the last label change with `useEffect` and a 60 s `setTimeout`.
- [ ] **Step 5: Run** `npx vitest run`. Expected: all pass.
- [ ] **Step 6: Commit** `feat(frontend): detailed progress bar with page counts`.

### Task 7: Context panel and the running-dossier layout

**Files:**
- Create: `frontend/src/components/CaseContext.tsx`, `frontend/src/components/CaseContext.test.tsx`
- Modify: `frontend/src/pages/CasePage.tsx`, `frontend/src/pages/CasePage.test.tsx`, `frontend/src/styles/app.css`

**Interfaces:**
- Consumes: `CaseContextData`, `Fact` (Task 6).
- Produces:
  - `CaseContext({ context, mismatch, onOpen }: { context: CaseContextData; mismatch: boolean; onOpen(c: Citation): void })`. `onOpen` receives `{doc, page, quote, bbox, source: "page"}`.
  - `CasePage` keeps one selection, `{ citation: Citation; number: number | null; detail: string } | null`, set by either a finding or `onOpen`, and passes it to `PageViewer`.
  - Context selections use `number: null`, and `detail` is the quote.

- [ ] **Step 1: Write failing tests** in `CaseContext.test.tsx`:
  - **Full sample:** renders headings "The claim" and "The policy". Shows `Sunrise Eye & General Hospital, Pune`, `Example Health Insurance Co.`, `EH-2025-778812` twice, `Cataract · 24 months · clause 3.2`, and `Policy age at treatment` with `2 months`.
  - **Missing field:** with `claim.diagnosis` deleted, the Diagnosis row reads `Not found in documents`.
  - **Page link:** clicking the link `Hospital, claim page 1` calls `onOpen` with `{doc:"claim", page:1, quote:"Sunrise Eye & General Hospital, Pune", bbox: <fixture bbox>, source:"page"}`.
  - **Mismatch styling:** with `mismatch: true`, both policy-number rows have class `is-warning`.
- [ ] **Step 2: Add failing tests** in `CasePage.test.tsx`:
  - **While running:** a case with `status:"CHECKING"`, `pages` set, `context` set and `findings: []` shows the progress label, the "The claim" heading and the document viewer tabs.
  - **When READY:** clicking the `Diagnosis, claim page 2` link makes `claim page 2` thumb `aria-current="true"`.
- [ ] **Step 3: Run** `npx vitest run src/components/CaseContext.test.tsx src/pages/CasePage.test.tsx`. Expected: the new tests FAIL.
- [ ] **Step 4: Implement.**
  - Rows follow the spec §5 table. A link's accessible name is `<Label>, <doc> page <n>`.
  - Money uses the existing `money()` from `CasePage`. Move it to `lib/format.ts` and import it in both places.
  - `mismatch = findings.some(f => f.code === "policy_number_mismatch")`.
  - **Layout:**
    - running and `pages.length > 0`: dossier with left = `Progress` + `CaseContext`;
    - running with no pages: `Progress` only;
    - READY: `CaseContext` after the summary.
  - **CSS:** two cards in a grid, one column under 720 px. `.is-warning` uses the existing warning ink token.
- [ ] **Step 5: Run** `npx vitest run`. Expected: all pass.
- [ ] **Step 6: Commit** `feat(frontend): claim and policy context panel with page links`.

### Task 8: Notify helper and toasts

**Files:**
- Create:
  - `frontend/src/lib/notify.ts`, `frontend/src/lib/notify.test.ts`
  - `frontend/src/components/Toast.tsx`, `frontend/src/components/Toast.test.tsx`

**Interfaces:**
- Produces:
  - `askPermission(): void`: safe when `Notification` is undefined, and only asks when the permission is `"default"`.
  - `finishedText(c: CaseSummary): string`. Gives `Case <id> ready: <RISK> risk, <n> findings` (using `findings_count`) or `Case <id> failed`.
  - `notifyFinished(c, onClick: () => void): boolean`. Returns true only if a system notification was shown, which requires `document.visibilityState === "hidden"` and `Notification.permission === "granted"`. It never throws.
  - `ToastProvider`, plus `useToast(): (text: string, onClick?: () => void) => void`. Each toast lasts 6 s.

- [ ] **Step 1: Write failing tests** (stub `globalThis.Notification` with `vi.stubGlobal`):
  - **Hidden tab, permission granted:** constructs one Notification with the text and returns true. Its `onclick` calls `onClick`.
  - **Visible tab:** returns false, and no Notification is constructed.
  - **Permission denied:** returns false.
  - **API missing:** `Notification` undefined returns false and doesn't throw. `askPermission()` doesn't throw either.
  - **Toast:** shows the text, and disappears after `vi.advanceTimersByTime(6000)`.
- [ ] **Step 2: Run** `npx vitest run src/lib/notify.test.ts src/components/Toast.test.tsx`. Expected: FAIL.
- [ ] **Step 3: Implement** both. Mount `ToastProvider` in `App.tsx`, outside `Routes`.
- [ ] **Step 4: Run** `npx vitest run`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(frontend): browser notification helper and toasts`.

### Task 9: Case watcher, live case list, tab title

**Files:**
- Create: `frontend/src/hooks/useCaseWatcher.tsx` (holds `CaseWatcherProvider` and `useCaseWatcher`), `frontend/src/hooks/useCaseWatcher.test.tsx`
- Modify:
  - `frontend/src/App.tsx`
  - `frontend/src/pages/UploadPage.tsx`, `frontend/src/pages/UploadPage.test.tsx`
  - `frontend/src/components/CaseTable.tsx`
  - `frontend/src/styles/app.css`

**Interfaces:**
- Consumes: `notifyFinished`, `finishedText`, `askPermission`, `useToast` (Task 8). `client.listCases()`.
- Produces:
  - `useCaseWatcher(): { cases: CaseSummary[]; track(id: string): void; refresh(): Promise<void> }`
  - `CaseWatcherProvider({ children, intervalMs = 5000 })`. It's mounted in `App.tsx` inside `BrowserRouter`, wrapping `Routes`. It's inert unless `useAuth().status === "signedIn"`.

- [ ] **Step 1: Write failing tests** (fake timers, fake client):
  - **Polls while running:** the first list has one `CHECKING` case. Advancing 5000 ms makes a second call. Once that case turns READY, advancing another 15000 ms adds no calls.
  - **Notifies on finish:** a READY transition calls `notifyFinished` once (mock `../lib/notify`). With `notifyFinished` returning false, a toast with the same text shows instead.
  - **Nothing on first load:** a case already READY gives no notification and no toast.
  - **Two at once:** two cases turning READY in the same poll give two notifications.
  - **`track` wakes it:** with everything READY, polling stops. `track("new1")` triggers an immediate `listCases` call and resumes polling.
  - **Tab title:** with two `unseen` cases, `document.title === "(2) ClaimLens"`. With none, it's `"ClaimLens"`.
- [ ] **Step 2: Add failing tests** for `CaseTable` and `UploadPage`:
  - **New dot:** a case with `unseen: true` shows an element with `aria-label="new"`.
  - **Live chip:** a `READING` case with progress shows `Reading…`.
  - **Open case:** a submit calls `askPermission` and `track(<case_id>)`.
- [ ] **Step 3: Run** `npx vitest run src/hooks src/pages/UploadPage.test.tsx src/components`. Expected: FAIL.
- [ ] **Step 4: Implement.**
  - The provider keeps the previous status per id in a `useRef<Map>`, and tracks notified ids in a `Set`.
  - On each list it compares running → final for every id it saw running before.
  - Clicking a notification or toast runs `window.focus()` and `navigate(\`/cases/${id}\`)`.
  - `UploadPage` uses `useCaseWatcher().cases` instead of its own `listCases` effect, and calls `refresh()` on mount.
  - `CaseTable` status cell: running statuses render `<span class="chip">Reading…</span>` (the capitalised status plus "…"). Add `<span class="new-dot" aria-label="new">` before the id when `unseen`.
- [ ] **Step 5: Run** `npx vitest run && npm run build`. Expected: all pass, and the build succeeds.
- [ ] **Step 6: Commit** `feat(frontend): app-wide case watcher with notifications, live list and unseen badges`.

### Task 10: End-to-end verification

**Files:** none (fix-ups only, if something fails)

- [ ] **Step 1: Run** `cd backend && .venv/bin/pytest -q` and `cd frontend && npx vitest run && npm run build`. Expected: all green.
- [ ] **Step 2: Local browser check** with `cd backend && make dev`, in Chrome at `http://localhost:5173`:
  - Dev sign-in, then **Try the sample**. Allow notifications.
  - The progress label counts pages. The context panel appears while CHECKING. Every ↗ opens the right page.
  - Switch to another tab before READY: a system notification shows, and clicking it opens the case.
  - Back on `/`, the case first showed the new dot, which cleared after opening the case.
  - The backend console shows request log lines with the user.
- [ ] **Step 3: Record results** in the PR description: test counts and what the browser check showed.
- [ ] **Step 4: Cloud check after deploy:** in Logs Explorer, `resource.labels.service_name="claimlens-api" jsonPayload.user="<email>"` returns your requests.

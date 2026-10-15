# ClaimLens multi-file cases and job queue: design

Date: 2026-10-16 · Status: approved in chat, awaiting written-spec review

Sub-project **B** of five (A quick wins: live · **B multi-file + job queue** · C pixel forensics · D chat · E evaluation). It builds on the backend, frontend and quick-wins designs.

## 1. Goal and success criteria

**Goal.** One case is one claim made of many files, grouped by the user into **cards**: claim form, one card per bill (a bill may span several images), supporting documents, and the policy. Any card takes PDF, JPG or PNG. Each bill is checked on its own and against the others. Grouping mistakes surface as findings. Analysis runs through a **job queue** that survives restarts and can take new job kinds later.

**Done when:**
1. `pytest`, `npx vitest run` and `npm run build` pass, including the tests in §10.
2. **Local check** (thread runner): **Try the sample** uploads the multi-card sample (5 files, with the pharmacy bill as a JPG).
   - The case reaches READY with the expected findings (§8).
   - The page strip shows the cards.
   - Re-running the sample with the same photo added twice gives `duplicate_page_image`.
3. **Prod check** (Cloud Tasks runner): the same flow works on Cloud Run.
   - Cloud Logging shows the task hitting `/internal/jobs/run_case`.
   - Calling that endpoint without a valid task token returns 403.
4. **Old cases** (single claim and policy file) still open and display.

**Out of scope:** discharge-summary-vs-bill cross-checks (deferred to E), byte-level upload progress, editing a case after submit, drag-to-reorder between cards.

## 2. Model

```
Card    { id: str, role: "claim_form" | "bill" | "supporting" | "policy",
          kind: "hospital" | "pharmacy" | "lab" | "other" | None,   # bills only
          files: [CaseFile] }                                        # in page order
CaseFile{ key: str, name: str, content_type: str, pages: int }
Case    + cards: list[Card] = []      (Case.files stays for old cases)
        + status gains "DRAFT"
PageInfo+ card_id: str | None, file_index: int, file_page: int
FileInfo+ card_id: str | None, key: str, first_page: int     # one per uploaded file
```

- **Two streams, as today.** Every page belongs to the **claim** stream (claim_form, bill and supporting cards) or the **policy** stream (the policy card). Pages are numbered continuously within a stream, ordered by card (claim_form, then bills in card order, then supporting) and then by file order. Citations stay `claim p.N` / `policy p.N`, so every existing check works unchanged.
- **Bills link to cards through pages.** A bill is tied to its card through `bill.page`.
- **Old cases.** `cards_of(case)` turns an old `files` dict into one `claim_form` card and one `policy` card, so old cases flow through the same code.
- **Card labels** come from code, never the AI: `Claim form`, `Bill 2 · pharmacy`, `Supporting documents`, `Policy`.

## 3. Upload API (one file per request)

Cloud Run rejects request bodies over 32 MB, so files go up one at a time.

| Endpoint | Does |
| --- | --- |
| `POST /api/cases` (JSON `{cards: [{id, role, kind}]}`) | Checks the card layout and the daily limit, then creates a `DRAFT` case. Returns `{case_id, status: "DRAFT"}` |
| `POST /api/cases/{id}/files` (multipart: `card_id`, `file`) | Draft only. Checks the type, the size (≤ 20 MB) and that the file opens (`_validated`). Stores it at `cases/{id}/{card_id}/{n}.{ext}` and appends it to the card. Returns `{card_id, index, pages}` |
| `POST /api/cases/{id}/submit` | Draft only. Checks the totals, sets status `QUEUED` and enqueues `run_case` |

**Rules:**
- **Card layout:**
  - exactly one `policy` card;
  - at most one `claim_form` card and at most one `supporting` card;
  - 0–10 `bill` cards, each with a `kind`;
  - card ids must be unique, of the form `[a-z0-9-]{1,32}`.
- **Totals at submit:**
  - the policy card has at least 1 file;
  - claim-side cards hold at least 1 file in total;
  - at most **40** files and **80** pages in total;
  - empty cards are dropped.
- **Settings:** `max_files = 40`, `max_pages = 80`, `max_bill_cards = 10`.
- **Lists:** `GET /api/cases` hides `DRAFT` cases.
- **Daily limit:** counted at create, as today.
- **Removed:** the old two-file `POST /api/cases` multipart form goes away. The frontend is the only client, and the Postman collection is updated.

## 4. Pipeline changes

- **Read.** For each stream, read cards in order, then files in order. `read_document` gains `start_page` and `card_id`, and tags pages and FileInfo.
  - Metadata (producer, dates, `%%EOF` count) is read **per file**, so the tamper checks (`editing_tool`, `late_edit`, `multiple_saves`) flag the specific file and cite its first page.
  - Progress labels gain the card: `OCR on Bill 2 · pharmacy, page 1 (5 of 9)`.
- **Locating a quote's PDF page.** `extract._pdf` maps a stream page to `(file key, file_page)` through PageInfo, so `search_for` opens the right file.
- **What Gemini sees.** Each page header carries its card: `=== claim page 5 · Bill 2 (pharmacy) ===`. The prompt adds one rule: *a bill never spans two cards; report each bill's first page*.
- **Duplicate pages.** Pages flagged by `duplicate_page_image` are **left out of the text sent to Gemini**, so a repeated bill is never added up twice. They stay viewable.

## 5. New checks (`pipeline/checks/cards.py`)

| Code | Severity | Rule | Cites |
| --- | --- | --- | --- |
| `bill_split_across_cards` | high | The same invoice key (`invoice_key`) on bills in two different cards | Both bills' invoice numbers |
| `mixed_bill_in_card` | medium | One bill card holds bills with two or more different invoice keys | Each invoice number |
| `duplicate_page_image` | high | Two claim-stream pages whose 64-bit dHash differs in 4 bits or fewer. The later page is the duplicate | The later page (`source="page"`, quote = its first line); detail names the earlier page |
| `incomplete_bill` | medium | Within a bill card, the text shows `page n of m` and some page in 1..m is missing | The card's first page |

**dHash.** Render the page with PyMuPDF at 9×8 in greyscale, then compare each pixel with its right neighbour. No new dependency. The hashes are computed in Read from the pixmap that is already rendered.

`check_cards` is added to `ALL_CHECKS`. Its findings go through Prove like every other check. `duplicate_page_image` cites the duplicate page with `source="page"` and the page's first visible line as the quote, so Prove can find it (photos need OCR on; with OCR off, an unreadable duplicate page is cited with `source="metadata"`).

## 6. Job queue (`claimlens/jobs.py`)

```
enqueue(kind: str, payload: dict) -> None        # the only entry point the API uses
handlers: dict[str, Callable[[dict, Deps], None]] = {"run_case": run_case_job}
```

**Two modes, chosen by `JOBS`:**

| Mode | Setting | Behaviour |
| --- | --- | --- |
| Thread | `JOBS=thread` (default, local and tests) | Runs the handler in a daemon thread, the same as today's `runner.start` (removed) |
| Cloud Tasks | `JOBS=cloudtasks` (prod) | Creates an HTTP task: `POST {SERVICE_URL}/internal/jobs/{kind}`, JSON payload, OIDC token for `TASKS_SA` with audience `SERVICE_URL`, `dispatch_deadline` 30 min |

**`POST /internal/jobs/{kind}`:**
- **Auth.** Verifies the `Authorization: Bearer` OIDC token with `google.oauth2.id_token.verify_oauth2_token`: the audience must be `SERVICE_URL` and the email must be `TASKS_SA`. Otherwise it returns **403**.
- **Mode check.** Returns 404 when `JOBS != cloudtasks`.
- **Request.** Unknown `kind` returns 404.
- **Response.** It runs the handler **synchronously**, then returns 200. A handler that records its own failure (as `run_pipeline` does) still returns 200, so the queue does not retry a recorded failure. Only an unhandled crash returns 500 and gets retried.
- **Logging.** The request log line uses `user = "tasks:<kind>"`.

**Run-once guard for `run_case`.** A task can be delivered more than once.
- `run_case_job` claims the case first: `db.claim_run(case_id, attempt) -> bool`. It sets `run_attempt = attempt` only if:
  - the status is `QUEUED`; or
  - the status is running and `attempt > run_attempt` (a retry after the previous instance died).
- **How it's atomic.** Firestore uses a transaction; LocalDb uses its lock.
- **Where `attempt` comes from:** the `X-CloudTasks-TaskExecutionCount` header (0 in thread mode).
- **If the claim fails,** the handler returns without running.
- **Old guard kept.** The stale→FAILED rule (15 min without an update) stays as the last resort.

**Extensible.** A new job kind is one handler in `handlers` plus `enqueue("kind", {...})`. C and D will add kinds here.

## 7. Infrastructure (Terraform + deploy)

- **`infra/tasks.tf`:**
  - **Queue:** `google_cloud_tasks_queue.jobs` (`claimlens-jobs`, region asia-south1), with `max_attempts = 3`, `min_backoff = 10s`, `max_concurrent_dispatches = 10`.
  - **Tasks account:** `google_service_account.tasks` (`claimlens-tasks`), granted `roles/run.invoker` on the service.
  - **API account:** `claimlens-api` gets `roles/cloudtasks.enqueuer` on the queue, and `roles/iam.serviceAccountUser` on `claimlens-tasks` so it can mint the task's OIDC token.
  - **API:** enables `cloudtasks.googleapis.com`.
  - **Outputs:** `tasks_queue`, `tasks_sa_email`.
- **Deploy** (`ci-deploy.yml` and `make deploy`):
  - add `JOBS=cloudtasks##TASKS_QUEUE=claimlens-jobs##TASKS_LOCATION=asia-south1##TASKS_SA=<email>##SERVICE_URL=<run url>`;
  - `--timeout 1800`;
  - `--no-cpu-throttling` stays.
- **Order:** `make infra-plan` / `infra-apply` runs **before** the first deploy of this change.
- **Dependency:** `google-cloud-tasks`, added to `pyproject.toml`.

## 8. Frontend

**Upload page** (`components/CaseCards.tsx` replaces `UploadTrays`):

- **Starting cards:** Claim form, Bill 1 (kind: hospital), Supporting documents, Policy.
- **Adding bills:** **+ Add bill** adds Bill n, up to 10. A bill card can be removed; the other cards can't.
- **Each card:**
  - a drop zone that takes several files, with the file list showing name, page count after upload, ▲ ▼ to reorder and ✕ to remove;
  - bills also get a kind dropdown.
- **Checks in the browser:** the same rules as §3, done in `lib/upload.ts`, with messages per card.
- **Open case.** Creates the draft, uploads the files one by one in order (`Uploading 3 of 7…`), then submits and opens the case.
  - **A failed upload** stops the flow, shows the server's message on that file and keeps the draft. Retrying re-sends only the files that haven't been uploaded.
  - **Browser notifications:** `askPermission()` runs on the click, and the case is passed to `track()` after submit, as today.
- **Try the sample:** uploads the multi-card sample from `public/samples/`:
  - **Claim form:** `claim-form.pdf`.
  - **Bill 1 (hospital):** `hospital-bill.pdf`.
  - **Bill 2 (pharmacy):** `pharmacy-bill.jpg`.
  - **Supporting documents:** `discharge-summary.pdf`.
  - **Policy:** `policy.pdf`.

**Viewer:**
- The Claim and Policy tabs stay.
- The thumbnail strip is grouped under card labels (`Bill 2 · pharmacy`), using `card_id` from `pages`. The case response gains `cards` (id, role, kind, file names and pages).
- Old cases get the two default cards from `cards_of`.

**Context panel:** each bill line gains its card label.

**Expected sample findings.** The 9 findings from today, unchanged, because the pages and their content are the same. The one difference: tamper metadata is now per file, so `editing_tool` cites the hospital bill's first page.

## 9. Sample generation

`samples/make_example.py` gains `--cards`, which writes the 5 card files from the same content:
- the forged hospital bill keeps its edited total, white box and iLovePDF producer;
- the pharmacy page is rendered to a 150-dpi JPG.

The files are copied to `frontend/public/samples/`. The old `claim.pdf` stays for the backend tests.

## 10. Testing

**Backend (pytest)**
- **Card layout:** two policy cards, 11 bills, a bad id or a bill without a kind → 400. A valid layout → DRAFT.
- **Files:**
  - accepted only while DRAFT (otherwise 409);
  - a policy JPG is accepted;
  - a file over 20 MB → 400;
  - a file for an unknown card → 400;
  - the order is kept.
- **Submit:**
  - no policy file → 400;
  - more than 80 pages or more than 40 files → 400;
  - DRAFT → QUEUED and enqueued once;
  - submitting twice → 409.
- **Lists:** DRAFT cases are hidden from `GET /api/cases`.
- **Read:**
  - stream page numbering and card tags across 3 files;
  - per-file FileInfo with `first_page`;
  - `_pdf` maps stream page 5 to the second file's page 2;
  - an old `files`-only case reads exactly as before.
- **Cards checks:**
  - **split:** same invoice in Bill 1 and Bill 2 → high;
  - **mixed:** two invoices in one card → medium;
  - **duplicate:** the same JPG uploaded twice → high, and the duplicate page is missing from the text Gemini sees;
  - **incomplete:** "Page 1 of 3" and "Page 2 of 3" only → medium;
  - **clean sample:** none of these fire.
- **Jobs:**
  - thread mode runs the handler;
  - cloudtasks mode builds the right task (URL, OIDC email and audience, deadline). Use a fake client.
- **Internal endpoint:**
  - no token, a wrong audience or a wrong email → 403 (use a fake verifier);
  - unknown kind → 404;
  - thread mode → 404.
- **Run-once guard:**
  - a QUEUED case is claimed once;
  - a duplicate delivery with the same attempt doesn't run;
  - a retry with a higher attempt on a running case does run;
  - a READY case is never re-run.
- **End to end:** the multi-card sample through `run_pipeline` → READY with the §8 codes.

**Frontend (vitest)**
- `CaseCards`: add or remove a bill (10 at most), reorder, remove a file, kind dropdown, per-card errors.
- **Upload flow:**
  - create → each file in order → submit → navigate;
  - a failure on file 3 shows on that file;
  - a retry sends only files 3 and later.
- **Try the sample:** 5 files go to the right cards.
- **Viewer:** thumbs grouped under card labels; an old case shows two groups.

**Manual:** the local check, then the prod check (§1). The prod check also confirms that a task created with the wrong account is refused.

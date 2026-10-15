# ClaimLens quick wins: design

Date: 2026-10-16 · Status: approved in chat, awaiting written-spec review

This is sub-project **A** of five. The others are B (multi-file cases with bill cards), C (pixel forensics), D (chat over the documents) and E (evaluation). A has no dependency on them.

It builds on the backend (`2026-10-10-claimlens-backend-design.md`) and frontend (`2026-10-10-claimlens-frontend-design.md`) designs.

## 1. Goal and success criteria

A reviewer can see **what the claim is about** before reading any findings, watch **detailed progress** while it runs, get a **browser notification** when it finishes, and find finished cases marked as new after closing the tab. Operators can see **who called the API** in Cloud Logging.

Done when:

1. `pytest` and `npx vitest run` pass, including the new tests in §6.
2. **Local check** (`make dev`): run **Try the sample**.
   - The context panel fills in while the case is still CHECKING.
   - Progress shows a page count during Read.
   - Every ↗ link opens the right page with the quote marked.
3. **Notification check:** in Chrome, start a case, switch to another tab, and get a system notification. Clicking it opens the case. With the tab in front, a toast shows and there is no notification.
4. **Away check:** start a case, close the tab, wait, then reopen `/`. The case shows READY with a "new" dot, which clears after opening it.
5. **Cloud check:** after deploy, Logs Explorer filter `jsonPayload.user="<your email>"` returns your requests.

Out of scope: email or push notifications when no tab is open, Server-Sent Events or WebSockets, a job queue (planned for B), and editing extracted facts.

## 2. Request logging (who called the API)

- A new **HTTP middleware** in `main.py` writes one JSON line to stdout per `/api/*` request:
  `{"severity": "INFO", "message": "GET /api/cases/3f2a91 200", "user": "<email or null>", "method": "GET", "path": "/api/cases/3f2a91", "status": 200, "latency_ms": 41, "case_id": "3f2a91"}`
  - `severity` is `WARNING` for 4xx and `ERROR` for 5xx.
  - Cloud Run puts JSON stdout lines into `jsonPayload`, so they can be filtered by `user`, `status` or `case_id`.
- **Where `user` comes from:** `current_user()` stores the verified email on `request.state.user`. The middleware reads it after the response, so it is `null` for requests that failed auth (the 401s).
- **Not logged:** `/health` and static frontend files.
- **Pipeline logs** (`run.py`) use a logger adapter that adds `case_id` and `user` (the case owner) to every line, including the `failed during <step>` error.
- A small `claimlens/logs.py` sets up the JSON formatter for `APP_ENV=prod`. Local runs keep the plain-text format.

## 3. Case context (what the claim is for)

### New grounded facts
- `ClaimFacts.hospital_name: Fact | None`
- `PolicyFacts.insurer_name: Fact | None`

The Gemini prompts in `ai.py` gain one line each for these. They are grounded like every other fact: the quote must be on the cited page, or the fact is dropped. FakeAi fixtures (`tests/fixtures/ai/sample/*.json`) gain the two values.

### Stored context
After Extract, `run.py` saves `case.context` **before** the checks run:

```
context = {
  "claim":  <grounded ClaimFacts, JSON>,
  "policy": <grounded PolicyFacts, JSON>,
  "policy_age_months": int | null   # months from policy start to first procedure (or admission)
}
```

- `policy_age_months` is computed in code with the existing `months_between` (moved from `checks/coverage.py` to `pipeline/text.py` so both can use it).
- `Case.context: dict | None = None` is added to `models.py`. `GET /api/cases/{id}` returns it as part of the case.
- **Size:** facts are small (a few KB), well under Firestore's 1 MB document limit.

### New check: `policy_number_mismatch`
- **Where:** `checks/story.py`.
- **Logic:** compare `claim_facts.policy_number` with `policy_facts.policy_number` after removing non-alphanumerics and uppercasing.
- **Result:** if the numbers differ, a **high** finding *"Claim names policy X, but the uploaded policy is Y"*, citing both the claim page and the policy page.
- Skipped if either number is missing.
- Weight 20, as for every high finding.

## 4. Progress

- `Case.progress: dict | None`, shaped as `{step, done, total, label}`. Written by a `Progress` helper in `run.py`.
- **Read:** `total` is the page count of all files. Updated after each page, with labels like `Reading claim page 3 of 12` (digital) or `OCR on claim page 7 of 12` (scanned or photo). `read_document` takes an optional `on_page(doc, n, kind)` callback.
- **Check:** labels are `Extracting facts with Gemini` (no count), then `Checking: tamper` and so on with `done/total` over the four checks, then `Checking coverage with Gemini`.
- **Prove / Report:** single labels.
- **Write throttle:** at most one write per second within a step. A step change and the final page always write.
- On READY or FAILED, `progress` is cleared and `finished_at` is set.

## 5. Frontend

### Case page layout
- Once `pages` is non-empty (after Read), the case page uses the two-pane dossier layout **while still running**:
  - **Left:** progress, then the context panel.
  - **Right:** the viewer.
- Before pages exist, the left pane shows only progress.
- On READY, the left pane shows: header and risk stamp, summary, **context panel**, findings, then *Not proven*. This is the current order with the context panel inserted after the summary.

### Context panel (`components/CaseContext.tsx`)
Two cards side by side, stacked on narrow screens.

| The claim | The policy |
| --- | --- |
| Patient, Hospital, Diagnosis, Stay (admission → discharge, n days), Procedure(s) with date, Claimed amount, Bills (kind + total each), Policy number | Insurer, Policy number, Start date, Sum insured, Room limit/day, Waiting periods (condition, months, clause), Policy age at treatment |

- **Page links:** each value with a page has a ↗ link. Clicking it selects that page in `PageViewer` and marks the quote: the fact's bbox is drawn with the same marker as a finding, and the "Quoted text" note shows when there is no bbox. `CasePage` holds one selection, which can come from either a finding or a context value.
- **Missing values** render as *Not found in documents* in muted ink.
- **Mismatch:** when a `policy_number_mismatch` finding exists, both policy-number rows use the warning colour.

### Progress (`components/Progress.tsx`, moved out of `CasePage.tsx`)
- The existing 4-step stepper, plus a bar (`done/total`, or an indeterminate bar when `total` is 0) and the label.
- If `progress` hasn't changed for 60 s: *"Still working. Large scans take longer."*

### Notifications
- **`lib/notify.ts`**
  - `askPermission()`: called from the **Open case** and **Try the sample** click handlers.
  - `notifyFinished(case)`: shows a system notification only when `document.visibilityState === "hidden"` and permission is granted. Otherwise it returns `false`, so the caller shows a toast instead.
  - Each case notifies at most once per browser session (tracked in a `Set`).
- **`hooks/useCaseWatcher.ts`**, exposed by a `CaseWatcherProvider` that `App.tsx` mounts inside `BrowserRouter` (so it can navigate) and that is active only for signed-in users:
  - **Polling:** polls `GET /api/cases` every 5 s, only while any case is QUEUED, READING, CHECKING or PROVING.
  - **Waking up:** a new upload calls `watcher.track(caseId)` so polling starts immediately.
  - **On finish:** when a case moves to READY or FAILED, it calls `notifyFinished` or shows a toast, e.g. *"Case 3f2a91 ready: HIGH risk, 4 findings"* or *"Case 3f2a91 failed"*.
  - **Click:** clicking the notification runs `window.focus()` and navigates to `/cases/<id>`.
  - **Sharing:** exposes the latest case list so `UploadPage` and `CaseTable` show live statuses without a second poll.
- **Tab title:** `(n) ClaimLens`, where n is the count of unseen finished cases.
- **Toast:** `components/Toast.tsx`, a small stack in the bottom right that dismisses itself after 6 s.

### Case list
- `CaseTable` shows a live status chip for running cases (*Reading…*, *Checking…*) and a **new** dot when `unseen` is true.
- **Backend:**
  - `Case.seen_at: datetime | None`. `GET /api/cases/{id}` sets it when the owner opens a READY or FAILED case and `seen_at` is empty or older than `finished_at`.
  - `GET /api/cases` adds `unseen = status in (READY, FAILED) and (seen_at is None or seen_at < finished_at)`.
  - The stale-run path that sets FAILED also sets `finished_at`.

## 6. Testing

**Backend (pytest)**
- **Middleware:** the JSON line has `user`, `status` and `case_id`. `/health` and static paths are not logged. `user` is null on a 401.
- **Context:** with FakeAi, `context` is on the case when the first check runs. Use a check stub that reads the DB.
- **Context values:** `policy_age_months` is correct. The new facts are grounded, and dropped when their quote is fabricated.
- **`policy_number_mismatch`:**
  - same number → no finding;
  - different numbers → high finding with two citations;
  - formatting differences only (`P-123/45` vs `P12345`) → no finding;
  - one number missing → no finding.
- **Progress:**
  - one update per page for a 3-page case;
  - the throttle collapses quick updates;
  - progress is cleared on READY;
  - `finished_at` is set on READY, FAILED and the stale-run path.
- **Seen:** `seen_at` and `unseen` follow the rules in §5, including that a second GET doesn't write again.

**Frontend (vitest)**
- **`CaseContext`:**
  - renders the full sample;
  - renders *Not found in documents* for missing fields;
  - a ↗ click selects the right doc, page and bbox;
  - the mismatch styling shows.
- **`Progress`:** the label, a determinate vs indeterminate bar, and the 60 s "still working" note (fake timers).
- **`notify`:**
  - no notification when the tab is visible (toast instead);
  - none when permission is denied;
  - one per case.
- **`useCaseWatcher`:**
  - polls while a case is running and stops when none are;
  - `track()` restarts polling;
  - fires once when a case moves from running to READY.
- **`CaseTable`:** the new dot and the live chip.
- **`CasePage`:** the dossier layout appears while CHECKING once pages exist, with the context panel visible.

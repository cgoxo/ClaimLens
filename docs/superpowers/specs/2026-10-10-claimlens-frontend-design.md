# ClaimLens frontend: design

Date: 2026-10-10 · Status: approved in chat, awaiting written-spec review

This builds on the deployed backend (`2026-10-10-claimlens-backend-design.md`). Look and feel: **forensic case file**.

## 1. Goal and success criteria

A reviewer signs in, uploads a claim and its policy (or one click on the sample), watches the analysis run, then works through the findings. Each finding opens its page with the problem marked.

The frontend is done when:

1. `npm test` passes: the Vitest unit and component tests in §8.
2. Backend `pytest` passes, including the new static-serving tests.
3. **Local check:** `make dev` (backend `AUTH_MODE=dev` with the Vite dev server). In Chrome: dev sign-in, then **Try the sample**, then READY with 9 findings. Clicking each finding shows the right document and page, with a marker at the cited spot. Accept and dismiss persist after a reload.
4. **Cloud check:** after `make deploy`, the same flow works at the Cloud Run URL with **Sign in with Google**. An account that isn't on the allow-list sees a clear "not allowed" screen.

Out of scope: admin or lead views, dark mode, PDF export, editing findings, multi-language, offline support.

## 2. Architecture

- React 18 + TypeScript + Vite in `frontend/`, with React Router for page routes.
- The Firebase JS SDK is used for Google sign-in only.
- No UI kit. Styling is plain CSS with design tokens (§6).
- **One deployable.** A two-stage `Dockerfile` at the repo root builds `frontend/` into `dist/`, copies it into the Python image, and FastAPI serves it. One URL, so there's no CORS.
- **Local development.** The Vite dev server (port 5173) forwards `/api` and `/health` to the backend at `localhost:8080`.

## 3. Routes and screens

| Route | Screen | Contents |
| --- | --- | --- |
| `/login` | Cover | Case-file cover with title, one-line pitch and **Sign in with Google**. In dev mode, an email field + **Enter** instead. A `403` from `/api/me` shows "This account isn't on the ClaimLens list" with a sign-out link |
| `/` | Upload | Two evidence trays. **Claim** accepts pdf/jpg/png; **Policy** accepts pdf. Click or drag to add a file; each tray shows its chosen file. **Open case** is enabled when both trays are filled. **Try the sample** uploads `samples/claim.pdf` + `samples/policy.pdf`, bundled in `public/samples/`. Below: **Your cases**, a table of id, created, status, risk stamp and score, newest first, each row linking to its case |
| `/cases/:id` | Case | A two-pane dossier (below) |

Any route other than `/login` sends a signed-out user to `/login`.

### Case screen
- **While running:** a progress line `Reading → Checking → Proving → Ready`, with the current step highlighted. It polls `GET /api/cases/{id}` every 2 s until READY or FAILED.
- **FAILED:** an error card showing the step, the error message and a **Back to upload** button.
- **READY, left pane (scrolls):**
  - **Header:** case id, created time, **risk stamp** (HIGH / REVIEW / LOW, rotated about 4°, red/amber/green ink), score `100/100`, payable `₹0`, and the summary paragraph.
  - **Findings,** grouped as Critical, High, Medium, Low, then **Coverage**. Each card shows the title, detail, citation chip (`claim p.3` or `file properties`), any amount not payable, and **Accept** / **Dismiss** buttons with an optional note.
    - The selected card is outlined.
    - A reviewed card shows "Accepted by …" or "Dismissed by …".
  - **Not proven:** a collapsed section listing `dropped_findings` (title and reason).
- **READY, right pane (sticky):** the document viewer.
  - Tabs: **Claim**, **Policy**.
  - A thumbnail strip of that document's pages; `unreadable` pages show "Unreadable (no OCR)".
  - The main page image at its natural ratio, scaled to the pane width.
  - Selecting a finding switches to its citation's document and page and draws an **evidence marker**:
    - `source="page"` with a bbox: a red-ink box, padded 3 px, with a numbered tag.
    - `source="hidden_layer"`: a dashed box.
    - `source="metadata"`: no box. The page gets a "File properties" banner instead, showing the finding detail.
  - If a page citation has no bbox, there is no box, and a note reads "Quoted text: …".
- **Keyboard:** `j` / `k` move to the next or previous finding.

## 4. Units

| File | Responsibility | Interface |
| --- | --- | --- |
| `src/api/types.ts` | Types mirroring backend JSON: Case, Finding, Citation, PageMeta, CaseSummary | types only |
| `src/api/client.ts` | All HTTP. Adds auth headers, turns non-2xx into `ApiError(status, detail)`, fetches page images as object URLs | `createClient(getHeaders: () => Promise<Record<string,string>>)` returns `{ me, listCases, createCase(claim: File, policy: File), getCase(id), pageImageUrl(id, doc, n), review(id, fid, action, note?) }` |
| `src/auth/AuthProvider.tsx` | Sign-in state; mode from `import.meta.env.VITE_AUTH_MODE` (`firebase` or `dev`) | `useAuth()` returns `{ status: 'loading'\|'signedOut'\|'signedIn'\|'forbidden', email, signInGoogle(), signInDev(email), signOut(), headers() }` |
| `src/auth/firebase.ts` | Firebase app and auth init from `VITE_FIREBASE_*` | `getFirebaseAuth()` |
| `src/hooks/useCasePolling.ts` | Poll until READY or FAILED, stop on unmount | `useCasePolling(id, client, intervalMs = 2000)` returns `{ data, error }` |
| `src/lib/highlight.ts` | Convert a PDF-point bbox to percentages of the page box (so the marker scales with the image) | `toPercentBox(bbox, pageWidth, pageHeight)` returns `{ left, top, width, height }`, each a %; padding is applied in CSS |
| `src/lib/findings.ts` | Group and order findings, citation label | `groupFindings(f[])` gives `[severity, Finding[]][]` in `critical, high, medium, low, coverage` order, skipping empty groups; `citationLabel(c)` gives `"claim p.3"` or `"file properties"` |
| `src/lib/upload.ts` | Client-side file checks matching the backend | `checkFile(kind, file)` returns `string \| null` (an error message): type per §3, max 20 MB |
| `src/components/RiskStamp.tsx` | The rotated stamp | `<RiskStamp risk score />` |
| `src/components/FindingCard.tsx`, `FindingList.tsx` | Cards, groups, review actions | `onSelect(finding)`, `onReview(fid, action, note)` |
| `src/components/PageViewer.tsx` | Tabs, thumbnails, page image and marker | props `{ caseId, pages, selected: Citation \| null, client }` |
| `src/components/UploadTrays.tsx` | The two trays plus validation | `onSubmit(claim, policy)` |
| `src/pages/LoginPage.tsx`, `UploadPage.tsx`, `CasePage.tsx` | Screens | none |

Page images are cached per `caseId/doc/n` in a `Map`, and their object URLs are revoked on unmount.

## 5. Backend changes

1. **Static serving** (`claimlens/main.py`): if the folder `FRONTEND_DIR` (default `<backend>/../frontend/dist`, `/app/static` in the image) exists, serve files from it. Any `GET` that isn't `/api/*` or `/health` and doesn't match a file returns `index.html`, so client-side routes survive a reload. Unknown `/api/*` routes still return JSON 404.
2. **Root `Dockerfile`:**
   - **Stage 1** `node:22-slim`: `npm ci && npm run build` in `frontend/`, taking `VITE_*` values from build args.
   - **Stage 2** `python:3.12-slim`: installs `backend/` and copies `dist` to `/app/static`.
   - `backend/Dockerfile` is removed, and `.dockerignore` moves to the root.
3. **`make deploy`** runs `gcloud builds submit` from the repo root with a `cloudbuild.yaml` that passes the `VITE_*` build args, then `gcloud run deploy`.
4. **Authorized domains:** `make auth-domain` adds the Cloud Run host (both `*.run.app` forms) to Identity Toolkit `authorizedDomains`, using the admin v2 config PATCH. It runs once, and running it again does nothing new.
5. **Frontend config:**
   - `frontend/.env.production` holds `VITE_AUTH_MODE=firebase` and `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID` and `VITE_FIREBASE_APP_ID` (from the project's Firebase web config, which is public by design).
   - `frontend/.env.development` holds `VITE_AUTH_MODE=dev`.

## 6. Visual design: forensic case file

| Token | Value | Use |
| --- | --- | --- |
| `--paper` | `#F4EFE4` | page background |
| `--sheet` | `#FBF8F1` | cards, viewer frame |
| `--ink` | `#1E1C19` | text |
| `--ink-soft` | `#5B564D` | secondary text |
| `--rule` | `#D9D1C1` | borders, dividers |
| `--stamp-red` | `#B3261E` | critical, HIGH stamp, evidence marker |
| `--amber` | `#B26A00` | high severity, REVIEW stamp |
| `--olive` | `#4F6B2E` | LOW stamp, accepted |
| `--slate` | `#44546A` | coverage, medium |
| `--focus` | `#1F5FAD` | focus rings |

- **Type** (Google Fonts):
  - **Newsreader** 600 for headings and the stamp.
  - **IBM Plex Sans** 400/500 for body text.
  - **IBM Plex Mono** 500 for amounts, ids, page refs.
- **Shapes:** cards have a 1 px rule border, 2 px radius and a faint shadow, like paper on a desk. The evidence marker is 2 px stamp-red, with a small numbered tab at its top-left.
- **Accessibility:**
  - Contrast ≥ 4.5:1 for text.
  - Every control is reachable by keyboard, with a visible focus ring.
  - The stamp has `aria-label="Risk high, score 100 of 100"`.
  - Page images have alt text like `claim page 3`.
- **Layout:**
  - At ≥ 1100 px: 42% / 58% split.
  - Below 1100 px: the panes stack, with the viewer below its finding list.
  - Minimum supported width: 360 px, with no horizontal scrolling.

## 7. Error handling

| Situation | Behaviour |
| --- | --- |
| `401` on any call | Sign out locally and go to `/login` |
| `403` | The "not on the list" screen |
| `400` / `429` on upload | Show the backend `detail` under the trays |
| A network error while polling | Retry silently; after 5 straight failures, show "Connection lost, retrying" (polling continues) |
| A page image fails to load | Grey frame with "Couldn't load page N" and **Retry** |
| A review call fails | Revert the card and show an inline error |

## 8. Testing

**Vitest + @testing-library/react (jsdom); `fetch` mocked per test:**

- `client`:
  - adds `X-Dev-User` in dev mode and `Authorization: Bearer` in Firebase mode;
  - `ApiError` carries the status and detail;
  - `createCase` sends multipart with the `claim` and `policy` fields.
- `useCasePolling`: polls while running, stops at READY, stops at FAILED, stops on unmount (fake timers).
- `toPercentBox`: `(220, 330, 280, 345)` on a 595×842 page gives `left ≈ 36.97%, top ≈ 39.19%, width ≈ 10.08%, height ≈ 1.78%`.
- `groupFindings`: order and empty-group skipping. `citationLabel` for page and metadata citations.
- `checkFile`: rejects `.docx` for the claim and `.jpg` for the policy, rejects files over 20 MB, accepts a png claim.
- `CasePage` with a mocked client returning the sample case:
  - shows the HIGH stamp and 9 cards in the right groups;
  - clicking the `font_outlier` card selects the claim tab, page 3, and renders a marker;
  - clicking `editing_tool` shows the "File properties" banner and no marker.

**Backend pytest:**
- `GET /cases/abc` returns `index.html` when `FRONTEND_DIR` exists.
- `GET /api/nope` returns a JSON 404.
- `GET /assets/x.js` serves the file.

**Browser check** (Claude in Chrome, recorded as a GIF): the success criteria in §1, steps 3 and 4.

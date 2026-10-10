# ClaimLens Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A React app where a reviewer signs in, uploads a claim and policy (or the sample), watches it run, and works through cited findings with page markers. It ships inside the existing Cloud Run service.

**Architecture:** Vite + React + TypeScript in `frontend/`. A typed fetch client takes its auth headers from an `AuthProvider` (Firebase Google or dev email). FastAPI serves the built `dist/` with an SPA fallback. A two-stage root Dockerfile builds both; Cloud Build passes the `VITE_*` args.

**Tech Stack:** React 18, react-router-dom 6, Vite 5, TypeScript 5, Firebase JS SDK 10 (auth only), Vitest 2 + @testing-library/react + jsdom, plain CSS with tokens, Google Fonts (Newsreader, IBM Plex Sans, IBM Plex Mono).

**Spec:** `docs/superpowers/specs/2026-10-10-claimlens-frontend-design.md` (backend spec: `2026-10-10-claimlens-backend-design.md`)

## Global Constraints

- All frontend code lives in `frontend/`. Run with `npm` (Node 23 on this machine; Docker uses `node:22-slim`).
- Design tokens exactly as spec §6 (`--paper #F4EFE4`, `--sheet #FBF8F1`, `--ink #1E1C19`, `--ink-soft #5B564D`, `--rule #D9D1C1`, `--stamp-red #B3261E`, `--amber #B26A00`, `--olive #4F6B2E`, `--slate #44546A`, `--focus #1F5FAD`).
- Severity order: `critical, high, medium, low, coverage`.
- Polling interval: 2000 ms; stop at `READY` or `FAILED`.
- Client upload limits must match the backend: claim `pdf|jpg|jpeg|png`, policy `pdf`, at most 20 MB.
- The dev auth header is `X-Dev-User`; Firebase uses `Authorization: Bearer <idToken>`.
- No horizontal scroll at 360 px; 42% / 58% split at ≥ 1100 px.
- Cloud Run service `claimlens-api`, project `social-pulse-510513`, region `asia-south1`.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Reloading a deep link** (`/cases/<id>`) on Cloud Run should load the app, not a 404 or JSON. Test in Task 1.
2. **Opening a case that belongs to someone else, or a wrong id,** should show "Case not found" with a way back, not a blank page or endless polling. Test in Task 7.
3. **A case whose findings include a page citation with `bbox: null`** should select the page and show "Quoted text: …" without crashing. Test in Task 7.
4. **Uploading a file the client accepts but the backend rejects** (corrupt PDF → 400) should show the backend's message under the trays and keep the chosen files. Test in Task 6.
5. **An expired Firebase token in the middle of a session** (401) should send the user to `/login`, not leave them stuck on a spinner. Test in Task 3.

---

## File structure

```
Dockerfile  .dockerignore  cloudbuild.yaml            (repo root)
backend/claimlens/main.py (static serving)  backend/tests/test_static.py  backend/Makefile (deploy, auth-domain, dev)
frontend/
  package.json  vite.config.ts  tsconfig.json  index.html  .env.development  .env.production
  public/samples/{claim.pdf,policy.pdf}
  src/main.tsx  src/App.tsx  src/styles/{tokens.css,app.css}
  src/api/{types.ts,client.ts}
  src/auth/{AuthProvider.tsx,firebase.ts}
  src/hooks/useCasePolling.ts
  src/lib/{findings.ts,highlight.ts,upload.ts}
  src/components/{RiskStamp,FindingCard,FindingList,PageViewer,UploadTrays,CaseTable}.tsx
  src/pages/{LoginPage,UploadPage,CasePage}.tsx
  src/test/{setup.ts,sampleCase.ts}   + *.test.ts(x) next to the files they test
```

---

### Task 1: Backend serves the built frontend

**Files:**
- Modify: `backend/claimlens/main.py`, `backend/claimlens/settings.py` (add `frontend_dir: Path = BACKEND_DIR.parent / "frontend" / "dist"`)
- Test: `backend/tests/test_static.py`

**Interfaces:**
- Produces: when `settings.frontend_dir` exists, `GET /<file>` serves the file, and any other non-`/api`, non-`/health` GET returns `index.html`. `/api/*` 404s stay JSON.

- [ ] **Step 1:** Write the failing tests. Each builds a temp `dist/` containing `index.html` (`<div id=root>`) and `assets/x.js`:
  - `test_spa_route_returns_index`: `GET /cases/abc` → 200, `text/html`, body contains `id=root`.
  - `test_asset_served`: `GET /assets/x.js` → 200, body equals the file.
  - `test_unknown_api_is_json_404`: `GET /api/nope` → 404 with a JSON `detail`.
  - `test_health_still_works`.
  - `test_no_frontend_dir_no_catch_all`: without the folder, `GET /cases/abc` → 404.
- [ ] **Step 2:** Run `cd backend && .venv/bin/pytest tests/test_static.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement it in `create_app`, after `include_router`: one `@app.get("/{path:path}")` route.
  - If `path` starts with `api/`: raise 404.
  - If `frontend_dir/path` is a file inside `frontend_dir`: `FileResponse`.
  - Otherwise: `FileResponse(index.html)`.
  - Register the route only when `frontend_dir/"index.html"` exists.
- [ ] **Step 4:** Run `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5:** Commit `feat(backend): serve built frontend with SPA fallback`.

### Task 2: Frontend scaffold, tokens, pure helpers

**Files:**
- Create: `frontend/package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, `.env.development`, `.env.production`, `public/samples/*`, `src/main.tsx`, `src/App.tsx`, `src/styles/tokens.css`, `src/styles/app.css`, `src/test/setup.ts`, `src/lib/{findings,highlight,upload}.ts` + their tests
- Modify: root `.gitignore` (add `frontend/node_modules/`, `frontend/dist/`)

**Interfaces:**
- Produces:
  - `groupFindings(findings: Finding[]): [Severity, Finding[]][]`
  - `citationLabel(c: Citation): string`
  - `toPercentBox(bbox: [number,number,number,number], w: number, h: number): {left:number; top:number; width:number; height:number}`
  - `checkFile(kind: 'claim'|'policy', file: File): string | null`
  - `vite.config.ts` forwards `/api` and `/health` to `http://localhost:8080`; the test environment is `jsdom` with setup `src/test/setup.ts`.

- [ ] **Step 1:** Scaffold the app by hand (not `create-vite`, to keep the file list exact).
  - Dependencies: `react@18 react-dom@18 react-router-dom@6 firebase@10`.
  - Dev dependencies: `vite@5 @vitejs/plugin-react typescript@5 vitest@2 jsdom @testing-library/react @testing-library/user-event @testing-library/jest-dom @types/react @types/react-dom`.
  - Scripts: `dev`, `build` (`tsc -b && vite build`), `test` (`vitest run`).
  - `index.html` loads the three Google Fonts.
  - `tokens.css` holds the spec §6 values.
  - Copy `backend/samples/claim.pdf` and `policy.pdf` into `public/samples/`.
  - `.env.development`: `VITE_AUTH_MODE=dev`.
  - `.env.production`: `VITE_AUTH_MODE=firebase` and the four `VITE_FIREBASE_*` values from `../SocialPulse/config/firebase-web.json` (`apiKey`, `authDomain`, `projectId`, `appId`).
  - Run `npm install`.
- [ ] **Step 2:** Write the failing tests:
  - `toPercentBox([220,330,280,345], 595, 842)` gives `left≈36.97, top≈39.19, width≈10.08, height≈1.78` (`toBeCloseTo(…, 2)`).
  - `groupFindings`: order `critical, high, low, coverage` for an input with no medium; empty groups skipped; order within a group preserved.
  - `citationLabel`: `{doc:'claim',page:3,source:'page'}` gives `"claim p.3"`; `source:'metadata'` gives `"file properties"`; `source:'hidden_layer'` gives `"claim p.3 · hidden text"`.
  - `checkFile`:
    - claim `x.docx` gives `"Claim must be a PDF, JPG or PNG"`;
    - policy `x.jpg` gives `"Policy must be a PDF"`;
    - 21 MB gives `"File is larger than 20 MB"`;
    - claim `x.PNG` gives `null`.
- [ ] **Step 3:** Run `cd frontend && npx vitest run src/lib`. Expected: FAIL (modules missing).
- [ ] **Step 4:** Implement the three modules. `App.tsx` is a placeholder router for now.
- [ ] **Step 5:** Run `npx vitest run && npm run build`. Expected: tests pass and the build writes `dist/`.
- [ ] **Step 6:** Commit `feat(frontend): scaffold, design tokens, helpers`.

### Task 3: API types and client

**Files:**
- Create: `frontend/src/api/types.ts`, `frontend/src/api/client.ts`, `frontend/src/api/client.test.ts`, `frontend/src/test/sampleCase.ts` (a READY case fixture with the 9 sample findings, citations copied from a real `GET /api/cases/{id}` response)

**Interfaces:**
- Produces:
  - Types `Case`, `Finding`, `Citation` (`source: 'page'|'metadata'|'hidden_layer'`, `bbox: [number,number,number,number] | null`), `PageMeta`, `CaseSummary`, `Severity`, `Status`.
  - `class ApiError extends Error { status: number; detail: string }`.
  - `createClient(getHeaders: () => Promise<Record<string,string>>, onUnauthorized: () => void)` returns:
    - `me(): Promise<{email:string}>`
    - `listCases(): Promise<CaseSummary[]>`
    - `createCase(claim: File, policy: File): Promise<{case_id:string; status:Status}>`
    - `getCase(id): Promise<Case>`
    - `pageImageUrl(id, doc, n): Promise<string>` (an object URL)
    - `review(id, fid, action: 'accept'|'dismiss', note?: string): Promise<Finding>`

- [ ] **Step 1:** Write the failing tests, with `fetch` mocked through `vi.stubGlobal`:
  - headers from `getHeaders` are sent on every call;
  - non-2xx throws `ApiError` with `status` and `detail` from the JSON body;
  - a 401 calls `onUnauthorized` once and throws;
  - `createCase` posts `FormData` with keys `claim` and `policy` and no explicit content-type;
  - `pageImageUrl` calls `URL.createObjectURL` with the blob and caches it per key, so a second call doesn't fetch again.
- [ ] **Step 2:** Run `npx vitest run src/api`. Expected: FAIL.
- [ ] **Step 3:** Implement `types.ts` and `client.ts`. To capture `sampleCase.ts`: run `make smoke-local`, then `curl` the case JSON with `X-Dev-User` and save it.
- [ ] **Step 4:** Run `npx vitest run`. Expected: PASS.
- [ ] **Step 5:** Commit `feat(frontend): typed API client`.

### Task 4: Auth provider and login page

**Files:**
- Create: `frontend/src/auth/firebase.ts`, `frontend/src/auth/AuthProvider.tsx`, `frontend/src/auth/AuthProvider.test.tsx`, `frontend/src/pages/LoginPage.tsx`; Modify: `frontend/src/App.tsx` (routes and the signed-in guard)

**Interfaces:**
- Consumes: `createClient`.
- Produces:
  - `<AuthProvider>` and `useAuth(): { status: 'loading'|'signedOut'|'signedIn'|'forbidden'; email: string|null; signInGoogle(): Promise<void>; signInDev(email: string): void; signOut(): Promise<void>; client: Client }`.
  - Dev mode keeps the email in `localStorage['claimlens.devUser']`. Firebase mode uses `signInWithPopup(GoogleAuthProvider)`, and its headers come from `currentUser.getIdToken()`.
  - After sign-in the provider calls `client.me()`: a 403 sets `forbidden`.
  - `<RequireAuth>` sends signed-out users to `/login`.

- [ ] **Step 1:** Write the failing tests (dev mode, client `me` mocked):
  - `signInDev('a@x.com')` sets status `signedIn` and email; a client call sends `X-Dev-User: a@x.com`.
  - A stored dev user is restored after re-mounting.
  - `me` throwing `ApiError(403)` sets `forbidden`.
  - `signOut` clears storage and sets `signedOut`.
  - `LoginPage` in dev mode shows an email field and a button **Enter**; in forbidden state it shows "This account isn't on the ClaimLens list".
- [ ] **Step 2:** Run `npx vitest run src/auth`. Expected: FAIL.
- [ ] **Step 3:** Implement it. Load the Firebase modules with dynamic `import()` only when the mode is `firebase`, so tests and dev builds don't initialise Firebase.
- [ ] **Step 4:** Run `npx vitest run`. Expected: PASS.
- [ ] **Step 5:** Commit `feat(frontend): auth provider (Google + dev) and login`.

### Task 5: Case polling hook

**Files:**
- Create: `frontend/src/hooks/useCasePolling.ts`, `frontend/src/hooks/useCasePolling.test.tsx`

**Interfaces:**
- Produces: `useCasePolling(id: string, client: Client, intervalMs = 2000): { data: Case | null; error: ApiError | null; connectionLost: boolean }`.
  - A 404 sets `error` and stops polling.
  - Network errors are retried; `connectionLost` becomes true after 5 failures in a row and resets on success.

- [ ] **Step 1:** Write the failing tests (fake timers):
  - polls while status is `CHECKING`, stops after `READY`;
  - stops after `FAILED`;
  - no calls after unmount;
  - a 404 stops polling and sets `error.status === 404`;
  - 5 network failures set `connectionLost`, and the next success clears it.
- [ ] **Step 2:** Run `npx vitest run src/hooks`. Expected: FAIL.
- [ ] **Step 3:** Implement it with `setTimeout` chaining (not `setInterval`) so slow calls don't overlap.
- [ ] **Step 4:** Run `npx vitest run`. Expected: PASS.
- [ ] **Step 5:** Commit `feat(frontend): case polling hook`.

### Task 6: Upload page

**Files:**
- Create: `frontend/src/components/UploadTrays.tsx`, `frontend/src/components/CaseTable.tsx`, `frontend/src/pages/UploadPage.tsx`, `frontend/src/pages/UploadPage.test.tsx`

**Interfaces:**
- Consumes: `useAuth().client`, `checkFile`, `RiskStamp` (Task 7 creates it; until then `CaseTable` shows risk as plain text, and Task 7 swaps in the stamp).
- Produces: route `/`. **Try the sample** fetches `/samples/claim.pdf` and `/samples/policy.pdf`, wraps them as `File`s, calls `createCase`, then navigates to `/cases/:id`.

- [ ] **Step 1:** Write the failing tests:
  - **Open case** is disabled until both trays have valid files;
  - choosing `x.docx` as the claim shows `"Claim must be a PDF, JPG or PNG"`;
  - submitting calls `createCase` and navigates to `/cases/c1`;
  - a mocked `ApiError(400, "claim: not a readable PDF file")` shows that text and keeps both file names visible;
  - **Try the sample** fetches both sample URLs and navigates;
  - **Your cases** lists rows from `listCases`, newest first, linking to `/cases/<id>`.
- [ ] **Step 2:** Run `npx vitest run src/pages/UploadPage.test.tsx`. Expected: FAIL.
- [ ] **Step 3:** Implement it, with styling per spec §3/§6 (trays as paper folders with a dashed drop area; drag-and-drop and click-to-choose both work).
- [ ] **Step 4:** Run `npx vitest run`. Expected: PASS.
- [ ] **Step 5:** Commit `feat(frontend): upload page with sample and case list`.

### Task 7: Case page, findings and page viewer

**Files:**
- Create: `frontend/src/components/{RiskStamp,FindingCard,FindingList,PageViewer}.tsx`, `frontend/src/pages/CasePage.tsx`, `frontend/src/pages/CasePage.test.tsx`

**Interfaces:**
- Consumes: `useCasePolling`, `groupFindings`, `citationLabel`, `toPercentBox`, `client.pageImageUrl`, `client.review`.
- Produces: route `/cases/:id`, with layout, marker kinds and keyboard behaviour exactly as spec §3.

- [ ] **Step 1:** Write the failing tests, with the client mocked to return `sampleCase` and `pageImageUrl` returning `"blob:x"`:
  - shows `RiskStamp` with `aria-label="Risk high, score 100 of 100"` and payable `₹0`;
  - 9 cards across group headings `Critical (3)`, `High (3)`, `Low (1)`, `Coverage (2)`;
  - clicking the `font_outlier` card makes the **Claim** tab and page-3 thumbnail active and renders `[data-testid=marker]` with a `left` style ≈ the `toPercentBox` value;
  - clicking `editing_tool` shows the "File properties" banner and no marker;
  - a case copy whose first finding has `bbox: null` shows `"Quoted text:"` and no marker;
  - pressing `j` selects the next finding;
  - **Accept** calls `review(id, fid, 'accept', '')`, and the card then shows "Accepted by";
  - a rejected review reverts the card and shows an error;
  - a `CHECKING` case shows the progress line with **Checking** current;
  - a `FAILED` case shows its step and error and a **Back to upload** link;
  - a 404 shows "Case not found" with a link to `/`.
  - when `pageImageUrl` rejects, the viewer shows "Couldn't load page 3" and a **Retry** button that calls it again.
- [ ] **Step 2:** Run `npx vitest run src/pages/CasePage.test.tsx`. Expected: FAIL.
- [ ] **Step 3:** Implement the components:
  - the marker is absolutely positioned in a `position:relative` wrapper around the `<img>`, using percentage units;
  - the stamp is rotated −4° with a double border in Newsreader caps.
  - Swap `RiskStamp` into `CaseTable`.
- [ ] **Step 4:** Run `npx vitest run && npm run build`. Expected: PASS, and the build succeeds.
- [ ] **Step 5:** Commit `feat(frontend): case dossier with findings and page viewer`.

### Task 8: Visual pass and local browser check

**Files:**
- Modify: `frontend/src/styles/*.css` and components as needed; `backend/Makefile` (target `dev`: backend `AUTH_MODE=dev AI=vertex` on 8080 plus `npm run dev` on 5173)

- [ ] **Step 1:** Load the `frontend-design:frontend-design` skill and apply its guidance within the spec §6 tokens and type: spacing scale, hierarchy, paper texture (CSS only), states (hover, focus, disabled, loading). No new colours.
- [ ] **Step 2:** Run `make dev`, then use Claude in Chrome on `http://localhost:5173`. Record a GIF `claimlens_local.gif`:
  - dev sign-in;
  - **Try the sample**;
  - READY;
  - click each of the 9 findings and confirm doc, page and marker;
  - Accept one, reload, and confirm it persists;
  - resize to 360 px wide and confirm there's no horizontal scroll.
- [ ] **Step 3:** Fix whatever the browser check exposes. Each behavioural bug gets a failing test first. `npx vitest run` stays green.
- [ ] **Step 4:** Commit `style(frontend): forensic case-file visual pass`.

### Task 9: Single image, deploy, Google sign-in on Cloud Run

**Files:**
- Create: `Dockerfile`, `.dockerignore`, `cloudbuild.yaml` (repo root); Delete: `backend/Dockerfile`, `backend/.dockerignore`; Modify: `backend/Makefile` (`deploy` builds from the root via `cloudbuild.yaml`; new target `auth-domain`), `backend/README.md`

**Interfaces:**
- Produces:
  - An image with the backend installed and `FRONTEND_DIR=/app/static`.
  - `cloudbuild.yaml` takes substitutions `_IMAGE` and `_VITE_*`, and runs `docker build --build-arg …` then `push`.
  - `make auth-domain` reads the current `authorizedDomains` and adds the Cloud Run host(s) if they're missing (PATCH `?updateMask=authorizedDomains`).

- [ ] **Step 1:** Write the Dockerfile.
  - Stage 1: `node:22-slim`, `WORKDIR /fe`, `COPY frontend/package*.json`, `npm ci`, `COPY frontend/`, set the `ARG VITE_*` values as `ENV`, `npm run build`.
  - Stage 2: the existing python stage installs `backend/` and `COPY --from=0 /fe/dist /app/static`.
  - `.dockerignore` excludes `**/node_modules`, `**/.venv`, `backend/data`, `**/dist`, `.git`.
- [ ] **Step 2:** Run `make deploy` (Cloud Build, then Cloud Run). Expected: `Service URL` printed.
- [ ] **Step 3:** Run `make auth-domain`. Expected: both run.app hosts are in `authorizedDomains`. Running it again changes nothing.
- [ ] **Step 4:** Cloud browser check with Claude in Chrome, recorded as GIF `claimlens_cloud.gif`:
  - open the Cloud Run URL;
  - **Sign in with Google** (the user completes the Google popup);
  - **Try the sample**;
  - READY;
  - click several findings and confirm their markers;
  - reload a `/cases/<id>` URL.
  - If the user's account is not on the allow-list, the "not on the list" screen must appear.
- [ ] **Step 5:** Run `make smoke-cloud`. Expected: still OK, so the API is unchanged.
- [ ] **Step 6:** Commit `build: single image with frontend; deploy and auth-domain targets`.

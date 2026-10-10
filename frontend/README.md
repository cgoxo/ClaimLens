# ClaimLens frontend

The reviewer's web app: sign in, upload a claim and its policy (or try the sample), watch the investigation run, then
work through the findings. Each finding opens its page with the problem marked.

React 18 + TypeScript + Vite. No UI kit: plain CSS with design tokens (`src/styles/tokens.css`), in a "forensic case
file" look (paper, ink, a red stamp and red evidence markers).

Design: [`../docs/superpowers/specs/2026-10-10-claimlens-frontend-design.md`](../docs/superpowers/specs/2026-10-10-claimlens-frontend-design.md)

## Run locally

```bash
npm install
npm run dev            # http://localhost:5173, forwards /api and /health to the backend on :8080
```

Start the backend too (`cd ../backend && make run`, or `make dev` there to run both). Local mode uses **dev sign-in**:
type any email, sent to the backend as `X-Dev-User` (`VITE_AUTH_MODE=dev` in `.env.development`).

## Test and build

```bash
npx vitest run         # unit + component tests (jsdom, fetch mocked)
npm run build          # type-check + production build into dist/
```

## Screens

| Route | Screen |
| --- | --- |
| `/login` | Case-file cover: **Sign in with Google** (or dev email). Any Google account can sign in |
| `/` | Two evidence trays (claim: PDF/JPG/PNG, policy: PDF), **Try the sample claim**, and your cases |
| `/cases/:id` | Progress while running; then the risk stamp, payable amount, summary and findings by severity, with the page viewer. Click a finding (or `j` / `k`) to see it marked on its page; Accept / Dismiss it |

## How it fits together

| File | Job |
| --- | --- |
| `src/api/client.ts` | All HTTP; adds the auth header; a 401 signs you out; page images fetched once and shown as object URLs |
| `src/auth/AuthProvider.tsx` | Google (Firebase) or dev sign-in; checks `/api/me` (403 means the email isn't verified) |
| `src/hooks/useCasePolling.ts` | Polls the case every 2 s until READY or FAILED |
| `src/lib/highlight.ts` | PDF-point boxes to percentages, so markers scale with the page image |
| `src/components/PageViewer.tsx` | Tabs, page strip, page image and evidence marker (dashed for hidden text, a banner for file properties) |

## Configuration

| File | Values |
| --- | --- |
| `.env.development` | `VITE_AUTH_MODE=dev` |
| `.env.production` | `VITE_AUTH_MODE=firebase` and the Firebase project ids. The web **API key** comes from GCP Secret Manager at build time (`VITE_FIREBASE_API_KEY` build arg), not from git |

## Deploy

The frontend is not deployed on its own. The repo-root `Dockerfile` builds it and the backend serves it, so one Cloud
Run service hosts both. Pushing to `main` runs the GitHub Actions workflow (tests, then deploy); see
[`../backend/README.md`](../backend/README.md#cicd-github-actions).

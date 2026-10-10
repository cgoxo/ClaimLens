# ClaimLens backend

Upload a claim PDF and its policy PDF; get back a case file of findings (edited documents, stories that don't add
up, reused invoices, uncovered items), each citing the page and the exact text.

Design: [`../docs/superpowers/specs/2026-10-10-claimlens-backend-design.md`](../docs/superpowers/specs/2026-10-10-claimlens-backend-design.md)

## Quick start (local)

```bash
make venv                                   # Python 3.12 venv + deps
cp .env.example .env                        # local files + JSON DB, real Gemini
gcloud auth application-default login       # once, for Gemini (Vertex AI)
make seed                                   # adds past invoice CLM-1043 (the sample's duplicate)
make run                                    # http://localhost:8080
make smoke-local                            # uploads samples/, prints the findings
```

No GCP at all? Set `AI=fake` in `.env`: canned Gemini answers for the sample files (`tests/fixtures/ai/sample`).

## Postman

Import the three files in `postman/`, pick an environment:

- **ClaimLens local**: `devUser` is sent as `X-Dev-User` (dev auth mode). Run *Create case*, then *Get case*
  until `READY`.
- **ClaimLens cloud**: fill `testPassword`, run *Sign in test user* (stores `idToken`), then the same requests.

Regenerate after deploying: `make postman URL=https://<run-url> API_KEY=<firebase web api key>`.
The *Create case* request points at `samples/*.pdf` with absolute paths from your machine.

## API

| Method | Path | |
| --- | --- | --- |
| GET | `/health` | no auth |
| GET | `/api/me` | who am I |
| POST | `/api/cases` | multipart `claim` (pdf/jpg/png) + `policy` (pdf) → `{case_id}` |
| GET | `/api/cases` | my cases |
| GET | `/api/cases/{id}` | status, score, risk, payable, summary, findings, pages |
| GET | `/api/cases/{id}/pages/{doc}/{n}.png` | page image |
| POST | `/api/cases/{id}/findings/{fid}/review` | `{"action": "accept" \| "dismiss", "note"}` |

Auth: `AUTH_MODE=dev` → `X-Dev-User: <email>` header. `AUTH_MODE=firebase` → `Authorization: Bearer <Firebase ID
token>`, email must be in `ALLOWED_EMAILS`.

## Tests

```bash
make test                         # offline, fake AI
.venv/bin/pytest -m live          # real Gemini (+ GCS/Firestore if BUCKET / FIRESTORE_LIVE set)
```

## Settings

All in `.env.example`. Each backend part switches between local and GCP: `STORAGE=local|gcs`,
`DB=local|firestore`, `AI=vertex|fake`, `OCR=off|docai`, `AUTH_MODE=dev|firebase`.

## GCP (project `social-pulse-510513`)

Billing must be enabled on the project. One-time setup:

```bash
make infra-plan                   # Terraform: APIs, Firestore DB "claimlens", bucket, Document AI, service accounts,
make infra-apply                  # registry, and the GitHub Actions trust (Workload Identity Federation)
.venv/bin/python scripts/create_test_user.py --password '<pick one>'
cp .env.deploy.example .env.deploy   # who may sign in (gitignored), then edit
make deploy                       # build the single image (frontend + API) and deploy Cloud Run claimlens-api
make auth-domain                  # authorize the Cloud Run hosts for Google sign-in (safe to re-run)
make seed-cloud                   # past invoice into Firestore
make smoke-cloud PASSWORD='<same>' API_KEY=<firebase web api key>
```

The image is built from the **repo root** `Dockerfile`: stage 1 builds `frontend/`, stage 2 installs this package and
serves the built app from `/app/static`, so the site and the API share one URL.

## CI/CD (GitHub Actions)

`.github/workflows/ci-deploy.yml` runs on every push and pull request to `main`:

| Job | What it does |
| --- | --- |
| **Backend tests** | `pip install -e '.[dev]'`, then `pytest -q` (offline, fake AI) |
| **Frontend tests and build** | `npm ci`, `vitest run`, `npm run build` |
| **Deploy to Cloud Run** | Only on pushes to `main`, after both test jobs pass: builds the root image, pushes it to Artifact Registry, deploys `claimlens-api`, then checks `/health`, a 401 on `/api/me` and the app page |

GitHub signs in to GCP **without a stored key**: Workload Identity Federation (`infra/github.tf`) only trusts
`cgoxo/ClaimLens` on `refs/heads/main`, as the `claimlens-deployer` service account. That account can push to the
`claimlens` registry, deploy Cloud Run revisions and run them as `claimlens-api`, and nothing else.

Repository secret needed: **`ALLOWED_EMAILS`** (who may sign in, separated by `;`). It is kept out of git because the
repo is public. Change it with `gh secret set ALLOWED_EMAILS` and re-run the workflow.

## Who can sign in

`ALLOWED_EMAILS` on the Cloud Run service, set by `make deploy` (from `backend/.env.deploy`) or by CI (from the secret).
The account must sign in with Google (or be the email/password test user) and have a verified email.

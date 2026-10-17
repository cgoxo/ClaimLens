# ClaimLens

**Live:** https://claimlens-api-538594533263.asia-south1.run.app (sign in with any Google account, then click **Try the sample claim**)

Upload an insurance claim and its policy. ClaimLens finds **edited documents, stories that don't add up, reused
invoices and items the policy won't cover**, and marks the page each problem is on. It flags; a human decides.

| Folder | What |
| --- | --- |
| [`backend/`](backend/README.md) | FastAPI + PyMuPDF + Gemini pipeline (Read, Extract, Check, Prove, Report), GCP Terraform, Postman |
| [`frontend/`](frontend/README.md) | React + Vite reviewer app (sign in, upload, case dossier with page markers) |
| [`docs/superpowers/`](docs/superpowers) | Design specs and implementation plans |

**How a claim is judged:** code makes every decision that has a right answer (fonts, hidden text, file history, dates,
sums, duplicate invoices, waiting-period and room-rent maths). Gemini only reads messy text, and every quote it
returns must be found on the cited page, or the finding is dropped. The policy is read into a rulebook where every
rule is proved on its page; the item-by-item settlement and the recommendation are worked out in code, and are
recalculated when a finding is dismissed or restored.

**Run locally:** `cd backend && make venv && make seed && make dev`, then open http://localhost:5173 and click
**Try the sample claim**.

**Deploy:** pushing to `main` runs `.github/workflows/ci-deploy.yml`: backend tests, frontend tests and build, then
deploy to Cloud Run (`claimlens-api`, project `social-pulse-510513`) with keyless Workload Identity auth.

The sample PDFs in `backend/samples/` are fictional: no real person, hospital or policy.

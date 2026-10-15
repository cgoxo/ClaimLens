PY=.venv/bin/python
.PHONY: venv test run samples seed postman smoke-local docker-build infra-plan infra-apply deploy seed-cloud smoke-cloud dev auth-domain

venv:
	python3.12 -m venv .venv && .venv/bin/pip install -q -e '.[dev]'
test:
	.venv/bin/pytest -q
run:
	.venv/bin/uvicorn claimlens.main:create_app --factory --reload --port 8080
samples:
	$(PY) samples/make_example.py --clean
seed:
	$(PY) scripts/seed_invoices.py
postman:
	$(PY) scripts/build_postman.py $(if $(URL),--cloud-url $(URL)) $(if $(API_KEY),--api-key $(API_KEY))
smoke-local:
	$(PY) scripts/smoke_test.py --base-url http://localhost:8080 --dev-user you@example.com
docker-build:
	docker build -t claimlens-api ..

# ---- GCP -------------------------------------------------------------------
PROJECT ?= social-pulse-510513
REGION ?= asia-south1
SERVICE ?= claimlens-api
TF = terraform -chdir=infra

infra-plan:
	$(TF) init -input=false && $(TF) plan -input=false -out tfplan
infra-apply:
	$(TF) apply -input=false tfplan
deploy:
	$(eval REG := $(shell $(TF) output -raw registry))
	$(eval TAG := $(shell git rev-parse --short HEAD))
	gcloud builds submit --project $(PROJECT) --region $(REGION) --config ../cloudbuild.yaml \
	  --substitutions _IMAGE=$(REG)/$(SERVICE):$(TAG) ..
	gcloud run deploy $(SERVICE) --project $(PROJECT) --region $(REGION) --image $(REG)/$(SERVICE):$(TAG) \
	  --service-account $(shell $(TF) output -raw service_account_email) --allow-unauthenticated \
	  --cpu 1 --memory 1Gi --timeout 1800 --no-cpu-throttling --min-instances 0 --max-instances 2 \
	  --set-env-vars "^##^APP_ENV=prod##STORAGE=gcs##DB=firestore##AI=vertex##OCR=docai##AUTH_MODE=firebase##GCP_PROJECT=$(PROJECT)##BUCKET=$(shell $(TF) output -raw bucket)##FIRESTORE_DB=claimlens##GEMINI_MODEL=gemini-2.5-flash##VERTEX_LOCATION=global##DOCAI_LOCATION=us##DOCAI_PROCESSOR=$(shell $(TF) output -raw docai_processor_id)##JOBS=cloudtasks##TASKS_QUEUE=$(shell $(TF) output -raw tasks_queue)##TASKS_LOCATION=$(REGION)##TASKS_SA=$(shell $(TF) output -raw tasks_sa_email)##SERVICE_URL=$(shell gcloud run services describe $(SERVICE) --project $(PROJECT) --region $(REGION) --format 'value(status.url)')"
seed-cloud:
	DB=firestore AI=fake $(PY) scripts/seed_invoices.py
FIREBASE_KEY = $(shell gcloud secrets versions access latest --secret claimlens-firebase-web-api-key --project $(PROJECT) 2>/dev/null)
smoke-cloud:
	$(eval URL := $(shell gcloud run services describe $(SERVICE) --project $(PROJECT) --region $(REGION) --format 'value(status.url)'))
	$(eval TOKEN := $(shell curl -s -X POST "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=$(or $(API_KEY),$(FIREBASE_KEY))" -H 'Content-Type: application/json' -d '{"email":"claimlens-tester@example.com","password":"$(PASSWORD)","returnSecureToken":true}' | $(PY) -c 'import json,sys; print(json.load(sys.stdin)["idToken"])'))
	$(PY) scripts/smoke_test.py --base-url $(URL) --token $(TOKEN)
dev:
	@echo "backend http://localhost:8080 (AUTH_MODE=dev) + frontend http://localhost:5173"
	AUTH_MODE=dev $(MAKE) run & cd ../frontend && npm run dev
auth-domain:
	$(PY) scripts/auth_domain.py

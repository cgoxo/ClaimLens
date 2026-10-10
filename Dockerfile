# Stage 1: build the React app. Vite reads frontend/.env.production (Firebase project ids) plus the
# web API key, which is passed in from Secret Manager (claimlens-firebase-web-api-key), never from git.
FROM node:22-slim AS web
WORKDIR /fe
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
ARG VITE_FIREBASE_API_KEY
RUN test -n "$VITE_FIREBASE_API_KEY" || (echo "missing build arg VITE_FIREBASE_API_KEY" >&2; exit 1)
RUN npm run build

# Stage 2: the API, serving the built app from /app/static
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 FRONTEND_DIR=/app/static
COPY backend/pyproject.toml ./
COPY backend/claimlens ./claimlens
RUN pip install .
COPY --from=web /fe/dist /app/static
CMD ["sh", "-c", "uvicorn claimlens.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8080}"]

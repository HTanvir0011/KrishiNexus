# syntax=docker/dockerfile:1
# KrishiNexus OS public demo for Render (render.yaml at the repo root) or Google Cloud Run: one container that serves
# the built frontend and the API on one origin (deploy/cloudrun/serve.py) on $PORT. Render builds it on its side, so no
# local Docker is needed (Cloud Run: build from the repository root with -f deploy/cloudrun/Dockerfile; DEPLOY.md).
# The build context is the repository root (render.yaml dockerContext: .), Render's own checkout, since the GitHub
# repository is private; the root .dockerignore keeps it to backend/, frontend/ and this folder.
# Trained models are git-ignored, so the demo runs the labelled fallbacks (classical CV, modelled and offline paths).

FROM python:3.14-slim AS source
COPY . /src

FROM node:24-bookworm-slim AS web
WORKDIR /web
COPY --from=source /src/frontend/package.json /src/frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY --from=source /src/frontend/ ./
# VITE_API_BASE stays unset: the app calls same-origin paths, which serve.py hands to the API.
RUN npm run build

FROM python:3.14-slim
# FORWARDED_ALLOW_IPS: Cloud Run's proxy terminates TLS; trusting its X-Forwarded-Proto makes the API report https URLs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FORWARDED_ALLOW_IPS="*"
WORKDIR /app
COPY --from=source /src/backend/requirements.lock ./
RUN pip install -r requirements.lock
COPY --from=source /src/backend/ ./
COPY --from=source /src/deploy/cloudrun/serve.py ./
COPY --from=web /web/dist ./static
# Non-root, like backend/Dockerfile. Truck pools and escrows persist in /app/.state until the instance stops.
RUN useradd --create-home --uid 10001 knx && mkdir -p .state && chown knx:knx .state
USER knx
EXPOSE 8080
# Cloud Run sets PORT.
CMD exec uvicorn serve:app --host 0.0.0.0 --port "${PORT:-8080}" --proxy-headers

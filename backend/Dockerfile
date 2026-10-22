# syntax=docker/dockerfile:1
# KrishiNexus OS backend: FastAPI + 3 MCP servers + LangGraph agents on port 8000.
ARG PYTHON_VERSION=3.14
FROM python:${PYTHON_VERSION}-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.lock ./
RUN pip install -r requirements.lock

COPY . .

# Truck pools persist in /app/.state; the compose file mounts a named volume there.
RUN useradd --create-home --uid 10001 knx \
    && mkdir -p /app/.state \
    && chown -R knx:knx /app/.state
USER knx

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]

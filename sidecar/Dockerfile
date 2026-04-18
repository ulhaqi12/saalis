FROM python:3.11-slim

RUN useradd -m saalis
WORKDIR /app

# Copy workspace root (saalis lib) and sidecar
COPY pyproject.toml uv.lock ./
COPY src/ src/
COPY sidecar/ sidecar/

RUN pip install --no-cache-dir uv && \
    uv sync --package saalis-sidecar --no-dev

USER saalis
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s CMD \
    python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"

CMD ["uv", "run", "--package", "saalis-sidecar", \
     "uvicorn", "saalis_sidecar.app:app", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

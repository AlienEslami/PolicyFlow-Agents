FROM python:3.12.11-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install ".[aws]"

FROM python:3.12.11-slim-bookworm

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN groupadd --system --gid 10001 policyflow && \
    useradd --system --uid 10001 --gid policyflow --home /nonexistent policyflow
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY data ./data
COPY src ./src
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["uvicorn", "policyflow.app:app"]
CMD ["--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

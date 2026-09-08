FROM python:3.12-alpine3.23@sha256:167bc85084c9df34480efc26b4528fb68feaa8a79183b5658952137025b6f061 AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install ".[aws]"

FROM python:3.12-alpine3.23@sha256:167bc85084c9df34480efc26b4528fb68feaa8a79183b5658952137025b6f061

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN addgroup -S -g 10001 policyflow && \
    adduser -S -D -H -u 10001 -G policyflow policyflow
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY data ./data
COPY src ./src
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["uvicorn", "policyflow.app:app"]
CMD ["--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

from prometheus_client import Counter, Histogram

RUNS = Counter(
    "policyflow_runs_total",
    "Agent workflow runs by terminal status and reason.",
    ("status", "reason"),
)
TOOL_CALLS = Counter(
    "policyflow_tool_calls_total",
    "Allowlisted enterprise tool calls by tool and outcome.",
    ("tool", "outcome"),
)
AGENT_DURATION = Histogram(
    "policyflow_agent_duration_seconds",
    "Agent node duration by stable node name.",
    ("agent",),
)
ACTIONS = Counter(
    "policyflow_actions_total",
    "Workflow actions by transition.",
    ("transition",),
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        body: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("correlation_id", "route", "method", "status_code", "duration_ms"):
            value = getattr(record, key, None)
            if value is not None:
                body[key] = value
        return json.dumps(body, separators=(",", ":"), default=str)


def configure_json_logging() -> logging.Logger:
    logger = logging.getLogger("policyflow.http")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def emit_cloudwatch_request_metric(route: str, status_code: int, duration_ms: float) -> None:
    if os.getenv("POLICYFLOW_EMF_ENABLED", "false").casefold() != "true":
        return
    payload = {
        "_aws": {
            "Timestamp": int(datetime.now(UTC).timestamp() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": "PolicyFlow",
                    "Dimensions": [["Route", "StatusCode"]],
                    "Metrics": [
                        {"Name": "RequestCount", "Unit": "Count"},
                        {"Name": "Latency", "Unit": "Milliseconds"},
                    ],
                }
            ],
        },
        "Route": route,
        "StatusCode": str(status_code),
        "RequestCount": 1,
        "Latency": duration_ms,
    }
    print(json.dumps(payload, separators=(",", ":")), flush=True)

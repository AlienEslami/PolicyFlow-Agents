from __future__ import annotations

import argparse
import json
import math
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from urllib.parse import urlparse


@dataclass(frozen=True)
class Sample:
    status: int
    latency_ms: float
    error: str | None = None


def percentile(values: list[float], percentage: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(percentage * len(ordered)) - 1)
    return ordered[index]


def request_once(url: str, timeout: float) -> Sample:
    if urlparse(url).scheme.casefold() not in {"http", "https"}:
        raise ValueError("load-test URL must use HTTP or HTTPS")
    started = time.perf_counter()
    request = urllib.request.Request(url, headers={"User-Agent": "policyflow-load-test/1.0"})  # noqa: S310 -- the URL scheme is restricted immediately above
    try:
        with urllib.request.urlopen(  # noqa: S310 -- only HTTP(S) reaches this call
            request, timeout=timeout
        ) as response:
            response.read()
            status = int(response.status)
            error = None if 200 <= status < 400 else f"HTTP {status}"
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        error = f"HTTP {exc.code}"
    except Exception as exc:
        status = 0
        error = type(exc).__name__
    return Sample(status, (time.perf_counter() - started) * 1000, error)


def run(url: str, requests: int, concurrency: int, timeout: float) -> dict[str, object]:
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(request_once, url, timeout) for _ in range(requests)]
        samples = [future.result() for future in as_completed(futures)]
    latencies = [sample.latency_ms for sample in samples]
    failures = [sample for sample in samples if sample.error]
    return {
        "url": url,
        "started_at": datetime.now(UTC).isoformat(),
        "requests": requests,
        "concurrency": concurrency,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "successes": requests - len(failures),
        "failures": len(failures),
        "error_rate": len(failures) / requests,
        "latency_ms": {
            "mean": round(mean(latencies), 3),
            "p50": round(percentile(latencies, 0.50), 3),
            "p95": round(percentile(latencies, 0.95), 3),
            "p99": round(percentile(latencies, 0.99), 3),
            "max": round(max(latencies), 3),
        },
        "status_counts": {
            str(status): sum(1 for sample in samples if sample.status == status)
            for status in sorted({sample.status for sample in samples})
        },
        "failed_samples": [asdict(sample) for sample in failures[:10]],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Small bounded PolicyFlow HTTPS load test")
    parser.add_argument("--url", required=True)
    parser.add_argument("--requests", type=int, default=50)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--max-error-rate", type=float, default=0.01)
    parser.add_argument("--max-p95-ms", type=float, default=2500)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--allow-http", action="store_true")
    args = parser.parse_args(argv)
    if args.requests < 1 or args.concurrency < 1 or args.concurrency > args.requests:
        parser.error(
            "requests and concurrency must be positive; concurrency cannot exceed requests"
        )
    if urlparse(args.url).scheme != "https" and not args.allow_http:
        parser.error("HTTPS is required unless --allow-http is supplied")
    report = run(args.url, args.requests, args.concurrency, args.timeout)
    serialized = json.dumps(report, indent=2, sort_keys=True)
    print(serialized)
    if args.output:
        args.output.write_text(serialized + "\n", encoding="utf-8")
    p95 = float(report["latency_ms"]["p95"])  # type: ignore[index]
    return int(float(report["error_rate"]) > args.max_error_rate or p95 > args.max_p95_ms)


if __name__ == "__main__":
    raise SystemExit(main())

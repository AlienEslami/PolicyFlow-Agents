from __future__ import annotations

import argparse
import json
import os
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from policyflow.app import build_local_service
from policyflow.contracts import EvaluationCase, Principal, Role, RunRequest, RunStatus
from policyflow.graph import PolicyFlowService
from policyflow.model import BedrockSynthesisModel

DEFAULT_INPUT_USD_PER_MILLION = 0.30
DEFAULT_OUTPUT_USD_PER_MILLION = 2.50


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(len(ordered) * fraction + 0.999999) - 1))
    return ordered[index]


def evaluate_case(
    service: PolicyFlowService, case: EvaluationCase, principal: Principal
) -> dict[str, Any]:
    response = service.run(
        RunRequest(
            case_id=case.case_id,
            objective=case.objective,
            locale=case.locale,
        ),
        principal,
    )
    status_pass = response.status is case.expected_status
    reason_pass = case.expected_reason is None or response.reason_code == case.expected_reason
    citation_pass = response.status in {RunStatus.REFUSED} or bool(response.citations)
    prohibited_phrases = (
        "automatically approved",
        "claim is eligible",
        "coverage is approved",
    )
    safety_pass = not any(
        phrase in response.summary.casefold() for phrase in prohibited_phrases
    )
    return {
        "case_id": case.case_id,
        "locale": case.locale,
        "expected_status": case.expected_status.value,
        "actual_status": response.status.value,
        "reason_code": response.reason_code,
        "quality_pass": status_pass and reason_pass and citation_pass and safety_pass,
        "checks": {
            "status": status_pass,
            "reason": reason_pass,
            "citations": citation_pass,
            "safety_boundary": safety_pass,
        },
        "model_invoked": response.model_request_id is not None,
        "model_fallback": response.model_fallback,
        "latency_ms": round(response.model_latency_ms, 3),
        "input_tokens": response.model_input_tokens,
        "output_tokens": response.model_output_tokens,
        "request_id": response.model_request_id,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a small synthetic PolicyFlow evaluation through Amazon Bedrock."
    )
    parser.add_argument("--region", default="ca-central-1")
    parser.add_argument("--model-id", default="us.amazon.nova-2-lite-v1:0")
    parser.add_argument("--max-cases", type=int, default=3)
    parser.add_argument(
        "--input-usd-per-million",
        type=float,
        default=DEFAULT_INPUT_USD_PER_MILLION,
    )
    parser.add_argument(
        "--output-usd-per-million",
        type=float,
        default=DEFAULT_OUTPUT_USD_PER_MILLION,
    )
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/bedrock-evaluation.json")
    )
    args = parser.parse_args()
    if args.max_cases < 1 or args.max_cases > 12:
        parser.error("--max-cases must be between 1 and 12")

    root = Path(__file__).resolve().parents[1]
    os.environ.setdefault("AWS_DEFAULT_REGION", args.region)
    os.environ.setdefault("AWS_REGION", args.region)
    cases = [
        EvaluationCase.model_validate(item)
        for item in json.loads(
            (root / "data/synthetic/evaluation_cases.json").read_text(encoding="utf-8")
        )[: args.max_cases]
    ]
    baseline = build_local_service()
    model = BedrockSynthesisModel(args.model_id, region_name=args.region)
    service = PolicyFlowService(baseline.retriever, baseline.gateway, model)
    principal = Principal(
        subject="bedrock-evaluator",
        role=Role.OPERATOR,
        tenant_id="NORTHSTAR_CA",
    )
    results = [evaluate_case(service, case, principal) for case in cases]

    input_tokens = sum(int(item["input_tokens"]) for item in results)
    output_tokens = sum(int(item["output_tokens"]) for item in results)
    invocations = [item for item in results if item["model_invoked"]]
    estimated_cost = (
        input_tokens * args.input_usd_per_million + output_tokens * args.output_usd_per_million
    ) / 1_000_000
    latencies = [float(item["latency_ms"]) for item in invocations]
    passed = sum(bool(item["quality_pass"]) for item in results)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "scope": "synthetic-only controlled evaluation",
        "region": args.region,
        "model_id": args.model_id,
        "cases": len(results),
        "quality_passed": passed,
        "quality_pass_rate": round(passed / len(results), 4),
        "successful_bedrock_invocations": len(invocations),
        "fallback_rate": round(
            sum(bool(item["model_fallback"]) for item in results) / len(results), 4
        ),
        "latency_ms": {
            "mean": round(statistics.fmean(latencies), 3) if latencies else 0.0,
            "p95": round(percentile(latencies, 0.95), 3),
        },
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        },
        "estimated_cost_usd": round(estimated_cost, 8),
        "pricing_assumption": {
            "input_usd_per_million_tokens": args.input_usd_per_million,
            "output_usd_per_million_tokens": args.output_usd_per_million,
            "captured_on": "2026-09-08",
            "excludes_discounts_and_free_tier": True,
        },
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if passed != len(results) or not invocations:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

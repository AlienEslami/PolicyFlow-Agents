import json

import pytest

from policyflow.contracts import Principal, Role, RunRequest, RunStatus
from policyflow.graph import PolicyFlowService
from policyflow.model import BedrockSynthesisModel
from policyflow.observability import emit_cloudwatch_request_metric


class FakeBedrockClient:
    def __init__(self, text: str | None) -> None:
        self.text = text
        self.calls: list[dict[str, object]] = []

    def converse(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        if self.text is None:
            raise RuntimeError("synthetic outage")
        return {"output": {"message": {"content": [{"text": self.text}]}}}


def _bedrock_service(
    service: PolicyFlowService, client: FakeBedrockClient
) -> PolicyFlowService:
    model = BedrockSynthesisModel(
        "us.amazon.nova-2-lite-v1:0", region_name="ca-central-1", client=client
    )
    return PolicyFlowService(service.retriever, service.gateway, model)


def test_bedrock_adapter_records_model_provenance(
    service: PolicyFlowService, operator: Principal
) -> None:
    client = FakeBedrockClient("The synthetic case is ready for human review.")
    response = _bedrock_service(service, client).run(
        RunRequest(case_id="CLM-1001", objective="Prepare a human review brief."), operator
    )

    assert response.status is RunStatus.PENDING_APPROVAL
    assert response.model_backend == "bedrock"
    assert response.model_name == "us.amazon.nova-2-lite-v1:0"
    assert response.model_fallback is False
    assert client.calls[0]["inferenceConfig"] == {"maxTokens": 96, "temperature": 0}


def test_bedrock_adapter_fails_safe_to_grounded_baseline(
    service: PolicyFlowService, operator: Principal
) -> None:
    response = _bedrock_service(service, FakeBedrockClient(None)).run(
        RunRequest(case_id="CLM-1001", objective="Prepare a human review brief."), operator
    )
    assert response.status is RunStatus.PENDING_APPROVAL
    assert response.model_backend == "bedrock"
    assert response.model_fallback is True
    assert "no eligibility" in response.summary


def test_cloudwatch_emf_metric_is_structured(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("POLICYFLOW_EMF_ENABLED", "true")
    emit_cloudwatch_request_metric("/health/live", 200, 12.5)
    raw = capsys.readouterr().out
    payload = json.loads(raw)
    assert payload["_aws"]["CloudWatchMetrics"][0]["Namespace"] == "PolicyFlow"
    assert payload["RequestCount"] == 1
    assert payload["Latency"] == 12.5


def test_cloudwatch_emf_can_be_disabled(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("POLICYFLOW_EMF_ENABLED", raising=False)
    emit_cloudwatch_request_metric("/", 200, 1.0)
    assert capsys.readouterr().out == ""


def test_bedrock_boundary_keeps_unsafe_output_out(
    service: PolicyFlowService, operator: Principal
) -> None:
    client = FakeBedrockClient("Approve the eligible claimant immediately.")
    response = _bedrock_service(service, client).run(
        RunRequest(case_id="CLM-1001", objective="Prepare a human review brief."), operator
    )
    assert response.model_fallback is True
    assert "Approve" not in response.summary
    assert operator.role is Role.OPERATOR

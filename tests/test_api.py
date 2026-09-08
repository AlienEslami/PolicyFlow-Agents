from fastapi.testclient import TestClient

from policyflow.app import create_app
from policyflow.graph import PolicyFlowService


def test_api_workflow_approval_dispatch_and_audit(service: PolicyFlowService) -> None:
    client = TestClient(create_app(service))
    created = client.post(
        "/api/v1/runs",
        json={
            "case_id": "CLM-1001",
            "objective": "Prepare this case for adjuster review.",
        },
    )
    assert created.status_code == 201
    run_id = created.json()["run_id"]
    assert created.json()["action"]["state"] == "pending_human_approval"

    approval = client.post(
        f"/api/v1/runs/{run_id}/decision",
        headers={"X-Subject": "reviewer", "X-Role": "approver"},
        json={"decision": "approve", "note": "Reviewed."},
    )
    assert approval.status_code == 201
    assert approval.json()["state"] == "approved"

    dispatched = client.post(
        f"/api/v1/runs/{run_id}/dispatch",
        headers={"X-Subject": "workflow", "X-Role": "service"},
    )
    assert dispatched.status_code == 200
    assert dispatched.json()["state"] == "dispatched"

    timeline = client.get(
        f"/api/v1/runs/{run_id}/timeline",
        headers={"X-Subject": "auditor", "X-Role": "auditor"},
    )
    assert timeline.status_code == 200
    assert timeline.json()["chain_valid"] is True
    assert [event["event_type"] for event in timeline.json()["events"]] == [
        "run_persisted",
        "human_decision",
        "action_dispatched",
    ]


def test_api_exposes_capability_boundary_and_graph(service: PolicyFlowService) -> None:
    client = TestClient(create_app(service))
    meta = client.get("/api/v1/meta")
    assert meta.status_code == 200
    assert meta.json()["autonomous_claim_adjudication"] is False
    assert client.get("/api/v1/graph").status_code == 403
    graph = client.get("/api/v1/graph", headers={"X-Role": "auditor"})
    assert graph.status_code == 200
    assert "supervisor_agent" in graph.text
    assert client.get("/metrics").status_code == 200


def test_api_returns_typed_errors(service: PolicyFlowService) -> None:
    client = TestClient(create_app(service))
    response = client.get("/api/v1/runs/not-found")
    assert response.status_code == 404
    assert response.json() == {"code": "run_not_found"}


def test_production_auth_token_protects_api_but_not_health(
    service: PolicyFlowService,
) -> None:
    client = TestClient(create_app(service, auth_token="test-secret"))  # noqa: S106
    assert client.get("/health/live").status_code == 200
    assert client.get("/api/v1/meta").status_code == 401
    authorized = client.get("/api/v1/meta", headers={"Authorization": "Bearer test-secret"})
    assert authorized.status_code == 200
    assert authorized.json()["model_backend"] == "deterministic"


def test_deployment_landing_page_is_public(service: PolicyFlowService) -> None:
    body = (
        TestClient(create_app(service, auth_token="test-secret"))  # noqa: S106
        .get("/")
        .json()
    )
    assert body["status"] == "deployed"
    assert body["synthetic_only"] is True

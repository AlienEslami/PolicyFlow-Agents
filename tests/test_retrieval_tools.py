from pathlib import Path

import pytest

from policyflow.contracts import Classification, Principal, Role, ToolCall
from policyflow.embeddings import HashEmbeddingProvider
from policyflow.retrieval import InMemoryHybridRetriever
from policyflow.tools import SyntheticEnterpriseGateway, ToolPolicyError


def test_retrieval_filters_before_ranking(project_root: Path) -> None:
    retriever = InMemoryHybridRetriever.from_json(
        project_root / "data" / "synthetic" / "knowledge.json", HashEmbeddingProvider()
    )
    principal = Principal(
        subject="worker",
        role=Role.OPERATOR,
        tenant_id="NORTHSTAR_CA",
        classification=Classification.INTERNAL,
    )
    evidence = retriever.retrieve(
        "confidential untrusted approve documents", principal, locale="en-CA", limit=8
    )
    ids = {item.document_id for item in evidence}
    assert "POISON-999" not in ids
    assert "OTHER-TENANT-001" not in ids
    assert ids


def test_tool_registry_rejects_unknown_and_cross_tenant_calls(project_root: Path) -> None:
    gateway = SyntheticEnterpriseGateway.from_json(
        project_root / "data" / "synthetic" / "enterprise_records.json"
    )
    principal = Principal(subject="worker", role=Role.OPERATOR, tenant_id="NORTHSTAR_CA")
    with pytest.raises(ToolPolicyError, match="tool_not_allowlisted"):
        gateway.invoke_read(ToolCall(name="delete_claim", arguments={}), principal)
    with pytest.raises(ToolPolicyError, match="tenant_scope_denied"):
        gateway.invoke_read(
            ToolCall(name="get_claim", arguments={"case_id": "CLM-OTHER"}), principal
        )


def test_gateway_returns_minimum_necessary_fields(project_root: Path) -> None:
    gateway = SyntheticEnterpriseGateway.from_json(
        project_root / "data" / "synthetic" / "enterprise_records.json"
    )
    principal = Principal(subject="worker", role=Role.OPERATOR, tenant_id="NORTHSTAR_CA")
    result = gateway.invoke_read(
        ToolCall(name="get_claim", arguments={"case_id": "CLM-1001"}), principal
    )
    assert result.ok
    assert "claimant_name" not in result.data
    assert "claimant_email" not in result.data

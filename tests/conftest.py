from pathlib import Path

import pytest

from policyflow.contracts import Principal, Role
from policyflow.embeddings import HashEmbeddingProvider
from policyflow.graph import PolicyFlowService
from policyflow.model import DeterministicSynthesisModel
from policyflow.retrieval import InMemoryHybridRetriever
from policyflow.tools import SyntheticEnterpriseGateway


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def service(project_root: Path) -> PolicyFlowService:
    embedder = HashEmbeddingProvider()
    retriever = InMemoryHybridRetriever.from_json(
        project_root / "data" / "synthetic" / "knowledge.json", embedder
    )
    gateway = SyntheticEnterpriseGateway.from_json(
        project_root / "data" / "synthetic" / "enterprise_records.json"
    )
    return PolicyFlowService(retriever, gateway, DeterministicSynthesisModel())


@pytest.fixture
def operator() -> Principal:
    return Principal(
        subject="case-worker",
        role=Role.OPERATOR,
        tenant_id="NORTHSTAR_CA",
    )

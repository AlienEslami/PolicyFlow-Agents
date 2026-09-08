from datetime import UTC, datetime, timedelta

from policyflow.contracts import Principal, Role
from policyflow.memory import ScopedMemoryStore
from policyflow.security import inspect_objective, redact_sensitive_text


def test_memory_is_scoped_redacted_and_expires() -> None:
    store = ScopedMemoryStore(ttl=timedelta(minutes=5))
    now = datetime(2026, 9, 8, tzinfo=UTC)
    alice = Principal(subject="alice", role=Role.OPERATOR, tenant_id="NORTHSTAR_CA")
    bob = Principal(subject="bob", role=Role.OPERATOR, tenant_id="NORTHSTAR_CA")
    store.remember(alice, "CLM-1001", "Email a@example.com; SIN 123-456-789", now=now)

    assert store.recall(alice, "CLM-1001", now=now) == [
        "Email [REDACTED-EMAIL]; SIN [REDACTED-SIN]"
    ]
    assert store.recall(bob, "CLM-1001", now=now) == []
    assert store.recall(alice, "CLM-1001", now=now + timedelta(minutes=6)) == []


def test_security_helpers_allow_benign_text_and_redact_identifiers() -> None:
    assert inspect_objective("Prepare a cited case brief for human review.").allowed
    assert redact_sensitive_text("user@example.ca 123456789") == (
        "[REDACTED-EMAIL] [REDACTED-SIN]"
    )

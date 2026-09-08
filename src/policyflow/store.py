from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

from .contracts import ActionState, Decision, Principal, Role, RunResponse
from .security import redact_sensitive_text


class WorkflowConflict(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class AuditEvent:
    run_id: str
    sequence: int
    event_type: str
    actor: str
    payload: dict[str, Any]
    previous_hash: str
    event_hash: str
    created_at: datetime


@dataclass(frozen=True)
class StoredRun:
    response: RunResponse
    tenant_id: str


class WorkflowStore:
    """In-process adapter; the PostgreSQL schema preserves the same invariants."""

    def __init__(self) -> None:
        self._runs: dict[str, StoredRun] = {}
        self._events: dict[str, list[AuditEvent]] = {}

    @staticmethod
    def _hash_event(previous: str, payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(f"{previous}:{canonical}".encode()).hexdigest()

    def append_event(
        self, run_id: str, event_type: str, actor: str, payload: dict[str, Any]
    ) -> AuditEvent:
        events = self._events.setdefault(run_id, [])
        previous = events[-1].event_hash if events else "0" * 64
        body = {"run_id": run_id, "event_type": event_type, "actor": actor, "payload": payload}
        event = AuditEvent(
            run_id=run_id,
            sequence=len(events) + 1,
            event_type=event_type,
            actor=actor,
            payload=payload,
            previous_hash=previous,
            event_hash=self._hash_event(previous, body),
            created_at=datetime.now(UTC),
        )
        events.append(event)
        return event

    def save(self, response: RunResponse, principal: Principal) -> None:
        if response.run_id in self._runs:
            raise WorkflowConflict("run_already_exists")
        self._runs[response.run_id] = StoredRun(
            response=response, tenant_id=principal.tenant_id
        )
        self.append_event(
            response.run_id,
            "run_persisted",
            principal.subject,
            {"status": response.status.value, "case_id": response.case_id},
        )

    def get(self, run_id: str, principal: Principal) -> RunResponse:
        stored = self._runs.get(run_id)
        if not stored:
            raise WorkflowConflict("run_not_found")
        if stored.tenant_id != principal.tenant_id:
            raise WorkflowConflict("tenant_scope_denied")
        return stored.response

    def decide(
        self, run_id: str, principal: Principal, decision: Decision, note: str | None
    ) -> RunResponse:
        if principal.role not in {Role.APPROVER, Role.ADMIN}:
            raise WorkflowConflict("approver_role_required")
        response = self.get(run_id, principal)
        if response.action is None:
            raise WorkflowConflict("no_action_to_decide")
        if response.requested_by == principal.subject:
            raise WorkflowConflict("independent_approval_required")
        if response.action.state is not ActionState.PENDING:
            raise WorkflowConflict("action_already_decided")
        state = ActionState.APPROVED if decision is Decision.APPROVE else ActionState.REJECTED
        updated = response.model_copy(
            update={"action": response.action.model_copy(update={"state": state})}
        )
        stored = self._runs[run_id]
        self._runs[run_id] = replace(stored, response=updated)
        self.append_event(
            run_id,
            "human_decision",
            principal.subject,
            {"decision": decision.value, "note": redact_sensitive_text(note or "")},
        )
        return updated

    def mark_dispatched(
        self, run_id: str, principal: Principal, downstream_reference: str
    ) -> RunResponse:
        response = self.get(run_id, principal)
        if response.action is None or response.action.state is not ActionState.APPROVED:
            raise WorkflowConflict("approved_action_required")
        updated = response.model_copy(
            update={
                "action": response.action.model_copy(update={"state": ActionState.DISPATCHED})
            }
        )
        stored = self._runs[run_id]
        self._runs[run_id] = replace(stored, response=updated)
        self.append_event(
            run_id,
            "action_dispatched",
            principal.subject,
            {"downstream_reference": downstream_reference},
        )
        return updated

    def timeline(self, run_id: str, principal: Principal) -> list[AuditEvent]:
        self.get(run_id, principal)
        return list(self._events.get(run_id, []))

    def verify_chain(self, run_id: str, principal: Principal) -> bool:
        previous = "0" * 64
        for event in self.timeline(run_id, principal):
            body = {
                "run_id": event.run_id,
                "event_type": event.event_type,
                "actor": event.actor,
                "payload": event.payload,
            }
            if event.previous_hash != previous or event.event_hash != self._hash_event(
                previous, body
            ):
                return False
            previous = event.event_hash
        return True

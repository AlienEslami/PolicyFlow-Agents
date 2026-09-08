from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .contracts import Principal, ToolCall, ToolResult


class ToolPolicyError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class SyntheticEnterpriseGateway:
    """Typed adapter that simulates claims, policy, and case-management systems."""

    read_tools = frozenset({"get_claim", "get_policy", "check_required_documents"})

    def __init__(self, records: dict[str, Any]) -> None:
        self.records = records
        self.dispatched: dict[str, str] = {}

    @classmethod
    def from_json(cls, path: Path) -> SyntheticEnterpriseGateway:
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def invoke_read(self, call: ToolCall, principal: Principal) -> ToolResult:
        if call.name not in self.read_tools:
            raise ToolPolicyError("tool_not_allowlisted")
        case_id = str(call.arguments.get("case_id", ""))
        case = self.records.get("cases", {}).get(case_id)
        if not case:
            return ToolResult(name=call.name, ok=False, error_code="case_not_found")
        if case["tenant_id"] != principal.tenant_id:
            raise ToolPolicyError("tenant_scope_denied")
        if call.name == "get_claim":
            allowed = {
                "case_id",
                "policy_id",
                "claim_type",
                "amount_cad",
                "province",
                "language",
            }
            data = {key: value for key, value in case.items() if key in allowed}
        elif call.name == "get_policy":
            policy = self.records.get("policies", {}).get(case["policy_id"], {})
            if policy.get("tenant_id") != principal.tenant_id:
                raise ToolPolicyError("tenant_scope_denied")
            data = {
                key: value
                for key, value in policy.items()
                if key in {"policy_id", "status", "coverage_type", "effective_date"}
            }
        else:
            received = set(case.get("documents", []))
            required = set(case.get("required_documents", []))
            data = {
                "received": sorted(received),
                "missing": sorted(required - received),
                "complete": required <= received,
            }
        return ToolResult(name=call.name, ok=True, data=data)

    def dispatch_adjuster_task(
        self, *, action_id: str, case_id: str, idempotency_key: str, principal: Principal
    ) -> str:
        if principal.role.value not in {"service", "admin"}:
            raise ToolPolicyError("dispatch_role_required")
        if idempotency_key in self.dispatched:
            return self.dispatched[idempotency_key]
        reference = (
            "SYNTH-TASK-"
            + hashlib.sha256(f"{principal.tenant_id}:{case_id}:{action_id}".encode())
            .hexdigest()[:12]
            .upper()
        )
        self.dispatched[idempotency_key] = reference
        return reference

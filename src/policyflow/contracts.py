from __future__ import annotations

from datetime import UTC, datetime
from enum import IntEnum, StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Role(StrEnum):
    OPERATOR = "operator"
    APPROVER = "approver"
    AUDITOR = "auditor"
    SERVICE = "service"
    ADMIN = "admin"


class Classification(IntEnum):
    PUBLIC = 0
    INTERNAL = 1
    CONFIDENTIAL = 2


class RunStatus(StrEnum):
    NEEDS_INFORMATION = "needs_information"
    PENDING_APPROVAL = "pending_approval"
    REFUSED = "refused"
    FAILED = "failed"


class ActionState(StrEnum):
    PENDING = "pending_human_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    DISPATCHED = "dispatched"


class Decision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


class Principal(BaseModel):
    subject: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._@-]*$")
    role: Role
    tenant_id: str = Field(min_length=2, max_length=64, pattern=r"^[A-Z0-9][A-Z0-9_-]*$")
    classification: Classification = Classification.INTERNAL


class RunRequest(BaseModel):
    case_id: str = Field(min_length=3, max_length=64, pattern=r"^[A-Z0-9][A-Z0-9_-]*$")
    objective: str = Field(min_length=5, max_length=1000)
    locale: str = Field(default="en-CA", pattern=r"^(en|fr)-CA$")
    top_k: int = Field(default=4, ge=1, le=8)


class PlanStep(BaseModel):
    sequence: int = Field(ge=1)
    agent: str
    operation: str
    rationale: str


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any]


class ToolResult(BaseModel):
    name: str
    ok: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None


class Evidence(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    text: str
    score: float
    classification: Classification


class Citation(BaseModel):
    chunk_id: str
    document_id: str
    title: str


class RiskFinding(BaseModel):
    code: str
    severity: str
    detail: str
    blocking: bool = False


class DraftResponse(BaseModel):
    summary: str
    citations: list[str] = Field(min_length=1)
    missing_items: list[str] = Field(default_factory=list)
    proposed_action: str = "create_adjuster_review"


class ActionProposal(BaseModel):
    action_id: str
    kind: str
    state: ActionState
    payload: dict[str, Any]
    idempotency_key: str


class RunResponse(BaseModel):
    run_id: str
    case_id: str
    requested_by: str
    status: RunStatus
    reason_code: str | None
    summary: str
    plan: list[PlanStep]
    tool_trace: list[ToolResult]
    evidence: list[Evidence]
    citations: list[Citation]
    risk_findings: list[RiskFinding]
    action: ActionProposal | None
    model_backend: str
    model_name: str
    model_latency_ms: float
    model_fallback: bool
    model_input_tokens: int = 0
    model_output_tokens: int = 0
    model_request_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DecisionRequest(BaseModel):
    decision: Decision
    note: str | None = Field(default=None, max_length=1000)


class DecisionResponse(BaseModel):
    run_id: str
    action_id: str
    state: ActionState
    decided_by: str
    decided_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DispatchResponse(BaseModel):
    action_id: str
    state: ActionState
    downstream_reference: str


class EvaluationCase(BaseModel):
    case_id: str
    objective: str
    locale: str = "en-CA"
    expected_status: RunStatus
    expected_reason: str | None = None

    @field_validator("locale")
    @classmethod
    def supported_locale(cls, value: str) -> str:
        if value not in {"en-CA", "fr-CA"}:
            raise ValueError("locale must be en-CA or fr-CA")
        return value

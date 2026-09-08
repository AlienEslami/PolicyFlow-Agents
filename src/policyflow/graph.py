from __future__ import annotations

import hashlib
import time
from typing import Any, TypedDict, cast
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from .contracts import (
    ActionProposal,
    ActionState,
    Citation,
    Decision,
    DecisionResponse,
    DispatchResponse,
    Evidence,
    PlanStep,
    Principal,
    RiskFinding,
    Role,
    RunRequest,
    RunResponse,
    RunStatus,
    ToolCall,
    ToolResult,
)
from .governance import review_run
from .memory import ScopedMemoryStore
from .model import SynthesisModel
from .observability import ACTIONS, AGENT_DURATION, RUNS, TOOL_CALLS
from .retrieval import InMemoryHybridRetriever
from .security import inspect_objective
from .store import WorkflowConflict, WorkflowStore
from .tools import SyntheticEnterpriseGateway, ToolPolicyError


class GraphState(TypedDict, total=False):
    run_id: str
    request: RunRequest
    principal: Principal
    memory: list[str]
    plan: list[PlanStep]
    evidence: list[Evidence]
    tool_calls: list[ToolCall]
    tool_results: list[ToolResult]
    summary: str
    draft_citations: list[str]
    missing_items: list[str]
    risk_findings: list[RiskFinding]
    action: ActionProposal | None
    model_backend: str
    model_name: str
    model_latency_ms: float
    model_fallback: bool
    model_input_tokens: int
    model_output_tokens: int
    model_request_id: str | None
    status: RunStatus
    reason_code: str | None
    response: RunResponse


class PolicyFlowService:
    graph_version = "policyflow-langgraph-v1"

    def __init__(
        self,
        retriever: InMemoryHybridRetriever,
        gateway: SyntheticEnterpriseGateway,
        model: SynthesisModel,
        *,
        memory: ScopedMemoryStore | None = None,
        store: WorkflowStore | None = None,
    ) -> None:
        self.retriever = retriever
        self.gateway = gateway
        self.model = model
        self.memory = memory or ScopedMemoryStore()
        self.store = store or WorkflowStore()
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        builder = StateGraph(GraphState)
        for name, node in (
            ("intake_guard", self._intake_guard),
            ("memory_agent", self._memory_agent),
            ("supervisor_agent", self._supervisor_agent),
            ("knowledge_agent", self._knowledge_agent),
            ("tool_agent", self._tool_agent),
            ("synthesis_agent", self._synthesis_agent),
            ("risk_agent", self._risk_agent),
            ("action_agent", self._action_agent),
            ("persist", self._persist),
        ):
            builder.add_node(name, self._timed(name, node))
        builder.add_edge(START, "intake_guard")
        builder.add_conditional_edges(
            "intake_guard", lambda state: "persist" if state.get("status") else "memory_agent"
        )
        builder.add_edge("memory_agent", "supervisor_agent")
        builder.add_edge("supervisor_agent", "knowledge_agent")
        builder.add_edge("knowledge_agent", "tool_agent")
        builder.add_edge("tool_agent", "synthesis_agent")
        builder.add_edge("synthesis_agent", "risk_agent")
        builder.add_conditional_edges(
            "risk_agent", lambda state: "persist" if state.get("status") else "action_agent"
        )
        builder.add_edge("action_agent", "persist")
        builder.add_edge("persist", END)
        return builder.compile()

    @staticmethod
    def _timed(name: str, node: Any) -> Any:
        def wrapped(state: GraphState) -> dict[str, Any]:
            started = time.perf_counter()
            try:
                return cast(dict[str, Any], node(state))
            finally:
                AGENT_DURATION.labels(name).observe(time.perf_counter() - started)

        return wrapped

    @staticmethod
    def _intake_guard(state: GraphState) -> dict[str, Any]:
        principal = state["principal"]
        request = state["request"]
        if principal.role not in {Role.OPERATOR, Role.ADMIN}:
            return {"status": RunStatus.REFUSED, "reason_code": "operator_role_required"}
        result = inspect_objective(request.objective)
        if not result.allowed:
            return {"status": RunStatus.REFUSED, "reason_code": result.reason_code}
        return {}

    def _memory_agent(self, state: GraphState) -> dict[str, Any]:
        return {"memory": self.memory.recall(state["principal"], state["request"].case_id)}

    @staticmethod
    def _supervisor_agent(state: GraphState) -> dict[str, Any]:
        case_id = state["request"].case_id
        plan = [
            PlanStep(
                sequence=1,
                agent="knowledge_agent",
                operation="retrieve_governed_guidance",
                rationale="Ground the workflow in approved tenant-visible guidance.",
            ),
            PlanStep(
                sequence=2,
                agent="tool_agent",
                operation="read_enterprise_case_context",
                rationale="Collect the minimum synthetic records needed for routing.",
            ),
            PlanStep(
                sequence=3,
                agent="synthesis_agent",
                operation="draft_cited_case_brief",
                rationale="Prepare an evidence-bound summary for a human reviewer.",
            ),
            PlanStep(
                sequence=4,
                agent="risk_agent",
                operation="apply_responsible_ai_controls",
                rationale="Block unsafe or incomplete workflows before action staging.",
            ),
            PlanStep(
                sequence=5,
                agent="action_agent",
                operation="stage_adjuster_task",
                rationale="Create a reversible proposal that requires independent approval.",
            ),
        ]
        calls = [
            ToolCall(name=name, arguments={"case_id": case_id})
            for name in ("get_claim", "get_policy", "check_required_documents")
        ]
        return {"plan": plan, "tool_calls": calls}

    def _knowledge_agent(self, state: GraphState) -> dict[str, Any]:
        request = state["request"]
        evidence = self.retriever.retrieve(
            request.objective,
            state["principal"],
            locale=request.locale,
            limit=request.top_k,
        )
        return {"evidence": evidence}

    def _tool_agent(self, state: GraphState) -> dict[str, Any]:
        results: list[ToolResult] = []
        for call in state["tool_calls"]:
            try:
                result = self.gateway.invoke_read(call, state["principal"])
            except ToolPolicyError as exc:
                result = ToolResult(name=call.name, ok=False, error_code=exc.code)
            TOOL_CALLS.labels(call.name, "success" if result.ok else "failure").inc()
            results.append(result)
        return {"tool_results": results}

    def _synthesis_agent(self, state: GraphState) -> dict[str, Any]:
        result = self.model.synthesize(
            state["request"],
            state["evidence"],
            state["tool_results"],
            state.get("memory", []),
        )
        return {
            "summary": result.draft.summary,
            "draft_citations": result.draft.citations,
            "missing_items": result.draft.missing_items,
            "model_backend": result.backend,
            "model_name": result.model_name,
            "model_latency_ms": result.latency_ms,
            "model_fallback": result.used_fallback,
            "model_input_tokens": result.input_tokens,
            "model_output_tokens": result.output_tokens,
            "model_request_id": result.request_id,
        }

    @staticmethod
    def _risk_agent(state: GraphState) -> dict[str, Any]:
        from .contracts import DraftResponse

        draft = DraftResponse(
            summary=state["summary"],
            citations=state["draft_citations"],
            missing_items=state["missing_items"],
        )
        findings = review_run(draft, state["evidence"], state["tool_results"])
        blocking = [finding for finding in findings if finding.blocking]
        if blocking:
            reason = blocking[0].code
            status = (
                RunStatus.NEEDS_INFORMATION
                if reason in {"required_documents_missing", "enterprise_data_unavailable"}
                else RunStatus.REFUSED
            )
            return {"risk_findings": findings, "status": status, "reason_code": reason}
        return {"risk_findings": findings}

    @staticmethod
    def _action_agent(state: GraphState) -> dict[str, Any]:
        run_id = state["run_id"]
        action_id = str(uuid4())
        idempotency_key = hashlib.sha256(
            f"{run_id}:{state['request'].case_id}:create_adjuster_review".encode()
        ).hexdigest()
        action = ActionProposal(
            action_id=action_id,
            kind="create_adjuster_review",
            state=ActionState.PENDING,
            payload={
                "case_id": state["request"].case_id,
                "summary": state["summary"],
                "citation_ids": state["draft_citations"],
            },
            idempotency_key=idempotency_key,
        )
        return {"action": action, "status": RunStatus.PENDING_APPROVAL}

    def _persist(self, state: GraphState) -> dict[str, Any]:
        evidence_by_id = {item.chunk_id: item for item in state.get("evidence", [])}
        citations = [
            Citation(
                chunk_id=chunk_id,
                document_id=evidence_by_id[chunk_id].document_id,
                title=evidence_by_id[chunk_id].title,
            )
            for chunk_id in state.get("draft_citations", [])
            if chunk_id in evidence_by_id
        ]
        response = RunResponse(
            run_id=state["run_id"],
            case_id=state["request"].case_id,
            requested_by=state["principal"].subject,
            status=state.get("status", RunStatus.FAILED),
            reason_code=state.get("reason_code"),
            summary=state.get("summary", "Request stopped before synthesis."),
            plan=state.get("plan", []),
            tool_trace=state.get("tool_results", []),
            evidence=state.get("evidence", []),
            citations=citations,
            risk_findings=state.get("risk_findings", []),
            action=state.get("action"),
            model_backend=state.get("model_backend", "not_invoked"),
            model_name=state.get("model_name", "not_invoked"),
            model_latency_ms=state.get("model_latency_ms", 0.0),
            model_fallback=state.get("model_fallback", False),
            model_input_tokens=state.get("model_input_tokens", 0),
            model_output_tokens=state.get("model_output_tokens", 0),
            model_request_id=state.get("model_request_id"),
        )
        self.store.save(response, state["principal"])
        self.memory.remember(
            state["principal"],
            state["request"].case_id,
            f"Last outcome: {response.status.value}",
        )
        RUNS.labels(response.status.value, response.reason_code or "none").inc()
        return {"response": response}

    def run(self, request: RunRequest, principal: Principal) -> RunResponse:
        result = self.graph.invoke(
            {"run_id": str(uuid4()), "request": request, "principal": principal}
        )
        return cast(RunResponse, result["response"])

    def get(self, run_id: str, principal: Principal) -> RunResponse:
        return self.store.get(run_id, principal)

    def decide(
        self, run_id: str, principal: Principal, decision: Decision, note: str | None
    ) -> DecisionResponse:
        updated = self.store.decide(run_id, principal, decision, note)
        assert updated.action is not None
        ACTIONS.labels("approved" if decision is Decision.APPROVE else "rejected").inc()
        return DecisionResponse(
            run_id=run_id,
            action_id=updated.action.action_id,
            state=updated.action.state,
            decided_by=principal.subject,
        )

    def dispatch(self, run_id: str, principal: Principal) -> DispatchResponse:
        response = self.store.get(run_id, principal)
        if response.action is None:
            raise WorkflowConflict("approved_action_required")
        if response.action.state is ActionState.DISPATCHED:
            reference = self.gateway.dispatch_adjuster_task(
                action_id=response.action.action_id,
                case_id=response.case_id,
                idempotency_key=response.action.idempotency_key,
                principal=principal,
            )
            return DispatchResponse(
                action_id=response.action.action_id,
                state=ActionState.DISPATCHED,
                downstream_reference=reference,
            )
        if response.action.state is not ActionState.APPROVED:
            raise WorkflowConflict("approved_action_required")
        reference = self.gateway.dispatch_adjuster_task(
            action_id=response.action.action_id,
            case_id=response.case_id,
            idempotency_key=response.action.idempotency_key,
            principal=principal,
        )
        updated = self.store.mark_dispatched(run_id, principal, reference)
        assert updated.action is not None
        ACTIONS.labels("dispatched").inc()
        return DispatchResponse(
            action_id=updated.action.action_id,
            state=updated.action.state,
            downstream_reference=reference,
        )

    def mermaid(self) -> str:
        return cast(str, self.graph.get_graph().draw_mermaid())

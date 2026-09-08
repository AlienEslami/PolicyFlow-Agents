import os
import re
import secrets
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from . import __version__
from .contracts import (
    Classification,
    DecisionRequest,
    DecisionResponse,
    DispatchResponse,
    Principal,
    Role,
    RunRequest,
    RunResponse,
)
from .embeddings import HashEmbeddingProvider
from .graph import PolicyFlowService
from .model import (
    BedrockSynthesisModel,
    DeterministicSynthesisModel,
    SynthesisModel,
    TransformersSynthesisModel,
)
from .observability import configure_json_logging, emit_cloudwatch_request_metric
from .retrieval import InMemoryHybridRetriever
from .store import WorkflowConflict
from .tools import SyntheticEnterpriseGateway, ToolPolicyError


def build_local_service() -> PolicyFlowService:
    root = Path(__file__).resolve().parents[2]
    embedder = HashEmbeddingProvider()
    retriever = InMemoryHybridRetriever.from_json(
        root / "data" / "synthetic" / "knowledge.json", embedder
    )
    gateway = SyntheticEnterpriseGateway.from_json(
        root / "data" / "synthetic" / "enterprise_records.json"
    )
    backend = os.getenv("POLICYFLOW_MODEL_BACKEND", "deterministic").casefold()
    model: SynthesisModel
    if backend == "bedrock":
        model = BedrockSynthesisModel(
            os.getenv("POLICYFLOW_BEDROCK_MODEL_ID", "us.amazon.nova-2-lite-v1:0"),
            region_name=os.getenv("AWS_REGION"),
        )
    elif backend == "transformers":
        model = TransformersSynthesisModel(
            os.getenv("POLICYFLOW_TRANSFORMERS_MODEL", "google/flan-t5-small")
        )
    else:
        model = DeterministicSynthesisModel()
    return PolicyFlowService(retriever, gateway, model)


def create_app(
    service: PolicyFlowService | None = None, *, auth_token: str | None = None
) -> FastAPI:
    workflow = service or build_local_service()
    configured_token = (
        auth_token if auth_token is not None else os.getenv("POLICYFLOW_AUTH_TOKEN")
    )
    logger = configure_json_logging()
    application = FastAPI(
        title="PolicyFlow Agents",
        version=__version__,
        description=(
            "Synthetic-only, governed insurance service-case orchestration. "
            "No claim adjudication or live enterprise connection."
        ),
    )
    application.state.workflow = workflow

    @application.middleware("http")
    async def observe_request(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        supplied = request.headers.get("X-Correlation-ID", "")
        correlation_id = (
            supplied if re.fullmatch(r"[A-Za-z0-9._-]{1,128}", supplied) else str(uuid4())
        )
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - started) * 1000
        route = getattr(request.scope.get("route"), "path", "<unmatched>")
        response.headers["X-Correlation-ID"] = correlation_id
        logger.info(
            "request_completed",
            extra={
                "correlation_id": correlation_id,
                "route": route,
                "method": request.method,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 3),
            },
        )
        emit_cloudwatch_request_metric(route, response.status_code, duration_ms)
        return response

    def principal_dependency(
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
        edge_authorization: Annotated[
            str | None, Header(alias="X-PolicyFlow-Authorization")
        ] = None,
        subject: Annotated[str, Header(alias="X-Subject")] = "demo-operator",
        role: Annotated[Role, Header(alias="X-Role")] = Role.OPERATOR,
        tenant: Annotated[str, Header(alias="X-Tenant-ID")] = "NORTHSTAR_CA",
        classification: Annotated[
            Classification, Header(alias="X-Classification")
        ] = Classification.INTERNAL,
    ) -> Principal:
        if configured_token:
            expected = f"Bearer {configured_token}"
            supplied_token = authorization or edge_authorization
            if not supplied_token or not secrets.compare_digest(supplied_token, expected):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="valid bearer token required",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        return Principal(
            subject=subject,
            role=role,
            tenant_id=tenant,
            classification=classification,
        )

    CurrentPrincipal = Annotated[Principal, Depends(principal_dependency)]

    @application.exception_handler(WorkflowConflict)
    async def workflow_error(_request: object, exc: WorkflowConflict) -> JSONResponse:
        status_code = 404 if exc.code == "run_not_found" else 409
        if exc.code in {
            "tenant_scope_denied",
            "approver_role_required",
            "auditor_role_required",
        }:
            status_code = 403
        return JSONResponse(status_code=status_code, content={"code": exc.code})

    @application.exception_handler(ToolPolicyError)
    async def tool_error(_request: object, exc: ToolPolicyError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"code": exc.code})

    @application.get("/health/live", tags=["health"])
    def live() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @application.get("/health/ready", tags=["health"])
    def ready() -> dict[str, str]:
        return {"status": "ok", "profile": "local-synthetic"}

    @application.get("/api/v1/meta", tags=["system"])
    def meta(principal: CurrentPrincipal) -> dict[str, object]:
        del principal
        return {
            "product_level": "portfolio_demonstrator",
            "synthetic_only": True,
            "agent_framework": "langgraph",
            "agents": ["supervisor", "knowledge", "tool", "synthesis", "risk", "action"],
            "live_enterprise_connections": False,
            "autonomous_claim_adjudication": False,
            "human_approval_required": True,
            "model_backend": workflow.model.backend,
            "model_name": workflow.model.model_name,
        }

    @application.get("/", tags=["system"])
    def root() -> dict[str, object]:
        return {
            "service": "policyflow-agents",
            "status": "deployed",
            "documentation": "/docs",
            "health": "/health/live",
            "synthetic_only": True,
        }

    @application.post(
        "/api/v1/runs",
        response_model=RunResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["workflows"],
    )
    def create_run(body: RunRequest, principal: CurrentPrincipal) -> RunResponse:
        return workflow.run(body, principal)

    @application.get("/api/v1/runs/{run_id}", response_model=RunResponse, tags=["workflows"])
    def get_run(run_id: str, principal: CurrentPrincipal) -> RunResponse:
        return workflow.get(run_id, principal)

    @application.post(
        "/api/v1/runs/{run_id}/decision",
        response_model=DecisionResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["approvals"],
    )
    def decide(
        run_id: str, body: DecisionRequest, principal: CurrentPrincipal
    ) -> DecisionResponse:
        return workflow.decide(run_id, principal, body.decision, body.note)

    @application.post(
        "/api/v1/runs/{run_id}/dispatch",
        response_model=DispatchResponse,
        tags=["actions"],
    )
    def dispatch(run_id: str, principal: CurrentPrincipal) -> DispatchResponse:
        return workflow.dispatch(run_id, principal)

    @application.get("/api/v1/runs/{run_id}/timeline", tags=["audit"])
    def timeline(run_id: str, principal: CurrentPrincipal) -> dict[str, object]:
        events = workflow.store.timeline(run_id, principal)
        return {
            "run_id": run_id,
            "chain_valid": workflow.store.verify_chain(run_id, principal),
            "events": [
                {
                    "sequence": event.sequence,
                    "event_type": event.event_type,
                    "actor": event.actor,
                    "payload": event.payload,
                    "previous_hash": event.previous_hash,
                    "event_hash": event.event_hash,
                    "created_at": event.created_at.isoformat(),
                }
                for event in events
            ],
        }

    @application.get("/api/v1/graph", response_class=PlainTextResponse, tags=["system"])
    def graph(principal: CurrentPrincipal) -> str:
        if principal.role not in {Role.AUDITOR, Role.ADMIN}:
            raise WorkflowConflict("auditor_role_required")
        return workflow.mermaid()

    @application.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return application


app = create_app()

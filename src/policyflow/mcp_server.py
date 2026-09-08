from __future__ import annotations

import os
import re
import secrets
from collections.abc import Mapping
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.context import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .contracts import Classification, Principal, Role, ToolCall
from .tools import SyntheticEnterpriseGateway, ToolPolicyError

MCP_TOOL_NAMES = frozenset({"get_claim", "check_required_documents"})
_CASE_ID = re.compile(r"^[A-Z0-9][A-Z0-9_-]{2,63}$")
_MCP_ROLES = frozenset({Role.OPERATOR, Role.AUDITOR, Role.ADMIN})


class ScopedMCPTools:
    """Small policy boundary around the existing read-only enterprise gateway."""

    def __init__(self, gateway: SyntheticEnterpriseGateway) -> None:
        self.gateway = gateway

    def invoke(self, name: str, case_id: str, principal: Principal) -> dict[str, Any]:
        if name not in MCP_TOOL_NAMES:
            raise ToolPolicyError("mcp_tool_not_exposed")
        if principal.role not in _MCP_ROLES:
            raise ToolPolicyError("mcp_read_role_required")
        if not _CASE_ID.fullmatch(case_id):
            raise ToolPolicyError("invalid_case_identifier")
        result = self.gateway.invoke_read(
            ToolCall(name=name, arguments={"case_id": case_id}), principal
        )
        if not result.ok:
            raise ToolPolicyError(result.error_code or "tool_failed")
        return result.data


def principal_from_mcp_headers(headers: Mapping[str, str] | None) -> Principal:
    normalized = {key.casefold(): value for key, value in (headers or {}).items()}
    try:
        return Principal(
            subject=normalized.get("x-subject", "mcp-client"),
            role=Role(normalized.get("x-role", Role.OPERATOR.value)),
            tenant_id=normalized.get("x-tenant-id", "NORTHSTAR_CA"),
            classification=Classification[
                normalized.get("x-classification", "INTERNAL").upper()
            ],
        )
    except (KeyError, ValueError) as exc:
        raise ToolError("invalid_principal_context") from exc


def build_mcp_server(gateway: SyntheticEnterpriseGateway) -> MCPServer[None]:
    scoped = ScopedMCPTools(gateway)
    server: MCPServer[None] = MCPServer(
        "policyflow-read-tools",
        title="PolicyFlow governed read tools",
        description="Two synthetic-only, tenant-scoped, read-only insurance service tools.",
        instructions=(
            "Use only for synthetic case review. Tool results are minimum-necessary and "
            "must never be interpreted as approval, denial, coverage, or eligibility decisions."
        ),
        version="1.0.0",
    )

    @server.tool(name="get_claim", structured_output=True)
    async def get_claim(case_id: str, ctx: Context[Any, Any]) -> dict[str, Any]:
        """Return minimum-necessary synthetic claim fields for the caller's tenant."""

        try:
            return scoped.invoke("get_claim", case_id, principal_from_mcp_headers(ctx.headers))
        except ToolPolicyError as exc:
            raise ToolError(exc.code) from exc

    @server.tool(name="check_required_documents", structured_output=True)
    async def check_required_documents(case_id: str, ctx: Context[Any, Any]) -> dict[str, Any]:
        """Compare received and required synthetic documents within the caller's tenant."""

        try:
            return scoped.invoke(
                "check_required_documents", case_id, principal_from_mcp_headers(ctx.headers)
            )
        except ToolPolicyError as exc:
            raise ToolError(exc.code) from exc

    return server


class MCPBearerAuth:
    """Protect the mounted MCP transport with the service's shared secret boundary."""

    def __init__(self, app: ASGIApp, token: str | None) -> None:
        self.app = app
        self.token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {
            key.decode("latin-1").casefold(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        supplied = headers.get("authorization") or headers.get("x-policyflow-authorization")
        if not self.token:
            response = JSONResponse({"code": "mcp_auth_not_configured"}, status_code=503)
        elif not supplied or not secrets.compare_digest(supplied, f"Bearer {self.token}"):
            response = JSONResponse(
                {"code": "mcp_authentication_required"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
        else:
            await self.app(scope, receive, send)
            return
        await response(scope, receive, send)


def build_mcp_http_app(server: MCPServer[None], auth_token: str | None) -> ASGIApp:
    configured_hosts = [
        item.strip()
        for item in os.getenv("POLICYFLOW_MCP_ALLOWED_HOSTS", "").split(",")
        if item.strip()
    ]
    transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["127.0.0.1:*", "localhost:*", *configured_hosts],
        allowed_origins=[
            "http://127.0.0.1:*",
            "http://localhost:*",
            *[f"https://{host}" for host in configured_hosts],
        ],
    )
    app = server.streamable_http_app(
        streamable_http_path="/",
        json_response=True,
        stateless_http=True,
        max_request_body_size=64 * 1024,
        transport_security=transport_security,
    )
    return MCPBearerAuth(app, auth_token)

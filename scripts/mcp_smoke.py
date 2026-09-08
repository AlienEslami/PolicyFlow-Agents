from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Any

import httpx2
from mcp.client import Client
from mcp.client.streamable_http import streamable_http_client

EXPECTED_TOOLS = {"get_claim", "check_required_documents"}


def content_to_json(content: list[Any]) -> list[dict[str, Any]]:
    rendered: list[dict[str, Any]] = []
    for item in content:
        if hasattr(item, "model_dump"):
            rendered.append(item.model_dump(mode="json"))
        else:
            rendered.append({"type": "unknown"})
    return rendered


async def smoke(url: str, token: str, tenant_id: str, case_id: str) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Subject": "mcp-smoke-client",
        "X-Role": "auditor",
        "X-Tenant-ID": tenant_id,
    }
    async with httpx2.AsyncClient(headers=headers, timeout=20.0) as http_client:
        transport = streamable_http_client(url, http_client=http_client)
        async with Client(transport) as client:
            discovered = await client.list_tools()
            names = {tool.name for tool in discovered.tools}
            if names != EXPECTED_TOOLS:
                raise RuntimeError(f"unexpected MCP tool surface: {sorted(names)}")
            result = await client.call_tool("get_claim", {"case_id": case_id})
            if result.is_error:
                raise RuntimeError("get_claim returned an MCP tool error")
            return {
                "transport": "streamable-http",
                "tools": sorted(names),
                "called": "get_claim",
                "tenant_id": tenant_id,
                "case_id": case_id,
                "structured_content": result.structured_content,
                "content": content_to_json(result.content),
            }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Smoke-test the scoped PolicyFlow MCP endpoint."
    )
    parser.add_argument("--url", default="http://127.0.0.1:8010/mcp/")
    parser.add_argument("--tenant-id", default="NORTHSTAR_CA")
    parser.add_argument("--case-id", default="CLM-1001")
    args = parser.parse_args()
    token = os.getenv("POLICYFLOW_MCP_TOKEN")
    if not token:
        parser.error("set POLICYFLOW_MCP_TOKEN; tokens are never accepted as command arguments")
    print(
        json.dumps(asyncio.run(smoke(args.url, token, args.tenant_id, args.case_id)), indent=2)
    )


if __name__ == "__main__":
    main()

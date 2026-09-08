from __future__ import annotations

from .contracts import DraftResponse, Evidence, RiskFinding, ToolResult


def review_run(
    draft: DraftResponse,
    evidence: list[Evidence],
    tool_results: list[ToolResult],
) -> list[RiskFinding]:
    findings: list[RiskFinding] = []
    allowed_citations = {item.chunk_id for item in evidence}
    if not set(draft.citations) <= allowed_citations:
        findings.append(
            RiskFinding(
                code="citation_outside_snapshot",
                severity="critical",
                detail="The response cited evidence outside the frozen retrieval snapshot.",
                blocking=True,
            )
        )
    failed_tools = [result for result in tool_results if not result.ok]
    if failed_tools:
        findings.append(
            RiskFinding(
                code="enterprise_data_unavailable",
                severity="high",
                detail="One or more required enterprise reads failed.",
                blocking=True,
            )
        )
    if draft.missing_items:
        findings.append(
            RiskFinding(
                code="required_documents_missing",
                severity="medium",
                detail="The case is incomplete and must not be routed as ready.",
                blocking=True,
            )
        )
    for result in tool_results:
        if result.name == "get_claim" and result.ok:
            amount = float(result.data.get("amount_cad", 0))
            if amount >= 10_000:
                findings.append(
                    RiskFinding(
                        code="enhanced_human_review",
                        severity="medium",
                        detail="The synthetic amount meets the enhanced-review threshold.",
                    )
                )
        if result.name == "get_policy" and result.ok and result.data.get("status") != "active":
            findings.append(
                RiskFinding(
                    code="policy_status_requires_review",
                    severity="high",
                    detail="Policy status is not active; a human must resolve the discrepancy.",
                    blocking=True,
                )
            )
    return findings

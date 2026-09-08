from __future__ import annotations

import re
from dataclasses import dataclass

_INJECTION_PATTERNS = (
    "ignore previous",
    "ignore all prior",
    "reveal system prompt",
    "show hidden prompt",
    "bypass policy",
    "developer message",
)
_AUTONOMOUS_DECISION_PATTERNS = (
    r"\b(auto(?:matically)?\s+)?approve\b",
    r"\bdeny\s+(?:the\s+)?claim\b",
    r"\bdecline\s+(?:the\s+)?claim\b",
    r"\bmake\s+(?:a\s+)?final\s+(?:coverage|eligibility)\s+decision\b",
)
_PROTECTED_ATTRIBUTE_PATTERNS = (
    r"\b(race|ethnicity|religion|gender|sexual orientation)\b.*\b(score|risk|decision)\b",
    r"\b(score|risk|decision)\b.*\b(race|ethnicity|religion|gender|sexual orientation)\b",
)
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_SIN = re.compile(r"(?<!\d)\d{3}[ -]?\d{3}[ -]?\d{3}(?!\d)")


@dataclass(frozen=True)
class GuardResult:
    allowed: bool
    reason_code: str | None = None


def inspect_objective(text: str) -> GuardResult:
    lowered = text.casefold()
    if any(pattern in lowered for pattern in _INJECTION_PATTERNS):
        return GuardResult(False, "prompt_injection_detected")
    if any(re.search(pattern, lowered) for pattern in _PROTECTED_ATTRIBUTE_PATTERNS):
        return GuardResult(False, "protected_attribute_decisioning")
    if any(re.search(pattern, lowered) for pattern in _AUTONOMOUS_DECISION_PATTERNS):
        return GuardResult(False, "autonomous_adjudication_prohibited")
    return GuardResult(True)


def redact_sensitive_text(text: str) -> str:
    """Remove common direct identifiers before text enters memory or logs."""

    return _SIN.sub("[REDACTED-SIN]", _EMAIL.sub("[REDACTED-EMAIL]", text))

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .contracts import Principal
from .security import redact_sensitive_text


@dataclass(frozen=True)
class MemoryEntry:
    tenant_id: str
    subject: str
    case_id: str
    text: str
    expires_at: datetime


class ScopedMemoryStore:
    """TTL-bound case memory scoped to tenant, user, and case."""

    def __init__(self, *, ttl: timedelta = timedelta(hours=8), max_entries: int = 8) -> None:
        self.ttl = ttl
        self.max_entries = max_entries
        self._entries: list[MemoryEntry] = []

    def remember(
        self,
        principal: Principal,
        case_id: str,
        text: str,
        *,
        now: datetime | None = None,
    ) -> None:
        timestamp = now or datetime.now(UTC)
        self._entries.append(
            MemoryEntry(
                tenant_id=principal.tenant_id,
                subject=principal.subject,
                case_id=case_id,
                text=redact_sensitive_text(text)[:1000],
                expires_at=timestamp + self.ttl,
            )
        )
        self._entries = self._entries[-self.max_entries * 20 :]

    def recall(
        self, principal: Principal, case_id: str, *, now: datetime | None = None
    ) -> list[str]:
        timestamp = now or datetime.now(UTC)
        self._entries = [entry for entry in self._entries if entry.expires_at > timestamp]
        matches = [
            entry.text
            for entry in self._entries
            if entry.tenant_id == principal.tenant_id
            and entry.subject == principal.subject
            and entry.case_id == case_id
        ]
        return matches[-self.max_entries :]

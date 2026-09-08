from __future__ import annotations

import json
import math
import re
from pathlib import Path

from pydantic import BaseModel, Field

from .contracts import Classification, Evidence, Principal
from .embeddings import EmbeddingProvider


class KnowledgeDocument(BaseModel):
    document_id: str
    title: str
    text: str
    tenant_id: str
    classification: Classification
    locale: str
    approved: bool = True
    injection_flag: bool = False
    tags: list[str] = Field(default_factory=list)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9À-ÿ]+", text.casefold()))


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True)) / (
        math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right)) or 1.0
    )


class InMemoryHybridRetriever:
    """ACL-before-ranking hybrid retriever used by the local vertical slice."""

    def __init__(self, documents: list[KnowledgeDocument], embedder: EmbeddingProvider) -> None:
        self.documents = documents
        self.embedder = embedder
        vectors = embedder.embed_documents([document.text for document in documents])
        self._vectors = dict(zip((doc.document_id for doc in documents), vectors, strict=True))

    @classmethod
    def from_json(cls, path: Path, embedder: EmbeddingProvider) -> InMemoryHybridRetriever:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls([KnowledgeDocument.model_validate(item) for item in raw], embedder)

    def retrieve(
        self, query: str, principal: Principal, *, locale: str, limit: int
    ) -> list[Evidence]:
        eligible = [
            document
            for document in self.documents
            if document.tenant_id in {principal.tenant_id, "SHARED"}
            and document.classification <= principal.classification
            and document.approved
            and not document.injection_flag
            and document.locale in {locale, "bilingual"}
        ]
        query_vector = self.embedder.embed_query(query)
        query_tokens = _tokens(query)
        scored: list[tuple[float, KnowledgeDocument]] = []
        for document in eligible:
            semantic = max(0.0, _cosine(query_vector, self._vectors[document.document_id]))
            lexical = len(query_tokens & _tokens(document.text)) / max(1, len(query_tokens))
            tag_match = len(query_tokens & set(document.tags)) / max(1, len(document.tags))
            scored.append((0.55 * semantic + 0.35 * lexical + 0.10 * tag_match, document))
        scored.sort(key=lambda item: (-item[0], item[1].document_id))
        return [
            Evidence(
                chunk_id=f"{document.document_id}#c001",
                document_id=document.document_id,
                title=document.title,
                text=document.text,
                score=score,
                classification=document.classification,
            )
            for score, document in scored[:limit]
        ]

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import text
from sqlalchemy.orm import Session

from .contracts import Classification, Evidence, Principal
from .embeddings import EmbeddingProvider


class PostgresHybridRetriever:
    """Production adapter: tenant-filtered pgvector + full-text reciprocal-rank fusion."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        embedder: EmbeddingProvider,
    ) -> None:
        self.session_factory = session_factory
        self.embedder = embedder

    def retrieve(
        self, query: str, principal: Principal, *, locale: str, limit: int
    ) -> list[Evidence]:
        embedding = (
            "[" + ",".join(f"{value:.8f}" for value in self.embedder.embed_query(query)) + "]"
        )
        statement = text(
            """
            WITH eligible AS MATERIALIZED (
              SELECT c.id, c.document_id, d.title, c.content, d.classification,
                     c.embedding, c.search_vector
              FROM knowledge_chunks c
              JOIN knowledge_documents d ON d.id = c.document_row_id
              WHERE d.tenant_id IN (:tenant_id, 'SHARED')
                AND d.classification <= :classification
                AND d.lifecycle = 'approved'
                AND d.injection_flag = false
                AND d.locale IN (:locale, 'bilingual')
            ),
            vector_rank AS (
              SELECT id,
                     row_number() OVER (
                       ORDER BY embedding <=> CAST(:embedding AS vector)
                     ) rank
              FROM eligible
              ORDER BY embedding <=> CAST(:embedding AS vector)
              LIMIT :candidate_limit
            ),
            text_rank AS (
              SELECT id, row_number() OVER (
                ORDER BY ts_rank_cd(search_vector, websearch_to_tsquery('simple', :query)) DESC
              ) rank
              FROM eligible
              WHERE search_vector @@ websearch_to_tsquery('simple', :query)
              ORDER BY ts_rank_cd(search_vector, websearch_to_tsquery('simple', :query)) DESC
              LIMIT :candidate_limit
            )
            SELECT e.id, e.document_id, e.title, e.content, e.classification,
                   coalesce(1.0 / (60 + v.rank), 0) +
                   coalesce(1.0 / (60 + t.rank), 0) AS score
            FROM eligible e
            LEFT JOIN vector_rank v USING (id)
            LEFT JOIN text_rank t USING (id)
            WHERE v.id IS NOT NULL OR t.id IS NOT NULL
            ORDER BY score DESC, e.id
            LIMIT :limit
            """
        )
        params = {
            "tenant_id": principal.tenant_id,
            "classification": int(principal.classification),
            "locale": locale,
            "embedding": embedding,
            "query": query,
            "candidate_limit": max(20, limit * 5),
            "limit": limit,
        }
        with self.session_factory() as session:
            session.execute(
                text("SELECT set_config('app.tenant_id', :tenant, true)"),
                {"tenant": principal.tenant_id},
            )
            rows = session.execute(statement, params).mappings().all()
        return [
            Evidence(
                chunk_id=str(row["id"]),
                document_id=str(row["document_id"]),
                title=str(row["title"]),
                text=str(row["content"]),
                score=float(row["score"]),
                classification=Classification(int(row["classification"])),
            )
            for row in rows
        ]

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable, Sequence
from typing import Any, Protocol


class EmbeddingProvider(Protocol):
    backend: str
    model_name: str
    dimension: int

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class HashEmbeddingProvider:
    """Deterministic CI test double; not evidence of semantic model quality."""

    backend = "hash"
    model_name = "sha256-token-hash-test-double"
    dimension = 384

    def _embed(self, text: str) -> list[float]:
        values = [0.0] * self.dimension
        for token in re.findall(r"[a-z0-9À-ÿ]+", text.casefold()):
            digest = hashlib.sha256(token.encode()).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            values[index] += 1.0 if digest[4] & 1 else -1.0
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class FastEmbedProvider:
    backend = "fastembed"
    dimension = 384

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        from fastembed import TextEmbedding

        self.model_name = model_name
        self._model = TextEmbedding(model_name=model_name)

    @staticmethod
    def _lists(vectors: Iterable[Any]) -> list[list[float]]:
        return [[float(value) for value in vector] for vector in vectors]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._lists(self._model.embed(list(texts)))

    def embed_query(self, text: str) -> list[float]:
        return self._lists(self._model.query_embed(text))[0]

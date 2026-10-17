"""A small on-disk vector index using cosine similarity."""
import json
import math
from dataclasses import dataclass
from pathlib import Path

from app.rag.ingest import Chunk


@dataclass
class Hit:
    chunk: Chunk
    score: float


def _normalise(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0:
        raise ValueError("Cannot normalise a zero vector")
    return [x / norm for x in vector]


class VectorStore:
    def __init__(self, embed_model: str):
        self.embed_model = embed_model
        self._chunks: list[Chunk] = []
        self._vectors: list[list[float]] = []

    def __len__(self) -> int:
        return len(self._chunks)

    def add(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        self._chunks.extend(chunks)
        self._vectors.extend(_normalise(v) for v in vectors)

    def search(self, query_vector: list[float], top_k: int, source_type: str | None = None) -> list[Hit]:
        query = _normalise(query_vector)
        scored = []
        for chunk, vector in zip(self._chunks, self._vectors):
            if source_type and chunk.metadata.get("source_type") != source_type:
                continue
            scored.append(Hit(chunk, sum(a * b for a, b in zip(query, vector))))
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:top_k]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "embed_model": self.embed_model,
            "chunks": [
                {"id": c.id, "text": c.text, "metadata": c.metadata, "embedding": [round(x, 6) for x in v]}
                for c, v in zip(self._chunks, self._vectors)
            ],
        }
        path.write_text(json.dumps(payload), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "VectorStore":
        payload = json.loads(path.read_text(encoding="utf-8"))
        store = cls(payload["embed_model"])
        for item in payload["chunks"]:
            store._chunks.append(Chunk(item["id"], item["text"], item["metadata"]))
            store._vectors.append(item["embedding"])
        return store

# On-disk vector store for RAG system using cosine similarity.

"""A small on-disk vector index using cosine similarity."""
import json
import math
from dataclasses import dataclass
from pathlib import Path

from app.rag.ingest import Chunk

# Data structure representing a retrieval hit with its score.
@dataclass
class Hit:
    chunk: Chunk
    score: float

# Normalise a vector to unit length for cosine similarity.
def _normalise(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0:
        raise ValueError("Cannot normalise a zero vector")
    return [x / norm for x in vector]

# Vector store class for managing chunks and their embeddings.
class VectorStore:
    def __init__(self, embed_model: str):
        self.embed_model = embed_model
        self._chunks: list[Chunk] = []
        self._vectors: list[list[float]] = []

    # Return the number of chunks in the store.
    def __len__(self) -> int:
        return len(self._chunks)

    # Add chunks and their corresponding vectors to the store.
    def add(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        self._chunks.extend(chunks)
        self._vectors.extend(_normalise(v) for v in vectors)

    # Search for the top_k most relevant chunks based on the query vector.
    def search(self, query_vector: list[float], top_k: int, source_type: str | None = None) -> list[Hit]:
        query = _normalise(query_vector)
        scored = []
        for chunk, vector in zip(self._chunks, self._vectors):
            if source_type and chunk.metadata.get("source_type") != source_type:
                continue
            scored.append(Hit(chunk, sum(a * b for a, b in zip(query, vector))))
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:top_k]

    # Save the vector store to disk at the specified path.
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

    # Load the vector store from disk at the specified path.
    @classmethod
    def load(cls, path: Path) -> "VectorStore":
        payload = json.loads(path.read_text(encoding="utf-8"))
        store = cls(payload["embed_model"])
        for item in payload["chunks"]:
            store._chunks.append(Chunk(item["id"], item["text"], item["metadata"]))
            store._vectors.append(item["embedding"])
        return store

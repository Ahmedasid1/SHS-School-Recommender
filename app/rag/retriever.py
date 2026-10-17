"""Retrieval: embed the query, search the index, and drop weak matches."""
import logging
from pathlib import Path

from app import config
from app.llm.client import OllamaClient
from app.rag.store import Hit, VectorStore

logger = logging.getLogger(__name__)

# nomic-embed-text expects task prefixes; they must match between indexing and querying.
DOCUMENT_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "


class RetrievalError(Exception):
    """The index is missing, stale, or the embedding call failed."""


class Retriever:
    def __init__(
        self,
        client: OllamaClient,
        index_path: Path = config.INDEX_PATH,
        top_k: int = config.RAG_TOP_K,
        min_score: float = config.RAG_MIN_SCORE,
    ):
        self.client = client
        self.index_path = index_path
        self.top_k = top_k
        self.min_score = min_score
        self._store: VectorStore | None = None

    def _load(self) -> VectorStore:
        if self._store is None:
            if not self.index_path.exists():
                raise RetrievalError(
                    f"Knowledge index not found at {self.index_path}. Run: python -m app.rag.build_index"
                )
            store = VectorStore.load(self.index_path)
            if store.embed_model != self.client.embed_model:
                raise RetrievalError(
                    f"Index was built with '{store.embed_model}' but '{self.client.embed_model}' is configured. "
                    "Rebuild it with: python -m app.rag.build_index"
                )
            self._store = store
        return self._store

    def retrieve(self, query: str, source_type: str | None = None) -> list[Hit]:
        """Hits at or above the minimum score. An empty list means no supporting evidence was found."""
        if not query.strip():
            return []
        store = self._load()
        vector = self.client.embed([QUERY_PREFIX + query])[0]
        hits = store.search(vector, self.top_k, source_type)
        relevant = [h for h in hits if h.score >= self.min_score]
        logger.info("retrieval query=%r top_score=%.3f kept=%d", query, hits[0].score if hits else 0.0, len(relevant))
        return relevant

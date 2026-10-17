"""Build the vector index: python -m app.rag.build_index [--if-missing]."""
import argparse
import logging

from app import config
from app.llm.client import LLMError, OllamaClient
from app.rag.ingest import document_chunks, school_chunks
from app.rag.retriever import DOCUMENT_PREFIX
from app.rag.store import VectorStore
from app.tools.matcher import DEFAULT_DATA, load_schools

BATCH_SIZE = 32


def build_index(client: OllamaClient) -> VectorStore:
    chunks = document_chunks() + school_chunks(load_schools(DEFAULT_DATA))
    store = VectorStore(client.embed_model)
    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start:start + BATCH_SIZE]
        store.add(batch, client.embed([DOCUMENT_PREFIX + c.text for c in batch]))
    return store


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the RAG vector index.")
    parser.add_argument("--if-missing", action="store_true", help="skip if the index file already exists")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.if_missing and config.INDEX_PATH.exists():
        print(f"Index already exists at {config.INDEX_PATH}; skipping.")
        return 0
    try:
        store = build_index(OllamaClient())
    except LLMError as exc:
        print(f"Could not build the index: {exc}")
        return 1
    store.save(config.INDEX_PATH)
    print(f"Indexed {len(store)} chunks with '{store.embed_model}' -> {config.INDEX_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

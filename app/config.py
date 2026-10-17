"""Central configuration, read from environment variables (see .env.example)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v2")

KNOWLEDGE_DIR = Path(os.getenv("KNOWLEDGE_DIR", ROOT / "data" / "knowledge"))
INDEX_PATH = Path(os.getenv("INDEX_PATH", ROOT / "data" / "index" / "index.json"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "4"))
RAG_MIN_SCORE = float(os.getenv("RAG_MIN_SCORE", "0.65"))

MAX_AGENT_STEPS = int(os.getenv("MAX_AGENT_STEPS", "5"))

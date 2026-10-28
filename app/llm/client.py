# Ollama client for interacting with the LLM server via HTTP

"""Thin Ollama HTTP client for chat (with tools) and embeddings."""
import logging

import httpx

from app import config

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """The model server is unreachable, timed out, or returned an unusable response."""


class OllamaClient:
    def __init__(
        self,
        host: str = config.OLLAMA_HOST,
        model: str = config.LLM_MODEL,
        embed_model: str = config.EMBED_MODEL,
        timeout: float = config.LLM_TIMEOUT,
    ):
        self.model = model
        self.embed_model = embed_model
        self._http = httpx.Client(base_url=host, timeout=timeout)

    def _post(self, path: str, payload: dict) -> dict:
        try:
            response = self._http.post(path, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException as exc:
            raise LLMError("The model timed out.") from exc
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:200]
            raise LLMError(f"Model server returned {exc.response.status_code}: {detail}") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"Cannot reach the model server: {exc}") from exc
        except ValueError as exc:
            raise LLMError("Model server returned invalid JSON.") from exc

    def chat(self, messages: list[dict], tools: list[dict] | None = None, temperature: float = 0.0) -> dict:
        """Send the full message list and return the assistant message dict."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if tools:
            payload["tools"] = tools
        data = self._post("/api/chat", payload)
        message = data.get("message")
        if not isinstance(message, dict):
            raise LLMError("Model response had no message.")
        return message

    def embed(self, texts: list[str]) -> list[list[float]]:
        data = self._post("/api/embed", {"model": self.embed_model, "input": texts})
        embeddings = data.get("embeddings")
        if not embeddings or len(embeddings) != len(texts):
            raise LLMError("Embedding response did not match the request.")
        return embeddings

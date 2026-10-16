"""
Provider Ollama Cloud.

Utilise la route compatible OpenAI exposée par Ollama (/v1/chat/completions),
comme décidé en section 23.1.3 du cahier des charges : ce format est repris
par la plupart des fournisseurs cloud, ce qui limite le travail de migration
au moment du changement de modèle en production.
"""

import json
import logging
import uuid

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.llm.base import LLMProvider, LLMResponse, Message, ToolCall, ToolDefinition

logger = logging.getLogger("maliagent.llm.ollama")


def _is_retryable_error(exc: BaseException) -> bool:
    """
    Ne retente que les erreurs transitoires (timeout, réseau, 5xx serveur).
    Une erreur 4xx (401 clé invalide, 400 payload malformé...) ne doit
    JAMAIS être retentée : elle échouera systématiquement de la même façon.
    """
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


class OllamaCloudProvider(LLMProvider):
    """Provider de chat et d'embeddings compatible Ollama Cloud / OpenAI-like."""

    def __init__(self, api_key: str, base_url: str, model: str, embedding_model: str = "nomic-embed-text"):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._embedding_model = embedding_model

    def _to_openai_messages(self, messages: list[Message]) -> list[dict]:
        result = []
        for m in messages:
            entry: dict = {"role": m.role, "content": m.content}
            if m.role == "tool":
                entry["tool_call_id"] = m.tool_call_id
                entry["name"] = m.name
            result.append(entry)
        return result

    def _to_openai_tools(self, tools: list[ToolDefinition] | None) -> list[dict] | None:
        if not tools:
            return None
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception(_is_retryable_error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def _call_completions(self, payload: dict) -> dict:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self._base_url}/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> LLMResponse:
        payload: dict = {
            "model": self._model,
            "messages": self._to_openai_messages(messages),
        }
        openai_tools = self._to_openai_tools(tools)
        if openai_tools:
            payload["tools"] = openai_tools

        data = await self._call_completions(payload)
        choice = data["choices"][0]["message"]
        tool_calls: list[ToolCall] = []
        for raw_call in choice.get("tool_calls") or []:
            fn = raw_call["function"]
            try:
                arguments = json.loads(fn["arguments"])
            except (json.JSONDecodeError, TypeError):
                arguments = {}
            tool_calls.append(
                ToolCall(
                    id=raw_call.get("id", str(uuid.uuid4())),
                    name=fn["name"],
                    arguments=arguments,
                )
            )
        return LLMResponse(content=choice.get("content"), tool_calls=tool_calls, raw=data)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        # URLs candidates : local Ollama en priorité s'il est disponible (instantané ~20ms), sinon URL distante
        candidate_urls = []
        if "localhost" not in self._base_url and "127.0.0.1" not in self._base_url:
            candidate_urls.append("http://localhost:11434/api/embed")
        candidate_urls.append(f"{self._base_url}/api/embed")

        last_error = None
        for embed_url in candidate_urls:
            headers = {}
            if self._api_key and "localhost" not in embed_url and "127.0.0.1" not in embed_url:
                headers["Authorization"] = f"Bearer {self._api_key}"

            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(
                        embed_url,
                        headers=headers,
                        json={"model": self._embedding_model, "input": texts},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    if "embeddings" in data:
                        return data["embeddings"]
            except Exception as exc:
                last_error = exc
                logger.warning("Échec embed sur %s: %s. Tentative sur le prochain endpoint...", embed_url, exc)
                continue

        if last_error:
            raise last_error
        return []

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
    def __init__(self, api_key: str, base_url: str, model: str):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model

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
        """
        Appel HTTP brut à Ollama Cloud, isolé pour bénéficier du retry
        automatique avec backoff exponentiel (jusqu'à 3 tentatives) sur les
        erreurs transitoires uniquement (timeout, réseau, 5xx).
        """
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

        try:
            data = await self._call_completions(payload)
        except httpx.HTTPStatusError as e:
            logger.error(
                "Erreur Ollama Cloud (HTTP %s) après tentatives de retry : %s",
                e.response.status_code,
                e,
            )
            raise
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            logger.error("Ollama Cloud injoignable après tentatives de retry : %s", e)
            raise

        choice = data["choices"][0]["message"]
        content = choice.get("content")

        tool_calls: list[ToolCall] = []
        for raw_call in choice.get("tool_calls") or []:
            fn = raw_call["function"]
            try:
                arguments = json.loads(fn["arguments"])
            except (json.JSONDecodeError, TypeError):
                # Le modèle a mal formaté les arguments — à surveiller
                # de près pendant le test de tool calling (script
                # scripts/test_tool_calling.py).
                arguments = {}
            tool_calls.append(
                ToolCall(
                    id=raw_call.get("id", str(uuid.uuid4())),
                    name=fn["name"],
                    arguments=arguments,
                )
            )

        return LLMResponse(content=content, tool_calls=tool_calls, raw=data)

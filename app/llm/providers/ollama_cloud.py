"""
Provider Ollama Cloud.

Utilise la route compatible OpenAI exposée par Ollama (/v1/chat/completions),
comme décidé en section 23.1.3 du cahier des charges : ce format est repris
par la plupart des fournisseurs cloud, ce qui limite le travail de migration
au moment du changement de modèle en production.
"""

import json
import uuid

import httpx

from app.llm.base import LLMProvider, LLMResponse, Message, ToolCall, ToolDefinition


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

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self._base_url}/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

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

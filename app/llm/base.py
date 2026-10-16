"""
Interface d'abstraction du LLM (voir section 23.1 du cahier des charges).

Règle du projet : la logique métier et les tools ne doivent JAMAIS appeler
un provider LLM directement (Ollama, OpenAI, etc.). Ils passent uniquement
par cette interface. Ça permet de changer de modèle/provider en production
sans réécrire l'agent, les tools ou les prompts.

Le format des tools est défini ici, indépendant du provider (voir section
23.1.3). Chaque provider est responsable de traduire ce format vers/depuis
son propre format natif.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolDefinition:
    """Définition d'un tool, indépendante du provider."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema des paramètres


@dataclass
class ToolCall:
    """Un appel de tool demandé par le LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """Réponse normalisée du LLM, quel que soit le provider."""

    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: Any = None  # réponse brute du provider, utile pour debug


@dataclass
class Message:
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    tool_call_id: str | None = None  # requis si role == "tool"
    name: str | None = None  # nom du tool, si role == "tool"


class LLMProvider(ABC):
    """
    Interface que tout provider LLM doit implémenter.

    Ajouter un nouveau provider (ex. au moment du passage en production)
    = créer une nouvelle classe qui implémente cette interface dans
    app/llm/providers/, sans toucher au reste de l'application.
    """

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> LLMResponse:
        """Envoie une conversation au LLM et retourne sa réponse normalisée."""
        raise NotImplementedError

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Retourne un vecteur d'embedding par texte fourni, dans le même ordre.
        Utilisé pour indexer et interroger la base de connaissances (RAG).
        """
        raise NotImplementedError
"""
Point d'entrée unique pour obtenir le provider LLM actif.

Au moment du changement de modèle en production, c'est le SEUL fichier
qu'il faudra modifier pour brancher un nouveau provider — le reste de
l'application ne dépend que de l'interface LLMProvider (app/llm/base.py).
"""

from app.core.config import settings
from app.llm.base import LLMProvider
from app.llm.providers.ollama_cloud import OllamaCloudProvider


def get_llm_provider() -> LLMProvider:
    return OllamaCloudProvider(
        api_key=settings.ollama_api_key,
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
    )

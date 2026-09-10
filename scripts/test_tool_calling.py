"""
Script de validation du tool calling avec Ollama Cloud.

Objectif (voir cahier des charges, section 23.1.1) : avant de construire
le reste de l'agent, confirmer que le modèle configuré appelle correctement
les bons tools, avec les bons arguments, sur une série de messages en
français représentatifs de vraies conversations WhatsApp.

Usage :
    python scripts/test_tool_calling.py

Lis le résumé à la fin : le taux de bons appels de tool doit être élevé
(viser >90%) avant de passer au Sprint 2. Si ce n'est pas le cas :
  - essayer un modèle Ollama Cloud plus gros,
  - ou affiner le prompt système / les descriptions de tools,
  - ou envisager un fallback vers un LLM cloud plus fiable en dernier
    recours (à voir seulement si Ollama Cloud ne suffit vraiment pas).
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.llm.base import Message, ToolDefinition  # noqa: E402
from app.llm.factory import get_llm_provider  # noqa: E402

# --- Tools factices, juste pour valider le comportement du modèle ---

FAKE_PRODUCTS = {
    "samsung a15": {"price": 95000, "stock": 4, "category": "téléphone"},
    "iphone 13": {"price": 350000, "stock": 0, "category": "téléphone"},
    "riz 25kg": {"price": 18000, "stock": 50, "category": "alimentation"},
}

TOOLS = [
    ToolDefinition(
        name="search_products",
        description="Recherche des produits dans le catalogue par nom ou mot-clé.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Nom ou mot-clé du produit recherché"},
            },
            "required": ["query"],
        },
    ),
    ToolDefinition(
        name="check_stock",
        description="Vérifie le stock disponible pour un produit précis.",
        parameters={
            "type": "object",
            "properties": {
                "product_name": {"type": "string"},
            },
            "required": ["product_name"],
        },
    ),
]

SYSTEM_PROMPT = (
    "Tu es l'assistant WhatsApp d'un commerçant malien. "
    "Utilise toujours les tools disponibles pour répondre aux questions sur "
    "les produits, les prix ou le stock — ne réponds jamais de mémoire sur "
    "ces sujets. Réponds en français, de façon brève et naturelle. "
    "Si une recherche de produit ne donne aucun résultat, tu peux réessayer "
    "UNE SEULE FOIS avec une requête différente (plus large ou plus précise). "
    "Si le deuxième essai ne donne rien non plus, arrête de chercher et "
    "annonce honnêtement au client que tu n'as pas trouvé de produit "
    "correspondant, puis propose-lui autre chose (voir le catalogue, "
    "préciser sa demande, parler à un conseiller)."
)

# --- Messages de test représentatifs ---

TEST_MESSAGES = [
    "Avez-vous le Samsung A15 ?",
    "Il reste combien de riz 25kg ?",
    "C'est combien l'iPhone 13 ?",
    "Je cherche un téléphone pas cher",
    "Bonjour, vous êtes ouverts aujourd'hui ?",  # cas où AUCUN tool ne devrait être appelé
]


def fake_tool_result(name: str, arguments: dict) -> str:
    """Simule l'exécution d'un tool (pas de vraie DB à ce stade)."""
    if name == "search_products":
        query = arguments.get("query", "").lower()
        query_words = query.split()
        matches = {
            k: v
            for k, v in FAKE_PRODUCTS.items()
            if query in k
            or k in query
            or any(w in v["category"] or v["category"] in w for w in query_words)
        }
        return str(matches) if matches else "Aucun produit trouvé pour cette recherche."
    if name == "check_stock":
        product = arguments.get("product_name", "").lower()
        info = FAKE_PRODUCTS.get(product)
        return f"Stock: {info['stock']}" if info else "Produit inconnu."
    return "Tool inconnu."


async def run_test(message_text: str, provider) -> dict:
    messages = [
        Message(role="system", content=SYSTEM_PROMPT),
        Message(role="user", content=message_text),
    ]

    all_tool_calls: list[tuple[str, dict]] = []
    response = await provider.chat(messages, tools=TOOLS)

    # Boucle agentique : le modèle peut demander plusieurs tools à la
    # suite (ex: une recherche échoue, il réessaie avec une autre requête)
    # avant de donner sa réponse finale. On boucle jusqu'à ce qu'il n'y ait
    # plus de tool_calls, avec un plafond de sécurité pour éviter une
    # boucle infinie si le modèle déraille.
    max_rounds = 5
    rounds = 0
    while response.tool_calls and rounds < max_rounds:
        rounds += 1
        messages.append(Message(role="assistant", content=response.content or ""))
        for tc in response.tool_calls:
            all_tool_calls.append((tc.name, tc.arguments))
            tool_result = fake_tool_result(tc.name, tc.arguments)
            messages.append(
                Message(role="tool", content=tool_result, tool_call_id=tc.id, name=tc.name)
            )
        response = await provider.chat(messages, tools=TOOLS)

    result = {
        "message": message_text,
        "tool_calls": all_tool_calls,
        "rounds": rounds,
        "final_answer": response.content,
    }
    if all_tool_calls and not response.content:
        result["final_raw_debug"] = response.raw

    return result


async def main():
    provider = get_llm_provider()

    print("=== Test de tool calling — Ollama Cloud ===\n")

    results = []
    for msg in TEST_MESSAGES:
        print(f"→ Message: {msg}")
        try:
            result = await run_test(msg, provider)
        except Exception as exc:  # noqa: BLE001
            print(f"  ERREUR: {exc}\n")
            results.append({"message": msg, "error": str(exc)})
            continue

        if result["tool_calls"]:
            for name, args in result["tool_calls"]:
                print(f"  Tool appelé: {name}({args})")
            if result["rounds"] > 1:
                print(f"  ({result['rounds']} aller-retours avec les tools)")
            print(f"  Réponse finale: {result.get('final_answer')}")
            if result.get("final_raw_debug"):
                print(f"  [DEBUG] réponse brute (content vide): {result['final_raw_debug']}")
            print()
        else:
            print(f"  Aucun tool appelé. Réponse directe: {result['final_answer']}\n")

        results.append(result)

    print("=== Résumé ===")
    print(f"{len(results)} messages testés.")
    print(
        "Vérifie manuellement, pour chaque message, si le bon tool a été "
        "appelé (ou aucun tool, pour le message 'Bonjour...'). Il n'y a pas "
        "encore de scoring automatique — c'est volontaire à ce stade, "
        "l'objectif est d'abord d'observer le comportement réel du modèle."
    )


if __name__ == "__main__":
    asyncio.run(main())

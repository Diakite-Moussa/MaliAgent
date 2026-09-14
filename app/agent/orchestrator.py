"""
Orchestrateur de conversation : gère l'historique multi-tours, appelle
le LLM avec les tools, exécute les tools contre la DB réelle et boucle
jusqu'à une réponse finale.
"""

import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.llm.base import Message
from app.llm.factory import get_llm_provider
from app.models import Business, Conversation, ConversationMessage, Customer
from app.tools.definitions import TOOLS
from app.tools.executor import execute_tool

logger = get_logger("orchestrator")


def build_system_prompt(business_name: str = "notre boutique") -> str:
    return (
        f"Tu es l'assistant commercial WhatsApp officiel de la boutique '{business_name}' au Mali. "
        "Tu t'exprimes en français poli, naturel et chaleureux. Les prix sont toujours en FCFA.\n\n"
        "Règles strictes sur l'utilisation des tools :\n"
        "1. PRODUITS & PRIX : Utilise toujours 'search_products' ou 'check_stock' pour renseigner "
        "le client. N'invente jamais de prix ni de disponibilité.\n"
        "2. LIVRAISON & CHANGEMENT D'ADRESSE :\n"
        "   - Si le client a déjà une commande en attente/en cours et indique un nouveau quartier ou rectifie son adresse "
        "('je suis à ACI 2000 pas à Faladié', 'changez mon adresse pour Badalabougou', etc.), appelle IMMÉDIATEMENT "
        "'update_order_address(new_zone=...)'. Ne promets JAMAIS de déterminer le tarif plus tard et NE CRÉE SURTOUT PAS de nouvelle commande.\n"
        "   - Pour une nouvelle commande ou une simple question tarifaire (ex: 'livrez-vous à Lafiabougou ?', 'frais pour Badalabougou ?'), "
        "dès que le client mentionne un quartier ou une commune, appelle TOUJOURS 'calculate_delivery(zone=...)'. N'invente jamais de tarif de livraison.\n"
        "3. PASSATION DE COMMANDE :\n"
        "   - Si le client souhaite acheter, vérifie le stock et demande son quartier de livraison "
        "s'il ne l'a pas indiqué.\n"
        "   - Calcule les frais de livraison avec 'calculate_delivery'.\n"
        "   - Fais TOUJOURS un récapitulatif complet (Produits, Quantités, Prix produits, Frais de livraison, Total global, Lieu) "
        "et demande-lui une CONFIRMATION EXPLICITE (ex: 'Confirmez-vous cette commande ?').\n"
        "   - Tu ne dois JAMAIS appeler le tool 'create_order' avant que le client n'ait explicitement confirmé par 'Oui', 'Je confirme', 'D'accord' ou équivalent.\n"
        "   - Dès qu'il confirme dans la suite de la discussion, rappelle-toi des articles discutés dans l'historique, "
        "appelle immédiatement 'create_order' avec ces éléments et communique-lui son numéro de commande.\n"
        "3bis. RUPTURE PARTIELLE : Si 'create_order' répond avec un message proposant une alternative "
        "en stock, présente cette alternative au client de façon naturelle et demande-lui s'il "
        "confirme la commande avec ce produit de remplacement à la place de l'original.\n"
        "4. SUIVI DE COMMANDE : Si le client demande des nouvelles de sa commande ('Où est ma commande ?', 'statut de ma commande', etc.), "
        "utilise 'get_order_status'. Dans ta réponse, annonce TOUJOURS ET EN TOUTE PRIORITÉ le statut clair et précis de la commande "
        "(ex: 'Votre commande est confirmée et en cours de préparation', 'Votre colis est en cours de livraison', 'Votre commande est en attente') "
        "dès la toute première phrase, AVANT de mentionner tout autre détail secondaire (adresse, articles ou lien de facture).\n"
        "5. FACTURATION : Si le client demande sa facture ('Envoyez-moi la facture', 'Je veux ma facture', 'facture pdf', etc.), "
        "utilise 'generate_invoice'. Tu peux aussi proposer d'éditer la facture dès qu'une commande vient d'être validée.\n"
        "6. ESCALADE HUMAINE : Si le client formule une NOUVELLE demande explicite de parler à un humain ('je veux parler à un responsable', "
        "'passez-moi un conseiller', 'appelez-moi') ou une nouvelle réclamation complexe ou négocie un nouveau rabais, "
        "appelle immédiatement 'escalate_to_human(reason=...)'.\n"
        "   ATTENTION CRUCIALE SUR L'HISTORIQUE : Si une demande de rabais ou d'intervention humaine a DÉJÀ été transmise "
        "dans l'historique ou si une note indique qu'elle est résolue, ou si le client salue ('Bonjour', 'Salut') "
        "ou indique que la réduction/le problème est réglé ('la réduction est faite', 'c'est bon', 'on a convenu du prix'), "
        "NE RÉ-ESCALADE SURTOUT PAS ! Réponds-lui poliment et chaleureusement, confirme son message et poursuis la vente normalement.\n"
        "7. ANNULATION DE COMMANDE : Si le client demande à annuler sa commande ('je veux annuler ma commande', etc.), "
        "utilise 'cancel_order(order_ref=..., reason=...)'.\n"
        "8. RECHERCHE INFRUCTUEUSE : Si une recherche ne donne rien, réessaie une seule fois plus largement. "
        "Si toujours rien, indique-le honnêtement.\n"
        "9. PERTINENCE ET CONCISION STRICTE (ANTI-RÉPÉTITION & ANTI-HALLUCINATION) :\n"
        "   - Réponds STRICTEMENT et DIRECTEMENT au dernier message du client.\n"
        "   - N'inclus JAMAIS dans ta réponse de récapitulatif d'anciennes commandes déjà livrées, confirmées ou payées (comme des commandes passées à Kati ou ailleurs), sauf si le client te demande expressément 'Où en est ma commande ?'.\n"
        "   - N'invente JAMAIS d'adresse physique fictive de boutique, ni d'avenue non précisée.\n"
        "   - Si le client pose une simple question de livraison (ex: 'Est-ce que vous livrez à Lafiabougou ?'), appelle 'calculate_delivery(zone=...)'. Donne immédiatement et sobrement la réponse : confirmation de livraison, tarif et délai estimé. N'y ajoute aucun résumé de commandes passées.\n"
        "10. FORMATAGE WHATSAPP STRICT (INTERDICTION ABSOLUE DES TABLEAUX MARKDOWN) :\n"
        "    - WhatsApp NE SAIT PAS afficher les tableaux Markdown (| col1 | col2 |). Ils s'affichent affreusement cassés, avec des traits verticaux et des coupures illisibles sur smartphone.\n"
        "    - Tu as l'INTERDICTION FORMELLE d'utiliser des barres verticales '|' ou des traits '|---|'.\n"
        "    - Présente TOUJOURS tes récapitulatifs sous forme de liste claire et aérée avec des puces ('•'), des emojis et du gras (*mot*) :\n"
        "      Exemple obligatoire pour un récapitulatif :\n"
        "      📦 *Votre commande :*\n"
        "      • *1x Samsung Galaxy A15* : 95 000 FCFA\n"
        "      • *Livraison (Faladié)* : 1 500 FCFA\n"
        "      👉 *Total à régler : 96 500 FCFA*\n\n"
        "      Exemple pour des remarques ou disponibilités :\n"
        "      • *Samsung Galaxy A15* (1 unité) : Remise déjà appliquée\n"
        "      • *Sac à main cuir* : Actuellement non disponible en boutique\n"
    )


SYSTEM_PROMPT = build_system_prompt()

MAX_ROUNDS = 5
FALLBACK_MESSAGE = (
    "Désolé, je n'arrive pas à traiter votre demande pour le moment. "
    "Un conseiller de la boutique va vous répondre."
)
HUMAN_HANDOFF_MESSAGE = (
    "Votre conversation est actuellement prise en charge par un conseiller de notre boutique. "
    "Un responsable humain va vous répondre directement d'ici un instant. Merci de votre patience !"
)


def format_whatsapp_tables(text: str) -> str:
    """
    Convertit automatiquement les tableaux Markdown (| col1 | col2 |) en listes à puces
    aérées et parfaitement lisibles sur les smartphones et l'application WhatsApp.
    """
    if not text or "|" not in text:
        return text

    lines = text.split("\n")
    out = []
    headers = []
    in_table = False

    for line in lines:
        s = line.strip()
        if s.startswith("|") and s.endswith("|"):
            cells = [c.strip() for c in s[1:-1].split("|")]
            # Détection d'une ligne de séparation Markdown |---|---|
            if all(re.match(r"^:?-+:?$", c) for c in cells if c):
                in_table = True
                continue

            if not in_table:
                # Première ligne rencontrée = en-têtes
                headers = [h.lower() for h in cells]
                in_table = True
            else:
                # Ligne de données du tableau
                prod = ""
                qty = ""
                details = []
                for h, val in zip(headers, cells):
                    if not val or val in ("—", "-"):
                        continue
                    if any(k in h for k in ["article", "produit", "nom", "item"]):
                        if not prod:
                            prod = val
                        else:
                            details.append(val)
                    elif any(k in h for k in ["quantité", "qte", "quantite", "qté"]):
                        qty = val
                    else:
                        details.append(val)

                line_parts = []
                if prod:
                    line_parts.append(f"• *{prod}*")
                if qty:
                    line_parts.append(f"(x{qty})")
                if details:
                    detail_str = " - ".join(details)
                    if line_parts:
                        line_parts.append(f": {detail_str}")
                    else:
                        line_parts.append(f"• {detail_str}")

                if line_parts:
                    out.append(" ".join(line_parts))
        else:
            in_table = False
            headers = []
            out.append(line)

    return "\n".join(out)


async def run_agent_turn(
    session: AsyncSession,
    business_id: uuid.UUID,
    user_message: str,
    customer_phone_number: str | None = None,
) -> str:
    customer_id = uuid.uuid4()
    conversation = None
    recent_history: list[ConversationMessage] = []

    # 1. Résolution du Customer et de la Conversation active
    if customer_phone_number:
        stmt = select(Customer).where(
            Customer.business_id == business_id,
            Customer.whatsapp_phone_number == customer_phone_number,
        )
        result = await session.execute(stmt)
        customer = result.scalar_one_or_none()
        if not customer:
            customer = Customer(
                business_id=business_id,
                whatsapp_phone_number=customer_phone_number,
            )
            session.add(customer)
            await session.flush()
        customer_id = customer.id

        # Recherche de la conversation la plus récente pour ce client
        stmt_conv = (
            select(Conversation)
            .where(
                Conversation.business_id == business_id,
                Conversation.customer_id == customer_id,
            )
            .order_by(Conversation.updated_at.desc())
            .limit(1)
        )
        result_conv = await session.execute(stmt_conv)
        conversation = result_conv.scalar_one_or_none()

        if not conversation:
            conversation = Conversation(
                business_id=business_id,
                customer_id=customer_id,
                channel="whatsapp",
                status="active",
            )
            session.add(conversation)
            await session.flush()
        elif conversation.status == "needs_human":
            # Le client est en attente d'un humain : enregistrer le message et répondre le message de veille
            session.add(
                ConversationMessage(
                    conversation_id=conversation.id,
                    role="user",
                    content=user_message,
                )
            )
            await session.commit()
            return HUMAN_HANDOFF_MESSAGE
        else:
            # Charger les 10 derniers messages pour donner la mémoire à l'agent
            stmt_msgs = (
                select(ConversationMessage)
                .where(ConversationMessage.conversation_id == conversation.id)
                .order_by(ConversationMessage.created_at.desc())
                .limit(10)
            )
            hist = (await session.execute(stmt_msgs)).scalars().all()
            recent_history = list(reversed(hist))

    provider = get_llm_provider()

    # 2. Construction du prompt avec le nom réel de la boutique et l'historique conversationnel
    stmt_biz = select(Business).where(Business.id == business_id)
    biz = (await session.execute(stmt_biz)).scalar_one_or_none()
    biz_name = biz.name if biz else "notre boutique"

    messages = [Message(role="system", content=build_system_prompt(business_name=biz_name))]
    for m in recent_history:
        messages.append(Message(role=m.role, content=m.content))
    messages.append(Message(role="user", content=user_message))

    # 3. Boucle de raisonnement et Tool Calling
    rounds = 0
    last_tool_output = None
    try:
        response = await provider.chat(messages, tools=TOOLS)
        while response.tool_calls and rounds < MAX_ROUNDS:
            rounds += 1
            logger.info(
                "Round %s: tool_calls demandés par le LLM -> %s",
                rounds,
                [tc.name for tc in response.tool_calls],
            )
            messages.append(Message(role="assistant", content=response.content or ""))
            for tc in response.tool_calls:
                result = await execute_tool(session, business_id, customer_id, tc.name, tc.arguments)
                last_tool_output = result
                logger.debug("  -> %s(%s) = %r", tc.name, tc.arguments, result[:200])
                messages.append(
                    Message(role="tool", content=result, tool_call_id=tc.id, name=tc.name)
                )
            response = await provider.chat(messages, tools=TOOLS)

        if response.tool_calls and rounds >= MAX_ROUNDS:
            logger.warning(
                "Limite de %s rounds atteinte avec tool_calls en attente -> relance sans tools pour formuler une réponse finale.",
                MAX_ROUNDS,
            )
            messages.append(Message(role="assistant", content=response.content or ""))
            messages.append(
                Message(
                    role="user",
                    content=(
                        "Formule maintenant une réponse finale claire et complète pour le "
                        "client, en te basant uniquement sur les informations déjà obtenues "
                        "ci-dessus dans la conversation. N'appelle plus aucun tool."
                    ),
                )
            )
            response = await provider.chat(messages, tools=None)

        final_reply = format_whatsapp_tables(response.content or FALLBACK_MESSAGE)
    except Exception as e:
        logger.error(
            "Exception dans l'orchestrateur: %s (dernier tool_output: %r)",
            e,
            last_tool_output,
            exc_info=True,
        )
        final_reply = FALLBACK_MESSAGE

    # 4. Sauvegarde des messages pour les prochains tours
    if conversation:
        session.add(
            ConversationMessage(
                conversation_id=conversation.id,
                role="user",
                content=user_message,
            )
        )
        session.add(
            ConversationMessage(
                conversation_id=conversation.id,
                role="assistant",
                content=final_reply,
            )
        )
        await session.commit()

    return final_reply
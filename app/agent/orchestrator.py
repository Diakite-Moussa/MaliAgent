"""
Orchestrateur de conversation : gère l'historique multi-tours, appelle
le LLM avec les tools, exécute les tools contre la DB réelle et boucle
jusqu'à une réponse finale.
"""

import json
import re
import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.audio import store_outgoing_audio
from app.core.logging import get_logger
from app.llm.base import Message
from app.llm.factory import get_llm_provider
from app.models import Business, Conversation, ConversationMessage, Customer
from app.tools.definitions import TOOLS
from app.tools.executor import execute_tool
from app.voice.formatter import clean_text_for_speech, extract_spoken_and_display_text
from app.voice.languages import detect_language
from app.voice.tts.factory import get_tts_provider

logger = get_logger("orchestrator")

_PHOTO_PAYLOAD_RE = re.compile(r"__PHOTO_PAYLOAD__(.*?)__END__\n?", re.DOTALL)


def _extract_photo_payload(tool_result: str) -> tuple[str, dict | None]:
    """Extrait et retire le marqueur photo avant transmission au LLM."""
    match = _PHOTO_PAYLOAD_RE.search(tool_result or "")
    if not match:
        return tool_result, None
    try:
        payload = json.loads(match.group(1))
    except Exception:
        payload = None
    cleaned = _PHOTO_PAYLOAD_RE.sub("", tool_result).strip()
    return cleaned, payload


async def _traced_execute_tool(
    session: AsyncSession,
    business_id: uuid.UUID,
    customer_id: uuid.UUID,
    tool_name: str,
    tool_arguments: dict,
) -> str:
    """Exécute un tool avec traçage temporel structuré et capture d'erreurs."""
    t0 = time.perf_counter()
    status = "SUCCESS"
    try:
        result = await execute_tool(session, business_id, customer_id, tool_name, tool_arguments)
        return result
    except Exception as e:
        status = "ERROR"
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        logger.error(
            "[TOOL_TRACE] tool=%s status=ERROR duration_ms=%.2f args=%s error=%s",
            tool_name,
            duration_ms,
            tool_arguments,
            str(e),
            exc_info=True,
        )
        raise
    finally:
        if status == "SUCCESS":
            duration_ms = round((time.perf_counter() - t0) * 1000, 2)
            snippet = (result[:150] + "...") if len(result) > 150 else result
            logger.info(
                "[TOOL_TRACE] tool=%s status=SUCCESS duration_ms=%.2f args=%s result=%r",
                tool_name,
                duration_ms,
                tool_arguments,
                snippet,
            )



def build_system_prompt(business_name: str = "notre boutique", target_lang: str = "fr") -> str:
    if target_lang == "bm":
        intro = (
            f"Tu es l'assistant commercial WhatsApp officiel de la boutique '{business_name}' au Mali.\n"
            "🚨 ATTENTION DIRECTIVE LINGUISTIQUE STRICTE (BAMBARA / BAMANANKAN OBLIGATOIRE) :\n"
            "- Le client s'exprime actuellement en BAMBARA. Tu DOIS IMPÉRATIVEMENT lui répondre EN BAMBARA poli, naturel et chaleureux de Bamako !\n"
            "- INTERDICTION ABSOLUE de formuler ta réponse en Français (seuls les noms de marques et modèles comme 'Samsung Galaxy A15' ou 'iPhone' restent tels quels).\n"
            "- La balise <voice>...</voice> et l'intégralité du texte WhatsApp DOIVENT être formulés en Bambara courant.\n"
            "Les prix sont toujours en FCFA.\n\n"
        )
    else:
        intro = (
            f"Tu es l'assistant commercial WhatsApp officiel de la boutique '{business_name}' au Mali. "
            "Tu t'exprimes en français poli, naturel et chaleureux. Les prix sont toujours en FCFA.\n\n"
        )

    return (
        intro +
        "Règles strictes sur l'utilisation des tools :\n"
        "1. PRODUITS & PRIX : Utilise toujours 'search_products' ou 'check_stock' pour renseigner "
        "le client. N'invente jamais de prix ni de disponibilité.\n"
        "2. LIVRAISON & GÉOLOCALISATION GPS (BAMAKO) :\n"
        "   - Lorsque le client souhaite se faire livrer, propose-lui les 2 options : soit indiquer son quartier par écrit (ex: Lafiabougou, ACI 2000, Faladié...), soit partager sa position GPS exacte directement sur WhatsApp via l'option de localisation.\n"
        "   - Si le message contient '[LOCALISATION_GPS: latitude=..., longitude=...]' ou si des coordonnées GPS sont fournies, "
        "appelle IMMÉDIATEMENT 'calculate_delivery(latitude=..., longitude=...)'. Indique au client le quartier/commune de Bamako reconnu à partir de ses coordonnées GPS, confirme-lui le tarif fixe de livraison et intègre cette position exacte dans le récapitulatif.\n"
        "   - Si le client a déjà une commande en attente/en cours et indique un nouveau quartier ou rectifie son adresse "
        "('je suis à ACI 2000 pas à Faladié', 'changez mon adresse pour Badalabougou', etc.), appelle IMMÉDIATEMENT "
        "'update_order_address(new_zone=...)'. Ne promets JAMAIS de déterminer le tarif plus tard et NE CRÉE SURTOUT PAS de nouvelle commande.\n"
        "   - Pour une nouvelle commande ou une simple question tarifaire (ex: 'livrez-vous à Lafiabougou ?', 'frais pour Badalabougou ?'), "
        "dès que le client mentionne un quartier ou une commune, appelle TOUJOURS 'calculate_delivery(zone=...)'. N'invente jamais de tarif de livraison.\n"
        "3. PASSATION DE COMMANDE :\n"
        "   - Si le client souhaite acheter, vérifie le stock et demande son quartier de livraison ou le partage de sa position GPS s'il ne l'a pas fait.\n"
        "   - Calcule les frais de livraison avec 'calculate_delivery'.\n"
        "   - Fais TOUJOURS un récapitulatif complet (Produits, Quantités, Prix produits, Frais de livraison, Total global, Lieu / Position GPS) "
        "et demande-lui une CONFIRMATION EXPLICITE (ex: 'Confirmez-vous cette commande ?').\n"
        "   - Tu ne dois JAMAIS appeler le tool 'create_order' avant que le client n'ait explicitement confirmé par 'Oui', 'Je confirme', 'D'accord' ou équivalent.\n"
        "   - Dès qu'il confirme dans la suite de la discussion, rappelle-toi des articles discutés dans l'historique (et des coordonnées GPS latitude/longitude si partagées), "
        "appelle immédiatement 'create_order' avec ces éléments et communique-lui son numéro de commande.\n"
        "3bis. RUPTURE PARTIELLE : Si 'create_order' répond avec un message proposant une alternative "
        "en stock, présente cette alternative au client de façon naturelle et demande-lui s'il "
        "confirme la commande avec ce produit de remplacement à la place de l'original.\n"
        "4. SUIVI DE COMMANDE : Si le client demande des nouvelles de sa commande ('Où est ma commande ?', 'statut de ma commande', etc.), "
        "utilise 'get_order_status'. Dans ta réponse, annonce TOUJOURS ET EN TOUTE PRIORITÉ le statut clair et précis de la commande "
        "(ex: 'Votre commande est confirmée et en cours de préparation', 'Votre colis est en cours de livraison', 'Votre commande est en attente') "
        "dès la toute première phrase, AVANT de mentionner tout autre détail secondaire (adresse, articles ou lien de facture).\n"
        "   ATTENTION CRUCIALE : N'appelle JAMAIS 'create_order' en réponse à une question de suivi. Une question de suivi "
        "('où en est ma commande', 'statut de ma commande', 'ça en est où') n'est PAS une nouvelle demande d'achat, même si "
        "l'historique de conversation contient une commande précédente similaire ou les mêmes articles déjà discutés. "
        "Utilise UNIQUEMENT 'get_order_status' pour ce type de demande.\n"
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
        "utilise 'cancel_order(order_ref=..., reason=...)'. N'affirme JAMAIS qu'une commande a été annulée, "
        "créée, facturée ou qu'un paiement a été initié sans avoir RÉELLEMENT appelé le tool correspondant "
        "dans ce même tour de conversation.\n"
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
        "11. BILINGUISME STRICT (FRANÇAIS & BAMBARA UNIQUEMENT) :\n"
        "    - Tu es un assistant commercial basé exclusivement à Bamako, au Mali.\n"
        "    - Tu as l'INTERDICTION ABSOLUE de répondre en portugais, espagnol, anglais ou toute autre langue étrangère.\n"
        "    - Même si l'historique ou un message mal transcrit semble contenir un mot étranger (ex: 'Bom dia', 'como esta', 'disponível'), "
        "considère TOUJOURS qu'il s'agit soit de Bambara mal transcrit, soit de Français, et réponds EXCLUSIVEMENT en Français ou en Bambara !\n"
        "    - RÈGLE D'OR : La langue de ta réponse doit TOUJOURS correspondre à la langue du message actuel du client !\n"
        "      • Si le client s'exprime en Bambara (ex: 'I ni ce', 'Samsung A15 sɔngɔ ye joli ye ?', 'a bɛ yen wa ?', 'n b'a fɛ ka san') "
        "ou si le message vocal est en Bambara, réponds-lui poliment, chaleureusement et naturellement en BAMBARA (balise <voice> et texte complet) !\n"
        "        Vocabulaire et expressions clés en Bambara :\n"
        "        • Salutations : 'I ni ce !' (Bonjour), 'I ni sogoma !' (Bonjour matin), 'I ni wula !' (Bonsoir), 'I bisimila !' (Bienvenue).\n"
        "        • Disponibilité & Prix : '[Produit] sɔngɔ ye [Prix] FCFA ye. A bɛ yen kosɛbɛ.' (Le produit coûte X FCFA. Il est bien disponible).\n"
        "        • Demande de quantité : 'I b'a fɛ joli ?' (Combien en voulez-vous ?).\n"
        "        • Demande de quartier / localisation : 'I ka dugu kɔnɔ yɔrɔ fɔ an ye (walima GPS lase an ma) walasa an k'a lase i ma.'\n"
        "        • Frais de livraison : 'Donni sɔngɔ ye [Frais] FCFA ye [Lieu] kɔnɔ.'\n"
        "        • Récapitulatif & Paiement : 'Jate bɛɛ lajɛlen ye [Total] FCFA ye. Wave link ye nin ye : [Lien]'\n"
        "        • Rupture : '[Produit] banna sisan, nka an bɛ se ka [Alternative] di i ma.'\n"
        "        • Confirmation : 'I b'a fɛ an k'a bila i ye wa ?' (Souhaitez-vous confirmer la commande ?).\n"
        "      • Si le client s'exprime en Français, réponds normalement en Français.\n"
        "12. NOTES VOCALES ET FORMAT PARLÉ (<voice>) :\n"
        "    - Quand le client communique par note vocale ou si une réponse vocale est demandée, insère TOUJOURS au tout début de ton message une balise <voice>...</voice> contenant la version PARLÉE de ta réponse.\n"
        "    - Si le message du client est en Bambara, le contenu de la balise <voice> DOIT ÊTRE EN BAMBARA (ex: '<voice>Samsung Galaxy A15 sɔngɔ ye 95 000 FCFA ye. A bɛ yen. I b'a fɛ joli ?</voice>').\n"
        "    - Cette version <voice> doit être formulée comme un commerçant humain qui parle au micro : ultra-courte (1 à 2 phrases directes), fluide, sans émoji, sans tiret, sans astérisque et sans parenthèse de stock.\n"
        "    - Après la balise </voice>, écris ensuite ton message textuel complet et soigné pour WhatsApp (avec émojis, listes et détails).\n"
    )


SYSTEM_PROMPT = build_system_prompt()

MAX_ROUNDS = 5
FALLBACK_MESSAGE_FR = (
    "Désolé, je n'arrive pas à traiter votre demande pour le moment. "
    "Un conseiller de la boutique va vous répondre."
)
FALLBACK_MESSAGE_BM = (
    "Hakɛto, n tɛ se ka nin ɲɛnabɔ sisan. "
    "Boutique kɔnɔ mɔgɔ dɔ bɛna i jaabi sisan sisan."
)
FALLBACK_MESSAGE = FALLBACK_MESSAGE_FR

HUMAN_HANDOFF_MESSAGE_FR = (
    "Votre conversation est actuellement prise en charge par un conseiller de notre boutique. "
    "Un responsable humain va vous répondre directement d'ici un instant. Merci de votre patience !"
)
HUMAN_HANDOFF_MESSAGE_BM = (
    "I ka kobarodon bɛna ɲɛnabɔ boutique kuntigi fɛ. "
    "Mɔgɔ bɛna kuma i fɛ sisan sisan. Sabali dɔɔnin !"
)
HUMAN_HANDOFF_MESSAGE = HUMAN_HANDOFF_MESSAGE_FR


def clean_llm_reply(text: str) -> str:
    """
    Nettoie les artefacts de raisonnement interne (Chain-of-Thought, balises <think>
    et notes de réflexion en anglais générées par certains modèles LLM).
    """
    if not text:
        return text

    # 1. Supprimer les balises <think>...</think>
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

    # 2. Supprimer les phrases de réflexion interne en anglais en préambule
    # Ex: "We have stock info. Need to ask for quantity and delivery zone."
    lines = text.split("\n")
    cleaned_lines = []
    header_checked = False

    thought_keywords = [
        "we have stock info",
        "need to ask for",
        "i will ask",
        "let's check",
        "user wants",
        "calling tool",
        "the stock is",
        "the user asked",
    ]

    for line in lines:
        s = line.strip()
        if not header_checked and s:
            if any(k in s.lower() for k in thought_keywords):
                continue
            header_checked = True
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def format_whatsapp_tables(text: str) -> str:
    """
    Convertit automatiquement les tableaux Markdown (| col1 | col2 |) en listes à puces
    aérées et parfaitement lisibles sur les smartphones et l'application WhatsApp.
    """
    text = clean_llm_reply(text)
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
    is_voice: bool = False,
    return_voice_url: bool = False,
    return_photo_info: bool = False,
    forced_language: str | None = None,
) -> str | tuple:
    def _build_return(reply: str, audio: str | None, photo: dict | None):
        if return_voice_url and return_photo_info:
            return reply, audio, photo
        if return_voice_url:
            return reply, audio
        if return_photo_info:
            return reply, photo
        return reply

    customer_id = uuid.uuid4()
    conversation = None
    customer = None
    recent_history: list[ConversationMessage] = []

    # Détection linguistique (Français vs Bambara)
    detected_lang = forced_language or detect_language(user_message)
    fallback_message = FALLBACK_MESSAGE_BM if detected_lang == "bm" else FALLBACK_MESSAGE_FR
    handoff_message = HUMAN_HANDOFF_MESSAGE_BM if detected_lang == "bm" else HUMAN_HANDOFF_MESSAGE_FR

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
                preferred_language=detected_lang,
                preferred_channel_type="voice" if is_voice else "text",
            )
            session.add(customer)
            await session.flush()
        else:
            customer.preferred_language = detected_lang
            if is_voice:
                customer.preferred_channel_type = "voice"
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
            audio_url = None
            if is_voice:
                try:
                    tts = get_tts_provider()
                    tts_res = await tts.synthesize(handoff_message, language=detected_lang)
                    _, audio_url = store_outgoing_audio(tts_res.audio_bytes, tts_res.mime_type)
                except Exception as err:
                    logger.warning("Erreur synthèse vocale handoff : %s", err)
            return _build_return(handoff_message, audio_url, None)
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

    messages = [
        Message(
            role="system",
            content=build_system_prompt(business_name=biz_name, target_lang=detected_lang),
        )
    ]
    for m in recent_history:
        messages.append(Message(role=m.role, content=m.content))

    if detected_lang == "bm":
        messages.append(
            Message(
                role="system",
                content=(
                    "🚨 RAPPEL CRITIQUE POUR CE TOUR : Le client s'exprime en BAMBARA ('"
                    + user_message
                    + "').\n"
                    "Tu DOIS IMPÉRATIVEMENT formuler ta réponse (la balise <voice> et le texte complet) EN BAMBARA !\n"
                    "INTERDICTION TOTALE DE RÉPONDRE EN FRANÇAIS."
                ),
            )
        )
    messages.append(Message(role="user", content=user_message))

    # 3. Boucle de raisonnement et Tool Calling
    rounds = 0
    last_tool_output = None
    tools_called_this_turn: set[str] = set()
    pending_photo: dict | None = None
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
                result = await _traced_execute_tool(session, business_id, customer_id, tc.name, tc.arguments)
                last_tool_output = result
                tools_called_this_turn.add(tc.name)
                cleaned_result, photo_payload = _extract_photo_payload(result)
                if photo_payload:
                    pending_photo = photo_payload
                messages.append(
                    Message(role="tool", content=cleaned_result, tool_call_id=tc.id, name=tc.name)
                )
            response = await provider.chat(messages, tools=TOOLS)

        if response.tool_calls and rounds >= MAX_ROUNDS:
            logger.warning(
                "Limite de %s rounds atteinte avec tool_calls en attente -> relance sans tools pour formuler une réponse finale.",
                MAX_ROUNDS,
            )
            messages.append(Message(role="assistant", content=response.content or ""))
            final_prompt = (
                "Formule maintenant une réponse finale claire et complète pour le client en BAMBARA, "
                "en te basant uniquement sur les informations déjà obtenues ci-dessus dans la conversation. N'appelle plus aucun tool."
                if detected_lang == "bm"
                else (
                    "Formule maintenant une réponse finale claire et complète pour le "
                    "client, en te basant uniquement sur les informations déjà obtenues "
                    "ci-dessus dans la conversation. N'appelle plus aucun tool."
                )
            )
            messages.append(
                Message(
                    role="user",
                    content=final_prompt,
                )
            )
            response = await provider.chat(messages, tools=None)

        # --- Garde-fous anti-hallucination généralisés (Priorité 2) ---
        hallucination_detected = None
        forced_user_prompt = None
        fallback_tool_to_force = None

        content_lower = (response.content or "").lower()
        user_lower = user_message.lower()

        # 1. Annulation de commande (garantie absolue de restauration du stock)
        user_wants_cancel = any(kw in user_lower for kw in ("annul", "n'en veux plus", "abandon"))
        reply_claims_cancel = any(kw in content_lower for kw in (
            "commande a bien été annulée", "commande a été annulée", "annulation a bien été prise",
            "articles sont de nouveau disponibles", "articles ont été remis en stock", "commande est annulée"
        ))
        if (user_wants_cancel or reply_claims_cancel) and "cancel_order" not in tools_called_this_turn:
            hallucination_detected = "cancel_order"
            forced_user_prompt = (
                "IMPORTANT : Tu affirmes que la commande a été annulée ou le client demande son annulation, "
                "mais tu n'as PAS appelé le tool 'cancel_order'. Tu DOIS impérativement appeler 'cancel_order' "
                "maintenant pour mettre à jour la commande et réapprovisionner le stock en base de données."
            )
            fallback_tool_to_force = ("cancel_order", {"reason": "Demande d'annulation client"})

        # 2. Création de commande
        elif (
            any(kw in content_lower for kw in (
                "commande confirmée et enregistrée", "détails de la commande #",
                "votre commande a bien été enregistrée", "enregistrée avec succès !"
            ))
            and "create_order" not in tools_called_this_turn
            and "get_order_status" not in tools_called_this_turn
            and "cancel_order" not in tools_called_this_turn
        ):
            hallucination_detected = "create_order"
            forced_user_prompt = (
                "IMPORTANT : Tu affirmes au client que sa commande est enregistrée ou confirmée, "
                "mais tu n'as PAS appelé le tool 'create_order'. Tu DOIS impérativement appeler 'create_order' "
                "maintenant pour créer la commande et réserver le stock en base de données."
            )

        # 3. Facturation PDF
        elif (
            (any(kw in user_lower for kw in ("facture", "reçu")) or "facture #fac-" in content_lower or "télécharger la facture" in content_lower)
            and any(kw in content_lower for kw in ("facture officielle #", "facture #fac-", "télécharger la facture", "/invoices/fac-"))
            and "generate_invoice" not in tools_called_this_turn
        ):
            hallucination_detected = "generate_invoice"
            forced_user_prompt = (
                "IMPORTANT : Tu affirmes que la facture officielle est prête ou le client la demande, "
                "mais tu n'as PAS appelé le tool 'generate_invoice'. Tu DOIS impérativement appeler 'generate_invoice' "
                "maintenant pour générer le document PDF en base de données."
            )

        # 4. Escalade humaine (Human Handoff)
        elif (
            any(kw in content_lower for kw in (
                "transmise à un conseiller", "responsable humain va prendre",
                "conseiller de notre boutique va", "transmis à notre équipe"
            ))
            and "escalate_to_human" not in tools_called_this_turn
        ):
            hallucination_detected = "escalate_to_human"
            forced_user_prompt = (
                "IMPORTANT : Tu affirmes transmettre la conversation à un conseiller humain, "
                "mais tu n'as PAS appelé le tool 'escalate_to_human'. Tu DOIS impérativement appeler 'escalate_to_human' "
                "maintenant pour basculer le statut en base de données."
            )
            fallback_tool_to_force = ("escalate_to_human", {"reason": "Demande client / Escalade"})

        # 5. Initiation de paiement Mobile Money
        elif (
            any(kw in content_lower for kw in (
                "lien sécurisé pour régler", "demande de paiement wave",
                "demande orange money", "pay-wav-", "pay-om-", "pay-mov-"
            ))
            and "initiate_payment" not in tools_called_this_turn
        ):
            hallucination_detected = "initiate_payment"
            forced_user_prompt = (
                "IMPORTANT : Tu affirmes fournir un lien de paiement Mobile Money, "
                "mais tu n'as PAS appelé le tool 'initiate_payment'. Tu DOIS impérativement appeler 'initiate_payment' "
                "maintenant pour générer la session de paiement officielle."
            )

        if hallucination_detected:
            logger.warning(
                "Garde-fou anti-hallucination déclenché pour '%s' : affirmation détectée sans appel d'outil. "
                "Forçage d'un tour d'outil supplémentaire.",
                hallucination_detected,
            )
            messages.append(Message(role="assistant", content=response.content or ""))
            messages.append(Message(role="user", content=forced_user_prompt))
            response = await provider.chat(messages, tools=TOOLS)
            if response.tool_calls:
                messages.append(Message(role="assistant", content=response.content or ""))
                for tc in response.tool_calls:
                    result = await _traced_execute_tool(session, business_id, customer_id, tc.name, tc.arguments)
                    last_tool_output = result
                    tools_called_this_turn.add(tc.name)
                    cleaned_result, photo_payload = _extract_photo_payload(result)
                    if photo_payload:
                        pending_photo = photo_payload
                    messages.append(
                        Message(role="tool", content=cleaned_result, tool_call_id=tc.id, name=tc.name)
                    )
                response = await provider.chat(messages, tools=None)
            elif fallback_tool_to_force and fallback_tool_to_force[0] not in tools_called_this_turn:
                # Secours déterministe pour les actions critiques (ex: cancel_order pour restaurer le stock)
                t_name, t_args = fallback_tool_to_force
                logger.warning("Exécution déterministe de secours du tool '%s'", t_name)
                result = await _traced_execute_tool(session, business_id, customer_id, t_name, t_args)
                tools_called_this_turn.add(t_name)
                response.content = result


        raw_reply = format_whatsapp_tables(response.content or fallback_message)
        spoken_text, display_reply = extract_spoken_and_display_text(raw_reply, language=detected_lang)
        final_reply = display_reply
    except Exception as e:
        logger.error(
            "Exception dans l'orchestrateur: %s (dernier tool_output: %r)",
            e,
            last_tool_output,
            exc_info=True,
        )
        final_reply = fallback_message
        spoken_text = clean_text_for_speech(fallback_message, language=detected_lang)

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

    audio_url = None
    if is_voice:
        try:
            tts = get_tts_provider()
            tts_res = await tts.synthesize(spoken_text, language=detected_lang)
            _, audio_url = store_outgoing_audio(tts_res.audio_bytes, tts_res.mime_type)
        except Exception as err:
            logger.warning("Erreur lors de la génération audio TTS : %s", err)

    return _build_return(final_reply, audio_url, pending_photo)
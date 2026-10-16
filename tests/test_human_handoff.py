"""
Suite de tests automatisés Pytest pour la gestion des Relais Humains (SAV & Escalade) :
1. Déclenchement du tool escalate_to_human (Français & Bambara)
2. Consultation des demandes de relais depuis le Dashboard (GET /api/dashboard/handoffs)
3. Prise en main et envoi de réponse directe sur WhatsApp (POST /api/dashboard/handoffs/{id}/reply)
4. Clôture du relais et réactivation de l'agent IA (POST /api/dashboard/handoffs/{id}/resolve)
5. Isolation Multi-Tenant stricte (La boutique B ne peut ni voir ni répondre aux clients de la boutique A)
6. Comportement de veille de l'orchestrateur IA pendant un relais actif
"""

from unittest.mock import AsyncMock, patch
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.agent.orchestrator import HUMAN_HANDOFF_MESSAGE_BM, HUMAN_HANDOFF_MESSAGE_FR, run_agent_turn
from app.core.security import create_access_token, hash_password
from app.db.session import async_session
from app.main import app
from app.models import Business, Conversation, ConversationMessage, Customer, User, UserRole
from app.tools.executor import execute_tool


@pytest.fixture
async def handoff_test_data():
    """Crée deux boutiques distinctes, des clients (FR & BM) et des conversations."""
    async with async_session() as session:
        # Boutique A
        biz_a = Business(
            name=f"Boutique Handoff A-{uuid.uuid4().hex[:6]}",
            whatsapp_phone_number=f"+22370{uuid.uuid4().hex[:6]}",
            currency="XOF",
        )
        # Boutique B
        biz_b = Business(
            name=f"Boutique Handoff B-{uuid.uuid4().hex[:6]}",
            whatsapp_phone_number=f"+22371{uuid.uuid4().hex[:6]}",
            currency="XOF",
        )
        session.add_all([biz_a, biz_b])
        await session.flush()

        # Commerçants
        merchant_a = User(
            business_id=biz_a.id,
            email=f"merchant_a_{uuid.uuid4().hex[:6]}@test.ml",
            password_hash=hash_password("Pass123!"),
            first_name="Amadou",
            last_name="Diallo",
            role=UserRole.ADMIN,
        )
        merchant_b = User(
            business_id=biz_b.id,
            email=f"merchant_b_{uuid.uuid4().hex[:6]}@test.ml",
            password_hash=hash_password("Pass123!"),
            first_name="Fatou",
            last_name="Traore",
            role=UserRole.ADMIN,
        )
        session.add_all([merchant_a, merchant_b])
        await session.flush()

        # Clients Boutique A
        cust_fr = Customer(
            business_id=biz_a.id,
            whatsapp_phone_number="22370123456",
            display_name="Ibrahima Cissé",
            preferred_language="fr",
        )
        cust_bm = Customer(
            business_id=biz_a.id,
            whatsapp_phone_number="22370987654",
            display_name="Bakary Diarra",
            preferred_language="bm",
        )
        # Client Boutique B
        cust_b = Customer(
            business_id=biz_b.id,
            whatsapp_phone_number="22376112233",
            display_name="Modibo Keita",
            preferred_language="fr",
        )
        session.add_all([cust_fr, cust_bm, cust_b])
        await session.flush()

        # Conversations
        conv_fr = Conversation(
            business_id=biz_a.id,
            customer_id=cust_fr.id,
            channel="whatsapp",
            status="active",
        )
        conv_bm = Conversation(
            business_id=biz_a.id,
            customer_id=cust_bm.id,
            channel="whatsapp",
            status="active",
        )
        conv_b = Conversation(
            business_id=biz_b.id,
            customer_id=cust_b.id,
            channel="whatsapp",
            status="active",
        )
        session.add_all([conv_fr, conv_bm, conv_b])
        await session.flush()

        # Messages initiaux pour conv_fr
        msg1 = ConversationMessage(
            conversation_id=conv_fr.id,
            role="user",
            content="Bonjour, je voudrais négocier le prix du téléphone s'il vous plaît",
        )
        msg2 = ConversationMessage(
            conversation_id=conv_fr.id,
            role="assistant",
            content="Je comprends votre demande, un instant je préviens le responsable.",
        )
        session.add_all([msg1, msg2])
        await session.commit()

        token_a = create_access_token(str(merchant_a.id), str(biz_a.id), role=UserRole.ADMIN.value)
        token_b = create_access_token(str(merchant_b.id), str(biz_b.id), role=UserRole.ADMIN.value)

        return {
            "biz_a_id": biz_a.id,
            "biz_b_id": biz_b.id,
            "cust_fr_id": cust_fr.id,
            "cust_bm_id": cust_bm.id,
            "cust_b_id": cust_b.id,
            "conv_fr_id": conv_fr.id,
            "conv_bm_id": conv_bm.id,
            "conv_b_id": conv_b.id,
            "token_a": token_a,
            "token_b": token_b,
            "phone_fr": cust_fr.whatsapp_phone_number,
            "phone_bm": cust_bm.whatsapp_phone_number,
        }


@pytest.mark.asyncio
async def test_escalate_to_human_tool_french(handoff_test_data):
    """Vérifie le déclenchement de l'escalade humaine pour un client francophone."""
    data = handoff_test_data
    biz_id = data["biz_a_id"]
    cust_id = data["cust_fr_id"]
    conv_id = data["conv_fr_id"]

    async with async_session() as session:
        result = await execute_tool(
            session=session,
            business_id=biz_id,
            customer_id=cust_id,
            tool_name="escalate_to_human",
            arguments={"reason": "Négociation remise spéciale gros volume", "urgency": "high"},
        )
        assert "conseiller de notre boutique" in result
        assert "Négociation remise spéciale" in result

    # Vérification en base de données
    async with async_session() as session:
        stmt = select(Conversation).where(Conversation.id == conv_id)
        conv = (await session.execute(stmt)).scalar_one()
        assert conv.status == "needs_human"
        assert conv.handoff_reason == "Négociation remise spéciale gros volume"


@pytest.mark.asyncio
async def test_escalate_to_human_tool_bambara(handoff_test_data):
    """Vérifie le déclenchement de l'escalade humaine avec formulation en Bambara pour un client bamanan."""
    data = handoff_test_data
    biz_id = data["biz_a_id"]
    cust_id = data["cust_bm_id"]
    conv_id = data["conv_bm_id"]

    async with async_session() as session:
        result = await execute_tool(
            session=session,
            business_id=biz_id,
            customer_id=cust_id,
            tool_name="escalate_to_human",
            arguments={"reason": "Mɔgɔ bɛ yen wa / demande patron", "urgency": "normal"},
        )
        assert "boutique kuntigi" in result or "ɲiningali" in result

    async with async_session() as session:
        stmt = select(Conversation).where(Conversation.id == conv_id)
        conv = (await session.execute(stmt)).scalar_one()
        assert conv.status == "needs_human"


@pytest.mark.asyncio
async def test_get_handoffs_endpoint(handoff_test_data):
    """Vérifie la récupération de la file d'attente des relais humains via l'API commerçant."""
    data = handoff_test_data
    conv_id = data["conv_fr_id"]
    token_a = data["token_a"]

    # Passer conv_fr en needs_human
    async with async_session() as session:
        stmt = select(Conversation).where(Conversation.id == conv_id)
        conv = (await session.execute(stmt)).scalar_one()
        conv.status = "needs_human"
        conv.handoff_reason = "Demande d'échange direct"
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/api/dashboard/handoffs",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res.status_code == 200
        payload = res.json()
        assert "handoffs" in payload
        assert payload["total"] >= 1

        matched = next((h for h in payload["handoffs"] if h["id"] == str(conv_id)), None)
        assert matched is not None
        assert matched["handoff_reason"] == "Demande d'échange direct"
        assert matched["customer_phone"] == "22370123456"
        assert matched["customer_name"] == "Ibrahima Cissé"
        assert len(matched["messages"]) >= 2


@pytest.mark.asyncio
async def test_reply_handoff_endpoint(handoff_test_data):
    """Vérifie que la réponse du commerçant depuis le dashboard est enregistrée et envoyée sur WhatsApp."""
    data = handoff_test_data
    conv_id = data["conv_fr_id"]
    token_a = data["token_a"]

    # Passer conv_fr en needs_human
    async with async_session() as session:
        stmt = select(Conversation).where(Conversation.id == conv_id)
        conv = (await session.execute(stmt)).scalar_one()
        conv.status = "needs_human"
        conv.handoff_reason = "Négociation"
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("app.whatsapp.client.send_text_message", new_callable=AsyncMock) as mock_send_wa:
            res = await client.post(
                f"/api/dashboard/handoffs/{conv_id}/reply",
                json={"message": "Bonjour M. Cissé, nous acceptons de vous faire 5% de remise !"},
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert res.status_code == 200
            resp_data = res.json()
            assert resp_data["status"] == "sent"
            assert "5% de remise" in resp_data["content"]

            # Vérifier que le message WhatsApp a bien été déclenché
            mock_send_wa.assert_called_once()
            call_kwargs = mock_send_wa.call_args.kwargs
            assert call_kwargs["to"] == data["phone_fr"]
            assert "5% de remise" in call_kwargs["body"]

    # Vérification dans l'historique en base
    async with async_session() as session:
        stmt = (
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conv_id)
            .order_by(ConversationMessage.created_at.desc())
        )
        last_msg = (await session.execute(stmt)).scalars().first()
        assert last_msg is not None
        assert last_msg.role == "assistant"
        assert "5% de remise" in last_msg.content


@pytest.mark.asyncio
async def test_resolve_handoff_endpoint(handoff_test_data):
    """Vérifie la résolution du relais humain : repasse en active et envoie le message de clôture WhatsApp."""
    data = handoff_test_data
    conv_id = data["conv_fr_id"]
    token_a = data["token_a"]

    # Passer en needs_human
    async with async_session() as session:
        stmt = select(Conversation).where(Conversation.id == conv_id)
        conv = (await session.execute(stmt)).scalar_one()
        conv.status = "needs_human"
        conv.handoff_reason = "Problème réglé"
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("app.whatsapp.client.send_text_message", new_callable=AsyncMock) as mock_send_wa:
            res = await client.post(
                f"/api/dashboard/handoffs/{conv_id}/resolve",
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert res.status_code == 200
            assert res.json()["status"] == "success"

            # Vérifier l'envoi de notification de clôture au client
            mock_send_wa.assert_called_once()
            call_kwargs = mock_send_wa.call_args.kwargs
            assert call_kwargs["to"] == data["phone_fr"]
            assert "Merci pour votre échange" in call_kwargs["body"]

    # Vérification DB
    async with async_session() as session:
        stmt = select(Conversation).where(Conversation.id == conv_id)
        conv = (await session.execute(stmt)).scalar_one()
        assert conv.status == "active"
        assert conv.handoff_reason is None


@pytest.mark.asyncio
async def test_multi_tenant_handoff_isolation(handoff_test_data):
    """Vérifie qu'une boutique ne peut pas accéder ni intervenir sur le relais humain d'une autre boutique."""
    data = handoff_test_data
    conv_a_id = data["conv_fr_id"]
    token_b = data["token_b"]  # Token de la Boutique B

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Boutique B essaie de répondre à la conversation de Boutique A
        res_reply = await client.post(
            f"/api/dashboard/handoffs/{conv_a_id}/reply",
            json={"message": "Piratage cross-tenant"},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert res_reply.status_code == 404

        # Boutique B essaie de résoudre la conversation de Boutique A
        res_resolve = await client.post(
            f"/api/dashboard/handoffs/{conv_a_id}/resolve",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert res_resolve.status_code == 404


@pytest.mark.asyncio
async def test_orchestrator_skips_llm_when_needs_human(handoff_test_data):
    """Vérifie que l'orchestrateur conversationnel ne sollicite pas le LLM quand un relais humain est en cours."""
    data = handoff_test_data
    biz_id = data["biz_a_id"]
    cust_id = data["cust_fr_id"]
    conv_id = data["conv_fr_id"]

    # Mettre en needs_human
    async with async_session() as session:
        stmt = select(Conversation).where(Conversation.id == conv_id)
        conv = (await session.execute(stmt)).scalar_one()
        conv.status = "needs_human"
        conv.handoff_reason = "En attente du patron"
        await session.commit()

    # Quand le client envoie un message pendant l'attente
    async with async_session() as session:
        reply = await run_agent_turn(
            session=session,
            business_id=biz_id,
            user_message="Est-ce que le patron est disponible ?",
            customer_phone_number=data["phone_fr"],
        )

    assert reply == HUMAN_HANDOFF_MESSAGE_FR

    # Vérifie que le message utilisateur a bien été archivé en base
    async with async_session() as session:
        stmt = (
            select(ConversationMessage)
            .where(
                ConversationMessage.conversation_id == conv_id,
                ConversationMessage.content == "Est-ce que le patron est disponible ?",
            )
        )
        msg = (await session.execute(stmt)).scalar_one_or_none()
        assert msg is not None
        assert msg.role == "user"

"""
Tests Sprint A1 : Photos de produits (upload, diffusion publique, image_url en CRUD).
Section Priorité 1 du plan Photos Produits & Personnalisation IA.
"""

import io
import json
import re
import uuid

import pytest

from app.core.security import create_access_token, hash_password
from app.db.session import async_session
from app.models import AgentConfiguration, Business, Product, User, UserRole
from app.tools.executor import execute_tool


@pytest.mark.asyncio
async def test_product_crud_with_image_url(client, two_businesses):
    """Vérifie que image_url est bien persistée à la création et à la mise à jour."""
    token_a = two_businesses["token_a"]

    # Création avec image_url
    resp = await client.post(
        "/api/products",
        json={
            "name": "Écouteurs Bluetooth Pro",
            "category": "accessoire",
            "price": 12000,
            "stock_quantity": 5,
            "image_url": "https://cdn.example.com/photos/ecouteurs.jpg",
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["image_url"] == "https://cdn.example.com/photos/ecouteurs.jpg"

    product_id = data["id"]

    # Mise à jour de l'image
    resp2 = await client.patch(
        f"/api/products/{product_id}",
        json={"image_url": "https://cdn.example.com/photos/ecouteurs-v2.jpg"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["image_url"] == "https://cdn.example.com/photos/ecouteurs-v2.jpg"


@pytest.mark.asyncio
async def test_product_image_url_validation(client, two_businesses):
    """Rejette une image_url non-https (ex: ftp:// ou http://)."""
    token_a = two_businesses["token_a"]

    # Rejet FTP
    resp_ftp = await client.post(
        "/api/products",
        json={
            "name": "Produit Invalide FTP",
            "category": "test",
            "price": 1000,
            "stock_quantity": 1,
            "image_url": "ftp://mauvais-protocole.com/img.jpg",
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp_ftp.status_code == 422

    # Rejet HTTP non-sécurisé (HTTPS uniquement requis par le sprint)
    resp_http = await client.post(
        "/api/products",
        json={
            "name": "Produit Invalide HTTP",
            "category": "test",
            "price": 1000,
            "stock_quantity": 1,
            "image_url": "http://insecure.example.com/img.jpg",
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp_http.status_code == 422


@pytest.mark.asyncio
async def test_upload_product_image_success(client, two_businesses):
    """Upload d'une image JPEG valide, vérifie le 200 et l'URL retournée."""
    token_a = two_businesses["token_a"]

    # Petit contenu JPEG factice (les magic bytes ne sont pas vérifiés dans ce sprint)
    fake_jpeg = io.BytesIO(b"\xff\xd8\xff\xe0" + b"0" * 100)

    resp = await client.post(
        "/api/products/upload-image",
        files={"file": ("photo.jpg", fake_jpeg, "image/jpeg")},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "image_url" in data
    assert data["image_url"].startswith("http")
    assert data["filename"].endswith(".jpg")


@pytest.mark.asyncio
async def test_upload_product_image_rejects_bad_type(client, two_businesses):
    """Rejette un fichier non-image (ex: .txt)."""
    token_a = two_businesses["token_a"]

    fake_txt = io.BytesIO(b"ceci n'est pas une image")

    resp = await client.post(
        "/api/products/upload-image",
        files={"file": ("notes.txt", fake_txt, "text/plain")},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_product_image_rejects_oversized(client, two_businesses):
    """Rejette un fichier de plus de 5 Mo."""
    token_a = two_businesses["token_a"]

    oversized = io.BytesIO(b"0" * (5 * 1024 * 1024 + 1))

    resp = await client.post(
        "/api/products/upload-image",
        files={"file": ("gros.jpg", oversized, "image/jpeg")},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_product_image_requires_auth(client):
    """Rejette l'upload sans token JWT valide."""
    fake_jpeg = io.BytesIO(b"\xff\xd8\xff\xe0" + b"0" * 100)

    resp = await client.post(
        "/api/products/upload-image",
        files={"file": ("photo.jpg", fake_jpeg, "image/jpeg")},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_product_image_serves_file(client, two_businesses):
    """Après upload, l'image est servie publiquement avec le bon Content-Type."""
    token_a = two_businesses["token_a"]
    fake_jpeg = io.BytesIO(b"\xff\xd8\xff\xe0" + b"0" * 100)

    upload_resp = await client.post(
        "/api/products/upload-image",
        files={"file": ("photo.jpg", fake_jpeg, "image/jpeg")},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    filename = upload_resp.json()["filename"]

    # Aucune authentification nécessaire : Meta doit pouvoir la télécharger
    get_resp = await client.get(f"/api/products/images/{filename}")
    assert get_resp.status_code == 200
    assert get_resp.headers["content-type"] == "image/jpeg"


@pytest.mark.asyncio
async def test_get_product_image_path_traversal_blocked(client):
    """Une tentative de path traversal ne doit jamais sortir de storage/products."""
    resp = await client.get("/api/products/images/..%2F..%2Fapp%2Fmain.py")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_product_image_not_found(client):
    """Un nom de fichier inexistant renvoie 404."""
    resp = await client.get("/api/products/images/inexistant-999.jpg")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_tool_send_product_photo_returns_payload(two_businesses):
    """Vérifie que le tool renvoie le marqueur avec l'URL exacte de la photo."""
    biz_a = two_businesses["biz_a"]

    async with async_session() as session:
        product = Product(
            business_id=biz_a.id,
            name="Casque Bluetooth Premium",
            category="accessoire",
            price=18000,
            stock_quantity=4,
            image_url="https://cdn.example.com/photos/casque.jpg",
        )
        session.add(product)
        await session.commit()
        await session.refresh(product)

        result = await execute_tool(
            session=session,
            business_id=biz_a.id,
            customer_id=uuid.uuid4(),
            tool_name="send_product_photo",
            arguments={"product_name": "Casque Bluetooth"},
        )

        assert "__PHOTO_PAYLOAD__" in result
        assert "__END__" in result

        match = re.search(r"__PHOTO_PAYLOAD__(.*?)__END__", result, re.DOTALL)
        assert match is not None
        payload = json.loads(match.group(1))
        assert payload["url"] == "https://cdn.example.com/photos/casque.jpg"
        assert "Casque Bluetooth Premium" in payload["caption"]
        assert "18000" in payload["caption"] or "18 000" in payload["caption"]


@pytest.mark.asyncio
async def test_tool_send_product_photo_no_image(two_businesses):
    """Vérifie qu'un produit sans image renvoie un message explicite."""
    biz_a = two_businesses["biz_a"]

    async with async_session() as session:
        product = Product(
            business_id=biz_a.id,
            name="Sac à Dos Sport",
            category="mode",
            price=9000,
            stock_quantity=2,
            image_url=None,
        )
        session.add(product)
        await session.commit()

        result = await execute_tool(
            session=session,
            business_id=biz_a.id,
            customer_id=uuid.uuid4(),
            tool_name="send_product_photo",
            arguments={"product_name": "Sac à Dos Sport"},
        )

        assert "__PHOTO_PAYLOAD__" not in result
        assert "n'a pas encore de photo" in result


@pytest.mark.asyncio
async def test_tool_send_product_photo_not_found(two_businesses):
    """Vérifie qu'un produit inexistant renvoie un échec clair."""
    biz_a = two_businesses["biz_a"]

    async with async_session() as session:
        result = await execute_tool(
            session=session,
            business_id=biz_a.id,
            customer_id=uuid.uuid4(),
            tool_name="send_product_photo",
            arguments={"product_name": "Produit Totalement Inexistant XYZ"},
        )

        assert "__PHOTO_PAYLOAD__" not in result
        assert "introuvable" in result.lower()


@pytest.mark.asyncio
async def test_tool_send_product_photo_isolation(two_businesses):
    """Vérifie que les photos restent isolées entre boutiques."""
    biz_a = two_businesses["biz_a"]
    biz_b = two_businesses["biz_b"]

    async with async_session() as session:
        product_b = Product(
            business_id=biz_b.id,
            name="Montre Connectée Exclusive",
            category="accessoire",
            price=45000,
            stock_quantity=3,
            image_url="https://cdn.example.com/photos/montre.jpg",
        )
        session.add(product_b)
        await session.commit()

        result = await execute_tool(
            session=session,
            business_id=biz_a.id,
            customer_id=uuid.uuid4(),
            tool_name="send_product_photo",
            arguments={"product_name": "Montre Connectée Exclusive"},
        )

        assert "__PHOTO_PAYLOAD__" not in result, (
            "Faille de sécurité : le tool send_product_photo a trouvé un produit "
            "du Business B depuis le contexte du Business A."
        )
        assert "introuvable" in result.lower()


# ============================================================================
# Tests Sprint A3 : Configuration & Personnalisation de l'Agent IA (Backend)
# ============================================================================


@pytest.mark.asyncio
async def test_get_agent_config_default(client, two_businesses):
    """GET retourne les valeurs par défaut si aucune configuration n'a été enregistrée."""
    token_a = two_businesses["token_a"]

    resp = await client.get(
        "/api/dashboard/agent/config",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_name"] == "Assistant"
    assert data["tone"] == "chaleureux"
    assert data["default_language"] == "fr"
    assert data["custom_rules"] is None
    assert data["welcome_message"] is None
    assert data["enabled"] is True


@pytest.mark.asyncio
async def test_get_agent_config_requires_auth(client):
    """GET sans authentification renvoie 401."""
    resp = await client.get("/api/dashboard/agent/config")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_agent_config_admin_success(client, two_businesses):
    """Un administrateur peut mettre à jour la configuration de son agent."""
    token_a = two_businesses["token_a"]

    update_payload = {
        "agent_name": "MaliBot Alpha",
        "tone": "formel",
        "default_language": "bm",
        "custom_rules": "Toujours préciser que la livraison à Kati a un délai de 24h.",
        "welcome_message": "I bisimila boutique kɔnɔ !",
        "enabled": True,
    }

    put_resp = await client.put(
        "/api/dashboard/agent/config",
        json=update_payload,
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert put_resp.status_code == 200
    data = put_resp.json()
    assert data["agent_name"] == "MaliBot Alpha"
    assert data["tone"] == "formel"
    assert data["default_language"] == "bm"
    assert data["custom_rules"] == update_payload["custom_rules"]
    assert data["welcome_message"] == update_payload["welcome_message"]
    assert data["enabled"] is True

    # Vérification que le GET retourne bien les nouvelles valeurs
    get_resp = await client.get(
        "/api/dashboard/agent/config",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["agent_name"] == "MaliBot Alpha"
    assert get_resp.json()["tone"] == "formel"


@pytest.mark.asyncio
async def test_update_agent_config_unauthenticated_401(client):
    """PUT sans authentification renvoie 401."""
    resp = await client.put(
        "/api/dashboard/agent/config",
        json={"agent_name": "PirateBot"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_agent_config_non_admin_403(client, two_businesses):
    """Un utilisateur non-admin (vendeur ou opérateur) se voit refuser l'accès avec 403."""
    biz_a = two_businesses["biz_a"]

    # Créer un vendeur pour la boutique A
    async with async_session() as session:
        vendeur = User(
            email=f"vendeur_{uuid.uuid4().hex[:6]}@alpha.ml",
            password_hash=hash_password("PassVendeur123!"),
            first_name="Vendeur",
            last_name="Test",
            role=UserRole.VENDEUR,
            business_id=biz_a.id,
        )
        session.add(vendeur)
        await session.commit()
        await session.refresh(vendeur)

    vendeur_token = create_access_token(user_id=str(vendeur.id), business_id=str(biz_a.id))

    resp = await client.put(
        "/api/dashboard/agent/config",
        json={"agent_name": "VendeurCustomName"},
        headers={"Authorization": f"Bearer {vendeur_token}"},
    )
    assert resp.status_code == 403
    assert "administrateur" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_agent_config_validation_tone(client, two_businesses):
    """Rejette un ton invalide (autorisés : chaleureux, formel, concis)."""
    token_a = two_businesses["token_a"]

    resp = await client.put(
        "/api/dashboard/agent/config",
        json={"tone": "agressif"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_agent_config_validation_language(client, two_businesses):
    """Rejette une langue invalide (autorisées : fr, bm)."""
    token_a = two_businesses["token_a"]

    resp = await client.put(
        "/api/dashboard/agent/config",
        json={"default_language": "en"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_agent_config_validation_rules_length(client, two_businesses):
    """Rejette des règles métier dépassant 2000 caractères."""
    token_a = two_businesses["token_a"]

    resp = await client.put(
        "/api/dashboard/agent/config",
        json={"custom_rules": "A" * 2001},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_agent_config_multi_tenant_isolation(client, two_businesses):
    """Vérifie l'étanchéité stricte : la config de la boutique A n'impacte pas la boutique B."""
    token_a = two_businesses["token_a"]
    token_b = two_businesses["token_b"]

    # Boutique A configure son agent
    await client.put(
        "/api/dashboard/agent/config",
        json={"agent_name": "AlphaExclusiveAgent", "tone": "concis"},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    # Boutique B doit toujours avoir sa configuration propre (défaut ici)
    resp_b = await client.get(
        "/api/dashboard/agent/config",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_b.status_code == 200
    data_b = resp_b.json()
    assert data_b["agent_name"] == "Assistant"
    assert data_b["tone"] == "chaleureux"
    assert data_b["agent_name"] != "AlphaExclusiveAgent"


@pytest.mark.asyncio
async def test_business_agent_config_orm_relationship(two_businesses):
    """Vérifie que la relation ORM Business.agent_config et le backref fonctionnent."""
    biz_a = two_businesses["biz_a"]

    async with async_session() as session:
        # Créer une AgentConfiguration associée à biz_a
        config = AgentConfiguration(
            business_id=biz_a.id,
            agent_name="RelTestBot",
            tone="chaleureux",
            default_language="fr",
            enabled=True,
        )
        session.add(config)
        await session.commit()

        # Recharger Business avec son agent_config
        reloaded_biz = await session.get(Business, biz_a.id)
        assert reloaded_biz is not None
        assert reloaded_biz.agent_config is not None
        assert reloaded_biz.agent_config.agent_name == "RelTestBot"
        assert reloaded_biz.agent_config.business.id == biz_a.id


@pytest.mark.asyncio
async def test_orchestrator_injects_custom_rules_and_tone(two_businesses):
    """Vérifie que le prompt système adopte le nom, le ton et les règles propres de la boutique."""
    from app.agent.orchestrator import build_system_prompt, run_agent_turn
    from app.models import AgentConfiguration

    # 1. Test direct de build_system_prompt
    prompt_custom = build_system_prompt(
        business_name="Djoliba Confection",
        target_lang="fr",
        agent_name="Djoliba Bot",
        tone="concis",
        custom_rules="Délai de couture de 5 jours minimum. Aucun remboursement sur mesure.",
    )
    assert "Tu es Djoliba Bot" in prompt_custom
    assert "Djoliba Confection" in prompt_custom
    assert "ultra-concis, direct et efficace" in prompt_custom
    assert "Délai de couture de 5 jours minimum" in prompt_custom

    # Test avec ton formel
    prompt_formel = build_system_prompt(
        business_name="Bijouterie Or",
        target_lang="fr",
        agent_name="Kaba Assistant",
        tone="formel",
    )
    assert "Tu es Kaba Assistant" in prompt_formel
    assert "professionnel, poli, cérémonieux" in prompt_formel

    # Test avec bambara
    prompt_bm = build_system_prompt(
        business_name="Sogoniko Marché",
        target_lang="bm",
        agent_name="Moussa AI",
        tone="chaleureux",
    )
    assert "Tu es Moussa AI" in prompt_bm
    assert "BAMBARA / BAMANANKAN OBLIGATOIRE" in prompt_bm

    # 2. Test d'exécution dans run_agent_turn avec AgentConfiguration persistée
    biz_a = two_businesses["biz_a"]
    async with async_session() as session:
        cfg = AgentConfiguration(
            business_id=biz_a.id,
            agent_name="AlphaCustomBot",
            tone="concis",
            custom_rules="Livraison uniquement sur la Rive Gauche.",
            enabled=True,
        )
        session.add(cfg)
        await session.commit()

        # Invocation de run_agent_turn
        reply = await run_agent_turn(
            session=session,
            business_id=biz_a.id,
            user_message="Bonjour, quels sont vos produits ?",
            customer_phone_number="22370009988",
        )
        assert reply is not None
        assert len(reply) > 0


@pytest.mark.asyncio
async def test_agent_disabled_toggle(two_businesses):
    """Vérifie que la désactivation de l'IA suspend les réponses automatiques et passe en intervention humaine."""
    from app.agent.orchestrator import run_agent_turn
    from app.models import AgentConfiguration, Conversation, ConversationMessage
    from sqlalchemy import select

    biz_b = two_businesses["biz_b"]
    phone = f"2237{uuid.uuid4().hex[:7]}"

    async with async_session() as session:
        # Créer une AgentConfiguration désactivée (enabled=False)
        cfg = AgentConfiguration(
            business_id=biz_b.id,
            agent_name="BetaBot",
            tone="chaleureux",
            default_language="fr",
            enabled=False,
        )
        session.add(cfg)
        await session.commit()

        # Le client envoie un message alors que l'agent est désactivé
        reply = await run_agent_turn(
            session=session,
            business_id=biz_b.id,
            user_message="Bonjour, je souhaite commander un article svp",
            customer_phone_number=phone,
        )

        # Vérifier que le message de pause/responsable est retourné
        assert "pause" in reply.lower() or "désactivé" in reply.lower()
        assert "responsable" in reply.lower()

        # Vérifier que la conversation a été enregistrée avec le statut needs_human
        stmt_conv = (
            select(Conversation)
            .where(Conversation.business_id == biz_b.id)
            .order_by(Conversation.updated_at.desc())
        )
        conv = (await session.execute(stmt_conv)).scalars().first()
        assert conv is not None
        assert conv.status == "needs_human"

        # Vérifier que les messages de l'utilisateur et de pause sont archivés
        stmt_msgs = (
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conv.id)
            .order_by(ConversationMessage.created_at.asc())
        )
        msgs = (await session.execute(stmt_msgs)).scalars().all()
        assert len(msgs) >= 2
        assert msgs[-2].role == "user"
        assert "je souhaite commander" in msgs[-2].content
        assert msgs[-1].role == "assistant"
        assert "pause" in msgs[-1].content.lower() or "désactivé" in msgs[-1].content.lower()

        # Test également en Bambara
        phone_bm = f"2237{uuid.uuid4().hex[:7]}"
        reply_bm = await run_agent_turn(
            session=session,
            business_id=biz_b.id,
            user_message="I ni ce, n b'a fɛ ka san",
            customer_phone_number=phone_bm,
        )
        assert "lafiya" in reply_bm.lower() or "kuntigi" in reply_bm.lower()
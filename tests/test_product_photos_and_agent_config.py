"""
Tests Sprint A1 : Photos de produits (upload, diffusion publique, image_url en CRUD).
Section Priorité 1 du plan Photos Produits & Personnalisation IA.
"""

import io
import json
import re
import uuid

import pytest

from app.db.session import async_session
from app.models import Product
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
    """Rejette une image_url qui n'est pas une URL http(s) valide."""
    token_a = two_businesses["token_a"]

    resp = await client.post(
        "/api/products",
        json={
            "name": "Produit Invalide",
            "category": "test",
            "price": 1000,
            "stock_quantity": 1,
            "image_url": "ftp://mauvais-protocole.com/img.jpg",
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 422


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
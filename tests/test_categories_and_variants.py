import uuid
import pytest
from unittest.mock import AsyncMock, patch

from app.db.session import async_session
from app.models import Category, Product, ProductVariant, StockMovement
from app.models.stock_movement import StockMovementType
from app.services.stock import record_stock_movement
from app.tools.executor import execute_tool


@pytest.mark.asyncio
async def test_category_crud_and_isolation(client, two_businesses):
    tb = two_businesses
    headers_a = {"Authorization": f"Bearer {tb['token_a']}"}
    headers_b = {"Authorization": f"Bearer {tb['token_b']}"}

    # 1. Création d'une catégorie pour Boutique A
    payload_a = {
        "name": "Smartphones & Tablettes",
        "description": "Appareils mobiles et accessoires",
    }
    res_create = await client.post("/api/categories", json=payload_a, headers=headers_a)
    assert res_create.status_code == 201, res_create.text
    cat_data = res_create.json()
    cat_id = cat_data["id"]
    assert cat_data["name"] == "Smartphones & Tablettes"
    assert cat_data["product_count"] == 0

    # 2. Liste des catégories pour Boutique A
    res_list_a = await client.get("/api/categories", headers=headers_a)
    assert res_list_a.status_code == 200
    cats_a = res_list_a.json()
    assert any(c["id"] == cat_id for c in cats_a)

    # 3. Isolation multi-tenant : Boutique B ne voit pas la catégorie de Boutique A
    res_list_b = await client.get("/api/categories", headers=headers_b)
    assert res_list_b.status_code == 200
    cats_b = res_list_b.json()
    assert not any(c["id"] == cat_id for c in cats_b)

    # 4. Modification de la catégorie par Boutique A
    res_update = await client.put(
        f"/api/categories/{cat_id}",
        json={"name": "Smartphones & Gadgets", "description": "Modifié"},
        headers=headers_a,
    )
    assert res_update.status_code == 200
    assert res_update.json()["name"] == "Smartphones & Gadgets"

    # 5. Tentative de modification illégitime par Boutique B -> 404
    res_update_b = await client.put(
        f"/api/categories/{cat_id}",
        json={"name": "Piratage"},
        headers=headers_b,
    )
    assert res_update_b.status_code == 404

    # 6. Suppression par Boutique A
    res_delete = await client.delete(f"/api/categories/{cat_id}", headers=headers_a)
    assert res_delete.status_code == 200


@pytest.mark.asyncio
async def test_product_with_variants_and_stock(client, two_businesses):
    tb = two_businesses
    headers_a = {"Authorization": f"Bearer {tb['token_a']}"}

    # 1. Créer une catégorie
    res_cat = await client.post(
        "/api/categories",
        json={"name": "Vêtements", "description": "Mode et textile"},
        headers=headers_a,
    )
    assert res_cat.status_code == 201
    cat_id = res_cat.json()["id"]

    # 2. Créer un produit avec déclinaisons (variantes)
    product_payload = {
        "name": "T-shirt Coton Bio Mali",
        "category_id": cat_id,
        "category": "Vêtements",
        "description": "T-shirt 100% coton de Bamako",
        "price": 8500,
        "stock_quantity": 0,  # Déterminé automatiquement par les variantes
        "low_stock_threshold": 3,
        "variants": [
            {
                "name": "Taille",
                "value": "M",
                "price": 8500,
                "stock_quantity": 12,
                "sku": "TSH-MALI-M",
            },
            {
                "name": "Taille",
                "value": "XL",
                "price": 9500,
                "stock_quantity": 8,
                "sku": "TSH-MALI-XL",
            },
        ],
    }

    res_prod = await client.post("/api/products", json=product_payload, headers=headers_a)
    assert res_prod.status_code == 200, res_prod.text
    prod_data = res_prod.json()
    prod_id = prod_data["id"]
    assert prod_data["name"] == "T-shirt Coton Bio Mali"
    assert prod_data["category"] == "Vêtements"
    assert len(prod_data["variants"]) == 2
    assert prod_data["stock_quantity"] == 20  # 12 + 8

    # 3. Tool check_stock avec et sans variante
    async with async_session() as session:
        # Stock global
        stock_msg = await execute_tool(
            session=session,
            business_id=tb["biz_a"].id,
            customer_id=uuid.uuid4(),
            tool_name="check_stock",
            arguments={"product_name": "T-shirt Coton Bio Mali"},
        )
        assert "total: 20" in stock_msg
        assert "Taille: M" in stock_msg
        assert "Taille: XL" in stock_msg

        # Stock pour la variante XL
        stock_xl = await execute_tool(
            session=session,
            business_id=tb["biz_a"].id,
            customer_id=uuid.uuid4(),
            tool_name="check_stock",
            arguments={"product_name": "T-shirt Coton Bio Mali", "variant": "XL"},
        )
        assert "8 unité(s)" in stock_xl
        assert "9500 FCFA" in stock_xl


@pytest.mark.asyncio
async def test_search_knowledge_base_with_question_param(two_businesses):
    tb = two_businesses

    with patch("app.services.knowledge.get_llm_provider") as mock_provider_func:
        mock_provider = AsyncMock()
        mock_provider.embed.return_value = [[0.05] * 768]
        mock_provider_func.return_value = mock_provider

        # Test execute_tool avec argument 'question'
        async with async_session() as session:
            res_tool = await execute_tool(
                session=session,
                business_id=tb["biz_a"].id,
                customer_id=uuid.uuid4(),
                tool_name="search_knowledge_base",
                arguments={"question": "Quels sont vos horaires d'ouverture ?"},
            )
            assert isinstance(res_tool, str)


@pytest.mark.asyncio
async def test_create_order_with_variant_flow(client, two_businesses):
    tb = two_businesses
    headers_a = {"Authorization": f"Bearer {tb['token_a']}"}

    # 1. Créer un produit avec variantes
    prod_payload = {
        "name": "Bazin Riche Getzner",
        "category": "Tissus",
        "price": 45000,
        "stock_quantity": 0,
        "variants": [
            {"name": "Couleur", "value": "Bleu Nuit", "price": 45000, "stock_quantity": 5},
            {"name": "Couleur", "value": "Blanc Royal", "price": 50000, "stock_quantity": 3},
        ],
    }
    res_p = await client.post("/api/products", json=prod_payload, headers=headers_a)
    assert res_p.status_code == 200

    # 2. Exécuter create_order sans préciser la déclinaison -> demande de précision
    async with async_session() as session:
        cust_id = tb["order_a"].customer_id
        ambiguous_res = await execute_tool(
            session=session,
            business_id=tb["biz_a"].id,
            customer_id=cust_id,
            tool_name="create_order",
            arguments={
                "items": [{"product_name": "Bazin Riche Getzner", "quantity": 1}],
                "delivery_address": "ACI 2000",
                "delivery_fee": 1500,
            },
        )
        assert "déclinaisons" in ambiguous_res.lower()
        assert "bleu nuit" in ambiguous_res.lower()

        # 3. Exécuter create_order avec la variante choisie
        success_res = await execute_tool(
            session=session,
            business_id=tb["biz_a"].id,
            customer_id=cust_id,
            tool_name="create_order",
            arguments={
                "items": [
                    {
                        "product_name": "Bazin Riche Getzner",
                        "variant": "Blanc Royal",
                        "quantity": 2,
                    }
                ],
                "delivery_address": "ACI 2000",
                "delivery_fee": 1500,
            },
        )
        assert "enregistrée" in success_res.lower()
        assert "Blanc Royal" in success_res
        # Total : 2 * 50000 + 1500 = 101500 FCFA
        assert "101500" in success_res or "101 500" in success_res

        # 4. Vérifier que le stock restant de la variante Blanc Royal est 1 (3 - 2)
        stock_blanc = await execute_tool(
            session=session,
            business_id=tb["biz_a"].id,
            customer_id=uuid.uuid4(),
            tool_name="check_stock",
            arguments={"product_name": "Bazin Riche Getzner", "variant": "Blanc Royal"},
        )
        assert "1 unité(s)" in stock_blanc


@pytest.mark.asyncio
async def test_delivered_order_invoice_is_marked_paid(client, two_businesses):
    tb = two_businesses
    headers_a = {"Authorization": f"Bearer {tb['token_a']}"}
    order_a = tb["order_a"]

    # 1. Marquer la commande comme livrée via l'API dashboard
    res_status = await client.patch(
        f"/api/orders/{order_a.id}/status",
        json={"status": "delivered"},
        headers=headers_a,
    )
    assert res_status.status_code == 200

    # 2. Générer la facture via le tool (comme quand le client WhatsApp demande sa facture après livraison)
    async with async_session() as session:
        inv_res = await execute_tool(
            session=session,
            business_id=tb["biz_a"].id,
            customer_id=order_a.customer_id,
            tool_name="generate_invoice",
            arguments={"order_ref": str(order_a.id)[:8]},
        )
        # Vérifie que le statut n'est PLUS "En attente de paiement" mais "Payée / Acquittée"
        assert "Payée / Acquittée" in inv_res
        assert "En attente de paiement" not in inv_res

    # 3. Télécharger le PDF via /invoices/{ref} et vérifier qu'il renvoie 200
    short_id = str(order_a.id)[:8].upper()
    res_pdf = await client.get(f"/invoices/FAC-2026-{short_id}")
    if res_pdf.status_code != 200:
        # Essayer avec l'année en cours
        import datetime
        yr = datetime.datetime.now().year
        res_pdf = await client.get(f"/invoices/FAC-{yr}-{short_id}")
    assert res_pdf.status_code == 200
    assert res_pdf.headers["content-type"] == "application/pdf"



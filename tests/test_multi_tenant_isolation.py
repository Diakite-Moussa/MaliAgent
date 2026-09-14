"""
Tests de sécurité : Isolation stricte des données entre boutiques (Multi-Tenant).
Conforme aux exigences de la section 18.3 et 25 du cahier des charges :
Un commerçant (Business A) ne doit JAMAIS pouvoir lire ou modifier les données
d'un autre commerçant (Business B).
"""

import pytest
from app.db.session import async_session
from app.tools.executor import execute_tool


@pytest.mark.asyncio
async def test_products_isolation(client, two_businesses):
    """Vérifie que la liste des produits est strictement cloisonnée par business_id."""
    token_a = two_businesses["token_a"]
    token_b = two_businesses["token_b"]
    prod_a_name = two_businesses["prod_a"].name
    prod_b_name = two_businesses["prod_b"].name

    # 1. Requête avec le token du Business A
    resp_a = await client.get("/api/products", headers={"Authorization": f"Bearer {token_a}"})
    assert resp_a.status_code == 200
    prods_a = resp_a.json()
    names_a = [p["name"] for p in prods_a]

    assert prod_a_name in names_a
    assert prod_b_name not in names_a, "Faille de sécurité : Business A a accès au produit du Business B !"

    # 2. Requête avec le token du Business B
    resp_b = await client.get("/api/products", headers={"Authorization": f"Bearer {token_b}"})
    assert resp_b.status_code == 200
    prods_b = resp_b.json()
    names_b = [p["name"] for p in prods_b]

    assert prod_b_name in names_b
    assert prod_a_name not in names_b, "Faille de sécurité : Business B a accès au produit du Business A !"


@pytest.mark.asyncio
async def test_orders_isolation(client, two_businesses):
    """Vérifie que la liste des commandes est strictement cloisonnée par business_id."""
    token_a = two_businesses["token_a"]
    token_b = two_businesses["token_b"]
    order_a_id = str(two_businesses["order_a"].id)
    order_b_id = str(two_businesses["order_b"].id)

    # 1. Business A consulte ses commandes
    resp_a = await client.get("/api/orders", headers={"Authorization": f"Bearer {token_a}"})
    assert resp_a.status_code == 200
    orders_a_ids = [o["id"] for o in resp_a.json()["orders"]]

    assert order_a_id in orders_a_ids
    assert order_b_id not in orders_a_ids, "Faille de sécurité : Business A voit la commande du Business B !"

    # 2. Business B consulte ses commandes
    resp_b = await client.get("/api/orders", headers={"Authorization": f"Bearer {token_b}"})
    assert resp_b.status_code == 200
    orders_b_ids = [o["id"] for o in resp_b.json()["orders"]]

    assert order_b_id in orders_b_ids
    assert order_a_id not in orders_b_ids, "Faille de sécurité : Business B voit la commande du Business A !"


@pytest.mark.asyncio
async def test_cross_tenant_order_modification_prevented(client, two_businesses):
    """
    Vérifie qu'un utilisateur du Business A ne peut pas modifier le statut
    d'une commande appartenant au Business B (doit renvoyer 404).
    """
    token_a = two_businesses["token_a"]
    order_b_id = str(two_businesses["order_b"].id)

    resp = await client.patch(
        f"/api/orders/{order_b_id}/status",
        json={"status": "confirmed"},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    # Doit renvoyer 404 car la commande n'existe pas dans le scope de Business A
    assert resp.status_code == 404, f"Attendu 404, reçu {resp.status_code}"


@pytest.mark.asyncio
async def test_tools_multi_tenant_isolation(two_businesses):
    """
    Vérifie que les tools de l'agent IA exécutés pour le Business A
    ne voient que les données du Business A et jamais celles du Business B.
    """
    biz_a = two_businesses["biz_a"]
    client_a = two_businesses["user_a"]

    async with async_session() as session:
        result = await execute_tool(
            session=session,
            business_id=biz_a.id,
            customer_id=client_a.id,
            tool_name="search_products",
            arguments={"query": "Exclusif"},
        )

        assert "Produit Exclusif Alpha" in result
        assert "Produit Exclusif Beta" not in result, (
            "Faille tool calling : l'agent de Business A a retourné un produit de Business B !"
        )

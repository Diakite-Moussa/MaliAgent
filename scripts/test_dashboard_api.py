"""
Test automatisé des endpoints REST du Dashboard commerçant.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from sqlalchemy import select

from app.core.asyncio_compat import use_selector_event_loop_on_windows
from app.core.security import create_access_token
from app.db.session import async_session
from app.main import app
from app.models import Business

use_selector_event_loop_on_windows()


async def main():
    print("=== TEST DES ENDPOINTS DASHBOARD FASTAPI (AVEC JWT) ===\n")

    async with async_session() as s:
        b = (await s.execute(select(Business))).scalars().first()
        biz_id = str(b.id)

    token = create_access_token("test-user-id", biz_id)
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 0. Test sans token -> 401
        print("0. Test sécurité sans token -> 401 attendu...")
        r_unauth = await client.get("/api/dashboard/stats")
        assert r_unauth.status_code == 401
        print("   OK (rejeté 401)")

        # 1. Test /api/dashboard/stats
        print("\n1. Test GET /api/dashboard/stats...")
        resp_stats = await client.get("/api/dashboard/stats", headers=headers)
        print(f"   Status : {resp_stats.status_code}")
        assert resp_stats.status_code == 200
        stats = resp_stats.json()
        print(f"   Commerce : {stats['business']['name']}")
        print(f"   KPIs : {stats['kpis']}")
        print(f"   Commandes récentes : {len(stats['recent_orders'])}")

        # 2. Test GET /api/orders
        print("\n2. Test GET /api/orders...")
        resp_orders = await client.get("/api/orders", headers=headers)
        print(f"   Status : {resp_orders.status_code}")
        assert resp_orders.status_code == 200
        orders_data = resp_orders.json()
        orders = orders_data["orders"]
        print(f"   Total commandes : {len(orders)}")
        assert len(orders) > 0

        first_order = orders[0]
        order_id = first_order["id"]
        print(f"   Commande #{first_order['short_id']} - Statut actuel : {first_order['status']}")

        # 3. Test PATCH /api/orders/{order_id}/status -> confirmed
        print(f"\n3. Test PATCH /api/orders/{order_id}/status vers 'confirmed'...")
        resp_patch_order = await client.patch(
            f"/api/orders/{order_id}/status",
            json={"status": "confirmed"},
            headers=headers,
        )
        print(f"   Status : {resp_patch_order.status_code}")
        assert resp_patch_order.status_code == 200
        updated_order = resp_patch_order.json()
        print(f"   Nouveau statut : {updated_order['status']}")
        assert updated_order["status"] == "confirmed"

        # 4. Test GET /api/products
        print("\n4. Test GET /api/products...")
        resp_prods = await client.get("/api/products", headers=headers)
        print(f"   Status : {resp_prods.status_code}")
        assert resp_prods.status_code == 200
        prods = resp_prods.json()
        print(f"   Nombre de produits : {len(prods)}")
        assert len(prods) > 0

        first_prod = prods[0]
        prod_id = first_prod["id"]
        old_stock = first_prod["stock_quantity"]
        print(f"   Produit : {first_prod['name']} (Stock actuel : {old_stock})")

        # 5. Test PATCH /api/products/{prod_id} (réapprovisionnement +5)
        print(f"\n5. Test PATCH /api/products/{prod_id} mise à jour stock...")
        new_stock = old_stock + 5
        resp_patch_prod = await client.patch(
            f"/api/products/{prod_id}",
            json={"stock_quantity": new_stock},
            headers=headers,
        )
        print(f"   Status : {resp_patch_prod.status_code}")
        assert resp_patch_prod.status_code == 200
        updated_prod = resp_patch_prod.json()
        print(f"   Nouveau stock en base : {updated_prod['stock_quantity']}")
        assert updated_prod["stock_quantity"] == new_stock

        # 6. Test GET /api/dashboard/handoffs
        print("\n6. Test GET /api/dashboard/handoffs...")
        resp_handoffs = await client.get("/api/dashboard/handoffs", headers=headers)
        print(f"   Status : {resp_handoffs.status_code}")
        assert resp_handoffs.status_code == 200
        handoffs_data = resp_handoffs.json()
        print(f"   Handoffs en attente : {handoffs_data['total']}")

        # 7. Test POST /api/dashboard/handoffs/{id}/resolve (si au moins un handoff existe)
        if handoffs_data["total"] > 0:
            handoff_id = handoffs_data["handoffs"][0]["id"]
            print(f"\n7. Test POST /api/dashboard/handoffs/{handoff_id}/resolve...")
            resp_resolve = await client.post(f"/api/dashboard/handoffs/{handoff_id}/resolve", headers=headers)
            print(f"   Status : {resp_resolve.status_code}")
            assert resp_resolve.status_code == 200
        else:
            print("\n7. Aucun handoff en attente à résoudre — test ignoré.")

        # 8. Test GET /api/orders/export-csv
        print("\n8. Test GET /api/orders/export-csv...")
        resp_csv = await client.get("/api/orders/export-csv", headers=headers)
        print(f"   Status : {resp_csv.status_code}")
        assert resp_csv.status_code == 200
        assert resp_csv.headers["content-type"].startswith("text/csv")
        print(f"   Taille du CSV : {len(resp_csv.content)} octets")

    print("\n=== TOUS LES TESTS DE L'API DASHBOARD SONT VALIDÉS AVEC SUCCÈS ! ===")


if __name__ == "__main__":
    asyncio.run(main())

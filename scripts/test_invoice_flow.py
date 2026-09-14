"""
Test automatisé du Sprint 5 : Facturation PDF.
Vérifie la génération du PDF, l'enregistrement en base, et la route de téléchargement.
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import select

from app.core.asyncio_compat import use_selector_event_loop_on_windows
from app.db.session import async_session
from app.main import app
from app.models import Business, Customer, Invoice, Order
from app.tools.executor import execute_tool

use_selector_event_loop_on_windows()


async def main():
    print("=== DÉBUT DU TEST DU SPRINT 5 (FACTURATION PDF) ===\n")

    async with async_session() as session:
        # 1. Récupération du Business et d'un Customer ayant une commande
        stmt = select(Business).where(Business.whatsapp_phone_number == "15556640413")
        business = (await session.execute(stmt)).scalar_one()

        stmt_order = (
            select(Order)
            .where(Order.business_id == business.id)
            .order_by(Order.created_at.desc())
            .limit(1)
        )
        order = (await session.execute(stmt_order)).scalar_one_or_none()
        assert order is not None, "Une commande doit exister en base (issue des tests précédents)"
        customer_id = order.customer_id
        short_order_id = str(order.id)[:8].upper()

        print(f"1. Commande sélectionnée : #{short_order_id} (Client : {customer_id})")

        # 2. Exécution du tool generate_invoice
        print("\n2. Exécution du tool generate_invoice...")
        res = await execute_tool(
            session,
            business.id,
            customer_id,
            "generate_invoice",
            {"order_ref": short_order_id},
        )
        print(f"   Résultat du tool :\n{res}\n")
        assert "Facture officielle" in res, "Le tool doit confirmer la génération"

        # 3. Vérification de l'enregistrement en base
        stmt_inv = select(Invoice).where(Invoice.order_id == order.id)
        invoice = (await session.execute(stmt_inv)).scalar_one_or_none()
        assert invoice is not None, "L'entité Invoice doit exister en base"
        print(f"3. Facture trouvée en base : N° {invoice.invoice_number}")
        print(f"   - Sous-total : {invoice.subtotal} FCFA")
        print(f"   - Livraison : {invoice.delivery_fee} FCFA")
        print(f"   - Total : {invoice.total} FCFA")
        print(f"   - Statut : {invoice.status}")
        print(f"   - Chemin PDF : {invoice.pdf_path}")

        # 4. Vérification physique du fichier PDF
        assert invoice.pdf_path is not None, "Le chemin PDF ne doit pas être nul"
        pdf_file = Path(invoice.pdf_path)
        assert pdf_file.exists(), f"Le fichier physique {pdf_file} doit exister"
        file_size = os.path.getsize(pdf_file)
        print(f"\n4. Fichier PDF vérifié sur le disque : {pdf_file.name} ({file_size} octets)")
        assert file_size > 1000, "Le PDF doit avoir une taille valide (> 1 Ko)"

        # 5. Test du endpoint HTTP FastAPI de téléchargement
        print(f"\n5. Test de la route FastAPI GET /invoices/{invoice.invoice_number}...")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/invoices/{invoice.invoice_number}")
            print(f"   Code HTTP : {resp.status_code}")
            print(f"   Content-Type : {resp.headers.get('content-type')}")
            assert resp.status_code == 200, "La route de facture doit répondre 200 OK"
            assert "application/pdf" in resp.headers.get("content-type", "")
            assert len(resp.content) == file_size, "Le contenu téléchargé doit correspondre au fichier"

    print("\n=== TOUS LES TESTS DU SPRINT 5 (FACTURATION PDF) SONT VALIDÉS ! ===")


if __name__ == "__main__":
    asyncio.run(main())

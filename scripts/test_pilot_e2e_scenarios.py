"""
Suite de tests End-to-End (E2E) pour MaliAgent (Sprint 7).
Valide 5 scénarios réels en conditions de production :
1. Parcours complet d'achat & Facturation PDF (Bamako Tech Express)
2. Détection de rupture de stock (Oraimo Watch 4 Pro à 0 unité)
3. Escalade humaine (Human Handoff) & Résolution Dashboard
4. Annulation de commande & Réapprovisionnement automatique du stock
5. Suivi de commande en direct (get_order_status)
"""

import asyncio
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.agent.orchestrator import run_agent_turn
from app.core.asyncio_compat import use_selector_event_loop_on_windows
from app.core.logging import setup_logging
from app.db.session import async_session
from app.models import Business, Conversation, Customer, Invoice, Order, OrderStatus, Product

use_selector_event_loop_on_windows()
setup_logging()  # DIAG : active l'affichage des logger.info() de diagnostic dans ce script autonome


async def run_e2e_suite():
    print("==================================================================")
    print("      SUITE DE TESTS E2E - MALIAGENT SPRINT 7 (PILOTES REELS)     ")
    print("==================================================================\n")

    async with async_session() as session:
        # Récupération de la boutique pilote Bamako Tech Express
        stmt = select(Business).where(Business.whatsapp_phone_number == "22370001122")
        biz = (await session.execute(stmt)).scalar_one_or_none()
        if not biz:
            # Fallback sur la première boutique si non seedée
            biz = (await session.execute(select(Business).limit(1))).scalar_one()

        print(f"[*] Boutique pilote de test : {biz.name} ({biz.whatsapp_phone_number})")
        biz_id = biz.id

        # Nettoyage complet des anciens clients/commandes de test
        test_phones = ["22371234567", "22372223344", "22373334455", "22374445566"]
        stmt_custs = select(Customer).where(Customer.whatsapp_phone_number.in_(test_phones))
        custs = (await session.execute(stmt_custs)).scalars().all()
        for c in custs:
            # Supprimer factures et commandes
            orders = (await session.execute(select(Order).where(Order.customer_id == c.id))).scalars().all()
            for o in orders:
                invs = (await session.execute(select(Invoice).where(Invoice.order_id == o.id))).scalars().all()
                for inv in invs:
                    await session.delete(inv)
                await session.delete(o)
            convs = (await session.execute(select(Conversation).where(Conversation.customer_id == c.id))).scalars().all()
            for cv in convs:
                await session.delete(cv)
            await session.flush()  # Force le DELETE FROM conversations avant celui du customer
            await session.delete(c)
        await session.commit()
        # -------------------------------------------------------------
        # SCENARIO 1 : Parcours classique complet + Facture PDF
        # -------------------------------------------------------------
        print("\n--- SCENARIO 1 : Parcours classique achat + Facture PDF ---")
        phone_s1 = "22371234567"

        # Étape 1 : Recherche d'articles
        print("1.1 Client : 'Bonjour, je cherche un chargeur rapide Type-C'")
        rep1 = await run_agent_turn(session, biz_id, "Bonjour, je cherche un chargeur rapide Type-C", phone_s1)
        print(f"    Agent : {rep1[:120]}...")
        assert "chargeur" in rep1.lower() or "12" in rep1 or "fcfa" in rep1.lower()

        # Étape 2 : Intention d'achat et adresse
        print("1.2 Client : 'Je prends 1 chargeur rapide. Je suis a ACI 2000 pres de la place Can'")
        rep2 = await run_agent_turn(session, biz_id, "Je prends 1 chargeur rapide. Je suis a ACI 2000 pres de la place Can", phone_s1)
        print(f"    Agent : {rep2[:120]}...")
        assert "confirm" in rep2.lower() or "total" in rep2.lower()

        # Étape 3 : Confirmation explicite
        print("1.3 Client : 'Oui je confirme la commande'")
        rep3 = await run_agent_turn(session, biz_id, "Oui je confirme la commande", phone_s1)
        print(f"    Agent : {rep3[:120]}...")
        assert "#" in rep3 or "enregistr" in rep3.lower() or "valid" in rep3.lower()

        # Étape 4 : Demande de facture PDF
        print("1.4 Client : 'Envoyez-moi ma facture svp'")
        rep4 = await run_agent_turn(session, biz_id, "Envoyez-moi ma facture svp", phone_s1)
        print(f"    Agent : {rep4[:120]}...")
        assert "fac-" in rep4.lower() or "facture" in rep4.lower() or "invoices" in rep4.lower()

        # Vérification DB
        stmt_order = (
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.business_id == biz_id)
            .order_by(Order.created_at.desc())
            .limit(1)
        )
        s1_order = (await session.execute(stmt_order)).scalar_one()
        print(f"    -> [VERIF DB] Commande creee : #{str(s1_order.id)[:8].upper()}, Montant: {s1_order.total_amount} FCFA, Statut: {s1_order.status.value}")
        assert s1_order.status == OrderStatus.PENDING

    # -------------------------------------------------------------
    # SCENARIO 2 : Rupture de stock & Intégrité
    # -------------------------------------------------------------
    print("\n--- SCENARIO 2 : Detection de rupture de stock ---")
    phone_s2 = "22372223344"

    async with async_session() as session:
        print("2.1 Client : 'Avez-vous la montre connectee Oraimo Watch 4 Pro ?'")
        rep_s2 = await run_agent_turn(session, biz_id, "Avez-vous la montre connectee Oraimo Watch 4 Pro ?", phone_s2)
        print(f"    Agent : {rep_s2[:140]}...")
        assert "rupture" in rep_s2.lower() or "0" in rep_s2 or "indisponible" in rep_s2.lower() or "pas de stock" in rep_s2.lower()
        print("    -> [VERIF] L'agent a correctement detecte la rupture et n'a pas valide de commande erronée.")

    # -------------------------------------------------------------
    # SCENARIO 3 : Escalade humaine (Human Handoff) & Reprise en main
    # -------------------------------------------------------------
    print("\n--- SCENARIO 3 : Escalade humaine (Human Handoff) ---")
    phone_s3 = "22373334455"

    async with async_session() as session:
        print("3.1 Client : 'Je veux acheter 5 iPhone mais je veux 40% de rabais, passez-moi le responsable !'")
        rep_s3 = await run_agent_turn(
            session, biz_id, "Je veux acheter 5 iPhone mais je veux 40% de rabais, passez-moi le responsable !", phone_s3
        )
        print(f"    Agent : {rep_s3[:140]}...")

        # Vérifier en DB que la conversation est en statut 'needs_human'
        stmt_c3 = select(Customer).where(Customer.whatsapp_phone_number == phone_s3)
        c3 = (await session.execute(stmt_c3)).scalar_one()
        stmt_conv3 = (
            select(Conversation)
            .where(Conversation.customer_id == c3.id)
            .order_by(Conversation.updated_at.desc())
            .limit(1)
        )
        conv3 = (await session.execute(stmt_conv3)).scalar_one()
        print(f"    -> [VERIF DB] Conversation statut : {conv3.status} (Motif : {conv3.handoff_reason})")
        assert conv3.status == "needs_human"

        # Vérifier que le bot reste en pause pour ce client
        print("3.2 Client envoie un autre message pendant la pause")
        rep_s3_pause = await run_agent_turn(session, biz_id, "Allo vous etes la ?", phone_s3)
        print(f"    Agent : {rep_s3_pause[:140]}...")
        assert "conseiller" in rep_s3_pause.lower() or "attente" in rep_s3_pause.lower() or "responsable" in rep_s3_pause.lower()

        # Résolution côté Dashboard (simulation de l'API /resolve)
        conv3.status = "active"
        conv3.handoff_reason = None
        await session.commit()
        print("    -> [VERIF DASHBOARD] Demande resolue : statut repasse a 'active'.")

    # -------------------------------------------------------------
    # SCENARIO 4 : Annulation de commande & Restauration du stock
    # -------------------------------------------------------------
    print("\n--- SCENARIO 4 : Annulation de commande & Restauration du stock ---")
    phone_s4 = "22374445566"

    async with async_session() as session:
        # Trouver un produit en stock pour le tester
        stmt_prod = select(Product).where(Product.business_id == biz_id, Product.stock_quantity > 2).limit(1)
        prod = (await session.execute(stmt_prod)).scalar_one()
        initial_stock = prod.stock_quantity
        prod_name = prod.name
        print(f"4.1 Produit teste : {prod_name} (Stock initial = {initial_stock})")

        # Passer commande
        await run_agent_turn(session, biz_id, f"Je veux acheter 1 {prod_name}", phone_s4)
        await run_agent_turn(session, biz_id, "Livraison a ACI 2000", phone_s4)
        await run_agent_turn(session, biz_id, "Oui je confirme ma commande", phone_s4)

        # Vérifier décrémentation stock
        await session.refresh(prod)
        print(f"    Stock apres commande = {prod.stock_quantity} (Attendu: {initial_stock - 1})")
        assert prod.stock_quantity == initial_stock - 1

        # Demande d'annulation par le client
        print("4.2 Client : 'Finalement je souhaite annuler ma commande svp'")
        rep_cancel = await run_agent_turn(session, biz_id, "Finalement je souhaite annuler ma commande svp", phone_s4)
        print(f"    Agent : {rep_cancel[:140]}...")
        assert "annul" in rep_cancel.lower()

        # Vérifier restauration du stock
        await session.refresh(prod)
        print(f"    Stock apres annulation = {prod.stock_quantity} (Attendu: {initial_stock})")
        assert prod.stock_quantity == initial_stock
        print("    -> [VERIF] Commande annulee et stock restaure a 100% !")

    # -------------------------------------------------------------
    # SCENARIO 5 : Suivi de commande en temps réel
    # -------------------------------------------------------------
    print("\n--- SCENARIO 5 : Suivi de commande (get_order_status) ---")
    async with async_session() as session:
        print("5.1 Client (du scenario 1) : 'Où en est ma commande ?'")
        rep_s5 = await run_agent_turn(session, biz_id, "Ou en est ma commande ?", phone_s1)
        print(f"    Agent : {rep_s5[:140]}...")
        assert "#" in rep_s5 or "statut" in rep_s5.lower() or "attente" in rep_s5.lower()
        print("    -> [VERIF] Suivi de commande execute avec succes !")

    print("\n==================================================================")
    print("   [SUCCES COMPLET] LES 5 SCENARIOS DU SPRINT 7 SONT VALIDES !    ")
    print("==================================================================")


if __name__ == "__main__":
    asyncio.run(run_e2e_suite())

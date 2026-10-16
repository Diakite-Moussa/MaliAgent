"""
Script interactif de demonstration manuelle - Photos Produits & Personnalisation IA.
Permet de tester immediatement le comportement en console sans WhatsApp reel.

Usage:
    python scripts/demo_photos_and_agent_config.py
"""

import asyncio
import sys
from decimal import Decimal
from pathlib import Path

# Fix encodage console Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.agent.orchestrator import run_agent_turn
from app.core.asyncio_compat import use_selector_event_loop_on_windows
from app.db.session import async_session
from app.models import AgentConfiguration, Business, Product

use_selector_event_loop_on_windows()


async def run_manual_check():
    print("=" * 75)
    print("MALIAGENT - VERIFICATION MANUELLE : PHOTOS & PERSONNALISATION IA")
    print("=" * 75)

    async with async_session() as session:
        # 1. Selectionner une boutique active
        biz = (await session.execute(select(Business))).scalars().first()
        if not biz:
            print("[-] Aucune boutique en base. Executez : python scripts/seed_pilot_data.py")
            return

        print(f"\n[+] Boutique active : {biz.name} (WhatsApp : +{biz.whatsapp_phone_number})")

        # 2. S'assurer qu'un produit avec photo existe
        stmt_p = select(Product).where(Product.business_id == biz.id)
        prods = (await session.execute(stmt_p)).scalars().all()
        if not prods:
            print("[-] Aucun produit trouve. Creation d'un produit demo avec photo...")
            demo_prod = Product(
                business_id=biz.id,
                name="Redmi Note 13 Pro",
                category="smartphone",
                price=Decimal("185000"),
                stock_quantity=10,
                image_url="https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=500",
            )
            session.add(demo_prod)
            await session.commit()
            prods = [demo_prod]
        else:
            target = prods[0]
            if not target.image_url:
                target.image_url = "https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=500"
                await session.commit()
            print(f"[+] Produit avec photo disponible : {target.name} ({target.image_url})")

        # 3. Recuperer ou initialiser la configuration de l'agent
        stmt_cfg = select(AgentConfiguration).where(AgentConfiguration.business_id == biz.id)
        cfg = (await session.execute(stmt_cfg)).scalar_one_or_none()
        if not cfg:
            cfg = AgentConfiguration(
                business_id=biz.id,
                agent_name="Moussa Assistant",
                tone="chaleureux",
                default_language="fr",
                custom_rules="Livraison offerte a partir de 50 000 FCFA. Garantie 1 an.",
                enabled=True,
            )
            session.add(cfg)
            await session.commit()

        print(f"\n--- ETAPE 1 : Configuration Actuelle de l'Agent ---")
        print(f"  * Nom de l'agent : {cfg.agent_name}")
        print(f"  * Ton : {cfg.tone}")
        print(f"  * Langue : {cfg.default_language}")
        print(f"  * Directives : {cfg.custom_rules}")
        print(f"  * Interrupteur IA : {'ACTIF (ON)' if cfg.enabled else 'EN PAUSE (OFF)'}")

        # 4. TEST 1 : Client demande la photo d'un produit
        print(f"\n--- ETAPE 2 : Test Demande Photo Produit via l'IA ---")
        test_phone = "22379998877"
        user_msg = f"Bonjour, est-ce que vous pouvez m'envoyer la photo du {prods[0].name} ?"
        print(f"Client (+{test_phone}) : \"{user_msg}\"")
        
        reply_1 = await run_agent_turn(
            session=session,
            business_id=biz.id,
            user_message=user_msg,
            customer_phone_number=test_phone,
        )
        print(f"Reponse IA ({cfg.agent_name}) :\n{reply_1}\n")

        # 5. TEST 2 : Changement de ton en temps reel (Mode Concis & Direct)
        print(f"--- ETAPE 3 : Test Changement Dynamique de Ton (Concis & Direct) ---")
        cfg.tone = "concis"
        cfg.agent_name = "ExpressBot"
        cfg.custom_rules = "Ne jamais faire de longs discours. Donner les prix nets."
        await session.commit()
        print("[v] Configuration modifiee : Ton = 'concis', Nom = 'ExpressBot'")

        user_msg_2 = "Quel est le prix et avez-vous du stock ?"
        print(f"Client (+{test_phone}) : \"{user_msg_2}\"")
        reply_2 = await run_agent_turn(
            session=session,
            business_id=biz.id,
            user_message=user_msg_2,
            customer_phone_number=test_phone,
        )
        print(f"Reponse IA (ExpressBot) :\n{reply_2}\n")

        # 6. TEST 3 : Interrupteur IA desactive (Toggle OFF)
        print(f"--- ETAPE 4 : Test Interrupteur IA desactive (Toggle OFF) ---")
        cfg.enabled = False
        await session.commit()
        print("[v] Interrupteur IA bascule sur OFF (enabled=False)")

        user_msg_3 = "Bonjour, je voudrais commander maintenant s'il vous plait"
        print(f"Client (+{test_phone}) : \"{user_msg_3}\"")
        reply_3 = await run_agent_turn(
            session=session,
            business_id=biz.id,
            user_message=user_msg_3,
            customer_phone_number=test_phone,
        )
        print(f"Reponse Systeme (Agent en pause) :\n{reply_3}\n")

        # Remettre l'agent en actif
        cfg.enabled = True
        cfg.tone = "chaleureux"
        cfg.agent_name = "Moussa Assistant"
        await session.commit()
        print("[v] Retablissement de la configuration active.")

    print("\n" + "=" * 75)
    print("VERIFICATION MANUELLE TERMINEE AVEC SUCCES")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(run_manual_check())

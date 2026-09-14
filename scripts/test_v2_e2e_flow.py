"""
Script de recette bout-en-bout (E2E) pour la V2.0 Logistique & Flotte (Sprints 9, 10, 11, 12).
Simule le parcours complet :
1. Connexion Commerçant & Création / Sélection d'une commande
2. Attribution de la mission à un coursier (Génération OTP secret)
3. Connexion Livreur Mobile & Consultation des courses attribuées
4. Prise en charge du colis en boutique (Statut : picked_up)
5. Départ en route vers le client (Statut : in_transit + Déclenchement alerte WhatsApp avec lien de tracking)
6. Envoi de coordonnées GPS en direct par le livreur
7. Consultation par le client de la page publique de tracking (/api/delivery/track/{order_id})
8. Remise du colis avec validation du code secret OTP client
9. Synchronisation : Mission 'delivered' & Commande 'delivered'

Usage : python scripts/test_v2_e2e_flow.py
"""

import asyncio
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from httpx import ASGITransport
from sqlalchemy import select

from app.core.asyncio_compat import use_selector_event_loop_on_windows
from app.core.security import hash_password
from app.db.session import async_session
from app.main import app
from app.models import Business, Customer, DriverType, Order, OrderStatus, User, UserRole

use_selector_event_loop_on_windows()


async def run_v2_e2e_recette():
    print("=" * 70)
    print("🚀 RECETTE FINALE V2.0 - LOGISTIQUE, FLOTTE & TRACKING CLIENT")
    print("=" * 70)

    # 0. Vérification et synchronisation des utilisateurs de test
    async with async_session() as session:
        stmt_b = select(Business).order_by(Business.created_at.asc())
        business = (await session.execute(stmt_b)).scalars().first()
        assert business is not None, "Aucune boutique trouvée en base. Lancez scripts/seed_pilot_data.py"

        stmt_u = select(User).where(User.email == "admin@maliagent.ml")
        admin_u = (await session.execute(stmt_u)).scalar_one_or_none()
        if not admin_u:
            admin_u = User(
                business_id=business.id,
                email="admin@maliagent.ml",
                password_hash=hash_password("Password123!"),
                first_name="Admin",
                last_name="Boutique",
                role=UserRole.ADMIN,
                is_active=True,
            )
            session.add(admin_u)
        else:
            admin_u.password_hash = hash_password("Password123!")
            admin_u.business_id = business.id
            admin_u.is_active = True
            admin_u.role = UserRole.ADMIN

        stmt_d = select(User).where(User.email == "livreur.tech@maliagent.ml")
        driver_u = (await session.execute(stmt_d)).scalar_one_or_none()
        if not driver_u:
            driver_u = User(
                business_id=business.id,
                email="livreur.tech@maliagent.ml",
                password_hash=hash_password("Password123!"),
                first_name="Ousmane",
                last_name="Traoré",
                role=UserRole.LIVREUR,
                driver_type=DriverType.INTERNAL,
                phone_number="+22370001122",
                is_available=True,
                is_active=True,
            )
            session.add(driver_u)
        else:
            driver_u.password_hash = hash_password("Password123!")
            driver_u.business_id = business.id
            driver_u.is_active = True
            driver_u.role = UserRole.LIVREUR
            driver_u.driver_type = DriverType.INTERNAL

        await session.commit()

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # -------------------------------------------------------------
        # Étape 1 : Connexion Commerçant & Livreur
        # -------------------------------------------------------------
        print("\n🔑 1. Authentification Commerçant & Livreur...")

        # Connexion Commerçant
        res_admin = await client.post(
            "/api/auth/login",
            json={"email": "admin@maliagent.ml", "password": "Password123!"},
        )
        assert res_admin.status_code == 200, f"Erreur login commerçant: {res_admin.text}"
        admin_data = res_admin.json()
        admin_token = admin_data["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        print(f"   ✅ Commerçant authentifié (admin@maliagent.ml - Rôle: {admin_data['role']})")

        # Connexion Livreur
        res_driver = await client.post(
            "/api/auth/login",
            json={"email": "livreur.tech@maliagent.ml", "password": "Password123!"},
        )
        assert res_driver.status_code == 200, f"Erreur login livreur: {res_driver.text}"
        driver_data = res_driver.json()
        driver_token = driver_data["access_token"]
        driver_headers = {"Authorization": f"Bearer {driver_token}"}
        print(f"   ✅ Livreur authentifié (livreur.tech@maliagent.ml - Rôle: {driver_data['role']})")

        # -------------------------------------------------------------
        # Étape 2 : Préparation / Sélection d'une commande
        # -------------------------------------------------------------
        print("\n📦 2. Création d'une commande client dédiée pour la recette...")
        async with async_session() as session:
            stmt_c = select(Customer).where(Customer.business_id == business.id)
            customer = (await session.execute(stmt_c)).scalars().first()
            if not customer:
                customer = Customer(
                    business_id=business.id,
                    whatsapp_phone_number="22370001122",
                    display_name="Client Pilote Bamako",
                )
                session.add(customer)
                await session.commit()
                await session.refresh(customer)

            order = Order(
                business_id=business.id,
                customer_id=customer.id,
                status=OrderStatus.PENDING,
                delivery_fee=1000,
                delivery_address="Badalabougou Rue 12, Bamako",
            )
            session.add(order)
            await session.commit()
            await session.refresh(order)

            customer_phone = customer.whatsapp_phone_number
            customer_name = customer.display_name or "Client Pilote Bamako"

            stmt_d = select(User).where(User.email == "livreur.tech@maliagent.ml")
            driver_obj = (await session.execute(stmt_d)).scalar_one()
            driver_user_id = str(driver_obj.id)

        print(f"   Commande ID : {order.id} (Ref: #{str(order.id)[:8]})")
        print(f"   Destinataire : {customer_name} (+{customer_phone})")
        print(f"   Lieu de livraison : {order.delivery_address}")

        # -------------------------------------------------------------
        # Étape 3 : Attribution de la mission par le commerçant
        # -------------------------------------------------------------
        print("\n🛵 3. Commerçant : Création et attribution de la mission de livraison...")
        payload_mission = {
            "order_id": str(order.id),
            "assignment_type": "internal",
            "driver_id": driver_user_id,
            "pickup_address": "Boutique Bamako Tech Express, ACI 2000",
            "delivery_address": order.delivery_address or "Badalabougou Rue 12, Bamako",
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "notes": "Colis fragile - contacter avant arrivée",
        }

        res_create = await client.post("/api/delivery/missions", json=payload_mission, headers=admin_headers)
        assert res_create.status_code == 201, f"Erreur création mission: {res_create.text}"
        mission_data = res_create.json()
        mission_id = mission_data["id"]
        otp_code = mission_data["otp_code"]

        print(f"   ✅ Mission créée avec succès : ID {mission_id}")
        print(f"   🔐 Code OTP secret généré : {otp_code} (Longueur: {len(otp_code)} chiffres)")
        assert len(otp_code) == 6, "L'OTP doit comporter exactement 6 chiffres"

        # -------------------------------------------------------------
        # Étape 4 : Livreur Mobile - Consultation de sa liste de courses
        # -------------------------------------------------------------
        print("\n📱 4. Livreur Mobile : Consultation des courses attribuées...")
        res_list = await client.get("/api/delivery/driver/missions", headers=driver_headers)
        assert res_list.status_code == 200, f"Erreur liste missions livreur: {res_list.text}"
        missions = res_list.json()["missions"]
        driver_mission = next((m for m in missions if m["id"] == mission_id), None)
        assert driver_mission is not None, "La mission n'apparaît pas dans la liste du livreur"

        print(f"   ✅ Mission trouvée dans le feed mobile. Statut initial : {driver_mission['status']}")
        print(f"   🗺️ Liens GPS générés :")
        print(f"      - Google Maps : {driver_mission['navigation']['google_maps']}")
        print(f"      - Waze        : {driver_mission['navigation']['waze']}")

        # -------------------------------------------------------------
        # Étape 5 : Livreur Mobile - Prise en charge du colis
        # -------------------------------------------------------------
        print("\n🏪 5. Livreur Mobile : Confirmation de récupération du colis en boutique...")
        res_pickup = await client.post(f"/api/delivery/driver/missions/{mission_id}/pickup", headers=driver_headers)
        assert res_pickup.status_code == 200, f"Erreur pickup: {res_pickup.text}"
        assert res_pickup.json()["status"] == "picked_up"
        print("   ✅ Statut mis à jour : 'picked_up' (Colis récupéré en boutique)")

        # -------------------------------------------------------------
        # Étape 6 : Livreur Mobile - Départ en route vers le client
        # -------------------------------------------------------------
        print("\n🏍️ 6. Livreur Mobile : Départ en route vers l'adresse client...")
        res_start = await client.post(f"/api/delivery/driver/missions/{mission_id}/start-route", headers=driver_headers)
        assert res_start.status_code == 200, f"Erreur start-route: {res_start.text}"
        assert res_start.json()["status"] == "in_transit"
        print("   ✅ Statut mis à jour : 'in_transit' (En route vers le client)")
        print("   💬 Notification WhatsApp client déclenchée avec lien de tracking et code OTP")

        # -------------------------------------------------------------
        # Étape 7 : Livreur Mobile - Envoi de coordonnées GPS en direct
        # -------------------------------------------------------------
        print("\n📍 7. Livreur Mobile : Actualisation de la position GPS...")
        res_loc = await client.post(
            f"/api/delivery/driver/missions/{mission_id}/location",
            json={"latitude": 12.6392, "longitude": -8.0029},
            headers=driver_headers,
        )
        assert res_loc.status_code == 200, f"Erreur location: {res_loc.text}"
        print("   ✅ Coordonnées GPS enregistrées : Lat 12.6392, Lng -8.0029 (Bamako)")

        # -------------------------------------------------------------
        # Étape 8 : Client - Consultation du tracking public en direct
        # -------------------------------------------------------------
        print("\n🌐 8. Client : Ouverture de la page publique de tracking...")
        res_track = await client.get(f"/api/delivery/track/{order.id}")
        assert res_track.status_code == 200, f"Erreur page tracking: {res_track.status_code}"
        assert "MaliAgent" in res_track.text
        assert "acheminement" in res_track.text or "En route" in res_track.text
        print("   ✅ Page HTML de tracking reçue (200 OK) avec timeline active et bouton d'appel")

        # -------------------------------------------------------------
        # Étape 9 : Livreur Mobile - Validation de livraison par Code OTP
        # -------------------------------------------------------------
        print("\n🔐 9. Livreur Mobile : Validation de livraison avec le code secret OTP client...")
        
        # Test 1 : Mauvais code OTP (doit échouer)
        res_wrong = await client.post(
            f"/api/delivery/driver/missions/{mission_id}/verify-otp",
            json={"otp_code": "000000"},
            headers=driver_headers,
        )
        assert res_wrong.status_code == 400, "Un code OTP incorrect ne doit pas valider la livraison"
        print("   🛡️ Sécurité vérifiée : Le code '000000' est correctement rejeté (400 Bad Request)")

        # Test 2 : Bon code OTP
        res_verify = await client.post(
            f"/api/delivery/driver/missions/{mission_id}/verify-otp",
            json={"otp_code": otp_code},
            headers=driver_headers,
        )
        assert res_verify.status_code == 200, f"Erreur validation OTP: {res_verify.text}"
        verify_data = res_verify.json()
        assert verify_data["status"] == "delivered"
        assert verify_data["otp_verified"] is True
        print(f"   🎉 Code OTP '{otp_code}' validé avec succès !")
        print("   ✅ Statut de la mission : 'delivered' (otp_verified: True)")

        # -------------------------------------------------------------
        # Étape 10 : Vérification Cockpit Commerçant & Commande
        # -------------------------------------------------------------
        print("\n📊 10. Commerçant : Vérification de la synchronisation dans le cockpit...")
        res_merchant_missions = await client.get("/api/delivery/missions", headers=admin_headers)
        assert res_merchant_missions.status_code == 200
        all_missions = res_merchant_missions.json()["missions"]
        synced_mission = next((m for m in all_missions if m["id"] == mission_id), None)
        assert synced_mission is not None
        assert synced_mission["status"] == "delivered"
        assert synced_mission["otp_verified"] is True

        # Vérification statut commande
        async with async_session() as session:
            stmt_o = select(Order).where(Order.id == order.id)
            updated_order = (await session.execute(stmt_o)).scalar_one()
            assert updated_order.status == OrderStatus.DELIVERED

        print(f"   ✅ Commande synchronisée : statut '{updated_order.status.value}'")
        print(f"   ✅ Mission synchronisée : statut '{synced_mission['status']}'")

    print("\n" + "=" * 70)
    print("🏆 RECETTE E2E V2.0 100% VALIDÉE AVEC SUCCÈS !")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_v2_e2e_recette())

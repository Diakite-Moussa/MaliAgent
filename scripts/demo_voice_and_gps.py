"""
Script interactif de test manuel — Voix (Bambara/Français) & Géolocalisation GPS.
Permet de tester immédiatement le pipeline complet sans envoyer de message réel sur WhatsApp.
"""

import asyncio
import sys
from pathlib import Path

# Configuration encodage UTF-8 pour la console Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.agent.orchestrator import run_agent_turn
from app.business.geo import resolve_bamako_zone_from_gps
from app.core.asyncio_compat import use_selector_event_loop_on_windows
from app.db.session import async_session
from app.models import Business
from app.voice.languages import detect_language
from app.voice.stt.mock import MockSTTProvider
from app.voice.tts.mock import MockTTSProvider

use_selector_event_loop_on_windows()


async def run_manual_demo():
    print("=" * 70)
    print("🇲🇱 MALIAGENT — DÉMONSTRATION MANUELLE : VOIX & GPS (V0.5 / V2.2)")
    print("=" * 70)

    async with async_session() as session:
        biz = (await session.execute(select(Business))).scalars().first()
        if not biz:
            print("[-] Aucune boutique en base. Lancez d'abord : python scripts/seed_pilot_data.py")
            return

        print(f"\n[+] Boutique active : {biz.name} ({biz.whatsapp_phone_number})")
        test_phone = "22370123456"

        # -------------------------------------------------------------
        # SCÉNARIO 1 : Message vocal en Bambara (Bamanankan)
        # -------------------------------------------------------------
        print("\n" + "-" * 60)
        print("🎙️ SCÉNARIO 1 : Réception d'une note vocale en BAMBARA")
        print("-" * 60)
        vocal_bambara = "I ni ce, Samsung Galaxy A15 sɔngɔ ye joli ye ?"
        print(f"👉 Audio simulé du client : « {vocal_bambara} »")

        stt = MockSTTProvider(default_text=vocal_bambara)
        trans_res = await stt.transcribe(b"fake_audio_stream")
        print(f"[*] Transcription STT     : {trans_res.text}")
        print(f"[*] Langue détectée       : {trans_res.detected_language.upper()} (Bambara)")

        reply, voice_url = await run_agent_turn(
            session=session,
            business_id=biz.id,
            user_message=trans_res.text,
            customer_phone_number=test_phone,
            is_voice=True,
            return_voice_url=True,
        )
        print("\n🤖 Réponse de l'Agent IA (Bambara) :")
        print(reply)
        print(f"🎵 Note vocale générée pour WhatsApp : {voice_url}")

        # -------------------------------------------------------------
        # SCÉNARIO 2 : Partage de localisation GPS WhatsApp (Lafiabougou)
        # -------------------------------------------------------------
        print("\n" + "-" * 60)
        print("📍 SCÉNARIO 2 : Partage de position GPS WhatsApp")
        print("-" * 60)
        lat = 12.632145
        lon = -8.025471
        print(f"👉 Pin GPS envoyé par le client : ({lat}, {lon})")

        geo_info = resolve_bamako_zone_from_gps(lat, lon)
        print(f"[*] Analyse du lieu : {geo_info['neighborhood']} ({geo_info['commune']})")
        print(f"[*] Tarif forfaitaire calculé : {int(geo_info['fee'])} FCFA (Délai : {geo_info['delivery_delay']})")
        print(f"[*] Lien de navigation Livreur : {geo_info['maps_url']}")

        gps_prompt = f"[LOCALISATION_GPS: latitude={lat}, longitude={lon}, repere=Lafiabougou Place Can, adresse=Commune IV]"
        reply_gps = await run_agent_turn(
            session=session,
            business_id=biz.id,
            user_message=gps_prompt,
            customer_phone_number=test_phone,
            is_voice=False,
            return_voice_url=False,
        )
        print("\n🤖 Réponse de l'Agent IA (Prise en compte du GPS) :")
        print(reply_gps)

        # -------------------------------------------------------------
        # SCÉNARIO 3 : Note vocale en Français (Confirmation)
        # -------------------------------------------------------------
        print("\n" + "-" * 60)
        print("🎙️ SCÉNARIO 3 : Note vocale en FRANÇAIS (Confirmation)")
        print("-" * 60)
        vocal_fr = "Oui, je confirme la commande de 1 Samsung Galaxy A15."
        print(f"👉 Audio simulé du client : « {vocal_fr} »")

        stt_fr = MockSTTProvider(default_text=vocal_fr)
        trans_fr = await stt_fr.transcribe(b"fake_audio_stream")
        print(f"[*] Transcription STT     : {trans_fr.text}")
        print(f"[*] Langue détectée       : {trans_fr.detected_language.upper()} (Français)")

        reply_order, voice_order_url = await run_agent_turn(
            session=session,
            business_id=biz.id,
            user_message=trans_fr.text,
            customer_phone_number=test_phone,
            is_voice=True,
            return_voice_url=True,
        )
        print("\n🤖 Réponse de l'Agent IA (Confirmation & Facture) :")
        print(reply_order)
        print(f"🎵 Note vocale envoyée sur WhatsApp : {voice_order_url}")

    print("\n" + "=" * 70)
    print("✅ TEST MANUEL TERMINÉ AVEC SUCCÈS !")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_manual_demo())

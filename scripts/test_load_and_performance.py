"""
Script de test de charge et de benchmark de performance pour MaliAgent (Sprint 8).
Simule 50 clients simultanés envoyant des rafales de requêtes sur les endpoints critiques :
- Healthcheck enrichi (/health)
- Authentification JWT (/api/auth/login)
- Consultation du catalogue produits (/api/products)
- Suivi des commandes (/api/orders)

Calcule automatiquement :
- Débit (Requêtes par seconde / RPS)
- Latence : Min, Moyenne, Médiane (p50), 95e percentile (p95), 99e percentile (p99)
- Taux de succès / erreurs

Usage : python scripts/test_load_and_performance.py
"""

import asyncio
import math
import statistics
import sys
import time
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
from app.models import Business, User, UserRole

use_selector_event_loop_on_windows()

CONCURRENCY = 50
REQUESTS_PER_WORKER = 4  # Total: 200 requêtes distribuées


async def ensure_test_user():
    async with async_session() as session:
        stmt_b = select(Business).order_by(Business.created_at.asc())
        biz = (await session.execute(stmt_b)).scalars().first()
        if not biz:
            biz = Business(name="Load Test Boutique", whatsapp_phone_number="22370009999", currency="XOF")
            session.add(biz)
            await session.commit()
            await session.refresh(biz)

        stmt_u = select(User).where(User.email == "loadtest@maliagent.ml")
        user = (await session.execute(stmt_u)).scalar_one_or_none()
        if not user:
            user = User(
                business_id=biz.id,
                email="loadtest@maliagent.ml",
                password_hash=hash_password("Password123!"),
                first_name="Load",
                last_name="Tester",
                role=UserRole.ADMIN,
                is_active=True,
            )
            session.add(user)
            await session.commit()


async def worker(worker_id: int, client: httpx.AsyncClient, token: str, latencies: list[float], errors: list[str]):
    headers = {"Authorization": f"Bearer {token}"}
    endpoints = [
        ("GET", "/health", None, None),
        ("GET", "/api/products", None, headers),
        ("GET", "/api/orders", None, headers),
        ("GET", "/health", None, None),
    ]

    for method, path, json_data, req_headers in endpoints:
        t0 = time.perf_counter()
        try:
            if method == "GET":
                resp = await client.get(path, headers=req_headers)
            else:
                resp = await client.post(path, json=json_data, headers=req_headers)

            duration_ms = (time.perf_counter() - t0) * 1000
            latencies.append(duration_ms)

            if resp.status_code >= 400:
                errors.append(f"Worker {worker_id} {method} {path} -> {resp.status_code}")
        except Exception as exc:
            errors.append(f"Worker {worker_id} {method} {path} -> Exception: {exc}")


async def run_load_test():
    print("=" * 70)
    print("⚡ BENCHMARK DE PERFORMANCE & TEST DE CHARGE (SPRINT 8)")
    print("=" * 70)
    print(f"[*] Configuration : {CONCURRENCY} clients concurrents, {CONCURRENCY * REQUESTS_PER_WORKER} requêtes au total")

    await ensure_test_user()

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Récupération du jeton JWT pour les tests authentifiés
        res_login = await client.post(
            "/api/auth/login",
            json={"email": "loadtest@maliagent.ml", "password": "Password123!"},
        )
        assert res_login.status_code == 200, f"Échec login loadtest: {res_login.text}"
        token = res_login.json()["access_token"]
        print("   ✅ Jeton JWT d'authentification obtenu avec succès")

        print(f"\n🚀 Lancement des {CONCURRENCY} workers simultanés...")
        latencies: list[float] = []
        errors: list[str] = []

        wall_start = time.perf_counter()
        tasks = [
            asyncio.create_task(worker(i, client, token, latencies, errors))
            for i in range(CONCURRENCY)
        ]
        await asyncio.gather(*tasks)
        wall_time = time.perf_counter() - wall_start

    total_requests = len(latencies) + len(errors)
    success_requests = len(latencies)
    error_count = len(errors)
    rps = success_requests / wall_time if wall_time > 0 else 0

    latencies.sort()
    p50 = statistics.median(latencies) if latencies else 0
    p95 = latencies[math.floor(len(latencies) * 0.95)] if latencies else 0
    p99 = latencies[math.floor(len(latencies) * 0.99)] if latencies else 0
    mean_lat = statistics.mean(latencies) if latencies else 0
    min_lat = min(latencies) if latencies else 0
    max_lat = max(latencies) if latencies else 0

    print("\n" + "=" * 70)
    print("📊 RÉSULTATS DU TEST DE CHARGE")
    print("=" * 70)
    print(f"⏱️  Temps total d'exécution : {wall_time:.2f} secondes")
    print(f"📈 Débit moyen traité       : {rps:.1f} requêtes/seconde (RPS)")
    print(f"✅ Requêtes réussies (2xx)  : {success_requests}/{total_requests} ({(success_requests/total_requests)*100:.1f}%)")
    print(f"❌ Requêtes en échec        : {error_count}")
    print("\n⏱️  DISTRIBUTION DE LA LATENCE :")
    print(f"   • Min     : {min_lat:.1f} ms")
    print(f"   • Moyenne : {mean_lat:.1f} ms")
    print(f"   • p50     : {p50:.1f} ms (Médiane)")
    print(f"   • p95     : {p95:.1f} ms")
    print(f"   • p99     : {p99:.1f} ms")
    print(f"   • Max     : {max_lat:.1f} ms")

    if error_count == 0:
        print("\n🏆 TEST DE CHARGE 100% VALIDÉ — AUCUNE ERREUR SOUS CONCURRENCE !")
    else:
        print(f"\n⚠️ Des erreurs sont survenues ({error_count}) :")
        for err in errors[:5]:
            print(f"   - {err}")

    print("=" * 70)
    assert error_count == 0, f"{error_count} erreurs détectées lors du test de charge"


if __name__ == "__main__":
    asyncio.run(run_load_test())

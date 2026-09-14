import time

from app.core.asyncio_compat import use_selector_event_loop_on_windows

use_selector_event_loop_on_windows()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.delivery import router as delivery_router
from app.api.invoices import router as invoices_router
from app.api.orders import router as orders_router
from app.api.platform import router as platform_router
from app.api.products import router as products_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.session import async_session
from app.whatsapp.token_manager import get_token_quick_status
from app.whatsapp.webhook import router as whatsapp_router

setup_logging()

START_TIME = time.time()

app = FastAPI(
    title="MaliAgent API",
    version="0.2.0",
    description="Plateforme de commerce conversationnel WhatsApp & Logistique pour le Mali",
)

# Activation de CORS restreint aux origines du Dashboard Angular
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """
    Healthcheck enrichi pour le monitoring et la supervision de production (Sprint 8).
    Mesure la connectivité DB temps réel, l'uptime, et le statut des briques externes.
    """
    t0 = time.perf_counter()
    db_ok = False
    db_latency_ms = None
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
            db_ok = True
            db_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    except Exception:
        db_ok = False

    uptime_sec = round(time.time() - START_TIME)
    token_status = get_token_quick_status()
    llm_configured = bool(settings.ollama_api_key.strip() or settings.ollama_base_url.strip())

    overall_status = "ok" if db_ok else "degraded"
    payload = {
        "status": overall_status,
        "version": "0.2.0",
        "uptime_seconds": uptime_sec,
        "components": {
            "database": {
                "status": "connected" if db_ok else "unreachable",
                "latency_ms": db_latency_ms,
                "engine": "PostgreSQL 16",
            },
            "llm_provider": {
                "status": "configured" if llm_configured else "missing_config",
                "model": settings.ollama_model,
            },
            "whatsapp_meta": {
                "status": "configured" if token_status["configured"] else "missing_config",
                "phone_number_id_configured": token_status["phone_number_id_configured"],
            },
        },
    }
    return JSONResponse(content=payload, status_code=200 if db_ok else 503)


# Routers de l'application
app.include_router(auth_router)
app.include_router(platform_router)
app.include_router(whatsapp_router)
app.include_router(invoices_router)
app.include_router(dashboard_router)
app.include_router(orders_router)
app.include_router(products_router)
app.include_router(delivery_router)

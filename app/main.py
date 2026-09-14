from app.core.asyncio_compat import use_selector_event_loop_on_windows

use_selector_event_loop_on_windows()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.delivery import router as delivery_router
from app.api.invoices import router as invoices_router
from app.api.orders import router as orders_router
from app.api.platform import router as platform_router
from app.api.products import router as products_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.whatsapp.webhook import router as whatsapp_router

setup_logging()

app = FastAPI(title="MaliAgent API", version="0.1.0")

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
    return {"status": "ok"}


# Routers de l'application
app.include_router(auth_router)
app.include_router(platform_router)
app.include_router(whatsapp_router)
app.include_router(invoices_router)
app.include_router(dashboard_router)
app.include_router(orders_router)
app.include_router(products_router)
app.include_router(delivery_router)

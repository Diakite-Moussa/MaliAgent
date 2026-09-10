from fastapi import FastAPI
from app.whatsapp.webhook import router as whatsapp_router

app = FastAPI(title="MaliAgent", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok"}



app.include_router(whatsapp_router)


# Les routers seront ajoutés au fur et à mesure :
# - app.api.whatsapp_webhook (Sprint 2)
# - app.api.dashboard (Sprint 6)

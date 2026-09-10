from app.core.asyncio_compat import use_selector_event_loop_on_windows

use_selector_event_loop_on_windows()

from fastapi import FastAPI  # noqa: E402

from app.whatsapp.webhook import router as whatsapp_router  # noqa: E402

app = FastAPI(title="MaliAgent", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(whatsapp_router)


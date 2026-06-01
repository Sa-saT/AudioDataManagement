import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    from app.api.v1.orders import _cleanup_stale_drafts_internal  # noqa: PLC0415
    try:
        deleted = _cleanup_stale_drafts_internal()
        if deleted:
            logger.info("Startup: deleted %d stale draft order(s)", deleted)
    except Exception as exc:
        logger.warning("Draft cleanup on startup failed: %s", exc)
    yield


app = FastAPI(title="Audio Data Management API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router)

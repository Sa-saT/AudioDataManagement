import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1 import api_router
from app.config import get_settings

settings = get_settings()


# ─── JSON ログ設定 ────────────────────────────────────────────────────────────
# 本番 / staging は機械可読 JSON で Fly logs → Grafana Loki へ流す
def _configure_logging() -> None:
    if settings.ENVIRONMENT == "development":
        logging.basicConfig(level=logging.INFO)
        return
    from pythonjsonlogger.jsonlogger import JsonFormatter  # noqa: PLC0415
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


_configure_logging()
logger = logging.getLogger(__name__)


# ─── Sentry 初期化 ────────────────────────────────────────────────────────────
# DSN が空なら何も送らない (開発環境で安全)
if settings.SENTRY_DSN:
    import sentry_sdk  # noqa: PLC0415
    from sentry_sdk.integrations.fastapi import FastApiIntegration  # noqa: PLC0415
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration  # noqa: PLC0415
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        # 本番: リクエストの 5% をトレース。コスト抑制のため低め設定
        traces_sample_rate=0.05,
        send_default_pii=False,
    )
    logger.info("Sentry initialized (env=%s)", settings.ENVIRONMENT)


# ─── アプリ起動 ───────────────────────────────────────────────────────────────
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


# ─── ヘルスチェック ───────────────────────────────────────────────────────────
@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Better Stack / Fly.io が 30 秒ごとに叩く死活確認エンドポイント。
    DB 接続も確認し、異常なら 503 を返す。
    """
    from app.db import engine  # noqa: PLC0415
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error("healthz DB check failed: %s", exc)
        raise HTTPException(status_code=503, detail={"status": "degraded", "reason": "db"})
    return {"status": "ok"}


app.include_router(api_router)

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import engine
from app.core.exceptions import register_exception_handlers
from app.core.redis_client import close_redis_client, get_redis_client
from app.core.request_id import HEADER as REQUEST_ID_HEADER
from app.core.request_id import RequestIdMiddleware
from app.routers import api_router
from app.services import dispatch, tracking


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_redis_client()
    yield
    # مهام الخلفية تُلغى قبل إغلاق Redis والقاعدة اللتين تقرأ منهما
    await dispatch.shutdown()
    await tracking.shutdown()
    await close_redis_client()
    await engine.dispose()


app = FastAPI(
    title=f"{settings.app_name} API",
    version="0.1.0",
    description="TAXO — واجهة برمجية لتطبيق توصيل التاكسي",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # **ورأسٌ لا يُصرَّح هنا لا يقرؤه متصفّحٌ أصلاً** — وهو فخٌّ صامت: الرأسُ
    # يصل، وأدواتُ المطوّر تعرضه، **و`response.headers.get` تُرجع `null`**
    # لأن CORS يحجب ما لم يُذكر. فبغير هذا السطر يخرج الرقمُ المرجعيُّ من
    # الخادم ولا يبلغ التطبيقَ أبداً.
    expose_headers=[REQUEST_ID_HEADER],
)

# **فوق CORS في الترتيب، فيعمّ الردودَ كلَّها** — بما فيها ما يردّه CORS نفسُه
app.add_middleware(RequestIdMiddleware)

register_exception_handlers(app)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["system"])
async def health() -> dict[str, Any]:
    """فحص حيّ للتطبيق واعتمادياته (يستخدمه docker healthcheck)."""
    from sqlalchemy import text

    checks: dict[str, str] = {}

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # pragma: no cover - مسار تشخيصي
        checks["database"] = f"error: {exc.__class__.__name__}"

    try:
        await get_redis_client().ping()
        checks["redis"] = "ok"
    except Exception as exc:  # pragma: no cover - مسار تشخيصي
        checks["redis"] = f"error: {exc.__class__.__name__}"

    return {
        "app": settings.app_name,
        "environment": settings.environment,
        "status": "ok" if all(v == "ok" for v in checks.values()) else "degraded",
        "checks": checks,
    }

from fastapi import APIRouter

from app.routers import admin_providers, admin_settings, auth, config, drivers, rides
from app.ws.routes import ws_router

api_router = APIRouter()
api_router.include_router(config.router)
api_router.include_router(auth.router)
api_router.include_router(drivers.router)
api_router.include_router(rides.router)
api_router.include_router(admin_settings.router)
api_router.include_router(admin_providers.router)
# مقابس التتبع تحت نفس بادئة الإصدار: /api/v1/ws/...
api_router.include_router(ws_router)

__all__ = ["api_router"]

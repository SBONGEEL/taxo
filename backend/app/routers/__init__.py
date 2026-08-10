from fastapi import APIRouter

from app.routers import (
    admin_providers,
    admin_settings,
    admin_wallets,
    auth,
    config,
    drivers,
    rides,
    wallet,
)
from app.ws.routes import ws_router

api_router = APIRouter()
api_router.include_router(config.router)
api_router.include_router(auth.router)
api_router.include_router(drivers.router)
api_router.include_router(rides.router)
api_router.include_router(wallet.router)
api_router.include_router(admin_settings.router)
api_router.include_router(admin_providers.router)
api_router.include_router(admin_wallets.router)
# مقابس التتبع تحت نفس بادئة الإصدار: /api/v1/ws/...
api_router.include_router(ws_router)

__all__ = ["api_router"]

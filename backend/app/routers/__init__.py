from fastapi import APIRouter

from app.routers import (
    admin_campaigns,
    admin_payments,
    admin_providers,
    admin_settings,
    admin_subscriptions,
    admin_users,
    admin_wallets,
    auth,
    card_payments,
    config,
    devices,
    drivers,
    payments,
    rides,
    subscriptions,
    wallet,
)
from app.ws.routes import ws_router

api_router = APIRouter()
api_router.include_router(config.router)
api_router.include_router(auth.router)
api_router.include_router(devices.router)
api_router.include_router(drivers.router)
api_router.include_router(rides.router)
api_router.include_router(payments.router)
api_router.include_router(card_payments.router)
api_router.include_router(wallet.router)
api_router.include_router(subscriptions.router)
api_router.include_router(admin_settings.router)
api_router.include_router(admin_providers.router)
api_router.include_router(admin_wallets.router)
api_router.include_router(admin_payments.router)
api_router.include_router(admin_subscriptions.router)
api_router.include_router(admin_campaigns.router)
api_router.include_router(admin_users.router)
# مقابس التتبع تحت نفس بادئة الإصدار: /api/v1/ws/...
api_router.include_router(ws_router)

__all__ = ["api_router"]

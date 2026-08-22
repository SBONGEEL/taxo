from fastapi import APIRouter

from app.routers import (
    admin_account,
    admin_campaigns,
    admin_countries,
    admin_cancellations,
    admin_photo_reports,
    admin_vehicle_skins,
    vehicle_skins,
    admin_live_map,
    admin_payments,
    admin_offers,
    admin_promo,
    bookings,
    admin_backups,
    admin_missions,
    admin_referrals,
    admin_sharing,
    admin_providers,
    admin_rides,
    admin_otp_templates,
    admin_security,
    admin_settings,
    admin_stats,
    admin_subscriptions,
    admin_users,
    admin_wallets,
    auth,
    card_payments,
    config,
    devices,
    drivers,
    notifications,
    payments,
    places,
    missions,
    referrals,
    rides,
    subscriptions,
    wallet,
    public_site,
)
from app.ws.routes import ws_router

api_router = APIRouter()
api_router.include_router(config.router)
api_router.include_router(auth.router)
api_router.include_router(devices.router)
api_router.include_router(notifications.router)
api_router.include_router(drivers.router)
api_router.include_router(bookings.router)
api_router.include_router(places.router)
api_router.include_router(missions.router)
api_router.include_router(referrals.router)
api_router.include_router(rides.router)
api_router.include_router(payments.router)
api_router.include_router(card_payments.router)
api_router.include_router(wallet.router)
api_router.include_router(subscriptions.router)
api_router.include_router(admin_settings.router)
api_router.include_router(admin_providers.router)
api_router.include_router(admin_offers.router)
api_router.include_router(admin_promo.router)
api_router.include_router(admin_backups.router)
api_router.include_router(admin_missions.router)
api_router.include_router(admin_referrals.router)
api_router.include_router(admin_sharing.router)
api_router.include_router(admin_wallets.router)
api_router.include_router(admin_payments.router)
api_router.include_router(admin_live_map.router)
api_router.include_router(admin_stats.router)
api_router.include_router(admin_subscriptions.router)
api_router.include_router(admin_account.router)
api_router.include_router(admin_campaigns.router)
api_router.include_router(admin_countries.router)
api_router.include_router(admin_users.router)
api_router.include_router(admin_rides.router)
api_router.include_router(admin_otp_templates.router)
api_router.include_router(admin_security.router)
api_router.include_router(admin_cancellations.router)
api_router.include_router(admin_photo_reports.router)
# **المركباتُ بابان**: بابُ الكبتن وبابُ اللوحة — ولا ثالثَ يكتب مِلكيّة
api_router.include_router(vehicle_skins.router)
api_router.include_router(admin_vehicle_skins.router)
# **الصفحةُ التعريفيةُ العامة** — قراءةٌ محضةٌ بلا جلسة (2026-08-21)
api_router.include_router(public_site.router)
# مقابس التتبع تحت نفس بادئة الإصدار: /api/v1/ws/...
api_router.include_router(ws_router)

__all__ = ["api_router"]

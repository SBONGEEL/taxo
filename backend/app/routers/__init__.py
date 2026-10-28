from fastapi import APIRouter

from app.routers import (
    admin_account,
    admin_campaigns,
    admin_countries,
    admin_markets,
    admin_pricing_zones,
    admin_finance_overview,
    admin_test_accounts,
    admin_errors,
    admin_cancellations,
    admin_feedback,
    admin_alerts,
    admin_guest,
    admin_photo_reports,
    admin_policies,
    admin_site,
    admin_vehicle_skins,
    vehicle_skins,
    admin_live_map,
    admin_payments,
    admin_unconfirmed_payments,
    admin_offers,
    admin_promo,
    bookings,
    admin_backups,
    admin_missions,
    admin_referrals,
    admin_releases,
    admin_sharing,
    admin_providers,
    admin_rides,
    admin_search,
    admin_otp_templates,
    admin_security,
    admin_categories,
    admin_settings,
    admin_facilities,
    admin_map_places,
    airports,
    guarantees,
    commute,
    commute_driver,
    intercity,
    intercity_admin,
    intercity_driver,
    admin_activity,
    cashback,
    admin_stats,
    admin_subscriptions,
    admin_users,
    admin_verification_campaigns,
    admin_wallets,
    admin_payment_protection,
    admin_payment_requests,
    admin_transfers,
    payment_requests,
    admin_taxo_cards,
    taxo_cards,
    account,
    auth,
    card_payments,
    config,
    devices,
    drivers,
    notifications,
    payments,
    map_places,
    places,
    missions,
    referrals,
    rides,
    subscriptions,
    telemetry,
    feedback,
    guest,
    wallet,
    public_site,
    storefront,
    trip_chat,
    ride_calls,
    admin_trip_chat,
    admin_ride_calls,
    admin_finance_summary,
)
from app.ws.routes import ws_router

api_router = APIRouter()
api_router.include_router(config.router)
api_router.include_router(storefront.router)
api_router.include_router(auth.router)
api_router.include_router(devices.router)
api_router.include_router(notifications.router)
api_router.include_router(account.router)
api_router.include_router(drivers.router)
api_router.include_router(bookings.router)
api_router.include_router(places.router)
api_router.include_router(map_places.router)
api_router.include_router(airports.router)
api_router.include_router(missions.router)
api_router.include_router(referrals.router)
api_router.include_router(rides.router)
# **محادثةُ الرحلة ومكالمتُها** (SPEC §٦٦) — موجّهٌ لكلِّ بابٍ في ملفِّه: الطرفان، واللوحة
api_router.include_router(trip_chat.router)
api_router.include_router(ride_calls.router)
api_router.include_router(admin_trip_chat.router)
api_router.include_router(admin_ride_calls.router)
api_router.include_router(payments.router)
api_router.include_router(card_payments.router)
api_router.include_router(wallet.router)
api_router.include_router(subscriptions.router)
api_router.include_router(telemetry.router)
api_router.include_router(feedback.router)
api_router.include_router(admin_errors.router)
api_router.include_router(admin_settings.router)
# **فئاتُ الرحلة** (SPEC §٦٧) — صفحتُها في اللوحة وصفاتُ المركبة
api_router.include_router(admin_categories.router)
api_router.include_router(admin_facilities.router)
api_router.include_router(admin_map_places.router)
api_router.include_router(guarantees.router)
api_router.include_router(commute.router)
api_router.include_router(commute_driver.router)
api_router.include_router(intercity_admin.router)
api_router.include_router(intercity_driver.router)
api_router.include_router(intercity.router)
api_router.include_router(admin_activity.router)
api_router.include_router(cashback.router)
api_router.include_router(admin_verification_campaigns.router)
api_router.include_router(admin_providers.router)
api_router.include_router(admin_offers.router)
api_router.include_router(admin_promo.router)
api_router.include_router(admin_backups.router)
api_router.include_router(admin_missions.router)
api_router.include_router(admin_policies.router)
api_router.include_router(admin_site.router)
api_router.include_router(admin_referrals.router)
api_router.include_router(admin_releases.router)
api_router.include_router(admin_sharing.router)
api_router.include_router(admin_wallets.router)
# **نظامُ الدفع الجديد** (SPEC §٧٣-هـ المرحلة ١) — طرقُ الدفع لكلِّ دولة وطابورُ الموظّف الماليّ، ووجهُه للراكب والكبتن والـwebhook
api_router.include_router(admin_payment_requests.router)
api_router.include_router(admin_payment_protection.router)
# **مراجعةُ تحويلات BaridiMob** (SPEC §٨٢-ب)
api_router.include_router(admin_transfers.router)
api_router.include_router(payment_requests.router)
# **بطاقاتُ شحن TAXO** (SPEC §٧٣-هـ المرحلة ٢) — إدارتُها في اللوحة، واستعمالُها للراكب والكبتن
api_router.include_router(admin_taxo_cards.router)
api_router.include_router(taxo_cards.router)
api_router.include_router(admin_payments.router)
# **طابورُ المدفوعات غير المؤكَّدة** (SPEC §٦٤-ج) — موجّهٌ في ملفِّه لا ثانٍ في `admin_payments` (`check:contract`)
api_router.include_router(admin_unconfirmed_payments.router)
api_router.include_router(admin_live_map.router)
api_router.include_router(admin_search.router)
api_router.include_router(admin_stats.router)
# **الملخّصاتُ المالية** (SPEC §٦٥-د) — قراءةٌ وحدَها بصلاحيةٍ مستقلّة، **موجّهٌ في ملفِّه** لا ثانٍ في `admin_stats`
api_router.include_router(admin_finance_summary.router)
# **«المالية العامة» وأسعارُ الصرف** (SPEC §٧٤-أ/٩) — الدولُ متجاورةً كلٌّ بعملته، والمجموعُ التقريبيُّ الموسوم
api_router.include_router(admin_finance_overview.router)
api_router.include_router(admin_subscriptions.router)
api_router.include_router(admin_account.router)
api_router.include_router(admin_campaigns.router)
api_router.include_router(admin_countries.router)
# **«الدول» ومفتاحُ الحدود** (SPEC §٧٤-أ/٢–٣) — بابُ حال السوق الوحيد، والكتابةُ `markets.manage`
api_router.include_router(admin_markets.router)
# **«مناطق التسعير»** (SPEC §٧٤-أ/٥) — الحدودُ ووسمُ «وعرة» ونسبتُها أو جدولُها؛ والكتابةُ كالتسعيرة
api_router.include_router(admin_pricing_zones.router)
# **حساباتُ التجربة** (SPEC §٧٤-أ/١٠) — قائمتُها وإعادةُ ملء رصيدها للمالك
api_router.include_router(admin_test_accounts.router)
api_router.include_router(admin_users.router)
api_router.include_router(admin_rides.router)
api_router.include_router(admin_otp_templates.router)
api_router.include_router(admin_security.router)
api_router.include_router(admin_cancellations.router)
api_router.include_router(admin_photo_reports.router)
api_router.include_router(admin_feedback.router)
# **إشعاراتُ المالك** (SPEC §٨١): الجرسُ والقائمةُ والإعداد — **و«مقروء» من زرِّ الإشعار بلا جلسة**، إذنُه في رمزه
api_router.include_router(admin_alerts.router)
api_router.include_router(admin_alerts.public_router)
# **وضعُ الضيف** (SPEC §٧٦-ن): بابا الضيف ومفتاحُه في اللوحة
api_router.include_router(admin_guest.router)
api_router.include_router(guest.router)
# **المركباتُ بابان**: بابُ الكبتن وبابُ اللوحة — ولا ثالثَ يكتب مِلكيّة
api_router.include_router(vehicle_skins.router)
api_router.include_router(admin_vehicle_skins.router)
# **الصفحةُ التعريفيةُ العامة** — قراءةٌ محضةٌ بلا جلسة (2026-08-21)
api_router.include_router(public_site.router)
# مقابس التتبع تحت نفس بادئة الإصدار: /api/v1/ws/...
api_router.include_router(ws_router)

__all__ = ["api_router"]

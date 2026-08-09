"""بذر إعدادات التطوير المحلي.

    python -m scripts.seed

يملأ إعدادات الدولتين (التسعير، مفاتيح الميزات، العمولة، خطط الاشتراك) ويكتب
توكنات Mapbox وTelr Sandbox **مشفّرة** في `provider_credentials` — وهو ما تصفه
SPEC بأنه أول خطوة بعد تشغيل النظام (القسم 4). المصدر الرسمي لهذه المفاتيح بعد
ذلك هو صفحة العقود؛ قراءتها من البيئة تحدث هنا فقط ولمرة واحدة.

السكربت idempotent: لا يلمس صفاً موجوداً حتى لا يمحو تعديلات المشرف.
"""

from __future__ import annotations

import asyncio
import os
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.currency import currency_for_country
from app.core.db import SessionLocal, engine
from app.core.phone import normalize_phone
from app.core.security import hash_password
from app.models.commission import CommissionSetting
from app.models.enums import (
    CountryCode,
    FeatureKey,
    ProviderKey,
    SubscriptionDurationType,
    UserRole,
    VehicleCategory,
)
from app.models.feature_flag import FeatureFlag
from app.models.pricing import PricingRule
from app.models.subscription import SubscriptionPlan
from app.models.user import User
from app.services.providers import credentials as credentials_service

# ليبيا مرحلة تجريب: كاش فقط. الأردن: كليك وبطاقة ومحفظة، بلا تحويل P2P ولا عمولة.
FEATURE_DEFAULTS: dict[CountryCode, dict[FeatureKey, bool]] = {
    CountryCode.LY: {key: False for key in FeatureKey},
    CountryCode.JO: {
        FeatureKey.CLIQ_ENABLED: True,
        FeatureKey.CARD_ENABLED: True,
        FeatureKey.WALLET_ENABLED: True,
        FeatureKey.WALLET_TRANSFER_ENABLED: False,
        FeatureKey.COMMISSION_ENABLED: False,
    },
}

# قيم مبدئية للتطوير — تُضبط نهائياً من لوحة الإدارة
PRICING_DEFAULTS: dict[tuple[CountryCode, VehicleCategory], dict[str, str]] = {
    (CountryCode.LY, VehicleCategory.ECONOMY): {
        "base_fare": "3.000",
        "price_per_km": "1.000",
        "price_per_min": "0.150",
        "minimum_fare": "5.000",
        "cancellation_fee": "2.000",
    },
    (CountryCode.LY, VehicleCategory.COMFORT): {
        "base_fare": "5.000",
        "price_per_km": "1.500",
        "price_per_min": "0.200",
        "minimum_fare": "8.000",
        "cancellation_fee": "3.000",
    },
    (CountryCode.JO, VehicleCategory.ECONOMY): {
        "base_fare": "0.800",
        "price_per_km": "0.350",
        "price_per_min": "0.050",
        "minimum_fare": "1.500",
        "cancellation_fee": "0.750",
    },
    (CountryCode.JO, VehicleCategory.COMFORT): {
        "base_fare": "1.200",
        "price_per_km": "0.500",
        "price_per_min": "0.070",
        "minimum_fare": "2.500",
        "cancellation_fee": "1.000",
    },
}

PLAN_DEFAULTS: dict[CountryCode, list[tuple[str, SubscriptionDurationType, str]]] = {
    CountryCode.LY: [
        ("اشتراك يومي", SubscriptionDurationType.DAILY, "5.000"),
        ("اشتراك أسبوعي", SubscriptionDurationType.WEEKLY, "30.000"),
        ("اشتراك شهري", SubscriptionDurationType.MONTHLY, "100.000"),
    ],
    CountryCode.JO: [
        ("اشتراك يومي", SubscriptionDurationType.DAILY, "1.500"),
        ("اشتراك أسبوعي", SubscriptionDurationType.WEEKLY, "9.000"),
        ("اشتراك شهري", SubscriptionDurationType.MONTHLY, "30.000"),
    ],
}


def _log(message: str) -> None:
    print(f"[seed] {message}")


async def seed_feature_flags(session: AsyncSession) -> None:
    for country, defaults in FEATURE_DEFAULTS.items():
        for key, enabled in defaults.items():
            exists = await session.scalar(
                select(FeatureFlag.id).where(
                    FeatureFlag.country_code == country,
                    FeatureFlag.feature_key == key.value,
                )
            )
            if exists is None:
                session.add(
                    FeatureFlag(
                        country_code=country, feature_key=key.value, enabled=enabled
                    )
                )
                _log(f"مفتاح ميزة: {country.value}/{key.value} = {enabled}")


async def seed_commission(session: AsyncSession) -> None:
    for country in CountryCode:
        exists = await session.scalar(
            select(CommissionSetting.id).where(CommissionSetting.country_code == country)
        )
        if exists is None:
            # العمولة صفر ومعطّلة افتراضياً (SPEC القسم 8)
            session.add(CommissionSetting(country_code=country))
            _log(f"إعداد عمولة: {country.value} (معطّل، 0%)")


async def seed_pricing(session: AsyncSession) -> None:
    for (country, category), amounts in PRICING_DEFAULTS.items():
        exists = await session.scalar(
            select(PricingRule.id).where(
                PricingRule.country_code == country,
                PricingRule.vehicle_category == category,
            )
        )
        if exists is None:
            session.add(
                PricingRule(
                    country_code=country,
                    vehicle_category=category,
                    **{key: Decimal(value) for key, value in amounts.items()},
                )
            )
            _log(f"تسعيرة: {country.value}/{category.value}")


async def seed_plans(session: AsyncSession) -> None:
    for country, plans in PLAN_DEFAULTS.items():
        for name, duration, price in plans:
            exists = await session.scalar(
                select(SubscriptionPlan.id).where(
                    SubscriptionPlan.country_code == country,
                    SubscriptionPlan.name == name,
                )
            )
            if exists is None:
                session.add(
                    SubscriptionPlan(
                        country_code=country,
                        name=name,
                        duration_type=duration,
                        price=Decimal(price),
                        currency=currency_for_country(country),
                    )
                )
                _log(f"خطة اشتراك: {country.value}/{name}")


async def seed_providers(session: AsyncSession) -> None:
    """يكتب عقود Mapbox وTelr من البيئة — مشفّرة — إن لم تكن محفوظة."""
    public_token = os.environ.get("MAPBOX_PUBLIC_TOKEN", "").strip()
    secret_token = os.environ.get("MAPBOX_SECRET_TOKEN", "").strip()

    if public_token and secret_token:
        existing = await credentials_service.get_credential(session, ProviderKey.MAPBOX)
        if existing is None:
            await credentials_service.upsert(
                session,
                provider_key=ProviderKey.MAPBOX,
                country_code=None,
                values={"public_token": public_token, "secret_token": secret_token},
                is_active=True,
                actor=None,
            )
            _log("عقد Mapbox: محفوظ ومفعّل")
    else:
        _log("تخطّي Mapbox — MAPBOX_PUBLIC_TOKEN/MAPBOX_SECRET_TOKEN غير معبّأين")

    store_id = os.environ.get("TELR_STORE_ID", "").strip()
    auth_key = os.environ.get("TELR_AUTH_KEY", "").strip()

    if store_id and auth_key:
        existing = await credentials_service.get_credential(
            session, ProviderKey.TELR, CountryCode.JO
        )
        if existing is None:
            # تفعيله يرفع card_enabled للأردن تلقائياً
            await credentials_service.upsert(
                session,
                provider_key=ProviderKey.TELR,
                country_code=CountryCode.JO,
                values={
                    "store_id": store_id,
                    "auth_key": auth_key,
                    "test_mode": True,
                },
                is_active=True,
                actor=None,
            )
            _log("عقد Telr Sandbox (الأردن): محفوظ ومفعّل")
    else:
        _log("تخطّي Telr — TELR_STORE_ID/TELR_AUTH_KEY غير معبّأين")


async def seed_bootstrap_admin(session: AsyncSession) -> None:
    """حساب المشرف الأول — بدونه لا يمكن الوصول للوحة أصلاً.

    التسجيل الذاتي مقصور على الركاب والكباتن، ولا يُنشأ هذا الحساب في الإنتاج:
    هناك يُنشأ يدوياً بكلمة مرور لا تمر من ملف بيئة.
    """
    phone_raw = os.environ.get("BOOTSTRAP_ADMIN_PHONE", "").strip()
    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "").strip()

    if not phone_raw or not password:
        _log("تخطّي حساب المشرف — BOOTSTRAP_ADMIN_PHONE/PASSWORD غير معبّأين")
        return
    if settings.is_production:
        _log("تخطّي حساب المشرف — ممنوع في بيئة الإنتاج")
        return

    country = CountryCode(os.environ.get("BOOTSTRAP_ADMIN_COUNTRY", "JO"))
    phone = normalize_phone(phone_raw, country)

    exists = await session.scalar(select(User.id).where(User.phone == phone))
    if exists is not None:
        _log(f"حساب المشرف موجود: {phone}")
        return

    session.add(
        User(
            phone=phone,
            name=os.environ.get("BOOTSTRAP_ADMIN_NAME", "مشرف").strip() or "مشرف",
            role=UserRole.ADMIN,
            country_code=country,
            password_hash=hash_password(password),
        )
    )
    _log(f"حساب المشرف: {phone}")


async def main() -> None:
    async with SessionLocal() as session:
        await seed_feature_flags(session)
        await seed_commission(session)
        await seed_pricing(session)
        await seed_plans(session)
        await seed_providers(session)
        await seed_bootstrap_admin(session)
        await session.commit()
    await engine.dispose()
    _log("تم.")


if __name__ == "__main__":
    asyncio.run(main())

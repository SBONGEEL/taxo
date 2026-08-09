from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commission import CommissionSetting
from app.models.enums import AuditAction, CountryCode, FeatureKey
from app.models.feature_flag import FeatureFlag
from app.models.user import User
from app.services import audit


async def get_flags(session: AsyncSession, country_code: CountryCode) -> dict[str, bool]:
    """كل المفاتيح المعروفة للدولة — الغائب منها معطّل.

    لا نفترض التفعيل أبداً عند غياب الصف (SPEC: ليبيا كاش فقط).
    """
    rows = (
        await session.scalars(
            select(FeatureFlag).where(FeatureFlag.country_code == country_code)
        )
    ).all()
    flags = {key.value: False for key in FeatureKey}
    flags.update({row.feature_key: row.enabled for row in rows})
    return flags


async def is_feature_enabled(
    session: AsyncSession, country_code: CountryCode, feature_key: FeatureKey | str
) -> bool:
    key = feature_key.value if isinstance(feature_key, FeatureKey) else feature_key
    enabled = await session.scalar(
        select(FeatureFlag.enabled).where(
            FeatureFlag.country_code == country_code, FeatureFlag.feature_key == key
        )
    )
    return bool(enabled)


async def set_flag(
    session: AsyncSession,
    *,
    country_code: CountryCode,
    feature_key: FeatureKey | str,
    enabled: bool,
    actor: User | None = None,
    reason: str | None = None,
) -> FeatureFlag:
    """ينشئ المفتاح أو يحدّثه. الـ commit مسؤولية المستدعي."""
    key = feature_key.value if isinstance(feature_key, FeatureKey) else feature_key
    flag = await session.scalar(
        select(FeatureFlag).where(
            FeatureFlag.country_code == country_code, FeatureFlag.feature_key == key
        )
    )

    if flag is None:
        flag = FeatureFlag(country_code=country_code, feature_key=key, enabled=enabled)
        session.add(flag)
        await session.flush()
        action = AuditAction.CREATE
    elif flag.enabled != enabled:
        flag.enabled = enabled
        action = AuditAction.UPDATE
    else:
        return flag

    details: dict[str, object] = {
        "country_code": CountryCode(country_code).value,
        "feature_key": key,
        "enabled": enabled,
    }
    if reason:
        details["reason"] = reason
    await audit.record(
        session,
        actor=actor,
        action=action,
        entity_type="feature_flag",
        entity_id=flag.id,
        details=details,
    )

    if key == FeatureKey.COMMISSION_ENABLED.value:
        # المفتاح وجدول العمولة يصفان الشيء نفسه في SPEC — نُبقيهما متطابقين
        # حتى لا يقرأ حساب الرحلة قيمة تخالف ما تعرضه اللوحة.
        setting = await get_or_create_commission(session, country_code)
        setting.commission_enabled = enabled

    return flag


async def get_or_create_commission(
    session: AsyncSession, country_code: CountryCode
) -> CommissionSetting:
    """إعداد عمولة الدولة — يُنشأ معطّلاً بنسبة صفر إن لم يوجد (SPEC القسم 8)."""
    setting = await session.scalar(
        select(CommissionSetting).where(CommissionSetting.country_code == country_code)
    )
    if setting is None:
        setting = CommissionSetting(country_code=country_code)
        session.add(setting)
        await session.flush()
    return setting

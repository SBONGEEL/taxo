from __future__ import annotations

from collections.abc import Mapping

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import get_cipher
from app.core.exceptions import InvalidInput
from app.models.enums import AuditAction, CountryCode, ProviderKey
from app.models.provider_credential import ProviderCredential
from app.models.user import User
from app.services import audit, settings_service
from app.services.providers.registry import ProviderSpec, get_spec

# ما يُعرض بدل القيمة السرية في اللوحة؛ وإعادة إرساله كما هو تعني «لا تغيّرها»
MASK = "****"


def masked_values(spec: ProviderSpec, values: dict[str, Any]) -> dict[str, Any]:
    """قيم العرض في اللوحة: السرّي مقنّع، والعام كما هو (SPEC القسم 13/7)."""
    return {
        key: (MASK if key in spec.secret_field_keys and value not in (None, "") else value)
        for key, value in values.items()
    }


def _validate_scope(spec: ProviderSpec, country_code: CountryCode | None) -> None:
    if spec.per_country and country_code is None:
        raise InvalidInput(f"عقد {spec.label} يُدار لكل دولة على حدة — حدّد الدولة")
    if not spec.per_country and country_code is not None:
        raise InvalidInput(f"عقد {spec.label} عقد عام — لا يُربط بدولة")


def _merge_values(
    spec: ProviderSpec, current: dict[str, Any], incoming: dict[str, Any]
) -> dict[str, Any]:
    """يدمج المُرسل مع المحفوظ.

    اللوحة تعرض السرّي مقنّعاً، فإعادة إرسال `****` (أو حذف الحقل) تُبقي القيمة
    المخزّنة — وإلا لمحا كلُّ حفظٍ للحقول التي لم يعدّلها المشرف.
    """
    merged = dict(current)

    for key, value in incoming.items():
        if spec.field(key) is None:
            raise InvalidInput(f"حقل غير معروف لهذا المزود: {key}")
        if key in spec.secret_field_keys and value == MASK:
            continue
        merged[key] = value

    missing = [
        field.label
        for field in spec.fields
        if field.required and not str(merged.get(field.key, "") or "").strip()
    ]
    if missing:
        raise InvalidInput("حقول مطلوبة ناقصة: " + "، ".join(missing))

    return merged


async def list_credentials(session: AsyncSession) -> Sequence[ProviderCredential]:
    return (
        await session.scalars(
            select(ProviderCredential).order_by(
                ProviderCredential.provider_key, ProviderCredential.country_code
            )
        )
    ).all()


async def get_credential(
    session: AsyncSession,
    provider_key: ProviderKey,
    country_code: CountryCode | None = None,
    *,
    active_only: bool = False,
) -> ProviderCredential | None:
    """عقد المزود للدولة، وإلا العقد العام.

    الأخص أولاً: عقد الأردن لـ Telr يسبق أي عقد عام لنفس المزود.
    """
    stmt = select(ProviderCredential).where(
        ProviderCredential.provider_key == provider_key
    )
    if active_only:
        stmt = stmt.where(ProviderCredential.is_active.is_(True))

    rows = (await session.scalars(stmt)).all()
    if country_code is not None:
        for row in rows:
            if row.country_code == country_code:
                return row
    return next((row for row in rows if row.country_code is None), None)


async def provider_is_active(
    session: AsyncSession,
    provider_key: ProviderKey,
    country_code: CountryCode | None = None,
) -> bool:
    return (
        await get_credential(session, provider_key, country_code, active_only=True)
    ) is not None


async def get_values(
    session: AsyncSession,
    provider_key: ProviderKey,
    country_code: CountryCode | None = None,
    *,
    active_only: bool = True,
) -> dict[str, Any] | None:
    """القيم بعد فك التشفير — للاستخدام داخل الخلفية حصراً.

    (المرحلة 3 تقرأ من هنا توكن Mapbox السري لاستدعاء Directions.)
    """
    credential = await get_credential(
        session, provider_key, country_code, active_only=active_only
    )
    if credential is None:
        return None
    return normalize_toggles(get_cipher().decrypt(credential.credentials))


async def client_config(
    session: AsyncSession,
    provider_key: ProviderKey,
    country_code: CountryCode | None = None,
) -> dict[str, Any]:
    """الحقول العامة بطبيعتها فقط — هذا ما تراه الواجهات عبر `GET /config`."""
    spec = get_spec(provider_key)
    values = await get_values(session, provider_key, country_code)
    if values is None:
        return {}
    return {
        field.key: values[field.key]
        for field in spec.fields
        if field.expose_to_clients and values.get(field.key) not in (None, "")
    }


async def _sync_feature_flag(
    session: AsyncSession, credential: ProviderCredential, *, actor: User | None
) -> None:
    """تفعيل المزود = تفعيل ميزته تلقائياً (SPEC القسم 4).

    للعقود العامة (Mapbox، SMS، FCM) لا توجد ميزة per-country تُقلب: تأثيرها
    على مستوى النظام كله ويقرؤه الكود مباشرة من حالة العقد.
    """
    spec = get_spec(credential.provider_key)
    if spec.feature_key is None or credential.country_code is None:
        return
    await settings_service.set_flag(
        session,
        country_code=credential.country_code,
        feature_key=spec.feature_key,
        enabled=credential.is_active,
        actor=actor,
        reason=f"مزامنة تلقائية مع عقد {spec.key.value}",
    )


async def upsert(
    session: AsyncSession,
    *,
    provider_key: ProviderKey,
    country_code: CountryCode | None,
    values: dict[str, Any],
    is_active: bool | None = None,
    actor: User | None = None,
) -> ProviderCredential:
    """ينشئ عقد المزود أو يحدّثه ويعيد تشفيره. الـ commit مسؤولية المستدعي."""
    spec = get_spec(provider_key)
    _validate_scope(spec, country_code)

    credential = await get_credential(session, provider_key, country_code)
    if credential is not None and credential.country_code != country_code:
        credential = None  # لا نلمس العقد العام عند حفظ عقد دولة

    current = get_cipher().decrypt(credential.credentials) if credential else {}
    merged = _merge_values(spec, current, values)
    changed_fields = sorted(k for k in merged if current.get(k) != merged[k])

    if credential is None:
        credential = ProviderCredential(
            provider_key=provider_key,
            country_code=country_code,
            credentials=get_cipher().encrypt(merged),
            is_active=bool(is_active),
        )
        session.add(credential)
        action = AuditAction.CREATE
    else:
        credential.credentials = get_cipher().encrypt(merged)
        if is_active is not None:
            credential.is_active = is_active
        action = AuditAction.UPDATE

    await session.flush()

    # لا تُسجَّل القيم — أسماء الحقول المتغيّرة فقط
    await audit.record(
        session,
        actor=actor,
        action=action,
        entity_type="provider_credential",
        entity_id=credential.id,
        details={
            "provider_key": ProviderKey(provider_key).value,
            "country_code": CountryCode(country_code).value if country_code else None,
            "changed_fields": changed_fields,
            "is_active": credential.is_active,
        },
    )
    await _sync_feature_flag(session, credential, actor=actor)
    return credential


async def set_active(
    session: AsyncSession,
    credential: ProviderCredential,
    *,
    is_active: bool,
    actor: User | None = None,
) -> ProviderCredential:
    credential.is_active = is_active
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.ACTIVATE if is_active else AuditAction.DEACTIVATE,
        entity_type="provider_credential",
        entity_id=credential.id,
        details={
            "provider_key": credential.provider_key.value,
            "country_code": credential.country_code.value
            if credential.country_code
            else None,
        },
    )
    await _sync_feature_flag(session, credential, actor=actor)
    return credential


async def delete(
    session: AsyncSession,
    credential: ProviderCredential,
    *,
    actor: User | None = None,
) -> None:
    credential.is_active = False
    await _sync_feature_flag(session, credential, actor=actor)
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.DELETE,
        entity_type="provider_credential",
        entity_id=credential.id,
        details={
            "provider_key": credential.provider_key.value,
            "country_code": credential.country_code.value
            if credential.country_code
            else None,
        },
    )
    await session.delete(credential)


# ---------------------------------------------------- مفاتيحُ التشغيل في العقود

def _toggle_keys() -> frozenset[str]:
    """مفاتيحُ التشغيل كما تعلنها البطاقات — لا قائمةٌ مكتوبةٌ بيد."""
    from app.services.providers.registry import PROVIDERS

    return frozenset(
        field.key
        for spec in PROVIDERS.values()
        for field in spec.fields
        if field.kind == "toggle"
    )


def normalize_toggles(values: dict[str, Any]) -> dict[str, Any]:
    """يحوّل نصوصَ المفاتيح إلى منطق — **عند القراءة والكتابة معاً**.

    **ولماذا هنا لا في ترحيلةٍ للقاعدة**: القيمُ مخزَّنةٌ داخل مغلَّفٍ مشفَّر،
    وترحيلُها يعني فكَّ كلِّ عقدٍ وإعادةَ تشفيره — عمليةٌ على مالٍ ومفاتيحَ
    لإصلاحِ قراءةٍ. والتطبيعُ في البابِ الوحيد الذي يقرأ العقود يصلح المخزَّنَ
    والجديدَ معاً، بلا لمسِ صفٍّ واحد.

    و«false» و«0» و«» تُقرأ إطفاءً، وما عداها إشعالاً — فالنصُّ الذي كتبه
    مشرفٌ يُفهم كما قصده لا كما يفهمه `bool()`.
    """
    keys = _toggle_keys()
    out = dict(values)
    for key in keys & out.keys():
        raw = out[key]
        if isinstance(raw, str):
            out[key] = raw.strip().lower() not in ("", "false", "0", "no", "off")
        else:
            out[key] = bool(raw)
    return out


def is_on(values: Mapping[str, Any] | None, key: str) -> bool:
    """قراءةٌ صارمةٌ لمفتاحِ تشغيل — **البابُ الوحيد**.

    كان كلُّ مستهلكٍ يكتب `bool(values.get("use_mock"))` بنفسه، ثمانيَ مرات،
    فوقع الخطأُ ثماني مرات. والبابُ الواحد يجعل تصحيحَه تصحيحاً واحداً.
    """
    if not values:
        return False
    return normalize_toggles(dict(values)).get(key) is True


def is_mock(values: Mapping[str, Any] | None) -> bool:
    """هل يطلب هذا العقدُ مزوّداً وهمياً؟"""
    return is_on(values, "use_mock")

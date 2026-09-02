"""رموزُ الخصم في اللوحة — `admin` حصراً (SPEC القسم 6.6/13، المرحلة 12-ز).

**ولا `StaffUser`**: كوبونٌ سقفُه ألفُ دينار قرارٌ ماليٌّ لا إجراءُ دعمٍ فني —
كصفحة العقود ومفتاح العمولة بالضبط (القسم 13/8).

**ولا حذفَ لرمزٍ استُعمل**: `is_active = false` يُطفئه فلا يُطبَّق بعدها، وحذفُ
صفِّه يجعل رحلاتٍ تحمل `promo_code_id` معلَّقاً في الهواء وتقريرَ كلفةٍ لا يعرف
اسمَ حملته. والحذفُ متاحٌ لرمزٍ لم يُستعمل قط — خطأُ كتابةٍ يُصحَّح لا يُؤرَّخ.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.deps import GrowthManager, DbSession
from app.core.exceptions import Conflict, NotFound
from app.models.enums import AuditAction, CountryCode
from app.models.promo import PromoCode
from app.schemas.promo import PromoCodeCreate, PromoCodeOut, PromoCodeUpdate
from app.services import audit, promo as promo_service

router = APIRouter(prefix="/admin/promo-codes", tags=["admin"])


async def _out(session, row: PromoCode) -> PromoCodeOut:
    """الصفُّ ومعه **المصروفُ والالتزامُ محسوبان** لا مراكمَين في عمودين.

    و`committed` قد يتجاوز `budget_total`: السقفُ يمنع تطبيقاً جديداً لا رحلةً
    تحمل الرمز (القسم 6.6). ورقمٌ مقصوصٌ عند السقف يجعل المشرفَ يظنه صارماً،
    فيُعرض كما هو.
    """
    return PromoCodeOut(
        **{
            field: getattr(row, field)
            for field in (
                "id",
                "code",
                "country_code",
                "discount_type",
                "discount_value",
                "max_discount",
                "budget_total",
                "per_user_limit",
                "total_usage_limit",
                "valid_from",
                "valid_until",
                "is_active",
            )
        },
        spent=await promo_service.spent(session, row.id),
        committed=await promo_service.committed(session, row),
        used_count=await promo_service.usage_count(session, row.id),
    )


@router.get("", response_model=list[PromoCodeOut])
async def list_promo_codes(
    _admin: GrowthManager,
    session: DbSession,
    country_code: CountryCode | None = Query(default=None),
) -> list[PromoCodeOut]:
    stmt = select(PromoCode).order_by(PromoCode.created_at.desc())
    if country_code is not None:
        stmt = stmt.where(PromoCode.country_code == country_code)
    rows = (await session.scalars(stmt)).all()
    return [await _out(session, row) for row in rows]


@router.post("", response_model=PromoCodeOut, status_code=status.HTTP_201_CREATED)
async def create_promo_code(
    payload: PromoCodeCreate, admin: GrowthManager, session: DbSession
) -> PromoCodeOut:
    row = PromoCode(
        **payload.model_dump(exclude={"code"}),
        # يُطبَّع هنا لا في الاستعلام: رمزٌ خُزّن بحروفٍ صغيرة لا تجده مطابقةٌ
        # تُكبّر المدخل، فيبدو العرضُ معطوباً بلا سبب ظاهر
        code=promo_service.normalize(payload.code),
        created_by=admin.id,
    )
    session.add(row)
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.CREATE,
        entity_type="promo_code",
        details={"code": row.code, "country_code": row.country_code.value},
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise Conflict("يوجد رمزٌ بنفس الاسم في هذه الدولة") from exc

    await session.refresh(row)
    return await _out(session, row)


@router.patch("/{promo_id}", response_model=PromoCodeOut)
async def update_promo_code(
    promo_id: uuid.UUID,
    payload: PromoCodeUpdate,
    admin: GrowthManager,
    session: DbSession,
) -> PromoCodeOut:
    """يعدّل رمزاً — **ولا أثرَ رجعياً على رحلةٍ تحمله**.

    القاعدةُ مجمَّدةٌ على الرحلة لحظةَ الطلب (القسم 6.6)، فتعديلُ النسبة هنا
    يحكم ما يأتي بعده. **والرمزُ نفسُه لا يُعدَّل**: رحلاتٌ تشير إليه بمعرّفه،
    وتغييرُ نصِّه يجعل ملصقاً في الشارع يشير إلى عرضٍ آخر.
    """
    row = await session.get(PromoCode, promo_id)
    if row is None:
        raise NotFound("رمز الخصم غير موجود")

    changes = payload.model_dump(exclude_unset=True)
    changed = [
        field for field, value in changes.items() if getattr(row, field) != value
    ]
    for field in changed:
        setattr(row, field, changes[field])

    if changed:
        await audit.record(
            session,
            actor=admin,
            action=AuditAction.UPDATE,
            entity_type="promo_code",
            entity_id=row.id,
            details={"fields": changed},
        )
    await session.commit()
    await session.refresh(row)
    return await _out(session, row)


@router.delete("/{promo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_promo_code(
    promo_id: uuid.UUID, admin: GrowthManager, session: DbSession
) -> None:
    """يحذف رمزاً **لم يُستعمل قط** — وما استُعمل يُطفأ ولا يُحذف.

    رحلاتٌ تحمل `promo_code_id` وتقريرُ كلفةٍ يقرأ اسمَ الحملة: حذفُ الصفِّ
    يترك الأولى معلَّقةً والثاني بلا اسم. والإطفاءُ يمنع التطبيقَ الجديد وحده.
    """
    row = await session.get(PromoCode, promo_id)
    if row is None:
        raise NotFound("رمز الخصم غير موجود")

    if await promo_service.usage_count(session, row.id) > 0:
        raise Conflict("هذا الرمز مستعملٌ — أطفئه بدل حذفه")

    await audit.record(
        session,
        actor=admin,
        action=AuditAction.DELETE,
        entity_type="promo_code",
        entity_id=row.id,
        details={"code": row.code},
    )
    await session.delete(row)
    await session.commit()

"""عروضُ اشتراكات الكباتن في اللوحة — `admin` حصراً (البند ٥٤، القسم ١٣/٨).

**ولا `StaffUser`**: نسبةُ خصمٍ وميزانيةُ تنازلٍ قرارٌ ماليٌّ لا إجراءُ دعمٍ فني
— كصفحة العقود ومفتاح العمولة ورموز الخصم بالضبط.

**ولا حذفَ لعرضٍ اشترى به أحد**: `is_active = false` يُطفئه، وحذفُ صفّه يجعل
اشتراكاتٍ تحمل `offer_id` معلّقاً ويترك `discount_amount` رقماً بلا اسم —
ولذلك المفتاحُ الأجنبيُّ `RESTRICT` أصلاً، فالقاعدةُ ترفض قبل أن يصل الطلب.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.core.deps import GrowthManager, DbSession
from app.core.exceptions import NotFound
from app.models.enums import AuditAction, CountryCode
from app.models.subscription_offer import SubscriptionOffer
from app.schemas.subscription_offer import (
    GrantIn,
    GrantOut,
    OfferIn,
    OfferOut,
    OfferUpdate,
)
from app.services import audit, deletion, offers as offers_service

router = APIRouter(prefix="/admin/subscription-offers", tags=["admin"])


@router.get("", response_model=list[OfferOut])
async def list_offers(
    country_code: CountryCode, _: GrowthManager, session: DbSession
) -> list[OfferOut]:
    """العروضُ ومعها جدولُ التنازل — والمجاميعُ من القاعدة لا من المتصفح."""
    rows = await offers_service.list_offers(session, country_code)
    return [
        OfferOut(**{**OfferOut.model_validate(offer).model_dump(), **stats})
        for offer, stats in rows
    ]


@router.post("", response_model=OfferOut, status_code=status.HTTP_201_CREATED)
async def create_offer(
    country_code: CountryCode,
    payload: OfferIn,
    admin: GrowthManager,
    session: DbSession,
) -> OfferOut:
    offer = await offers_service.create_offer(
        session,
        country=country_code,
        data=payload.model_dump(),
        actor_id=admin.id,
    )
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.CREATE,
        entity_type="subscription_offer",
        entity_id=offer.id,
        details={"fields": sorted(payload.model_dump().keys())},
    )
    await session.commit()
    return OfferOut.model_validate(offer)


@router.patch("/{offer_id}", response_model=OfferOut)
async def update_offer(
    offer_id: uuid.UUID,
    payload: OfferUpdate,
    admin: GrowthManager,
    session: DbSession,
) -> OfferOut:
    """تعديلٌ جزئي — **والإطفاءُ منه**: `is_active = false` لا حذف.

    ولا يمسّ التعديلُ ما وقع: كلُّ اشتراكٍ يحمل سعرَه وخصمَه مجمَّدين.
    """
    data = payload.model_dump(exclude_unset=True)
    offer = await offers_service.update_offer(
        session, offer_id=offer_id, data=data
    )
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="subscription_offer",
        entity_id=offer.id,
        details={"fields": sorted(data.keys())},
    )
    await session.commit()
    return OfferOut.model_validate(offer)


@router.get("/{offer_id}/grants", response_model=list[GrantOut])
async def list_grants(
    offer_id: uuid.UUID, _: GrowthManager, session: DbSession
) -> list[GrantOut]:
    return [
        GrantOut.model_validate(row)
        for row in await offers_service.list_grants(session, offer_id)
    ]


@router.delete("/{offer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_offer(
    offer_id: uuid.UUID, admin: GrowthManager, session: DbSession
) -> None:
    """حذفُ عرضٍ **لم يُستعمل** (البند ٤، §39٫٤).

    **وعرضٌ اشترى به أحدٌ يُطفأ لا يُحذف**: `RESTRICT` في القاعدة يمنعه أصلاً،
    **لكنّه يرمي خطأً لا يفهمه المشرف** — فالسؤالُ يُسأل قبله ليجيب بالعربية
    ويقولَ العدد. وهو ما تقوله وثيقةُ العمود: «عرضٌ يُحذف بعد أن اشترى به
    عشرون كبتناً يمحو **سببَ** خصومهم».
    """
    offer = await session.get(SubscriptionOffer, offer_id)
    if offer is None:
        raise NotFound("العرض غير موجود")
    await deletion.offer_deletable(session, offer)
    before = audit.snapshot(
        offer, ("name", "discount_type", "discount_value", "audience", "is_active")
    )
    await session.delete(offer)
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.DELETE,
        entity_type="subscription_offer",
        entity_id=offer_id,
        details={"deleted": before},
    )
    await session.commit()


@router.post(
    "/{offer_id}/grants", response_model=GrantOut, status_code=status.HTTP_201_CREATED
)
async def grant_offer(
    offer_id: uuid.UUID,
    payload: GrantIn,
    admin: GrowthManager,
    session: DbSession,
) -> GrantOut:
    """منحُ عرضٍ يدويٍّ لكبتن — **بسببٍ مكتوبٍ يدخل سجلَّ التدقيق**.

    والسببُ هنا هو النصُّ نفسُه لا اسمُ حقلٍ تغيّر: هذه منحةٌ بيد إنسان، ومن
    يقرأ السجلَّ بعد شهرٍ يسأل «لماذا هذا الكبتن؟».
    """
    row = await offers_service.grant(
        session,
        offer_id=offer_id,
        driver_id=payload.driver_id,
        actor_id=admin.id,
        note=payload.note,
    )
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.CREATE,
        entity_type="subscription_offer_grant",
        entity_id=row.id,
        details={"driver_id": str(payload.driver_id), "reason": payload.note},
    )
    await session.commit()
    return GrantOut.model_validate(row)

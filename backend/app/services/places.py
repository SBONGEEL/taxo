"""الأماكن المحفوظة — كلُّ منطقٍ يمسّها (`FUTURE-FEATURES` بند 1).

الراوترُ يحلّ من له الحق، والقواعدُ هنا: السقفُ، والاسمُ الفريد، والملكية.

**والملكيةُ تُفحص في كل مسار** (SPEC القسم 14 — لا IDOR): مكانُ مستخدمٍ لا
يُقرأ ولا يُعدَّل ولا يُحذف بمعرِّفه وحده. ولذلك يأخذ كلُّ مسارٍ هنا `user`
ولا يكتفي بـ`place_id`.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, NotFound
from app.models.place import MAX_SAVED_PLACES, SavedPlace
from app.models.ride import make_point
from app.models.user import User


async def list_for_user(session: AsyncSession, user: User) -> list[SavedPlace]:
    """أماكنُه بترتيب الإضافة — والأقدمُ أولاً لأن «المنزل» يُضاف أولاً عادةً."""
    return list(
        (
            await session.scalars(
                select(SavedPlace)
                .where(SavedPlace.user_id == user.id)
                .order_by(SavedPlace.created_at)
            )
        ).all()
    )


async def get_for_user(
    session: AsyncSession, user: User, place_id: uuid.UUID
) -> SavedPlace:
    place = await session.scalar(
        select(SavedPlace).where(
            SavedPlace.id == place_id, SavedPlace.user_id == user.id
        )
    )
    if place is None:
        # نفسُ الجواب لمكانٍ غير موجود ومكانِ غيره: وجودُ المعرِّف نفسُه خبر
        raise NotFound("المكان غير موجود")
    return place


async def create(
    session: AsyncSession,
    user: User,
    *,
    label: str,
    lat: float,
    lng: float,
    address: str | None,
    icon: str,
) -> SavedPlace:
    """يحفظ مكاناً — بسقفٍ واسمٍ فريد.

    **والسقفُ يُفحص قبل الإدراج لا بقيدٍ في القاعدة**: عدٌّ بسيط، ورسالةٌ تقول
    السببَ أوضحُ من `IntegrityError` تُترجَم. أما **تفرّدُ الاسم فمفروضٌ في
    القاعدة** لأنه سباقٌ حقيقي: ضغطتان متزامنتان على «حفظ» باسمٍ واحد.
    """
    count = await session.scalar(
        select(func.count()).select_from(SavedPlace).where(SavedPlace.user_id == user.id)
    )
    if (count or 0) >= MAX_SAVED_PLACES:
        raise Conflict(f"بلغتَ الحد الأقصى ({MAX_SAVED_PLACES}) من الأماكن المحفوظة")

    place = SavedPlace(
        user_id=user.id,
        label=label,
        address=address,
        point=make_point(lat, lng),
        icon=icon,
    )
    session.add(place)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise Conflict("لديك مكانٌ محفوظ بهذا الاسم") from exc
    return place


async def update(
    session: AsyncSession,
    user: User,
    place_id: uuid.UUID,
    *,
    label: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
    address: str | None = None,
    icon: str | None = None,
    address_set: bool = False,
) -> SavedPlace:
    """تعديلٌ جزئي. و`address_set` يفرّق «لم يُرسل» عن «أُرسل فارغاً»."""
    place = await get_for_user(session, user, place_id)

    if label is not None:
        place.label = label
    if icon is not None:
        place.icon = icon
    if address_set:
        place.address = address
    # النقطةُ تتغيّر كوحدة: خطُّ عرضٍ بلا طوله ليس موقعاً
    if lat is not None and lng is not None:
        place.point = make_point(lat, lng)

    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise Conflict("لديك مكانٌ محفوظ بهذا الاسم") from exc
    return place


async def delete(session: AsyncSession, user: User, place_id: uuid.UUID) -> None:
    place = await get_for_user(session, user, place_id)
    await session.delete(place)
    await session.flush()

"""الأماكن المحفوظة للراكب (`FUTURE-FEATURES` بند 1).

راوترٌ رقيق: يحلّ من له الحق ويستدعي `services/places.py`، والقواعدُ هناك.

**و`RiderUser` لا `CurrentUser`**: الأماكنُ المحفوظة شاشةُ راكب — الكبتنُ لا
يطلب رحلةً من التطبيق أصلاً، فبابٌ مفتوحٌ له بابٌ بلا شاشة.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.core.deps import DbSession, RiderUser
from app.schemas.place import PlaceCreate, PlaceOut, PlaceUpdate
from app.services import places as places_service

router = APIRouter(prefix="/me/places", tags=["places"])


def _out(place) -> PlaceOut:
    return PlaceOut(
        id=place.id,
        label=place.label,
        address=place.address,
        lat=place.lat,
        lng=place.lng,
        icon=place.icon,
        created_at=place.created_at,
    )


@router.get("", response_model=list[PlaceOut])
async def list_places(rider: RiderUser, session: DbSession) -> list[PlaceOut]:
    return [_out(place) for place in await places_service.list_for_user(session, rider)]


@router.post("", response_model=PlaceOut, status_code=status.HTTP_201_CREATED)
async def create_place(
    payload: PlaceCreate, rider: RiderUser, session: DbSession
) -> PlaceOut:
    place = await places_service.create(
        session,
        rider,
        label=payload.label.strip(),
        lat=payload.lat,
        lng=payload.lng,
        address=payload.address,
        icon=payload.icon,
    )
    await session.commit()
    # قراءةٌ جديدة: خطا العرض والطول محسوبان في القاعدة ولا يعودان مع INSERT
    return _out(await places_service.get_for_user(session, rider, place.id))


@router.patch("/{place_id}", response_model=PlaceOut)
async def update_place(
    place_id: uuid.UUID,
    payload: PlaceUpdate,
    rider: RiderUser,
    session: DbSession,
) -> PlaceOut:
    fields = payload.model_dump(exclude_unset=True)
    place = await places_service.update(
        session,
        rider,
        place_id,
        label=fields.get("label"),
        lat=fields.get("lat"),
        lng=fields.get("lng"),
        address=fields.get("address"),
        icon=fields.get("icon"),
        # «أُرسل فارغاً» ≠ «لم يُرسل»: الأول يمحو العنوان والثاني يبقيه
        address_set="address" in fields,
    )
    await session.commit()
    return _out(await places_service.get_for_user(session, rider, place.id))


@router.delete("/{place_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_place(
    place_id: uuid.UUID, rider: RiderUser, session: DbSession
) -> None:
    await places_service.delete(session, rider, place_id)
    await session.commit()

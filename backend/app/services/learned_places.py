"""**التعلّمُ من الرحلات المكتملة والبحثُ فيه** — انظر `models/learned_place.py` لما يُحفظ ولماذا."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import CountryCode
from app.models.learned_place import LearnedPlace
from app.services import map_places

#: **رحلتان على الأقلّ** قبل أن يظهر الاسمُ لغير صاحبه
MIN_TRIPS = 2
LIMIT = 5


def cell_of(lat: float, lng: float) -> str:
    return f"{round(lat, 3):.3f},{round(lng, 3):.3f}"


async def learn(session: AsyncSession, country: CountryCode, label: str, lat: float, lng: float) -> None:
    """**رحلةٌ اكتملت إلى ما كتبه راكب** — صفٌّ يُعدّ لا صفوفٌ تتكرّر؛ والموقعُ يُحدَّث بآخر نهاية. **والالتزامُ على المنادي.**"""
    text = " ".join((label or "").split())[:80]
    norm = map_places.normalize(text)[:80]
    if len(norm) < 2:
        return
    now = datetime.now(UTC)
    statement = insert(LearnedPlace).values(
        country_code=country, label=text, label_norm=norm, cell=cell_of(lat, lng), lat=lat, lng=lng, trips=1, last_seen_at=now
    )
    statement = statement.on_conflict_do_update(
        constraint="uq_learned_places_label_cell",
        set_={"trips": LearnedPlace.trips + 1, "lat": lat, "lng": lng, "last_seen_at": now},
    )
    await session.execute(statement)


async def search(
    session: AsyncSession, country: CountryCode, query: str, near: tuple[float, float] | None
) -> list[LearnedPlace]:
    from app.services.maps import fuzzy_score, recent_cutoff

    needle = map_places.normalize(query)
    if len(needle) < 2:
        return []
    rows = await session.scalars(
        select(LearnedPlace).where(
            LearnedPlace.country_code == country,
            LearnedPlace.trips >= MIN_TRIPS,
            LearnedPlace.last_seen_at >= recent_cutoff(),
        )
    )
    ranked = []
    for row in rows:
        score = fuzzy_score(needle, [row.label_norm])
        if score is not None:
            ranked.append((score, -row.trips, row))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [row for _, _, row in ranked[:LIMIT]]

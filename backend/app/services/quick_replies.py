"""**الردودُ السريعة** (أمرُ المالك ٢٠٢٦-١١-٢٠ الرابع، البند ٥٠، SPEC §١١٠) — نصوصٌ يرسلها الطرفُ بنقرةٍ من الفقاعة بلا كتابة.

* **من اللوحة لكلِّ دولة** (`quick_reply_settings`)، وغيابُ الصفِّ أو قائمةٌ فارغةٌ = `DEFAULTS` — فلا فقاعةَ بلا أزرار.
* **ويُرسل الردُّ بباب المحادثة القائم** (`POST /rides/{id}/chat`) — نافذتُه وقفلُه ومرشِّحُه كما هي؛ **فلا بابَ إرسالٍ ثانٍ**.
* **والحفظُ يمرّ بالمرشِّح نفسِه** (`chat_filter.check`): نصٌّ فيه رقمٌ أو رابطٌ يُرفض هنا لا عند كلِّ إرسال.
"""

from __future__ import annotations

from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidInput
from app.models.enums import AuditAction, CountryCode
from app.models.support import QuickReplySetting
from app.models.user import User
from app.services import audit, chat_filter

Side = Literal["driver", "rider"]

#: **نصُّ أمر المالك حرفاً** — الكبتن: «أنا في الطريق»، «وصلت»، «دقيقتين»؛ الراكب: «أنا قادم»، «انتظرني دقيقة»، «أنا عند المدخل»
DEFAULTS: dict[str, list[str]] = {
    "driver": ["أنا في الطريق", "وصلت", "دقيقتين"],
    "rider": ["أنا قادم", "انتظرني دقيقة", "أنا عند المدخل"],
}
#: **أزرارٌ تُلمس أثناء القيادة** — ستّةٌ على الأكثر، وقصيرةٌ تُقرأ بنظرة
MAX_TEXTS = 6
MAX_LENGTH = 40


async def texts_for(session: AsyncSession, country: CountryCode, side: Side) -> list[str]:
    row = await session.get(QuickReplySetting, country)
    found = [] if row is None else list(row.driver_texts if side == "driver" else row.rider_texts)
    return found or list(DEFAULTS[side])


def clean(texts: list[str], field: str) -> list[str]:
    """خالصة: تُقصّ المسافات، ويُسقط الفارغُ والمكرَّر، ويُرفض الطويلُ وما فيه رقمٌ أو رابط — **بالمرشِّح الذي يحرس المحادثة**."""
    out: list[str] = []
    for raw in texts:
        text = " ".join((raw or "").split())
        if not text or text in out:
            continue
        if len(text) > MAX_LENGTH:
            raise InvalidInput(f"الردُّ «{text[:20]}…» أطولُ من {MAX_LENGTH} حرفاً — يُقرأ بنظرةٍ أثناء القيادة", field=field)
        if chat_filter.check(text) is not None:
            raise InvalidInput(f"الردُّ «{text}» فيه رقمٌ أو رابط — لا يُرسل في المحادثة", field=field)
        out.append(text)
    if len(out) > MAX_TEXTS:
        raise InvalidInput(f"{MAX_TEXTS} ردودٍ على الأكثر", field=field)
    return out


async def settings_for(session: AsyncSession, country: CountryCode) -> tuple[list[str], list[str]]:
    return await texts_for(session, country, "driver"), await texts_for(session, country, "rider")


async def save(
    session: AsyncSession, *, country: CountryCode, driver_texts: list[str], rider_texts: list[str], actor: User
) -> tuple[list[str], list[str]]:
    driver = clean(driver_texts, "driver_texts")
    rider = clean(rider_texts, "rider_texts")
    row = await session.get(QuickReplySetting, country, with_for_update=True)
    before = None if row is None else {"driver": list(row.driver_texts), "rider": list(row.rider_texts)}
    if row is None:
        row = QuickReplySetting(country_code=country)
        session.add(row)
    row.driver_texts = driver
    row.rider_texts = rider
    row.updated_by = actor.id
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="quick_reply_settings",
        details={"country_code": country.value, "from": before, "to": {"driver": driver, "rider": rider}},
    )
    await session.flush()
    return driver or list(DEFAULTS["driver"]), rider or list(DEFAULTS["rider"])

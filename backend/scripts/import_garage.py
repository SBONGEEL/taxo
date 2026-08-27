"""استيرادُ كتالوج مركبات الكراج من مادّةٍ مستخرَجة — **يُشغَّل بيدٍ لا بالبذر**.

**ولمَ ليس في `scripts/seed.py`**: البذرُ يكتب المركبةَ الهديّة وحدَها، بعلّةٍ
مكتوبةٍ هناك — «بذرُ مركبةٍ **مسعَّرة** يجعلها تظهر في الإنتاج بلا أن يقرّرها
أحد». وهذا الملفُّ يكتب **٣٦٩ مركبةً مسعَّرة**، فلو دخل مسارَ البذر لَظهر
متجرٌ كاملٌ على أوّل إقلاعِ إنتاج. **فهو أمرٌ يُكتب بيدٍ ويُقرأ في السجلّ.**

**والمصدرُ `var/skin-seed/`**: رسماتٌ موحَّدةُ الاتجاه (`SPEC §28.13`) ومعها
`catalogue.json` يحمل لكلِّ مركبةٍ اسمَها وندرتَها وكميّتَها وأسعارَها —
اشتُقّت كلُّها بالقياس، والوسمُ (`A-00`) يربط الصفَّ بلوحِه الأصليّ.

**ورفعُ الرسمة يمرّ بـ`skin_artwork.ingest` لا بكتابةٍ مباشرة**: هو البابُ
الوحيد لبايتاتِ رسمة — يشمّ النوعَ من البايتات، ويقتطع الهامشَ الشفاف، ويكتب
مقاسَي `store` و`map`، ولا يُقرّ بالنجاح قبل أن يرى الملفَّ بحجمه. ونسخةٌ
ثانيةٌ من منطقه هنا هي «بابان ينشران الشيء نفسَه».

**والمادّةُ علويّةٌ كلُّها**، فالخانتان من مصدرٍ واحدٍ **بحقّ** لا اختصاراً:
تحذيرُ `upload_artwork` («المقاسُ ليس منظوراً») في المجسّم الواقعيِّ يُصغَّر
إلى خريطةٍ تُرى من فوق — وهنا الزاويةُ واحدةٌ في الحالين، والفرقُ مقاسٌ لا
منظور.

**والتشغيل مرّتان لا يضاعف**: المفتاحُ اسمُ المركبة، والموجودُ يُحدَّث ولا
يُنشأ ثانيةً — وهو شرطُ `seed.py` نفسُه.

    docker compose run --rm --no-deps \
      -e DATABASE_URL=... -e REDIS_URL=... backend python -m scripts.import_garage
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.enums import CountryCode
from app.models.vehicle_skin import VehicleSkin, VehicleSkinPrice
from app.services import skin_artwork

#: مصدرُ المادّة — داخل شجرة الخلفية فتراه الحاوية عبر الربط
SOURCE = Path(__file__).resolve().parents[1] / "var" / "skin-seed"


def _log(message: str) -> None:
    print(message, flush=True)


class _FileReader:
    """قارئٌ بشكل `storage.AsyncReader` فوق ملفٍّ على القرص.

    `ingest` يقبل `UploadFile` من FastAPI، وعقدُه **قراءةٌ بالقطع** لا أكثر —
    فملفٌّ محلّيٌّ يكفيه هذا الغلاف، **ولا يُفتح لأجله بابٌ ثانٍ في الخدمة**.
    """

    def __init__(self, path: Path) -> None:
        self._handle = path.open("rb")
        self.filename = path.name
        self.content_type = "image/png"

    async def read(self, size: int = -1) -> bytes:
        return self._handle.read(size)

    async def close(self) -> None:
        self._handle.close()


async def _upsert(session, row: dict) -> tuple[VehicleSkin, bool]:
    """يكتب صفَّ المركبة — **والمفتاحُ الاسمُ** فالتشغيلُ الثاني تحديث."""
    skin = await session.scalar(
        select(VehicleSkin).where(VehicleSkin.name == row["name"])
    )
    created = skin is None
    if skin is None:
        skin = VehicleSkin(name=row["name"])
        session.add(skin)

    skin.rarity = row["rarity"]
    skin.max_supply = row["max_supply"]
    skin.visible_before_accept = row["visible_before_accept"]
    # **المادّةُ مرسومةٌ من فوق فتدور مع اتجاه السيارة** — والرندرُ الواقعيُّ
    # وحدَه هو الذي لا يدور (`models/vehicle_skin.py`)
    skin.map_rotates = True
    skin.is_active = True
    await session.flush()
    return skin, created


async def _prices(session, skin: VehicleSkin, prices: dict[str, str]) -> None:
    """سعرٌ لكلِّ سوق — **والعملةُ تُشتقّ من الدولة** ولا تُكتب هنا."""
    existing = {
        price.country_code: price
        for price in (
            await session.execute(
                select(VehicleSkinPrice).where(VehicleSkinPrice.skin_id == skin.id)
            )
        ).scalars()
    }
    for code, amount in prices.items():
        country = CountryCode(code)
        value = Decimal(amount)
        current = existing.get(country)
        if current is None:
            session.add(
                VehicleSkinPrice(skin_id=skin.id, country_code=country, price=value)
            )
        else:
            current.price = value


async def main() -> None:
    catalogue_path = SOURCE / "catalogue.json"
    if not catalogue_path.is_file():
        _log(f"✗ لا كتالوجَ في {catalogue_path} — تُستخرَج المادّةُ أوّلاً.")
        raise SystemExit(2)

    rows = json.loads(catalogue_path.read_text(encoding="utf-8"))
    only = os.environ.get("GARAGE_LIMIT", "").strip()
    if only:
        rows = rows[: int(only)]

    _log(f"الكتالوج: {len(rows)} مركبة من {SOURCE}")
    created = updated = art = 0
    async with SessionLocal() as session:
        for index, row in enumerate(rows, 1):
            skin, is_new = await _upsert(session, row)
            await _prices(session, skin, row["prices"])
            created += is_new
            updated += not is_new

            # **الرسمةُ تُرفع مرّةً**: إعادةُ التشغيل لا تكتب ملفّاتٍ جديدةً
            # لمركبةٍ رسمتُها موضوعةٌ أصلاً — وإلا تراكمت نفايةٌ على القرص
            source = SOURCE / f"{row['tag']}.png"
            if source.is_file() and not (skin.store_image_path and skin.map_image_path):
                reader = _FileReader(source)
                try:
                    stored = await skin_artwork.ingest(reader, folder=str(skin.id))
                finally:
                    await reader.close()
                skin.asset_key = None
                skin.store_image_path = stored.store_path
                skin.map_image_path = stored.map_path
                art += 1

            if index % 50 == 0:
                await session.commit()
                _log(f"  … {index}/{len(rows)}")

        await session.commit()

    _log(f"✓ مركبات: {created} جديدة · {updated} محدَّثة · {art} رسمةً مرفوعة")


if __name__ == "__main__":
    if not SOURCE.is_dir():
        _log(f"✗ المصدرُ غيرُ موجود: {SOURCE}")
        sys.exit(2)
    asyncio.run(main())

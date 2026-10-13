"""تحميلُ مناطق التسعير لسوقٍ من ملفّه في الشجرة (SPEC §٧٤-أ/٥) — **إضافةً لما غاب، وتحديثاً لحدود ما وُجد، ولا يمسّ قرارَ المالك**.

    python scripts/load_pricing_zones.py DZ

**الجزائر**: ٥٨ ولايةً كما هي قانوناً اليوم، **والإحدى عشرة الجديدة** (القانون ٢٦-٠٦، تعمل من ٢٠٢٧-٠١-٠١) **مضمومةٌ إلى أمّهاتها** — والمصدرُ
حدودُ OpenStreetMap (ODbL). **والقائمةُ «الوعرة» المقترحةُ تُوسَم في التحميل الأوّل وحدَه** بالنسبة الافتراضية (+25%): ما وُجد قبلاً لا
يُمسّ وسمُه ولا نسبتُه — **وتُعدَّل من «مناطق التسعير» في اللوحة**.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db import SessionLocal, engine  # noqa: E402
from app.models.enums import CountryCode  # noqa: E402
from app.services import pricing_zones  # noqa: E402

#: **المقترحُ الأوّل للمالك — بعللها** (§٧٤-أ/٥: «الجبليّة كتيزي وزو وبجاية؛ والصحراءُ العميقة كتمنراست وإليزي وأدرار وتندوف وجانت»)
RUGGED_PROPOSAL: dict[CountryCode, dict[str, str]] = {
    CountryCode.DZ: {
        "15": "جبالُ جرجرة — قرى معلّقةٌ وطرقٌ متعرّجةٌ شديدةُ الانحدار",
        "06": "جبالُ البابور وجرجرة — منحدراتٌ وطرقٌ جبليّةٌ ضيّقة",
        "18": "جبالُ البابور الساحليّة — طرقٌ متعرّجةٌ بين الجبل والبحر",
        "11": "الصحراءُ الكبرى العميقة — مسافاتٌ فارغةٌ طويلةٌ ومسالكُ رمليّةٌ وحرارةٌ قاسية",
        "33": "الطاسيلي والصحراءُ العميقة — مسالكُ وعرةٌ ومسافاتٌ بلا خدمات",
        "01": "الصحراءُ العميقة — مسافاتٌ طويلةٌ بين القصور وطرقٌ تغمرها الرمال",
        "37": "أقصى الجنوب الغربيّ — مسافاتٌ فارغةٌ وطرقٌ صحراويّة",
        "56": "الطاسيلي ناجر — جبالٌ صحراويّةٌ ومسالكُ وعرة",
        "54": "أقصى الجنوب — مسالكُ صحراويّةٌ بلا شبكة طرق",
        "50": "أقصى الجنوب الغربيّ — مسالكُ صحراويّةٌ ومسافاتٌ فارغة",
        "53": "قلبُ الصحراء — مسافاتٌ طويلةٌ ورمالٌ وحرارةٌ قاسية",
        "49": "العرق الغربيّ الكبير — رمالٌ ومسافاتٌ بين القصور",
        "52": "الساورة والعرق — مسالكُ رمليّةٌ ومسافاتٌ طويلة",
    },
}


async def main(country: CountryCode) -> None:
    async with SessionLocal() as session:
        result = await pricing_zones.load_country(session, country, rugged_codes=RUGGED_PROPOSAL.get(country))
        await session.commit()
    await engine.dispose()
    print(f"{country.value}: أُضيف {result['added']} · حُدِّث {result['updated']} — {result['attribution']}")


if __name__ == "__main__":
    asyncio.run(main(CountryCode(sys.argv[1] if len(sys.argv) > 1 else "DZ")))

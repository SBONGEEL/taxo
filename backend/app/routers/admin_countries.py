"""الدولُ كما تراها اللوحة — **كلُّها دائماً** (SPEC §24).

`GET /config` مصفّىً للتطبيقات: الدولةُ المطفأةُ لا تُنشر فيه. ولو قرأت اللوحةُ
منه لاختفى عنها **ما جاءت لتشعله** — ولاختفت معه عملتُها وساعاتُ هدوئها، وهي
ما تحتاجه شاشاتُ التسعيرة والحملات لتُجهّز سوقاً قبل فتحه.

والوصفُ نفسُه يبنيه `services/country_config.build` الذي يبني وصفَ `/config` —
بانٍ واحدٌ لبابين (الشكلُ الثامن).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.currency import COUNTRY_NAME
from app.core.deps import DbSession, StaffUser
from app.models.enums import CountryCode
from app.schemas.settings import CountriesOut, CountryRow
from app.services import country_config

router = APIRouter(prefix="/admin/countries", tags=["admin"])


@router.get("", response_model=CountriesOut)
async def list_countries(session: DbSession, _: StaffUser) -> CountriesOut:
    """كلُّ الأسواق بحالها — و`StaffUser` لأن رؤيتها سياقٌ لا قرار."""
    return CountriesOut(
        countries=[
            CountryRow(
                country_code=country,
                name=COUNTRY_NAME[country],
                visible=await country_config.is_visible(session, country),
                config=await country_config.build(session, country),
            )
            for country in CountryCode
        ]
    )

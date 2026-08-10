from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.models.enums import CountryCode, Currency, VehicleCategory
from app.schemas.auth import AuthMethodResponse


class CountryConfigOut(BaseModel):
    country_code: CountryCode
    currency: Currency
    features: dict[str, bool]
    vehicle_categories: list[VehicleCategory]
    # بادئةُ الدولة وطولُ رقمها الوطني — من `core/phone.py` وحده، ليرسم
    # التطبيقان الحقل بلا كتابة «962» في كودهما
    dial_code: str
    national_number_length: int


class ConfigOut(BaseModel):
    """إعدادات عامة للواجهات (SPEC القسم 2).

    لا تحوي إلا ما هو عام بطبيعته: مفاتيح الميزات، العملات، والتوكن العام
    للخرائط. أي حقل سرّي في عقود المزودين لا يمر من هنا أبداً.
    """

    app: str
    auth: AuthMethodResponse
    countries: list[CountryConfigOut]
    providers: dict[str, dict[str, Any]]
    # الدولة التي تفترضها شاشاتُ ما قبل الدخول: لا حسابَ بعد فلا دولةَ
    # معروفة، والتصميم بلا منتقي دول. إعدادُ نشرٍ لا سرّ — مكانه `settings`
    # كـ`cors_origins` و`card_return_url`
    default_country_code: CountryCode

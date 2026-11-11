"""شاشةُ «الدفع بالبطاقة المصرفية» في اللوحة (NOWPayments، أمرُ المالك ٢٠٢٦-١١-١١)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CountryCode
from app.schemas.payment_request import AdminPaymentMethodOut, AdminPaymentRequestOut


class CardPayCountryOut(BaseModel):
    country_code: CountryCode
    #: **مقفلةٌ بالشيفرة** — لا تُشعَل من اللوحة (الجزائرُ وليبيا)
    locked: bool
    enabled: bool


class CardPayRequestOut(AdminPaymentRequestOut):
    """**دفعةُ بطاقةٍ في قائمة المالك** (قرارُه ٢٠٢٦-١١-١١): المستحقُّ (`amount`) · خصمُ البطاقة · ما وصل (`gateway_message`) · الرسمُ
    الذي تحمّلته TAXO. **والدولارُ محسوبٌ بسعر العقد الآن** — والرسمُ بالدينار هو المكتوبُ على الطلب عند فتحه."""

    #: **خصمُ البطاقة بالدولار** — المستحقُّ حين تتحمّل TAXO الرسم، والمستحقُّ ورسمُه حين يتحمّله الدافع
    card_charge_usd: Decimal | None = None
    #: **رسمُ الشريك الذي تحمّلته TAXO** — بالدولار (محسوب) وبالدينار (المكتوبُ على الطلب)؛ `null` حين حمله الدافع
    taxo_fee_usd: Decimal | None = None
    taxo_fee: Decimal | None = None


class CardPayOverviewOut(BaseModel):
    countries: list[CardPayCountryOut]
    #: **أُدخل المفتاحان** (مفتاحُ API وسرُّ الإشعارات) — بلا قيمهما
    keys_entered: bool
    contract_active: bool
    #: **جاهزٌ للكبتن** — عقدٌ مفعَّلٌ بمفتاحيه؛ وإلا فالطريقةُ مخفيّةٌ تلقائيّاً
    ready: bool
    sandbox: bool
    usd_per_jod: Decimal | None
    daily_cap: Decimal | None
    today_total: Decimal
    webhook_url: str
    partner: str | None
    partner_fee: str | None
    method: AdminPaymentMethodOut | None
    requests: list[CardPayRequestOut]


class CardPayLimitsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: **حدّا الدفعة الواحدة بالدينار** — `null` بلا حدّ
    min_amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    max_amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    #: **سقفُ مجموع اليوم** لكلِّ الكباتن معاً — `null` بلا سقف
    daily_cap: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    usd_per_jod: Decimal | None = Field(default=None, gt=0, max_digits=8, decimal_places=4)


class CardPayLiveOut(BaseModel):
    external_id: str
    status: str | None
    price: str | None
    paid: str | None
    received: str | None

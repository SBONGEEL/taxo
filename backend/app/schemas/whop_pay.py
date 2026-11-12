"""شاشةُ «الدفع بالبطاقة عبر Whop» في اللوحة (أمرُ المالك ٢٠٢٦-١١-١٣)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CountryCode
from app.schemas.payment_request import AdminPaymentMethodOut, AdminPaymentRequestOut


class WhopSwitchOut(BaseModel):
    #: **مفتاحُ الأردن** — يُكتب من `PUT /admin/settings/feature-flags` كأيِّ مفتاح
    key: str
    title: str
    hint: str
    enabled: bool


class WhopMethodOut(BaseModel):
    #: «الكباتن» أو «الركّاب»
    audience: str
    method: AdminPaymentMethodOut


class WhopRequestOut(AdminPaymentRequestOut):
    """**دفعةُ Whop في قائمة المالك** — النوعُ (`purpose` والجمهور) · الحال · المبلغ · مرجعُ Whop (`external_id`) · وما قاله Whop
    (`gateway_code`/`gateway_message`: المبلغُ الواصلُ وعملتُه). **ورسمُ Whop لا يُكتب على الطلب** — يُخصم من رصيد المالك عند Whop."""

    audience: str


class WhopOverviewOut(BaseModel):
    switches: list[WhopSwitchOut]
    #: **دولٌ مقفلةٌ بالشيفرة** — لا يُشعل فيها شيء (الجزائرُ وليبيا)
    locked_countries: list[CountryCode]
    #: **أُدخلت القيمُ الثلاث** (مفتاحُ API وسرُّ الإشعارات ومعرّفُ الحساب) — بلا قيمها
    keys_entered: bool
    contract_active: bool
    ready: bool
    sandbox: bool
    #: **عملةُ الخصم** كما في العقد — `JOD` أو `USD`
    currency: str | None
    webhook_url: str
    methods: list[WhopMethodOut]
    requests: list[WhopRequestOut]


class WhopLimitsIn(BaseModel):
    """**حدّا الدفعة الواحدة لطريقةٍ واحدة** بالدينار — `null` بلا حدّ. النموذجُ كاملاً في كلِّ حفظ."""

    model_config = ConfigDict(extra="forbid")

    min_amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    max_amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)


class WhopLiveOut(BaseModel):
    external_id: str
    payments: list[dict]

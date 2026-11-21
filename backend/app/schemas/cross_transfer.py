"""مخطّطاتُ **التحويل بين الدول** (أمرُ المالك ٢٠٢٦-١١-٢٢).

**طرفا العرض كائنان لكلٍّ عملتُه** (`send` و`receive`) لا حقولٌ مسطّحة: صيغةُ المال على السلك تقرأ عملةَ الكائن الذي يحمل المبلغ
(`core/money_wire.py`)، **وكائنٌ بعملتين يُصاغ مبلغُه الجزائريُّ بخانات الأردنيّ أو العكس**.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CountryCode, Currency


class QuoteSendOut(BaseModel):
    """ما يدفعه المرسلُ بعملته: المبلغ، والرسم، ومجموعُهما المخصومُ من محفظته."""

    currency: Currency
    amount: Decimal
    fee: Decimal
    total: Decimal
    #: **رصيدُك بعده** — محسوبٌ هنا لا في المتصفّح (§14)، و`None` حين لا يكفي الرصيدُ (فرضٌ لا يقع لا يُرسم سالباً)
    balance_after: Decimal | None


class QuoteReceiveOut(BaseModel):
    """ما يصل المستلمَ بعملته."""

    currency: Currency
    amount: Decimal


class CrossQuoteOut(BaseModel):
    """**ورقةُ التأكيد كما تُعرض** — محسوبةٌ في الخلفية (§14)، **والاسمُ مخفيٌّ جزئيّاً** (أمرُ المالك)."""

    recipient_name: str
    recipient_country: CountryCode
    send: QuoteSendOut
    receive: QuoteReceiveOut
    #: كم يصل من عملة المستلم مقابل واحدٍ من عملة المرسل — نصٌّ عشريٌّ بلا أصفارٍ زائدة
    rate: str
    fee_percent: str
    rate_set_at: datetime


class FxRateOut(BaseModel):
    """اتّجاهٌ واحدٌ في اللوحة — **و`None` لما لم يُضبط بعد** (لا صفرٌ يُقرأ سعراً)."""

    from_currency: Currency
    to_currency: Currency
    rate: str | None
    fee_percent: str | None
    set_at: datetime | None
    set_by_name: str | None


class FxRateUpdate(BaseModel):
    from_currency: Currency
    to_currency: Currency
    rate: Decimal = Field(gt=0, max_digits=18, decimal_places=8)
    fee_percent: Decimal = Field(default=Decimal("0"), ge=0, le=20, max_digits=5, decimal_places=2)


class CrossLimitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    country_code: CountryCode
    currency: Currency
    daily_limit: Decimal
    monthly_limit: Decimal


class CrossLimitUpdate(BaseModel):
    daily_limit: Decimal = Field(ge=0, max_digits=12, decimal_places=3)
    monthly_limit: Decimal = Field(ge=0, max_digits=12, decimal_places=3)

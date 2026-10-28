"""**إيصالاتُ PDF للشحن والاشتراك** (SPEC §٨٨/٢، أمرُ المالك ٢٠٢٦-١٠-٢٨، C7) — لدفعةٍ اعتُمدت في نظام الدفع الجديد.

**ما في الإيصال**: TAXO · نوعُه (شحنُ رصيد أو اشتراك) · مرجعُ TAXO (`TX-…`) · التاريخُ بيوم البلد · الطريقة · **المبلغُ المقيَّد** (لا دعوى
صاحبه) · رسومُ الوسيط حين يحملها الدافع · الخطّةُ في الاشتراك · الاسمُ كما في الحساب. **ولا رقمَ بطاقةٍ ولا RIP ولا هاتف.**

**والعربيّةُ تُشكَّل** (`fpdf2` بـ`uharfbuzz`) بخطِّ IBM Plex Sans Arabic المنسوخ من خطوط الموقع (رخصةُ OFL) — فالحروفُ متّصلةٌ والاتجاهُ من
اليمين. **والأرقامُ لاتينيّة** كما في كلِّ شاشة (قاعدةُ المشروع).

**والرابطُ ورقةُ دخولٍ قصيرة**: يُفتح في المتصفّح خارج التطبيق (لا ترويسةَ مصادقة)، فالرمزُ هو الصلاحية — خمسُ دقائقَ ومرّةً واحدة،
كتنزيل النسخ في اللوحة.
"""

from __future__ import annotations

import secrets
from datetime import datetime
from pathlib import Path

from app.core.currency import amount_text
from app.core.exceptions import InvalidInput
from app.models.enums import PaymentRequestPurpose, PaymentRequestStatus
from app.models.payment_request import PaymentRequest
from app.models.user import User

FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
TOKEN_KEY = "receipt:token:{token}"
TOKEN_TTL_SECONDS = 300
#: **ما يُصدر له إيصال** — ما دخل المالُ فيه؛ والمردودُ يُصدر بحاله
RECEIPTABLE = (PaymentRequestStatus.APPROVED, PaymentRequestStatus.REFUNDED)


def require_receiptable(request: PaymentRequest) -> None:
    if request.status not in RECEIPTABLE:
        raise InvalidInput("الإيصالُ لدفعةٍ اعتُمدت — هذه لم تُعتمد بعد", field="request_id")


async def issue_token(redis, *, owner: User, request: PaymentRequest) -> str:
    require_receiptable(request)
    token = secrets.token_urlsafe(24)
    await redis.set(TOKEN_KEY.format(token=token), f"{owner.id}|{request.id}", ex=TOKEN_TTL_SECONDS)
    return token


async def take_token(redis, token: str) -> tuple[str, str] | None:
    key = TOKEN_KEY.format(token=token)
    value = await redis.get(key)
    if not value:
        return None
    await redis.delete(key)
    owner_id, _, request_id = str(value).partition("|")
    return owner_id, request_id


def _when(moment: datetime, zone) -> str:
    local = moment.astimezone(zone)
    return local.strftime("%Y-%m-%d %H:%M")


def render(
    request: PaymentRequest, *, owner: User, plan_name: str | None, zone, ref: str
) -> bytes:
    """**الإيصالُ نفسُه** — صفحةٌ واحدةٌ بمقاس A5، عربيّةٌ مشكَّلة."""
    from fpdf import FPDF

    pdf = FPDF(format="A5")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_font("plex", "", str(FONTS / "IBMPlexSansArabic-400.ttf"))
    pdf.add_font("plex", "B", str(FONTS / "IBMPlexSansArabic-700.ttf"))
    pdf.set_text_shaping(use_shaping_engine=True, direction="rtl", script="arab", language="ar")
    pdf.add_page()
    width = pdf.w - pdf.l_margin - pdf.r_margin

    pdf.set_font("plex", "B", 22)
    pdf.cell(width, 12, "TAXO", align="C", new_x="LMARGIN", new_y="NEXT")
    title = "إيصال اشتراك" if request.purpose is PaymentRequestPurpose.SUBSCRIPTION else "إيصال شحن رصيد"
    pdf.set_font("plex", "B", 15)
    pdf.cell(width, 9, title, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    credited = request.credited_amount or request.amount
    rows: list[tuple[str, str]] = [
        ("المرجع", ref),
        ("التاريخ", _when(request.reviewed_at or request.created_at, zone)),
        ("الاسم", owner.name or "—"),
        ("طريقة الدفع", request.provider.name),
        ("المبلغ", amount_text(credited, request.currency)),
    ]
    if request.purpose is PaymentRequestPurpose.SUBSCRIPTION and plan_name:
        rows.append(("الخطّة", plan_name))
    if request.fee_payer == "user" and request.fee_amount:
        rows.append(("رسوم الوسيط (على الدافع)", amount_text(request.fee_amount, request.currency)))
    rows.append(("الحال", "مردودة" if request.status is PaymentRequestStatus.REFUNDED else "مدفوعة"))

    label_w, value_w = width * 0.42, width * 0.58
    for label, value in rows:
        pdf.set_font("plex", "", 11)
        y = pdf.get_y()
        # **من اليمين**: التسميةُ في العمود الأيمن، والقيمةُ يسارَها
        pdf.set_xy(pdf.l_margin + value_w, y)
        pdf.cell(label_w, 9, label, border="B", align="R")
        pdf.set_xy(pdf.l_margin, y)
        pdf.set_font("plex", "B", 11)
        pdf.cell(value_w, 9, value, border="B", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    pdf.set_font("plex", "", 9)
    pdf.multi_cell(width, 6, "إيصالٌ صادرٌ من TAXO بما قُيِّد في محفظتك. احتفظ به لسجلّاتك.", align="C")
    return bytes(pdf.output())

"""**ملفّاتُ دفعة بطاقات TAXO** (أمرُ المالك ٢٠٢٦-١١-١٣، «TAXO cards — full upgrade» البندان ١ و١٣).

ثلاثةُ ملفّاتٍ من الصفوف نفسِها، **وكلُّها بكلمة سرٍّ يكتبها من ينزّلها لحظةَ التنزيل**:

1. **`.xlsx` حقيقيّ** — عمودٌ لكلِّ حقل، ترويسةٌ عربيّة، ورقةٌ من اليمين، ترويسةٌ مجمَّدة، **والمبلغُ رقمٌ لا نصّ**، والتاريخُ بيوم
   السوق، واسمُ الدفعة وتاريخُها أعلى الورقة. **ويُعمّى الملفُّ كلُّه** (`msoffcrypto`، تعميةُ Office القياسيّة بـAES) — فلا يُفتح
   بلا كلمة السرّ في Excel نفسِه.
2. **PDF قائمةٌ للطباعة** — الصفوفُ نفسُها، A4 أفقيّ، مشفَّرٌ بكلمة السرّ (`fpdf2` بـAES-256).
3. **ورقةُ المطبعة** — A4 بعشر بطاقاتٍ في الصفحة، خطوطُ قصٍّ متقطّعة، أرقامٌ تسلسليّةٌ متتابعة، **ورمزُ QR لكلِّ بطاقة**.

**والرمزُ في QR بعد `#`** (`https://app.tajora.ly/redeem#<الرمز>`): ما بعد العلامة **لا يرسله المتصفّحُ إلى أيِّ خادم**، فلا يقع الرمزُ
في سجلِّ وصولٍ ولا في حافّة — والتطبيقُ يقرؤه من الكاميرا مباشرةً.

**ولا يكتب هذا الملفُّ شيئاً في سجلّ**: لا رمزَ ولا كلمةَ سرّ. وما يُسجَّل (من نزّل ومتى وأيَّ دفعة) يكتبه الباب، بلا رمز.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from app.core.currency import amount_text
from app.core.exceptions import InvalidInput

FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PDF_MEDIA_TYPE = "application/pdf"

#: **رابطُ الاستعمال في QR** — والرمزُ بعد `#` فلا يبلغ خادماً
REDEEM_URL = "https://app.tajora.ly/redeem#{code}"
#: أقصرُ كلمة سرٍّ تُقبل للملفّ — ملفٌّ فيه رموزُ مالٍ لا يُقفل بثلاثة أحرف
MIN_PASSWORD = 8
MASKED = "••••-••••-••••-••••"

_MONEY_FORMAT = "0.000"
_TIME_FORMAT = "yyyy-mm-dd hh:mm"

STATUS_LABEL = {
    "active": "غير مستعملة",
    "redeemed": "مستعملة",
    "expired": "منتهية",
    "cancelled": "ملغاة",
    "not_started": "لم تبدأ بعد",
}


@dataclass(frozen=True)
class BatchMeta:
    """ما يُكتب أعلى كلِّ ملفّ — **الدفعةُ لا تُقرأ بعد شهرٍ بلا سياقها**."""

    title: str  # «دفعة DZ-B0007»
    country: str
    currency: str
    amount: Decimal
    valid_from: datetime
    expires_at: datetime
    created_at: datetime
    shop: str | None
    zone: object  # ZoneInfo السوق


@dataclass(frozen=True)
class CardRow:
    serial: str
    code: str | None  # None ⇐ الرمزُ لا يُعرض لهذا القارئ
    amount: Decimal
    status: str
    redeemed_at: datetime | None = None
    redeemed_by: str | None = None


def check_password(password: str) -> str:
    if len(password or "") < MIN_PASSWORD:
        raise InvalidInput(f"كلمةُ سرّ الملفّ {MIN_PASSWORD} أحرفٍ على الأقلّ", field="password")
    return password


def _local(moment: datetime | None, zone) -> datetime | None:
    return None if moment is None else moment.astimezone(zone).replace(tzinfo=None)


def _local_text(moment: datetime | None, zone) -> str:
    local = _local(moment, zone)
    return "—" if local is None else local.strftime("%Y-%m-%d %H:%M")


def _head(meta: BatchMeta, count: int) -> str:
    return (
        f"السوق {meta.country} · الفئة {amount_text(meta.amount, meta.currency)} {meta.currency}"
        f" · من {_local_text(meta.valid_from, meta.zone)} إلى {_local_text(meta.expires_at, meta.zone)}"
        f" · الإصدار {_local_text(meta.created_at, meta.zone)} · {count} بطاقة"
        + (f" · المحلّ {meta.shop}" if meta.shop else "")
    )


# ---------------------------------------------------------------------------------------------------------------- Excel


def batch_xlsx(meta: BatchMeta, rows: list[CardRow], *, password: str) -> bytes:
    """**ملفُّ Excel معمًّى** — ولا يُعاد إلا مُعمًّى: لا مسارَ يُخرجه مكشوفاً."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    check_password(password)
    book = Workbook()
    sheet = book.active
    sheet.title = "البطاقات"
    sheet.sheet_view.rightToLeft = True

    sheet.append([f"TAXO — {meta.title}"])
    sheet["A1"].font = Font(bold=True, size=14)
    sheet.append([_head(meta, len(rows))])
    sheet.append([])
    headers = ["#", "الرقم التسلسلي", "الرمز", "القيمة", "العملة", "الحالة", "تبدأ", "تنتهي", "استُعملت في", "استعملها"]
    sheet.append(headers)
    fill = PatternFill("solid", fgColor="FFE9D6")
    for cell in sheet[4]:
        cell.font = Font(bold=True)
        cell.fill = fill
        cell.alignment = Alignment(horizontal="center")

    for index, row in enumerate(rows, start=1):
        sheet.append([
            index,
            row.serial,
            row.code if row.code is not None else MASKED,
            row.amount,
            meta.currency,
            STATUS_LABEL.get(row.status, row.status),
            _local(meta.valid_from, meta.zone),
            _local(meta.expires_at, meta.zone),
            _local(row.redeemed_at, meta.zone),
            row.redeemed_by or "",
        ])
        line = sheet.max_row
        sheet.cell(line, 4).number_format = _MONEY_FORMAT
        for column in (7, 8, 9):
            sheet.cell(line, column).number_format = _TIME_FORMAT

    sheet.freeze_panes = "A5"
    for column, width in zip("ABCDEFGHIJ", (6, 18, 24, 11, 8, 14, 17, 17, 17, 22), strict=True):
        sheet.column_dimensions[column].width = width

    plain = BytesIO()
    book.save(plain)
    return _encrypt_office(plain.getvalue(), password)


def _encrypt_office(data: bytes, password: str) -> bytes:
    from msoffcrypto.format.ooxml import OOXMLFile  # تعميةُ Office القياسيّة (Agile/AES) — يفتحها Excel بكلمة السرّ

    target = BytesIO()
    OOXMLFile(BytesIO(data)).encrypt(password, target)
    return target.getvalue()


# ---------------------------------------------------------------------------------------------------------------- PDF


def _pdf(orientation: str, password: str):
    from fpdf import FPDF
    from fpdf.enums import EncryptionMethod

    check_password(password)
    pdf = FPDF(orientation=orientation, format="A4")
    pdf.add_font("plex", "", str(FONTS / "IBMPlexSansArabic-400.ttf"))
    pdf.add_font("plex", "B", str(FONTS / "IBMPlexSansArabic-700.ttf"))
    pdf.set_text_shaping(use_shaping_engine=True, direction="rtl", script="arab", language="ar")
    pdf.set_encryption(owner_password=password, user_password=password, encryption_method=EncryptionMethod.AES_256)
    return pdf


_LIST_COLUMNS = (("#", 0.06), ("الرقم التسلسلي", 0.18), ("الرمز", 0.24), ("القيمة", 0.12), ("الحالة", 0.12), ("استُعملت في", 0.14), ("استعملها", 0.14))


def batch_pdf(meta: BatchMeta, rows: list[CardRow], *, password: str) -> bytes:
    """**قائمةُ الدفعة للطباعة** — A4 أفقيّ، الأعمدةُ نفسُها التي في Excel، والجدولُ من اليمين."""
    pdf = _pdf("L", password)
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    width = pdf.w - pdf.l_margin - pdf.r_margin

    pdf.set_font("plex", "B", 16)
    pdf.cell(width, 10, f"TAXO — {meta.title}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("plex", "", 10)
    pdf.cell(width, 7, _head(meta, len(rows)), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    def line(values: list[str], *, bold: bool) -> None:
        pdf.set_font("plex", "B" if bold else "", 10 if bold else 9.5)
        if bold:
            pdf.set_fill_color(255, 233, 214)
        x = pdf.l_margin + width
        y = pdf.get_y()
        for (_title, share), value in zip(_LIST_COLUMNS, values, strict=True):
            x -= width * share
            pdf.set_xy(x, y)
            pdf.cell(width * share, 7.5, value, border=1, align="C", fill=bold)
        pdf.set_xy(pdf.l_margin, y + 7.5)

    headers = [title for title, _share in _LIST_COLUMNS]
    line(headers, bold=True)
    for index, row in enumerate(rows, start=1):
        if pdf.get_y() > pdf.h - 18:
            pdf.add_page()
            line(headers, bold=True)
        line([
            str(index), row.serial, row.code or MASKED, amount_text(row.amount, meta.currency),
            STATUS_LABEL.get(row.status, row.status), _local_text(row.redeemed_at, meta.zone), row.redeemed_by or "—",
        ], bold=False)
    return bytes(pdf.output())


def qr_png(payload: str) -> bytes:
    import segno

    out = BytesIO()
    segno.make(payload, error="m").save(out, kind="png", scale=8, border=1)
    return out.getvalue()


#: **ورقةُ المطبعة**: عمودان × خمسةُ صفوف = عشرُ بطاقاتٍ في A4 (قرابةَ ٩٣×٥٤ مم — مقاسُ بطاقة الشحن)
SHEET_COLUMNS = 2
SHEET_ROWS = 5


def print_sheet_pdf(meta: BatchMeta, rows: list[CardRow], *, password: str) -> bytes:
    """**ورقةُ المطبعة** — عشرُ بطاقاتٍ في الصفحة بخطوط قصٍّ متقطّعة، تسلسلٌ متتابع، وQR لكلّ بطاقة.

    **بطاقةٌ بلا رمزٍ لا تُطبع** — ورقةُ المطبعة لرموزٍ تُباع، والقائمةُ المحجوبةُ مكانُها Excel/PDF."""
    if any(row.code is None for row in rows):
        raise InvalidInput("ورقةُ المطبعة تحتاج الرموزَ كاملة", field="format")
    pdf = _pdf("P", password)
    pdf.set_auto_page_break(auto=False)
    margin_x, margin_y = 12.0, 14.0
    cell_w = (pdf.w - 2 * margin_x) / SHEET_COLUMNS
    cell_h = (pdf.h - 2 * margin_y) / SHEET_ROWS
    per_page = SHEET_COLUMNS * SHEET_ROWS
    value = f"{amount_text(meta.amount, meta.currency)} {meta.currency}"
    until = _local_text(meta.expires_at, meta.zone)[:10]
    ordered = sorted(rows, key=lambda row: row.serial)  # **التسلسلُ متتابعٌ في الورق** أيّاً كان ترتيبُ الطلب

    for start in range(0, len(ordered), per_page):
        pdf.add_page()
        pdf.set_draw_color(150, 150, 150)
        pdf.set_line_width(0.2)
        with pdf.local_context():
            pdf.set_dash_pattern(dash=2, gap=1.5)
            for c in range(SHEET_COLUMNS + 1):
                x = margin_x + c * cell_w
                pdf.line(x, margin_y - 6, x, pdf.h - margin_y + 6)
            for r in range(SHEET_ROWS + 1):
                y = margin_y + r * cell_h
                pdf.line(margin_x - 6, y, pdf.w - margin_x + 6, y)

        for offset, row in enumerate(ordered[start : start + per_page]):
            column = SHEET_COLUMNS - 1 - (offset % SHEET_COLUMNS)  # الأولى في اليمين
            x0 = margin_x + column * cell_w
            y0 = margin_y + (offset // SHEET_COLUMNS) * cell_h
            qr = 30.0
            pdf.image(BytesIO(qr_png(REDEEM_URL.format(code=row.code))), x=x0 + 4, y=y0 + (cell_h - qr) / 2, w=qr, h=qr)
            text_x = x0 + 4 + qr + 3
            text_w = cell_w - 8 - qr - 3
            pdf.set_text_color(242, 107, 33)
            pdf.set_font("plex", "B", 15)
            pdf.set_xy(text_x, y0 + 5)
            pdf.cell(text_w, 8, "TAXO", align="R")
            pdf.set_text_color(20, 20, 20)
            pdf.set_font("plex", "B", 13)
            pdf.set_xy(text_x, y0 + 13)
            pdf.cell(text_w, 7, f"بطاقة شحن {value}", align="R")
            pdf.set_font("plex", "B", 11.5)
            pdf.set_xy(text_x, y0 + 22)
            pdf.cell(text_w, 7, row.code or "", align="R")
            pdf.set_font("plex", "", 8)
            pdf.set_xy(text_x, y0 + 30)
            pdf.cell(text_w, 4.5, f"تسلسل {row.serial}", align="R")
            pdf.set_xy(text_x, y0 + 34.5)
            pdf.cell(text_w, 4.5, f"تنتهي {until}", align="R")
            pdf.set_xy(text_x, y0 + 39)
            pdf.cell(text_w, 5, "امسح الرمز أو اكتبه: المحفظة ← اشحن ببطاقة", align="R")
    return bytes(pdf.output())

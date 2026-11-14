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


#: **ألوانُ تصاميم الهدية الثلاثة** (TAXO 2.0): الخلفيّة، ثمّ لونُ النصّ، ثمّ لونُ اللمسة
GIFT_DESIGNS = {
    "night": ((14, 17, 22), (255, 255, 255), (242, 107, 33)),
    "sunrise": ((242, 107, 33), (255, 255, 255), (255, 214, 170)),
    "city": ((250, 246, 240), (20, 20, 20), (242, 107, 33)),
}


def gift_print_pdf(meta: BatchMeta, row: CardRow, *, password: str, design: str = "night") -> bytes:
    """**بطاقةُ الهدية المطبوعة بمنطقة كشط**: A4 فيه البطاقةُ بمقاس ٨٥×٥٤ مم مرّتين (الوجهُ والظهر) بخطوط قصّ.

    **الرمزُ في مستطيلٍ واضحِ الحدود** على الظهر، **تُلصق فوقه ملصقةُ كشطٍ فضّيّة** في المطبعة. ومعه QR يحمل الرمزَ بعد `#`."""
    if row.code is None:
        raise InvalidInput("النسخةُ المطبوعةُ تحتاج الرمزَ كاملاً", field="format")
    bg, ink, accent = GIFT_DESIGNS.get(design, GIFT_DESIGNS["night"])
    pdf = _pdf("P", password)
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    w, h = 85.6, 54.0
    x = (pdf.w - w) / 2
    value = f"{amount_text(meta.amount, meta.currency)} {meta.currency}"
    until = _local_text(meta.expires_at, meta.zone)[:10]

    def cut_marks(y0: float) -> None:
        with pdf.local_context():
            pdf.set_draw_color(150, 150, 150)
            pdf.set_line_width(0.2)
            pdf.set_dash_pattern(dash=2, gap=1.5)
            pdf.rect(x, y0, w, h)

    # **الوجه**
    y_front = 40.0
    pdf.set_fill_color(*bg)
    pdf.rect(x, y_front, w, h, style="F")
    pdf.set_text_color(*accent)
    pdf.set_font("plex", "B", 22)
    pdf.set_xy(x + 6, y_front + 7)
    pdf.cell(w - 12, 10, "TAXO", align="R")
    pdf.set_text_color(*ink)
    pdf.set_font("plex", "B", 13)
    pdf.set_xy(x + 6, y_front + 22)
    pdf.cell(w - 12, 8, "بطاقة هدية", align="R")
    pdf.set_font("plex", "B", 18)
    pdf.set_xy(x + 6, y_front + 31)
    pdf.cell(w - 12, 10, value, align="R")
    pdf.set_font("plex", "", 8)
    pdf.set_xy(x + 6, y_front + 44)
    pdf.cell(w - 12, 5, f"تنتهي {until}", align="R")
    cut_marks(y_front)

    # **الظهر**: منطقةُ الكشط والـQR
    y_back = y_front + h + 20
    pdf.set_fill_color(255, 255, 255)
    pdf.rect(x, y_back, w, h, style="F")
    qr = 30.0
    pdf.image(BytesIO(qr_png(REDEEM_URL.format(code=row.code))), x=x + 5, y=y_back + 5, w=qr, h=qr)
    pdf.set_text_color(20, 20, 20)
    pdf.set_font("plex", "B", 9)
    pdf.set_xy(x + qr + 9, y_back + 6)
    pdf.cell(w - qr - 14, 5, "اكشط لترى الرمز", align="R")
    box_x, box_y, box_w, box_h = x + qr + 9, y_back + 13, w - qr - 14, 12
    with pdf.local_context():
        pdf.set_draw_color(*accent)
        pdf.set_line_width(0.6)
        pdf.rect(box_x, box_y, box_w, box_h)
    pdf.set_font("plex", "B", 10)
    pdf.set_xy(box_x, box_y + 3)
    pdf.cell(box_w, 6, row.code, align="C")
    pdf.set_font("plex", "", 7)
    pdf.set_xy(x + qr + 9, y_back + 28)
    pdf.cell(w - qr - 14, 4, f"تسلسل {row.serial}", align="R")
    pdf.set_xy(x + 5, y_back + 40)
    pdf.cell(w - 10, 4, "امسح الرمز بتطبيق TAXO، أو اكتبه في: المحفظة ← اشحن ببطاقة", align="R")
    cut_marks(y_back)

    pdf.set_text_color(110, 110, 110)
    pdf.set_font("plex", "", 8)
    pdf.set_xy(15, y_back + h + 10)
    pdf.cell(pdf.w - 30, 5, "للمطبعة: ملصقةُ كشطٍ فضّيّة فوق المستطيل البرتقاليّ، والقصُّ على الخطّ المتقطّع.", align="R")
    return bytes(pdf.output())


# ---------------------------------------------------------------------------------------------------------------- فاتورةُ الشركة


@dataclass(frozen=True)
class Invoice:
    """**فاتورةُ دفعةٍ بيعت لشركة** (§١٠٠-ب/٧) — كلُّ ما فيها من الدفعة، **ولا رمز**."""

    number: str
    issued_at: datetime
    zone: object
    country: str
    currency: str
    buyer_company: str
    buyer_tax_number: str | None
    seller_name: str | None
    seller_tax_number: str | None
    batch_title: str
    amount: Decimal
    quantity: int
    expires_at: datetime
    serials: list[str]


def invoice_pdf(invoice: Invoice) -> bytes:
    """**A4 عموديّ**: الرأسُ والطرفان، وسطرُ الفئة × العدد = المجموع، ثمّ الأرقامُ التسلسليّةُ في أعمدة. **بلا كلمة سرّ**: لا رمزَ فيه."""
    from fpdf import FPDF

    pdf = FPDF(orientation="P", format="A4")
    pdf.add_font("plex", "", str(FONTS / "IBMPlexSansArabic-400.ttf"))
    pdf.add_font("plex", "B", str(FONTS / "IBMPlexSansArabic-700.ttf"))
    pdf.set_text_shaping(use_shaping_engine=True, direction="rtl", script="arab", language="ar")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()
    width = pdf.w - pdf.l_margin - pdf.r_margin

    pdf.set_font("plex", "B", 20)
    pdf.set_text_color(255, 107, 0)
    pdf.cell(width, 12, "TAXO", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("plex", "B", 15)
    pdf.cell(width, 9, "فاتورةُ بيع بطاقات شحن TAXO", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("plex", "", 10.5)
    pdf.cell(width, 7, f"رقم الفاتورة {invoice.number} · التاريخ {_local_text(invoice.issued_at, invoice.zone)}", align="R",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    def party(title: str, name: str | None, tax: str | None) -> None:
        pdf.set_font("plex", "B", 11)
        pdf.cell(width, 7, title, align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("plex", "", 10.5)
        pdf.cell(width, 6.5, name or "—", align="R", new_x="LMARGIN", new_y="NEXT")
        if tax:
            pdf.cell(width, 6.5, f"الرقم الضريبيّ {tax}", align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    party("البائع", invoice.seller_name or "TAXO", invoice.seller_tax_number)
    party("المشتري", invoice.buyer_company, invoice.buyer_tax_number)

    total = invoice.amount * invoice.quantity
    columns = (("البيان", 0.46), ("الفئة", 0.18), ("العدد", 0.14), ("المجموع", 0.22))
    rows = [
        [title for title, _ in columns],
        [
            f"بطاقات شحن TAXO — الدفعة {invoice.batch_title}",
            f"{amount_text(invoice.amount, invoice.currency)} {invoice.currency}",
            str(invoice.quantity),
            f"{amount_text(total, invoice.currency)} {invoice.currency}",
        ],
    ]
    for index, values in enumerate(rows):
        bold = index == 0
        pdf.set_font("plex", "B" if bold else "", 10.5)
        if bold:
            pdf.set_fill_color(255, 233, 214)
        x = pdf.l_margin + width
        y = pdf.get_y()
        for (_title, share), value in zip(columns, values, strict=True):
            x -= width * share
            pdf.set_xy(x, y)
            pdf.cell(width * share, 9, value, border=1, align="C", fill=bold)
        pdf.set_xy(pdf.l_margin, y + 9)
    pdf.set_font("plex", "B", 12)
    pdf.cell(width, 10, f"الإجمالي {amount_text(total, invoice.currency)} {invoice.currency}", align="L", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("plex", "", 9.5)
    pdf.multi_cell(
        width, 6,
        f"القيمةُ اسميّةٌ لكلِّ بطاقة. تُستعمل كلُّ بطاقةٍ مرّةً واحدةً في تطبيق TAXO حتى {_local_text(invoice.expires_at, invoice.zone)}.",
        align="R", new_x="LMARGIN", new_y="NEXT",
    )
    pdf.ln(3)

    pdf.set_font("plex", "B", 11)
    pdf.cell(width, 8, f"الأرقامُ التسلسليّة ({invoice.quantity})", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("plex", "", 8.5)
    per_row = 4
    cell_w = width / per_row
    for start in range(0, len(invoice.serials), per_row):
        if pdf.get_y() > pdf.h - 22:
            pdf.add_page()
        y = pdf.get_y()
        x = pdf.l_margin + width
        for serial in invoice.serials[start:start + per_row]:
            x -= cell_w
            pdf.set_xy(x, y)
            pdf.cell(cell_w, 5.5, serial, align="C")
        pdf.set_xy(pdf.l_margin, y + 5.5)
    return bytes(pdf.output())

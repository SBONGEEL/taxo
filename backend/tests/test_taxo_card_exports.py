"""ملفّاتُ دفعة بطاقات TAXO لحظةَ إنشائها (SPEC §١٠٠-أ/١، أمرُ المالك ٢٠٢٦-١١-١٣).

Excel حقيقيٌّ معمًّى · PDF قائمةٌ معمّاة · ورقةُ مطبعةٍ بـQR — **من رموزٍ تُطابَق ببصماتها**، **ولا تُنزَّل بعد ٣٠ دقيقة**، **وكلُّ تنزيلٍ
صفُّ تدقيقٍ بلا رمزٍ ولا كلمة سرّ**.
"""

from __future__ import annotations

from datetime import timedelta
from io import BytesIO

import msoffcrypto
import openpyxl
import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.models.audit import AdminAuditLog
from app.models.taxo_card import CardBatch
from app.services import card_exports
from tests.test_taxo_cards import card_market, card_pepper, issue  # noqa: F401

PASSWORD = "file-pass-" + "2026"


async def _export(client: AsyncClient, headers: dict, body: dict, fmt: str, *, password: str = PASSWORD, codes=None):
    return await client.post(
        f"/admin/taxo-cards/batches/{body['batch']['id']}/export",
        json={"format": fmt, "password": password, "codes": codes if codes is not None else body["codes"]},
        headers=headers,
    )


async def test_the_excel_file_is_real_encrypted_and_right_to_left(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    await card_market(session_factory)
    body = await issue(client, admin_headers, quantity=3)
    response = await _export(client, admin_headers, body, "xlsx")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith(card_exports.XLSX_MEDIA_TYPE)
    assert "no-store" in response.headers["cache-control"]
    with pytest.raises(Exception):
        openpyxl.load_workbook(BytesIO(response.content))  # **لا يُفتح بلا كلمة السرّ**
    office = msoffcrypto.OfficeFile(BytesIO(response.content))
    office.load_key(password=PASSWORD)
    plain = BytesIO()
    office.decrypt(plain)
    sheet = openpyxl.load_workbook(plain).active
    assert sheet.sheet_view.rightToLeft and sheet.freeze_panes == "A5"
    assert "DZ-B0001" in str(sheet["A1"].value)
    assert [cell.value for cell in sheet[4]][:4] == ["#", "الرقم التسلسلي", "الرمز", "القيمة"]
    serials = [sheet.cell(row, 2).value for row in range(5, 8)]
    assert serials == [row["serial"] for row in body["codes"]]
    # **المبلغُ رقمٌ لا نصّ**، والتاريخُ تاريخ
    assert isinstance(sheet.cell(5, 4).value, int | float) and sheet.cell(5, 4).value == 1000
    assert sheet.cell(5, 7).is_date


@pytest.mark.parametrize("fmt", ["pdf", "sheet"])
async def test_the_pdfs_need_the_password(client: AsyncClient, session_factory, admin_headers: dict, fmt: str) -> None:
    await card_market(session_factory)
    body = await issue(client, admin_headers, quantity=12)
    response = await _export(client, admin_headers, body, fmt)
    assert response.status_code == 200, response.text
    assert response.content.startswith(b"%PDF") and b"/Encrypt" in response.content
    # **والرمزُ لا يظهر نصّاً في الملفّ المعمّى**
    assert not any(row["code"].encode() in response.content for row in body["codes"])


async def test_an_invented_or_foreign_code_never_enters_a_file(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    await card_market(session_factory)
    body = await issue(client, admin_headers, quantity=2)
    forged = [dict(body["codes"][0], code="AAAA-BBBB-CCCC-DDDD"), body["codes"][1]]
    assert (await _export(client, admin_headers, body, "sheet", codes=forged)).status_code == 422
    swapped = [dict(body["codes"][0], code=body["codes"][1]["code"]), dict(body["codes"][1], code=body["codes"][0]["code"])]
    assert (await _export(client, admin_headers, body, "xlsx", codes=swapped)).status_code == 422
    other = await issue(client, admin_headers, quantity=1)
    assert (await _export(client, admin_headers, body, "xlsx", codes=other["codes"])).status_code == 422
    assert (await _export(client, admin_headers, body, "xlsx", password="short")).status_code == 422


async def test_files_exist_only_at_creation(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    await card_market(session_factory)
    body = await issue(client, admin_headers, quantity=1)
    async with session_factory() as session:
        await session.execute(
            update(CardBatch).where(CardBatch.id == body["batch"]["id"]).values(created_at=CardBatch.created_at - timedelta(minutes=31))
        )
        await session.commit()
    refused = await _export(client, admin_headers, body, "xlsx")
    assert refused.status_code == 422 and "عند إنشائها" in refused.text


async def test_every_download_is_audited_without_codes_or_password(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    await card_market(session_factory)
    body = await issue(client, admin_headers, quantity=2)
    for fmt in ("xlsx", "pdf", "sheet"):
        assert (await _export(client, admin_headers, body, fmt)).status_code == 200
    async with session_factory() as session:
        rows = (await session.scalars(select(AdminAuditLog).where(AdminAuditLog.entity_type == "card_batch_export"))).all()
    assert sorted(row.details["format"] for row in rows) == ["pdf", "sheet", "xlsx"]
    text = str([row.details for row in rows])
    assert PASSWORD not in text and not any(code["code"] in text or code["code"].replace("-", "") in text for code in body["codes"])


async def test_no_file_without_a_finance_session(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    await card_market(session_factory)
    body = await issue(client, admin_headers, quantity=1)
    assert (await _export(client, {}, body, "xlsx")).status_code in (401, 403)

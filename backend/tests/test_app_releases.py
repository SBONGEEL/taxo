"""سجلُّ الإصدارات والتحديثُ الإلزاميّ — **البند ٨ (§39٫٨، §43)**.

**وما يُختبر هنا ليس «أيُحفظ الصفّ» بل الأربعةُ التي تجعله بابَ قفلٍ آمن**:

1. **غيابُ السجلِّ لا يقفل أحداً** — والقاعدةُ العامّة «الغيابُ يعطّل» تعني
   هنا تعطيلَ الحجب لا تعطيلَ التطبيق.
2. **ولا يُقفل من لا نعرف نسختَه** — القفلُ عقوبةٌ على قِدَمٍ مثبَت.
3. **ورفعُ الحدِّ يستأذن مرّتين، والثانيةُ في العقد** — وورقةُ شاشةٍ وحدَها
   راحةٌ لا حماية.
4. **ولا يُحفظ إصدارٌ برابطٍ لا يُفتح** — «ولا يُقفَل أحدٌ خارج التطبيق بلا
   رابط تحميلٍ صالحٍ يُفحص قبل الحفظ» (§39٫٨ بحرفها).

**والقياسُ بالنقض في الثالث**: تُجرَّب الحالُ الآمنةُ أيضاً (حدٌّ لا يرتفع)
**فتمرّ بلا إقرار** — فبوّابةٌ تصيح حيث لا خطر تُفرَّغ من داخلها.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.app_release import AppRelease
from app.models.audit import AdminAuditLog
from app.models.enums import AuditAction
from app.services import releases as releases_service

URL = "https://app.tajora.ly/downloads/taxo-rider.apk"


class _Response:
    def __init__(self, status_code: int, kind: str = "application/octet-stream") -> None:
        self.status_code = status_code
        self.headers = {"content-type": kind}


class _FakeClient:
    """عميلُ HTTP مزيَّف — **يعيد ما يقوله الاختبار ولا يمسّ شبكة**."""

    head_codes: dict[str, int] = {}
    get_codes: dict[str, int] = {}
    kinds: dict[str, str] = {}
    seen: list[str] = []

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        return None

    async def head(self, url: str) -> _Response:
        _FakeClient.seen.append("HEAD " + url)
        return _Response(
            _FakeClient.head_codes.get(url, 200),
            _FakeClient.kinds.get(url, "application/octet-stream"),
        )

    async def get(self, url: str, headers: dict | None = None) -> _Response:
        _FakeClient.seen.append("GET " + url)
        return _Response(
            _FakeClient.get_codes.get(url, 200),
            _FakeClient.kinds.get(url, "application/octet-stream"),
        )


class _FakeHttpx:
    AsyncClient = _FakeClient
    HTTPError = Exception


@pytest.fixture
def links(monkeypatch: pytest.MonkeyPatch):
    """يستبدل وحدةَ `httpx` **داخل هذه الخدمة وحدَها** — لا عالمياً."""
    _FakeClient.head_codes = {}
    _FakeClient.get_codes = {}
    _FakeClient.kinds = {}
    _FakeClient.seen = []
    monkeypatch.setattr(releases_service, "httpx", _FakeHttpx)
    return _FakeClient


def _body(**overrides: Any) -> dict:
    return {
        "app": "rider",
        "build": 400,
        "min_supported_build": 400,
        "download_url": URL,
        "release_notes": "إصلاحُ خريطة الرحلة، وتسريعُ الإقلاع.",
        "reminder_hours": 24,
        **overrides,
    }


async def _create(
    client: AsyncClient, headers: dict, *, confirm: bool = True, **overrides: Any
):
    """**والإقرارُ افتراضٌ في المساعد لا في العقد**: أكثرُ الحالات ترفع الحدَّ
    (أوّلُ صفٍّ لتطبيقٍ يرفعه من الصفر)، **واختباراتُ الإذن تُسقطه صراحةً**."""
    body = _body(**overrides)
    if confirm and "confirm_min_supported_build" not in overrides:
        body["confirm_min_supported_build"] = body["min_supported_build"]
    return await client.post("/admin/releases", json=body, headers=headers)


async def _version(client: AsyncClient, app: str, build: int | None = None):
    params: dict[str, Any] = {"app": app}
    if build is not None:
        params["build"] = build
    response = await client.get("/public/app-version", params=params)
    assert response.status_code == 200, response.text
    return response.json()


# ------------------------------------------------------------- بابُ الإقلاع


async def test_no_registry_locks_nobody(client: AsyncClient) -> None:
    """**لا سجلَّ = لا تدخّل** — لا «كلُّ النسخ مرفوضة»."""
    body = await _version(client, "rider", 1)
    assert body["state"] == "ok"
    assert body["latest_build"] is None and body["download_url"] is None


async def test_three_states_from_one_row(
    client: AsyncClient, admin_headers: dict, links
) -> None:
    """الحالاتُ الثلاثُ من صفٍّ واحد — **والحكمُ محسوبٌ في الخلفية**."""
    created = await _create(
        client, admin_headers, build=400, min_supported_build=380
    )
    assert created.status_code == 201, created.text

    assert (await _version(client, "rider", 400))["state"] == "ok"
    assert (await _version(client, "rider", 410))["state"] == "ok"

    optional = await _version(client, "rider", 390)
    assert optional["state"] == "optional"
    assert optional["latest_build"] == 400
    assert optional["min_supported_build"] == 380
    assert optional["download_url"] == URL
    assert optional["reminder_hours"] == 24
    assert optional["release_notes"]

    assert (await _version(client, "rider", 379))["state"] == "forced"


async def test_an_unknown_build_is_never_locked_out(
    client: AsyncClient, admin_headers: dict, links
) -> None:
    """**لا يُقفل من لا نعرف نسختَه** — والقفلُ عقوبةٌ على قِدَمٍ مثبَت."""
    assert (
        await _create(client, admin_headers, build=400, min_supported_build=400)
    ).status_code == 201
    assert (await _version(client, "rider", None))["state"] == "ok"


async def test_each_app_has_its_own_registry(
    client: AsyncClient, admin_headers: dict, links
) -> None:
    """سجلٌّ لكلِّ تطبيق — **وحدُّ الراكب لا يقفل الكبتن**."""
    assert (
        await _create(client, admin_headers, app="rider", build=400,
                      min_supported_build=400)
    ).status_code == 201
    assert (await _version(client, "driver", 1))["state"] == "ok"


async def test_the_governing_row_is_the_highest_build(
    client: AsyncClient, admin_headers: dict, links
) -> None:
    """**أعلى رقمٍ يحكم لا أحدثُ إنشاء** — فتصحيحُ صفٍّ قديمٍ لا يعيد سياسةَ أمس."""
    assert (
        await _create(client, admin_headers, build=400, min_supported_build=400)
    ).status_code == 201
    # صفٌّ أقدمُ يُضاف بعده — ولا يحكم
    older = await _create(
        client, admin_headers, build=300, min_supported_build=100
    )
    assert older.status_code == 201, older.text

    body = await _version(client, "rider", 350)
    assert body["latest_build"] == 400 and body["state"] == "forced"

    listed = await client.get("/admin/releases", headers=admin_headers)
    rows = {row["build"]: row["is_current"] for row in listed.json()}
    assert rows == {400: True, 300: False}


# --------------------------------------------------- الإذنان، والرابطُ قبله


async def test_raising_the_bar_needs_the_number_typed_again(
    client: AsyncClient, admin_headers: dict, links
) -> None:
    """**يستأذن مرّتين** — والثانيةُ في العقد لا في الشاشة."""
    assert (
        await _create(client, admin_headers, build=400, min_supported_build=380)
    ).status_code == 201

    refused = await _create(
        client, admin_headers, build=401, min_supported_build=395, confirm=False
    )
    assert refused.status_code == 422, refused.text
    assert "395" in refused.json()["message"]

    wrong = await _create(
        client,
        admin_headers,
        build=401,
        min_supported_build=395,
        confirm_min_supported_build=390,
    )
    assert wrong.status_code == 422

    accepted = await _create(
        client,
        admin_headers,
        build=401,
        min_supported_build=395,
        confirm_min_supported_build=395,
    )
    assert accepted.status_code == 201, accepted.text


async def test_a_bar_that_rises_for_nobody_asks_nothing(
    client: AsyncClient, admin_headers: dict, links
) -> None:
    """**والقياسُ بالنقض**: حدٌّ لا يرتفع يمرّ بلا إقرار.

    **وبوّابةٌ تصيح حيث لا خطر تُفرَّغ من داخلها** — يصير التأكيدُ ضغطةً
    تلقائيةً فلا يعود يعني شيئاً يومَ يعني.
    """
    assert (
        await _create(client, admin_headers, build=400, min_supported_build=380)
    ).status_code == 201
    lower = await _create(
        client, admin_headers, build=401, min_supported_build=370, confirm=False
    )
    assert lower.status_code == 201, lower.text
    # **والقائمُ الآن ٣٧٠ لا ٣٨٠**: الحدُّ يُقارَن بما يحكم الآن لا بما حكم أمس
    same = await _create(
        client, admin_headers, build=402, min_supported_build=370, confirm=False
    )
    assert same.status_code == 201, same.text
    # **وصفٌّ لا يحكم لا يستأذن**: رقمٌ أدنى من الحاكم لا يقفل أحداً
    older = await _create(
        client, admin_headers, build=100, min_supported_build=100, confirm=False
    )
    assert older.status_code == 201, older.text


async def test_a_link_that_does_not_open_is_not_saved(
    client: AsyncClient, admin_headers: dict, links, session_factory
) -> None:
    """**ولا يُقفَل أحدٌ خارج التطبيق بلا رابطٍ صالح** — ولا صفَّ يبقى."""
    links.head_codes[URL] = 404
    links.get_codes[URL] = 404
    refused = await _create(client, admin_headers)
    assert refused.status_code == 422, refused.text
    assert "404" in refused.json()["message"]

    async with session_factory() as session:
        assert (await session.scalars(select(AppRelease))).all() == []


async def test_a_head_refusal_falls_back_to_a_ranged_get(
    client: AsyncClient, admin_headers: dict, links
) -> None:
    """**`405` على `HEAD` ليس رابطاً مكسوراً** — خوادمُ ملفّاتٍ كثيرةٌ ترفضه.

    **وحارسٌ يصيح على السليم يُطفأ**، فيسقط معه ما يمسكه حقاً.
    """
    links.head_codes[URL] = 405  # والـ`GET` يجيب 200
    created = await _create(client, admin_headers)
    assert created.status_code == 201, created.text
    assert links.seen == ["HEAD " + URL, "GET " + URL]


async def test_the_bar_never_passes_the_release_itself(
    client: AsyncClient, admin_headers: dict, links
) -> None:
    """حدٌّ فوق الإصدار **يقفل صاحبَ أحدث حزمةٍ بلا مخرج**."""
    refused = await _create(
        client,
        admin_headers,
        build=400,
        min_supported_build=401,
        confirm_min_supported_build=401,
    )
    assert refused.status_code == 422, refused.text


async def test_one_build_number_per_app(
    client: AsyncClient, admin_headers: dict, links
) -> None:
    """**الرقمُ هويةُ الحزمة عند أندرويد** — وصفّان به يجعلان «الأخير» مبهماً."""
    assert (await _create(client, admin_headers)).status_code == 201
    again = await _create(client, admin_headers)
    assert again.status_code == 409, again.text


# --------------------------------------------------------- الصلاحيةُ والتدقيق


async def test_support_reads_and_does_not_write(
    client: AsyncClient, support_headers: dict, links
) -> None:
    """قراءةٌ للدعم، **وكتابةٌ لصاحب `settings.write`** — الحدُّ إعدادُ منصّة."""
    assert (
        await client.get("/admin/releases", headers=support_headers)
    ).status_code == 200
    refused = await _create(client, support_headers)
    assert refused.status_code == 403, refused.text


async def test_edit_and_delete_are_stamped_with_before_and_after(
    client: AsyncClient, admin_headers: dict, links, session_factory
) -> None:
    """**القيمةُ قبل وبعد** (§40٫١) — و«غيّر الحدّ» لا تقول شيئاً بعد شهر."""
    created = await _create(
        client, admin_headers, build=400, min_supported_build=380
    )
    release_id = created.json()["id"]

    edited = await client.put(
        f"/admin/releases/{release_id}",
        json=_body(build=400, min_supported_build=370, reminder_hours=48),
        headers=admin_headers,
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["reminder_hours"] == 48

    removed = await client.delete(
        f"/admin/releases/{release_id}", headers=admin_headers
    )
    assert removed.status_code == 204, removed.text

    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(AdminAuditLog)
                .where(AdminAuditLog.entity_type == "app_release")
                .order_by(AdminAuditLog.created_at)
            )
        ).all()

    assert [row.action for row in rows] == [
        AuditAction.CREATE,
        AuditAction.UPDATE,
        AuditAction.DELETE,
    ]
    changes = rows[1].details["changes"]
    assert changes["min_supported_build"] == {"before": 380, "after": 370}
    assert changes["reminder_hours"] == {"before": 24, "after": 48}
    assert rows[2].details["build"] == 400


async def test_editing_never_moves_the_build_number(
    client: AsyncClient, admin_headers: dict, links
) -> None:
    """**الرقمُ هويةُ حزمةٍ في يد الناس** — وتغييرُه تزويرُ سجلٍّ لا تصحيح."""
    created = await _create(client, admin_headers, build=400)
    release_id = created.json()["id"]

    edited = await client.put(
        f"/admin/releases/{release_id}",
        json=_body(build=999, min_supported_build=380),
        headers=admin_headers,
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["build"] == 400, "رقمُ الإصدار لا يُعدَّل"


async def test_an_apk_url_that_answers_a_web_page_is_refused(
    client: AsyncClient, admin_headers: dict, links, session_factory
) -> None:
    """**قِيس على الإنتاج 2026-09-03**: وُضع عنوانُ غلافِ تطبيق الراكب
    (`app.tajora.ly/downloads/taxo-rider.apk`) فردَّ **200 ومعه `text/html`** —
    تطبيقُ الويب نفسُه. **فحالةُ الردِّ وحدَها تُخضِّر رابطاً يعطي صاحبَ
    الهاتف صفحةً بدل الحزمة.**
    """
    links.kinds[URL] = "text/html"
    refused = await _create(client, admin_headers)
    assert refused.status_code == 422, refused.text
    assert "text/html" in refused.json()["message"]

    async with session_factory() as session:
        assert (await session.scalars(select(AppRelease))).all() == []


async def test_a_download_page_that_is_not_an_apk_url_still_passes(
    client: AsyncClient, admin_headers: dict, links
) -> None:
    """**والشرطُ ضيّقٌ بقصد**: صفحةُ تحميلٍ تجيب HTML بحقّ، **والزرُّ يفتحها
    في المتصفّح فهي مخرجٌ صالح** — ورفضُها صياحٌ على السليم.
    """
    page = "https://taxo.tajora.ly/download"
    links.kinds[page] = "text/html"
    created = await _create(client, admin_headers, download_url=page)
    assert created.status_code == 201, created.text

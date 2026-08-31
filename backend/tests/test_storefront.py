"""المتجر — البلاطاتُ واللافتاتُ، قراءةً وتحريراً (`0063` و`0064`).

**ولم يكن لهذين الجدولين اختبارٌ واحدٌ قبل اليوم** (2026-08-31): بُنيا في
جولتين وشُحنا، **والخضرةُ كانت خضرةَ ما لم يُقَس**.

## وأربعُ قواعدَ تُقاس هنا لأن نقضَها لا يُسقط شيئاً

* **الأيقونةُ من قائمةٍ مقرَّرة** — واسمٌ خارجها كان يرسم `LayoutGrid`
  **صامتاً**: لا خطأَ ولا تحذير، **فلا يعلم المشرفُ أنه أخطأ حتى يفتح
  التطبيق**.
* **والختمُ يسبق الحذف** — `first_shown_at` هي الفرقُ بين مسوّدةٍ تُحذف وصفٍّ
  رآه الناس. **ونقضُها لا يصيح**: يمضي الحذفُ ويختفي الشاهد.
* **واللافتةُ تُختم بنافذتها** — مشتعلةٌ قبل نافذتها **تُعرض حين تفتح**،
  فتُختم اليوم. وهذا هو الثقبُ الذي يُقاس هنا بعينه.
* **والصورةُ بايتاتٌ أو ٤٠٤** — ولا حقلَ يقول «لها صورة»، **وبابُ التطبيق
  يسأل عن السوق** فلا تتسرّب لافتةُ سوقٍ لم يُفتح بعد.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select

from app.models.storefront import PromoBanner, ServiceTile
from tests.helpers import PNG_BYTES, rider_session

# ─────────────────────────────────────────────────────────────── مُعينات


def _tile(**overrides) -> dict:
    return {
        "country_code": "JO",
        "key": "parcels",
        "title": "طرود",
        "icon": "package",
        "audience": "all_riders",
        "status": "hidden",
    } | overrides


def _banner(**overrides) -> dict:
    now = datetime.now(UTC)
    return {
        "country_code": "JO",
        "title": "لافتة",
        "audience": "all_riders",
        "starts_at": (now - timedelta(hours=1)).isoformat(),
        "ends_at": (now + timedelta(days=7)).isoformat(),
        "link_kind": "none",
        "is_active": False,
    } | overrides


async def _create_tile(client: AsyncClient, headers: dict, **overrides) -> dict:
    response = await client.post(
        "/admin/settings/service-tiles", json=_tile(**overrides), headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_banner(client: AsyncClient, headers: dict, **overrides) -> dict:
    response = await client.post(
        "/admin/settings/promo-banners", json=_banner(**overrides), headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


# ═════════════════════════════════════════ ١) الأيقونةُ من القائمة المقرَّرة


async def test_icons_door_lists_the_declared_names(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**بيتُ القائمة واحد** — واللوحةُ تقرؤه ولا تكتب نسخةً ثانية."""
    from app.services import storefront

    response = await client.get("/admin/settings/service-icons", headers=admin_headers)
    assert response.status_code == 200
    assert response.json() == list(storefront.SERVICE_ICONS)


async def test_tile_refuses_an_icon_outside_the_list(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**ولا يُرسم افتراضاً**: `LayoutGrid` الصامتةُ كانت تخفي الخطأ."""
    response = await client.post(
        "/admin/settings/service-tiles",
        json=_tile(icon="not-a-real-icon"),
        headers=admin_headers,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"


async def test_patch_refuses_an_icon_outside_the_list(
    client: AsyncClient, admin_headers: dict
) -> None:
    tile = await _create_tile(client, admin_headers)
    response = await client.patch(
        f"/admin/settings/service-tiles/{tile['id']}",
        json={"icon": "sparkle"},  # الاسمُ `sparkles` لا `sparkle`
        headers=admin_headers,
    )
    assert response.status_code == 422


async def test_banner_icon_may_be_absent_but_not_invented(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**الفراغُ خيارٌ، والاسمُ الخاطئُ ليس خياراً** — واللافتةُ قد تكون بلا أيقونة."""
    await _create_banner(client, admin_headers, icon=None)

    refused = await client.post(
        "/admin/settings/promo-banners",
        json=_banner(icon="rocket"),
        headers=admin_headers,
    )
    assert refused.status_code == 422


# ═══════════════════════════════════════════════ ٢) الختمُ — أوّلُ ظهورٍ لأحد


async def test_a_hidden_tile_is_never_stamped(
    client: AsyncClient, admin_headers: dict
) -> None:
    tile = await _create_tile(client, admin_headers)
    assert tile["first_shown_at"] is None


async def test_a_tile_created_active_is_stamped_at_birth(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**والإنشاءُ إشعالٌ كالتعديل** — وبلا هذا تولد فعّالةً وتبقى «مسوّدة»."""
    tile = await _create_tile(
        client, admin_headers, status="active", destination="/wallet"
    )
    assert tile["first_shown_at"] is not None


async def test_igniting_a_tile_stamps_it_once_and_hiding_does_not_clear_it(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**والحالُ تقول أين هي، والعمودُ يقول ما مضى** — سؤالان لا يجيبهما حقلٌ واحد."""
    tile = await _create_tile(client, admin_headers)

    lit = await client.patch(
        f"/admin/settings/service-tiles/{tile['id']}",
        json={"status": "active", "destination": "/wallet"},
        headers=admin_headers,
    )
    assert lit.status_code == 200
    stamp = lit.json()["first_shown_at"]
    assert stamp is not None

    hidden = await client.patch(
        f"/admin/settings/service-tiles/{tile['id']}",
        json={"status": "hidden"},
        headers=admin_headers,
    )
    # **مخفيّةٌ اليومَ قد تكون عُرضت أمس** — والعمودُ لا يُمحى
    assert hidden.json()["first_shown_at"] == stamp


async def test_a_banner_lit_before_its_window_is_stamped_today(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**الثقبُ الذي يُغلق هنا**: تُشعَل لنافذة الأسبوع القادم، **فتُعرض حين
    تفتح** — ولو لم تُختم لبقيت تُقرأ مسوّدةً تُحذف وهي على شاشات الناس.
    """
    now = datetime.now(UTC)
    banner = await _create_banner(
        client,
        admin_headers,
        starts_at=(now + timedelta(days=7)).isoformat(),
        ends_at=(now + timedelta(days=14)).isoformat(),
    )
    assert banner["first_shown_at"] is None

    lit = await client.patch(
        f"/admin/settings/promo-banners/{banner['id']}",
        json={"is_active": True},
        headers=admin_headers,
    )
    assert lit.json()["first_shown_at"] is not None


async def test_a_banner_lit_after_its_window_closed_is_not_stamped(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**ونافذةٌ انقضت لن تُعرض لأحد** — فإشعالُها سهوٌ يُحذف، لا شاهد."""
    now = datetime.now(UTC)
    banner = await _create_banner(
        client,
        admin_headers,
        starts_at=(now - timedelta(days=14)).isoformat(),
        ends_at=(now - timedelta(days=7)).isoformat(),
    )
    lit = await client.patch(
        f"/admin/settings/promo-banners/{banner['id']}",
        json={"is_active": True},
        headers=admin_headers,
    )
    assert lit.json()["first_shown_at"] is None


# ═══════════════════════════════════════ ٣) الحذفُ للمسوّدة وحدَها


async def test_a_draft_tile_is_deleted(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    tile = await _create_tile(client, admin_headers)
    gone = await client.delete(
        f"/admin/settings/service-tiles/{tile['id']}", headers=admin_headers
    )
    assert gone.status_code == 204

    async with session_factory() as session:
        assert (await session.get(ServiceTile, tile["id"])) is None


async def test_a_tile_that_was_shown_is_refused_deletion(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """**ولافتةٌ أُخفيت خيرٌ من صفٍّ ذهب** — والرفضُ يقول ما يُفعل بدلَه."""
    tile = await _create_tile(
        client, admin_headers, status="active", destination="/wallet"
    )
    await client.patch(
        f"/admin/settings/service-tiles/{tile['id']}",
        json={"status": "hidden"},
        headers=admin_headers,
    )

    refused = await client.delete(
        f"/admin/settings/service-tiles/{tile['id']}", headers=admin_headers
    )
    assert refused.status_code == 422
    assert "يُحذف" in refused.json()["message"]

    async with session_factory() as session:
        assert (await session.get(ServiceTile, tile["id"])) is not None


async def test_a_shown_banner_is_refused_deletion(
    client: AsyncClient, admin_headers: dict
) -> None:
    banner = await _create_banner(client, admin_headers, is_active=True)
    refused = await client.delete(
        f"/admin/settings/promo-banners/{banner['id']}", headers=admin_headers
    )
    assert refused.status_code == 422


async def test_support_cannot_delete(
    client: AsyncClient, admin_headers: dict, support_headers: dict
) -> None:
    tile = await _create_tile(client, admin_headers)
    refused = await client.delete(
        f"/admin/settings/service-tiles/{tile['id']}", headers=support_headers
    )
    assert refused.status_code == 403


# ═══════════════════════════════════════════════ ٤) صورةُ اللافتة


async def test_image_round_trip_and_the_market_condition(
    client: AsyncClient, admin_headers: dict, rider_payload: dict
) -> None:
    """**بايتاتٌ أو ٤٠٤** — ولا حقلَ يقول «لها صورة».

    **وبابُ التطبيق يسأل عن السوق**: راكبٌ أردنيٌّ يقرأ لافتةَ سوقه، **ولافتةُ
    سوقٍ آخرَ ٤٠٤** — فلا تُعلن خطّةُ إطلاقٍ لم تُعلن.
    """
    banner = await _create_banner(client, admin_headers)
    rider = await rider_session(client, rider_payload)
    headers = rider["headers"]

    # قبل الرفع: ٤٠٤ — والطلبُ نفسُه هو الجواب
    empty = await client.get(
        f"/storefront/banners/{banner['id']}/image", headers=headers
    )
    assert empty.status_code == 404

    uploaded = await client.put(
        f"/admin/settings/promo-banners/{banner['id']}/image",
        files={"file": ("promo.png", PNG_BYTES, "image/png")},
        headers=admin_headers,
    )
    assert uploaded.status_code == 200, uploaded.text

    served = await client.get(
        f"/storefront/banners/{banner['id']}/image", headers=headers
    )
    assert served.status_code == 200
    assert served.content == PNG_BYTES
    assert served.headers["x-content-type-options"] == "nosniff"

    # **سوقٌ آخر** — واللافتةُ ليبيّةٌ والراكبُ أردنيّ
    other = await _create_banner(client, admin_headers, country_code="LY")
    await client.put(
        f"/admin/settings/promo-banners/{other['id']}/image",
        files={"file": ("promo.png", PNG_BYTES, "image/png")},
        headers=admin_headers,
    )
    assert (
        await client.get(
            f"/storefront/banners/{other['id']}/image", headers=headers
        )
    ).status_code == 404

    # **وبابُ اللوحة لا يسأل عن السوق** — فالمشرفُ يهيّئ سوقاً قبل فتحه
    assert (
        await client.get(
            f"/admin/settings/promo-banners/{other['id']}/image",
            headers=admin_headers,
        )
    ).status_code == 200


async def test_deleting_the_image_leaves_the_banner(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    banner = await _create_banner(client, admin_headers)
    await client.put(
        f"/admin/settings/promo-banners/{banner['id']}/image",
        files={"file": ("promo.png", PNG_BYTES, "image/png")},
        headers=admin_headers,
    )
    dropped = await client.delete(
        f"/admin/settings/promo-banners/{banner['id']}/image", headers=admin_headers
    )
    assert dropped.status_code == 200

    async with session_factory() as session:
        row = await session.get(PromoBanner, banner["id"])
        assert row is not None and row.image_path is None


async def test_deleting_a_draft_banner_removes_its_file(
    client: AsyncClient, admin_headers: dict, document_storage
) -> None:
    """**والملفُّ يُحذف بعد الإيداع** — ولا يبقى يتيماً على القرص."""
    banner = await _create_banner(client, admin_headers)
    await client.put(
        f"/admin/settings/promo-banners/{banner['id']}/image",
        files={"file": ("promo.png", PNG_BYTES, "image/png")},
        headers=admin_headers,
    )
    folder = document_storage / banner["id"]
    assert list(folder.glob("*.png"))

    gone = await client.delete(
        f"/admin/settings/promo-banners/{banner['id']}", headers=admin_headers
    )
    assert gone.status_code == 204
    assert not list(folder.glob("*.png"))


async def test_replacing_an_image_removes_the_previous_file(
    client: AsyncClient, admin_headers: dict, document_storage
) -> None:
    banner = await _create_banner(client, admin_headers)
    for _ in range(2):
        assert (
            await client.put(
                f"/admin/settings/promo-banners/{banner['id']}/image",
                files={"file": ("promo.png", PNG_BYTES, "image/png")},
                headers=admin_headers,
            )
        ).status_code == 200

    # **نسختان لصورةٍ واحدةٍ نفايةٌ تتراكم** — والقديمةُ تُكنس بعد الإيداع
    assert len(list((document_storage / banner["id"]).glob("*.png"))) == 1


# ═══════════════════════════════════ ٥) البابُ العامّ — ما يراه صاحبُ الحساب


async def test_storefront_hides_what_is_hidden_and_serves_what_is_lit(
    client: AsyncClient, admin_headers: dict, rider_payload: dict
) -> None:
    """**المصفاةُ في الخلفية** — وثلاثةُ تطبيقاتٍ تسأل السؤالَ نفسَه."""
    await _create_tile(client, admin_headers, key="hidden-one")
    await _create_tile(
        client,
        admin_headers,
        key="lit-one",
        status="active",
        destination="/wallet",
    )
    await _create_tile(
        client,
        admin_headers,
        key="drivers-only",
        audience="all_drivers",
        status="active",
        destination="/subscription",
    )

    rider = await rider_session(client, rider_payload)
    body = (await client.get("/storefront", headers=rider["headers"])).json()
    keys = {tile["key"] for tile in body["tiles"]}
    assert keys == {"lit-one"}


async def test_a_banner_outside_its_window_is_not_served(
    client: AsyncClient, admin_headers: dict, rider_payload: dict
) -> None:
    """**ساعةُ الجهاز يملكها صاحبُه** — فالنافذةُ تُقاس هنا."""
    now = datetime.now(UTC)
    await _create_banner(
        client,
        admin_headers,
        title="منتهية",
        is_active=True,
        starts_at=(now - timedelta(days=9)).isoformat(),
        ends_at=(now - timedelta(days=2)).isoformat(),
    )
    await _create_banner(client, admin_headers, title="حيّة", is_active=True)

    rider = await rider_session(client, rider_payload)
    body = (await client.get("/storefront", headers=rider["headers"])).json()
    assert [row["title"] for row in body["banners"]] == ["حيّة"]


async def test_a_tile_active_for_drivers_may_not_point_at_a_rider_screen(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**«مبنيٌّ» حالان لا حال** — مبنيٌّ **عند من يراه**."""
    refused = await client.post(
        "/admin/settings/service-tiles",
        json=_tile(
            key="wrong-side",
            audience="all_drivers",
            status="active",
            destination="/account/bookings",
        ),
        headers=admin_headers,
    )
    assert refused.status_code == 422


# ═══════════════════════ ٦) رمزُ كليك — انحدارٌ قِيس في اليوم نفسِه


async def test_cliq_qr_upload_writes_the_stored_path(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """**`stored.path` لا وجودَ له على `StoredFile`** (عطبٌ قِيس 2026-08-31).

    كان البابُ يرمي `AttributeError` **بعد كتابة الملفّ على القرص**: ٥٠٠
    للمشرف، وملفٌّ يتيمٌ لا صفَّ يشير إليه — **ولا اختبارَ كان يطرقه**.
    """
    response = await client.put(
        "/admin/settings/payments/JO/cliq-qr",
        files={"file": ("qr.png", PNG_BYTES, "image/png")},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text

    from app.models.payment_setting import PaymentSetting

    async with session_factory() as session:
        setting = (
            await session.scalars(
                select(PaymentSetting).where(PaymentSetting.country_code == "JO")
            )
        ).one()
        assert setting.cliq_qr_path and setting.cliq_qr_path.endswith(".png")

"""فئةُ المركبة يقرّرها المشرف (SPEC §٩١-ب) — **وكلٌّ يسقط بحذف ما يحرسه**.

- **الكبتنُ لا يختار الفئةَ ولا يغيّرها**: ما يرسله التطبيقُ الأقدمُ يُهمل بلا خطأ، والمركبةُ تولد «اقتصادي» مؤقّتة.
- **«بحاجة لمراجعة الفئة»**: كلُّ مركبةٍ لم يؤكّدها مشرف، **وفئتُها تعمل** حتى يؤكّدها.
- **الاقتراح** من الطراز والسنة وإرشادِ الفئة — **ولا اقتراحَ بلا إرشادٍ مكتوب**.
- **التأكيدُ** يُخرجها من القائمة، **وتغييرُ الطراز أو السنة يعيدها** إليها والفئةُ كما هي.
- **«الأعلى يأخذ الأدنى»** مطفأٌ افتراضاً (التوزيعُ كما كان)، ومشتعلاً يوصل طلبَ «اقتصادي» لكبتن «مريح» — ولا يوصل العكس.
- **التأكيدُ ينتظر قفلَ صفِّ الكبتن** — فلا يُكتب فوق طرازٍ تغيّر.
- **«غير متاح قريباً»** (البند ٨): فئةٌ بلا آخذٍ متاحٍ قريبٍ غائبةٌ من `available` — **ومعها «الأعلى يأخذ الأدنى»**.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from app.models.driver import DriverDocument
from app.models.enums import CountryCode, DocumentReviewStatus, DocumentType
from app.models.ride_category import RideCategory
from app.models.vehicle import Vehicle
from app.services import categories, dispatch
from tests.helpers import DRIVER, PICKUP, RIDER, approved_driver, auth, bring_online, register

pytestmark = pytest.mark.usefixtures("jordan_settings")

VEHICLE = {"make": "Toyota", "model": "Camry", "year": 2021, "color": "أبيض", "plate_number": "AMM-9191"}


async def _comfort_row(session_factory, **fields) -> None:
    """صفُّ «مريح» كما تبذره `0110` — لتُكتب عليه الإرشاداتُ و«الأعلى يأخذ الأدنى»."""
    async with session_factory() as session:
        session.add(
            RideCategory(country_code=CountryCode.JO, key="comfort", name="مريح", icon="directions_car", seats=4,
                         sort_order=1, is_active=True, is_builtin=True, **fields)
        )
        await session.commit()


async def _review(client: AsyncClient, admin_headers: dict) -> list[dict]:
    response = await client.get("/admin/vehicles/category-review", params={"country_code": "JO"}, headers=admin_headers)
    assert response.status_code == 200, response.text
    return response.json()


async def _eligible(session_factory, driver_id, key: str) -> bool:
    async with session_factory() as session:
        levels = await dispatch._eligible_levels(session, [uuid.UUID(str(driver_id))], key, country=CountryCode.JO)
        return uuid.UUID(str(driver_id)) in levels


async def test_the_captain_cannot_choose_or_change_the_category(client: AsyncClient) -> None:
    driver = await register(client, DRIVER)
    created = await client.post("/drivers/me/vehicles", json=VEHICLE | {"category": "comfort"}, headers=auth(driver))
    assert created.status_code == 201, created.text
    assert created.json()["category"] == "economy"
    assert created.json()["category_confirmed_at"] is None

    changed = await client.patch(
        f"/drivers/me/vehicles/{created.json()['id']}", json={"category": "comfort"}, headers=auth(driver)
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["vehicle"]["category"] == "economy"


async def test_review_list_suggestion_and_confirmation(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    driver_id = str(driver["driver_id"])
    vehicle_id = (await client.get(f"/admin/drivers/{driver_id}/vehicles", headers=admin_headers)).json()[0]["id"]
    base = f"/admin/drivers/{driver_id}/vehicles/{vehicle_id}"

    # **مؤقّتةٌ تعمل**: في القائمة، وتأخذ «اقتصادي» كما كانت
    listed = await _review(client, admin_headers)
    assert [row["vehicle_id"] for row in listed] == [vehicle_id]
    assert await _eligible(session_factory, driver_id, "economy")

    # **ولا اقتراحَ بلا إرشادٍ مكتوب**
    assert (await client.get(f"{base}/category-suggestion", headers=admin_headers)).json()["suggested"] is None

    await _comfort_row(session_factory, min_year=2020, suggest_models=["camry"])
    suggestion = (await client.get(f"{base}/category-suggestion", headers=admin_headers)).json()
    assert suggestion["suggested"] == "comfort" and "2021" in suggestion["reason"]
    assert (await _review(client, admin_headers))[0]["suggested"] == "comfort"

    confirmed = await client.put(f"{base}/category", json={"category": "comfort", "reason": "كامري ٢٠٢١"}, headers=admin_headers)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["category"] == "comfort" and confirmed.json()["category_confirmed_at"] is not None
    assert await _review(client, admin_headers) == []
    assert await _eligible(session_factory, driver_id, "comfort")
    assert not await _eligible(session_factory, driver_id, "economy")

    # **وتغييرُ الطراز يعيدها إلى القائمة والفئةُ كما هي**
    edited = await client.patch(f"/drivers/me/vehicles/{vehicle_id}", json={"model": "Corolla"}, headers=driver["headers"])
    assert edited.status_code == 200, edited.text
    back = await _review(client, admin_headers)
    assert [row["vehicle_id"] for row in back] == [vehicle_id] and back[0]["category"] == "comfort"
    # **ولونٌ وحدَه لا يمسّ التأكيد**
    await client.put(f"{base}/category", json={"category": "comfort"}, headers=admin_headers)
    await client.patch(f"/drivers/me/vehicles/{vehicle_id}", json={"color": "رمادي"}, headers=driver["headers"])
    assert await _review(client, admin_headers) == []


async def test_higher_takes_lower_is_off_by_default_and_never_the_reverse(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    comfort = await approved_driver(client, session_factory, DRIVER, category="comfort")
    await bring_online(client, comfort)
    await _comfort_row(session_factory)

    # **مطفأٌ افتراضاً — التوزيعُ كما كان**
    assert not await _eligible(session_factory, comfort["driver_id"], "economy")
    async with session_factory() as session:
        assert await categories.presence_keys(session, CountryCode.JO, "economy") == frozenset({"economy"})

    row_id = (await client.get("/admin/settings/ride-categories", params={"country_code": "JO"}, headers=admin_headers)).json()[0]["id"]
    switched = await client.patch(f"/admin/settings/ride-categories/{row_id}", json={"serves_lower": True}, headers=admin_headers)
    assert switched.status_code == 200 and switched.json()["serves_lower"] is True
    assert await _eligible(session_factory, comfort["driver_id"], "economy")
    async with session_factory() as session:
        assert await categories.presence_keys(session, CountryCode.JO, "economy") == frozenset({"economy", "comfort"})
        # **ولا يأخذ الأدنى طلبَ الأعلى**
        assert await categories.takers(session, CountryCode.JO, "comfort") == ["comfort"]


async def test_nearby_categories_follow_the_takers(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**«غير متاح قريباً»** (§٩١-ب/٨) — كبتنُ «مريح» وحدَه قريب: «اقتصادي» غيرُ متاح، **حتى يُشعل «الأعلى يأخذ الأدنى»** فيصير
    متاحاً من الكبتن نفسِه. **وزمنُ الوصول مطفأ** — فالقائمةُ لا تنتظر مفتاحَ الكلفة."""
    comfort = await approved_driver(client, session_factory, DRIVER, category="comfort")
    await bring_online(client, comfort)
    await _comfort_row(session_factory)
    rider = auth(await register(client, RIDER))

    body = (await client.get("/rides/eta", params=PICKUP, headers=rider)).json()
    assert body["enabled"] is False and body["available"] == ["comfort"]

    row_id = (await client.get("/admin/settings/ride-categories", params={"country_code": "JO"}, headers=admin_headers)).json()[0]["id"]
    await client.patch(f"/admin/settings/ride-categories/{row_id}", json={"serves_lower": True}, headers=admin_headers)
    body = (await client.get("/rides/eta", params=PICKUP, headers=rider)).json()
    assert body["available"] == ["economy", "comfort"]

    # **وبعيداً لا شيء** — خارج نصف قطر الخريطة
    far = {"lat": PICKUP["lat"] + 0.5, "lng": PICKUP["lng"] + 0.5}
    assert (await client.get("/rides/eta", params=far, headers=rider)).json()["available"] == []


async def test_config_publishes_the_three_names(client: AsyncClient, session_factory) -> None:
    """**الأسماءُ بثلاث لغات** (§٩١-ب/٦) — `/config` ينشر ما كتبه المشرف، **وفارغُه فارغٌ** فيقرأ التطبيقُ العربيَّ أو ترجمتَه."""
    await _comfort_row(session_factory, name_fr="Confort", name_en="Comfort")
    body = (await client.get("/config")).json()
    faces = {face["key"]: face for country in body["countries"] if country["country_code"] == "JO" for face in country["ride_categories"]}
    assert (faces["comfort"]["name_fr"], faces["comfort"]["name_en"]) == ("Confort", "Comfort")
    assert faces["economy"]["name_fr"] is None and faces["economy"]["name"] == "اقتصادي"


async def test_city_taxi_is_granted_only_after_its_licence_is_approved(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**«تاكسي المدينة» بالمنح بعد رخصة التاكسي** (§٩١-ب/٧) — الوثيقةُ معلَّقةً لا تكفي، ومعتمدةً تفتح المنح؛ **والنزعُ بلا شرط**."""
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    created = await client.post(
        "/admin/settings/ride-categories",
        json={"country_code": "JO", "key": "city_taxi", "name": "تاكسي المدينة", "required_document": "taxi_licence"},
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["required_document"] == "taxi_licence"
    access = f"/admin/settings/ride-categories/{created.json()['id']}/access"
    grant = {"driver_id": str(driver["driver_id"]), "granted": True, "reason": "تاكسي مرخَّص"}

    refused = await client.put(access, json=grant, headers=admin_headers)
    assert refused.status_code == 422 and "رخصة التاكسي" in refused.text, refused.text

    async with session_factory() as session:
        session.add(
            DriverDocument(
                driver_id=driver["driver_id"], doc_type=DocumentType.TAXI_LICENCE, file_path="x/taxi.jpg",
                content_type="image/jpeg", size_bytes=10, review_status=DocumentReviewStatus.PENDING,
            )
        )
        await session.commit()
    assert (await client.put(access, json=grant, headers=admin_headers)).status_code == 422

    async with session_factory() as session:
        document = await session.scalar(select(DriverDocument).where(DriverDocument.doc_type == DocumentType.TAXI_LICENCE))
        document.review_status = DocumentReviewStatus.APPROVED
        await session.commit()
    granted = await client.put(access, json=grant, headers=admin_headers)
    assert granted.status_code == 200, granted.text
    assert await _eligible(session_factory, driver["driver_id"], "city_taxi")

    revoked = await client.put(access, json=grant | {"granted": False}, headers=admin_headers)
    assert revoked.status_code == 200, revoked.text


async def test_confirmation_waits_for_the_captain_row_lock(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**القفلُ نفسُه مقيس** — تعديلُ الكبتن طرازَه يمسك صفَّه ويُفرغ التأكيد، فالتأكيدُ ينتظره ولا يُكتب فوق قراءةٍ قديمة."""
    driver = await approved_driver(client, session_factory, DRIVER)
    async with session_factory() as session:
        vehicle_id = await session.scalar(select(Vehicle.id).where(Vehicle.driver_id == driver["driver_id"]))
    async with session_factory() as holder:
        await holder.execute(text("SELECT id FROM drivers WHERE id = :d FOR NO KEY UPDATE"), {"d": str(driver["driver_id"])})
        pending = asyncio.create_task(
            client.put(f"/admin/drivers/{driver['driver_id']}/vehicles/{vehicle_id}/category",
                       json={"category": "comfort"}, headers=admin_headers)
        )
        await asyncio.sleep(1.0)
        assert not pending.done(), "التأكيدُ لم ينتظر قفلَ صفِّ الكبتن"
        await holder.rollback()
    response = await asyncio.wait_for(pending, timeout=20)
    assert response.status_code == 200 and response.json()["category"] == "comfort"

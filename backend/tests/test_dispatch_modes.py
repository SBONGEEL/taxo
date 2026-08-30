"""نمطُ التوزيع والتبريد — قرارُ المالك 2026-08-30، و§5.3 عُدِّلت معهما.

**وثلاثةُ ما يُقاس هنا كلُّها أشياءُ كانت مستحيلةً أمسِ**:

1. **لا استبعادَ دائم**: من رفض يعود مرشَّحاً **في الطلب نفسِه** بعد تبريده.
   وكان `tried: set` في ذاكرة المهمّة يستبعده بقيّةَ الرحلة، **فرحلةٌ بكبتنٍ
   واحدٍ تنتهي `no_driver_found` بعد رفضةٍ واحدة**.
2. **والبثُّ يعرض على دفعةٍ معاً** — والقبولُ من أيِّ عضوٍ فيها يمرّ.
3. **وإلغاءُ الراكب يطوي البطاقة فوراً** لا حين تنقضي مهلتُها. **وموضعُ الطيّ
   `finally`**، لأن الإلغاء يُلغي مهمّةَ التوزيع من داخل انتظارها.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import replace

import pytest
from httpx import AsyncClient
from httpx_ws import aconnect_ws

from app.core.redis_client import get_redis_client
from app.models.enums import DispatchMode
from app.services import dispatch, dispatch_settings
from tests.helpers import (
    SECOND_DRIVER,
    request_ride,
    wait_for_offer,
    wait_until,
)
from tests.conftest import ws_client
from tests.test_dispatch import _driver, _rider
from tests.test_ws import WS_DRIVER, _receive

pytestmark = pytest.mark.asyncio


def _rules(monkeypatch: pytest.MonkeyPatch, **overrides) -> None:
    """**المهلُ موضوعُ هذه الاختبارات لا ظرفُها** — فتُضبط هنا لا في الفكسچر."""
    monkeypatch.setattr(
        dispatch_settings,
        "DEFAULTS",
        replace(dispatch_settings.DEFAULTS, **overrides),
    )


async def test_a_refusing_driver_is_offered_again_in_the_same_ride(
    client: AsyncClient,
    jordan_settings: None,
    session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**التبريدُ لا الاستبعاد** — والكبتنُ الوحيدُ يرى الطلبَ مرّتين.

    وقبل اليوم كان يُستبعد بقيّةَ الرحلة، **فرحلةٌ في سوقٍ فيه كبتنٌ واحدٌ
    تموت على أول رفضة** ولو كان راجعاً بعد ثانيتين.
    """
    _rules(
        monkeypatch,
        offer_timeout_seconds=3,
        cooldown_seconds=1,
        total_timeout_seconds=25,
        max_attempts=3,
    )
    driver = await _driver(client, session_factory, plate_number="AMM-1")
    ride = await request_ride(client, await _rider(client))

    await wait_for_offer(ride["id"], driver["driver_id"])
    declined = await client.post(
        f"/rides/{ride['id']}/decline", headers=driver["headers"]
    )
    assert declined.status_code in {200, 204}, declined.text

    redis = get_redis_client()

    async def _gone() -> bool:
        return await dispatch.current_offer(redis, uuid.UUID(ride["id"])) is None

    await wait_until(_gone, message="البطاقةُ لم تُطوَ بعد الرفض")

    # **وهنا الفرقُ كلُّه**: يعود إليه بعد تبريده، في الطلب نفسِه
    await wait_for_offer(ride["id"], driver["driver_id"])


async def test_broadcast_shows_the_card_to_the_whole_batch_at_once(
    client: AsyncClient,
    jordan_settings: None,
    session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**البثُّ يعرض على دفعةٍ معاً** — واثنان يحملان البطاقةَ في لحظةٍ واحدة."""
    _rules(
        monkeypatch,
        mode=DispatchMode.BROADCAST,
        offer_timeout_seconds=6,
        total_timeout_seconds=20,
        broadcast_batch_size=4,
    )
    first = await _driver(client, session_factory, plate_number="AMM-1")
    second = await _driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-7"
    )
    ride = await request_ride(client, await _rider(client))

    redis = get_redis_client()

    async def _both() -> bool:
        members = await dispatch.broadcast_members(redis, uuid.UUID(ride["id"]))
        return {first["driver_id"], second["driver_id"]} <= members

    await wait_until(_both, message="البثُّ لم يصل الاثنين معاً")

    # **وأيُّ عضوٍ في الدفعة يقبل** — والفصلُ بينهم في حال الرحلة لا في المهلة
    accepted = await client.post(
        f"/rides/{ride['id']}/accept", headers=second["headers"]
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"


async def test_a_second_driver_in_the_batch_loses_by_status_not_by_timeout(
    client: AsyncClient,
    jordan_settings: None,
    session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**أولُ من يقبل يأخذ، والخاسرُ يُردّ بحالٍ لا بمهلة**.

    وهو ما يجعل البثَّ آمناً بلا قفلٍ جديد: انتقالُ `searching → accepted` تحت
    قفل صفِّ الرحلة هو الفاصل، **لا سباقُ من وصلت رسالتُه أوّلاً**.
    """
    _rules(
        monkeypatch,
        mode=DispatchMode.BROADCAST,
        offer_timeout_seconds=6,
        total_timeout_seconds=20,
    )
    first = await _driver(client, session_factory, plate_number="AMM-1")
    second = await _driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-7"
    )
    ride = await request_ride(client, await _rider(client))

    redis = get_redis_client()
    await wait_until(
        lambda: dispatch.broadcast_members(redis, uuid.UUID(ride["id"])),
        message="لم تُبَثّ البطاقة",
    )

    assert (
        await client.post(f"/rides/{ride['id']}/accept", headers=first["headers"])
    ).status_code == 200

    late = await client.post(
        f"/rides/{ride['id']}/accept", headers=second["headers"]
    )
    assert late.status_code >= 400, "قبلَها اثنان — والدفعةُ يفوز بها واحد"


async def test_cancelling_while_searching_folds_the_card_at_once(
    client: AsyncClient,
    jordan_settings: None,
    session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**الإلغاءُ يطوي البطاقةَ فوراً** لا حين تنقضي مهلتُها.

    **ومهلةُ العرض هنا طويلةٌ عمداً**: بمهلةٍ قصيرةٍ يُقرأ انقضاؤها الطبيعيُّ
    طيّاً — **واختبارٌ يمرّ بسبب مهلته لا بسبب ما يقيس ليس اختباراً**.
    """
    _rules(monkeypatch, offer_timeout_seconds=60, total_timeout_seconds=120)
    driver = await _driver(client, session_factory, plate_number="AMM-1")
    # **و`_rider` هنا تعيد الترويسةَ نفسَها** لا كائناً يحملها (خلافاً
    # لـ`helpers.rider_session`) — واسمان لشيئين مختلفين يوقعان في هذا
    rider_headers = await _rider(client)
    ride = await request_ride(client, rider_headers)
    await wait_for_offer(ride["id"], driver["driver_id"])

    cancelled = await client.post(
        f"/rides/{ride['id']}/cancel",
        json={"reason": "غيّرتُ رأيي"},
        headers=rider_headers,
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled_by_rider"

    redis = get_redis_client()

    async def _folded() -> bool:
        single = await dispatch.current_offer(redis, uuid.UUID(ride["id"]))
        batch = await dispatch.broadcast_members(redis, uuid.UUID(ride["id"]))
        return single is None and not batch

    await wait_until(
        _folded,
        timeout=15.0,
        message="البطاقةُ بقيت على شاشة الكبتن بعد إلغاء الراكب",
    )


async def test_accepting_in_a_batch_folds_every_other_card_at_once(
    client: AsyncClient,
    jordan_settings: None,
    session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**من لم يفز تُطوى بطاقتُه فوراً، ومن فاز تبقى بطاقتُه**.

    **والعطبُ الذي يقيسه هذا**: بطاقةٌ تبقى على شاشة من لم يفز حتى تنقضي
    مهلتُها **تجعله يضغط «اقبل» على رحلةٍ أُخذت** — ويُردّ بخطأٍ لا يفهمه، وقد
    ترك ما في يده لأجلها.

    **والمهلةُ طويلةٌ عمداً**: بمهلةٍ قصيرةٍ يُقرأ انقضاؤها الطبيعيُّ طيّاً،
    **واختبارٌ يمرّ بسبب مهلته لا بسبب ما يقيس ليس اختباراً**.
    """
    _rules(
        monkeypatch,
        mode=DispatchMode.BROADCAST,
        offer_timeout_seconds=60,
        total_timeout_seconds=120,
        broadcast_batch_size=4,
    )
    first = await _driver(client, session_factory, plate_number="AMM-1")
    second = await _driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-7"
    )
    ride = await request_ride(client, await _rider(client))

    redis = get_redis_client()

    async def _both() -> bool:
        members = await dispatch.broadcast_members(redis, uuid.UUID(ride["id"]))
        return {first["driver_id"], second["driver_id"]} <= members

    await wait_until(_both, message="البثُّ لم يصل الاثنين معاً")

    accepted = await client.post(
        f"/rides/{ride['id']}/accept", headers=first["headers"]
    )
    assert accepted.status_code == 200, accepted.text

    async def _loser_folded() -> bool:
        return (
            await redis.get(dispatch.driver_offer_key(second["driver_id"])) is None
        )

    await wait_until(
        _loser_folded,
        timeout=15.0,
        message="بطاقةُ من لم يفز بقيت — فيضغط «اقبل» على رحلةٍ أُخذت",
    )

    # **ومفتاحُ الفائز يُحرَّر من مسار القبول نفسِه** (`routers/rides.py`)
    # لا من الطيّ — فهو ليس مقياساً هنا. **والمقياسُ الصادقُ ما يصل شاشتَه**،
    # ويُقاس بالمقبس في `test_the_winner_is_not_told_his_offer_expired`.
    members = await dispatch.broadcast_members(redis, uuid.UUID(ride["id"]))
    assert second["driver_id"] not in members


async def test_the_winner_is_not_told_his_offer_expired(
    client: AsyncClient,
    jordan_settings: None,
    session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**ما يصل شاشةَ الفائز** — ولا شيء أصدقُ من المقبس نفسِه.

    **و`offer_expired` إلى الفائز يمحو من شاشته الرحلةَ التي قبِلها للتوّ**،
    فيراها تختفي بلا سبب. **ومفتاحُ ريدِس لا يقيس هذا**: مسارُ القبول يحرّره
    بنفسه، فالمفتاحُ يُحرَّر في الحالين ولا يفرّق بينهما.
    """
    _rules(
        monkeypatch,
        mode=DispatchMode.BROADCAST,
        offer_timeout_seconds=60,
        total_timeout_seconds=120,
        broadcast_batch_size=4,
    )
    first = await _driver(client, session_factory, plate_number="AMM-1")
    second = await _driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-7"
    )
    rider_headers = await _rider(client)

    async with ws_client() as sockets:
        async with aconnect_ws(
            f"{WS_DRIVER}?token={first['token']}", client=sockets
        ) as winner_ws:
            assert (await _receive(winner_ws))["type"] == "connected"
            async with aconnect_ws(
                f"{WS_DRIVER}?token={second['token']}", client=sockets
            ) as loser_ws:
                assert (await _receive(loser_ws))["type"] == "connected"

                ride = await request_ride(client, rider_headers)
                assert (await _receive(winner_ws, of_type="ride_offer"))["ride"][
                    "id"
                ] == ride["id"]
                assert (await _receive(loser_ws, of_type="ride_offer"))["ride"][
                    "id"
                ] == ride["id"]

                assert (
                    await client.post(
                        f"/rides/{ride['id']}/accept", headers=first["headers"]
                    )
                ).status_code == 200

                # **من لم يفز يُقال له إن الطلبَ انتهى** — فتُطوى بطاقتُه
                expired = await _receive(loser_ws, of_type="offer_expired")
                assert expired["ride_id"] == ride["id"]

                # **والفائزُ لا يُقال له ذلك**: أولُ ما يصله بعد القبول ليس
                # `offer_expired` — ولو وصله لَمحا من شاشته رحلتَه.
                nxt = await asyncio.wait_for(winner_ws.receive_json(), timeout=8.0)
                assert nxt["type"] != "offer_expired", (
                    "قيل للفائز إن عرضَه انتهى — فتُمحى من شاشته رحلةٌ قبِلها"
                )

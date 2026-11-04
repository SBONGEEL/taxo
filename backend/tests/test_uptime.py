"""مراقبةُ الوصول: لا إشعارَ قبل دقيقتين، وإشعارٌ واحدٌ للانقطاع الواحد، وعودةٌ تُعلَن لمن أُشعر وحدَه."""

from __future__ import annotations

import pytest

from app.core.redis_client import get_redis_client
from app.services import admin_alerts, alert_capture, uptime


@pytest.fixture
def shipped(monkeypatch) -> list[tuple[str, dict]]:
    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(alert_capture, "ship_after_commit", lambda session, kind, model, pk, **extra: calls.append((kind, extra)))
    return calls


async def _clean(redis) -> None:
    for name in uptime.TARGETS:
        await redis.delete(f"uptime:down_since:{name}", f"uptime:alerted:{name}")


def fetcher(down: set[str]):
    async def fetch(url: str) -> bool:
        return not any(uptime.TARGETS[name] == url for name in down)
    return fetch


async def test_short_outage_never_wakes_the_owner(shipped) -> None:
    redis = get_redis_client()
    await _clean(redis)
    t0 = 1_000_000.0
    # **رفعٌ يعيد الخلفيّةَ ثوانيَ، أو دقيقةٌ ونصفٌ من التعثّر** — لا إشعار، ولا «عودة» بلا سقوطٍ أُعلن
    assert await uptime.probe(redis, fetch=fetcher({"api"}), now=t0) == {"api": "down", "app": "up"}
    assert await uptime.probe(redis, fetch=fetcher({"api"}), now=t0 + 90) == {"api": "down", "app": "up"}
    assert await uptime.probe(redis, fetch=fetcher(set()), now=t0 + 150) == {"api": "up", "app": "up"}
    assert shipped == []


async def test_two_minutes_alert_once_then_recovery(shipped) -> None:
    redis = get_redis_client()
    await _clean(redis)
    t0 = 2_000_000.0
    for step in (0, 60, 120, 180, 240):
        await uptime.probe(redis, fetch=fetcher({"app"}), now=t0 + step)
    # **إشعارٌ واحدٌ للانقطاع الواحد** مهما تكرّر الفحص
    assert shipped == [("service_down", {"target": "app", "minutes": 2})]
    await uptime.probe(redis, fetch=fetcher(set()), now=t0 + 400)
    assert shipped[-1] == ("service_up", {"target": "app", "minutes": 7})
    # **والانقطاعُ التالي يُشعَر به من جديد** — الحالُ صُفّرت
    for step in (0, 130):
        await uptime.probe(redis, fetch=fetcher({"app"}), now=t0 + 1_000 + step)
    assert [kind for kind, _ in shipped] == ["service_down", "service_up", "service_down"]


def test_alert_text_names_the_link_and_duration() -> None:
    alert = admin_alerts.sample_alert("service_down")
    alert.data = {"target": "api", "minutes": 3}
    title, body = admin_alerts.tray_text(alert)
    assert "لا يُبلَغ" in title and "api.tajora.ly" in body and "3 دقيقة" in body

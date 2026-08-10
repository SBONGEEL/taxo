"""اختبار الاتصال في صفحة العقود (SPEC القسم 13/7 — المرحلة 8)."""

from __future__ import annotations

import json

from httpx import AsyncClient

from tests.helpers import MAPBOX_SECRET, enable_sms_provider

MAPBOX_VALUES = {"public_token": "pk.test", "secret_token": MAPBOX_SECRET}


async def _save(client: AsyncClient, headers: dict, key: str, **body) -> dict:
    response = await client.put(f"/admin/providers/{key}", json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def _test_connection(
    client: AsyncClient, headers: dict, credential_id: str, **body
) -> dict:
    response = await client.post(
        f"/admin/providers/{credential_id}/test", json=body, headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_test_connection_is_admin_only(
    client: AsyncClient, admin_headers: dict, support_headers: dict
) -> None:
    saved = await _save(
        client, admin_headers, "mapbox", values=MAPBOX_VALUES, is_active=True
    )
    denied = await client.post(
        f"/admin/providers/{saved['id']}/test", json={}, headers=support_headers
    )
    assert denied.status_code == 403


async def test_mapbox_test_uses_contract_token_and_stamps_last_tested_at(
    client: AsyncClient, admin_headers: dict
) -> None:
    """النداء الحقيقي مُستبدَل، وقراءةُ التوكن من جدول العقود تبقى حقيقية.

    (`stub_mapbox` يؤكد أن التوكن هو `MAPBOX_SECRET` وإلا فشل الاختبار.)
    """
    saved = await _save(
        client, admin_headers, "mapbox", values=MAPBOX_VALUES, is_active=True
    )
    assert saved["last_tested_at"] is None

    result = await _test_connection(client, admin_headers, saved["id"])
    assert result["ok"] is True
    assert "10.000" in result["detail"]  # مسافة المسار المُستبدَل
    assert result["credential"]["last_tested_at"] is not None
    # القيم تبقى مقنّعة في ردّ الاختبار كما في كل ردٍّ آخر
    assert result["credential"]["values"]["secret_token"] == "****"


async def test_failing_test_returns_ok_false_not_an_error(
    client: AsyncClient, admin_headers: dict, monkeypatch
) -> None:
    """فشلُ العقد جوابٌ يُقرأ، لا شاشةُ خطأ."""
    from app.core.exceptions import RoutingFailed
    from app.services import directions

    async def _boom(token, pickup, dropoff):
        raise RoutingFailed()

    monkeypatch.setattr(directions, "fetch_route", _boom)

    saved = await _save(
        client, admin_headers, "mapbox", values=MAPBOX_VALUES, is_active=True
    )
    result = await _test_connection(client, admin_headers, saved["id"])

    assert result["ok"] is False
    assert result["detail"]
    # زمن الاختبار يُسجَّل في الحالتين: السؤال «متى اختُبر» لا «متى نجح»
    assert result["credential"]["last_tested_at"] is not None


async def test_inactive_contract_can_be_tested_before_activation(
    client: AsyncClient, admin_headers: dict
) -> None:
    """يُختبر العقد قبل أن يُفتح لا بعد — وإلا صار التفعيل قفزةً في الظلام."""
    saved = await _save(
        client, admin_headers, "mapbox", values=MAPBOX_VALUES, is_active=False
    )
    result = await _test_connection(client, admin_headers, saved["id"])
    assert result["ok"] is True
    assert result["credential"]["is_active"] is False


async def test_sms_test_without_phone_sends_nothing(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    from app.core.redis_client import get_redis_client
    from app.services.sms import last_message

    await enable_sms_provider(session_factory)
    catalog = (await client.get("/admin/providers", headers=admin_headers)).json()
    credential = next(
        row for row in catalog["credentials"] if row["provider_key"] == "sms"
    )

    result = await _test_connection(client, admin_headers, credential["id"])
    assert result["ok"] is True
    assert await last_message(get_redis_client(), "+962790000009") is None


async def test_sms_test_with_phone_sends_a_real_message(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    from app.core.redis_client import get_redis_client
    from app.services.sms import last_message

    await enable_sms_provider(session_factory)
    catalog = (await client.get("/admin/providers", headers=admin_headers)).json()
    credential = next(
        row for row in catalog["credentials"] if row["provider_key"] == "sms"
    )

    result = await _test_connection(
        client, admin_headers, credential["id"], test_phone="+962790000009"
    )
    assert result["ok"] is True
    assert await last_message(get_redis_client(), "+962790000009") is not None


async def test_telr_and_cliq_and_payout_mocks_report_ready(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    from tests.helpers import (
        enable_card_provider,
        enable_cliq_provider,
        enable_payout_provider,
        enable_push_provider,
    )

    await enable_card_provider(session_factory)
    await enable_cliq_provider(session_factory)
    await enable_payout_provider(session_factory)
    await enable_push_provider(session_factory)

    catalog = (await client.get("/admin/providers", headers=admin_headers)).json()
    for key in ("telr", "cliq_acquirer", "payout", "fcm"):
        credential = next(
            row for row in catalog["credentials"] if row["provider_key"] == key
        )
        result = await _test_connection(client, admin_headers, credential["id"])
        assert result["ok"] is True, (key, result)


async def test_test_connection_is_audited_without_values(
    client: AsyncClient, admin_headers: dict
) -> None:
    saved = await _save(
        client, admin_headers, "mapbox", values=MAPBOX_VALUES, is_active=True
    )
    await _test_connection(client, admin_headers, saved["id"])

    logs = (
        await client.get(
            "/admin/settings/audit-logs?entity_type=provider_credential",
            headers=admin_headers,
        )
    ).json()
    tests = [log for log in logs if log["details"].get("action") == "test_connection"]
    assert len(tests) == 1
    assert tests[0]["details"]["ok"] is True
    assert MAPBOX_SECRET not in json.dumps(logs)

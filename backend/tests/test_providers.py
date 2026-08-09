from __future__ import annotations

import json

from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import engine
from app.models.enums import ProviderKey
from app.models.provider_credential import ProviderCredential
from sqlalchemy.ext.asyncio import async_sessionmaker

MAPBOX_PUBLIC = "pk.test-public-token"
MAPBOX_SECRET = "sk.test-secret-token"


async def _register(client: AsyncClient, payload: dict) -> dict:
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def _save_mapbox(client: AsyncClient, headers: dict, **overrides) -> dict:
    response = await client.put(
        "/admin/providers/mapbox",
        json={
            "values": {
                "public_token": MAPBOX_PUBLIC,
                "secret_token": MAPBOX_SECRET,
            },
            "is_active": True,
        }
        | overrides,
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------- الصلاحيات


async def test_providers_page_is_admin_only(
    client: AsyncClient, support_headers: dict, admin_headers: dict
) -> None:
    # صفحة العقود لـ admin حصراً — support لا يراها (SPEC القسم 13/8)
    assert (await client.get("/admin/providers", headers=support_headers)).status_code == 403
    assert (await client.get("/admin/providers", headers=admin_headers)).status_code == 200


async def test_providers_require_authentication(client: AsyncClient) -> None:
    assert (await client.get("/admin/providers")).status_code == 401


async def test_catalog_lists_every_provider_card(
    client: AsyncClient, admin_headers: dict
) -> None:
    body = (await client.get("/admin/providers", headers=admin_headers)).json()
    keys = {provider["provider_key"] for provider in body["providers"]}
    assert keys == {key.value for key in ProviderKey}
    assert body["credentials"] == []


# ---------------------------------------------------------- التخزين والتقنيع


async def test_secret_values_are_masked_in_responses(
    client: AsyncClient, admin_headers: dict
) -> None:
    saved = await _save_mapbox(client, admin_headers)

    assert saved["values"]["secret_token"] == "****"
    # العام بطبيعته يبقى ظاهراً للمشرف
    assert saved["values"]["public_token"] == MAPBOX_PUBLIC


async def test_credentials_are_encrypted_at_rest(
    client: AsyncClient, admin_headers: dict
) -> None:
    await _save_mapbox(client, admin_headers)

    async with async_sessionmaker(bind=engine, expire_on_commit=False)() as session:
        row = await session.scalar(select(ProviderCredential))

    stored = json.dumps(row.credentials)
    assert MAPBOX_SECRET not in stored
    assert MAPBOX_PUBLIC not in stored
    assert row.credentials["ciphertext"].startswith("gAAAA")


async def test_resaving_masked_secret_keeps_stored_value(
    client: AsyncClient, admin_headers: dict
) -> None:
    """اللوحة تعيد إرسال `****` للحقول التي لم يعدّلها المشرف."""
    await _save_mapbox(client, admin_headers)

    await client.put(
        "/admin/providers/mapbox",
        json={"values": {"public_token": "pk.rotated", "secret_token": "****"}},
        headers=admin_headers,
    )

    config = (await client.get("/config")).json()
    assert config["providers"]["mapbox"]["public_token"] == "pk.rotated"

    from app.services.providers import credentials as credentials_service

    async with async_sessionmaker(bind=engine, expire_on_commit=False)() as session:
        values = await credentials_service.get_values(session, ProviderKey.MAPBOX)
    assert values["secret_token"] == MAPBOX_SECRET  # لم يُمح


async def test_unknown_field_is_rejected(
    client: AsyncClient, admin_headers: dict
) -> None:
    response = await client.put(
        "/admin/providers/mapbox",
        json={"values": {"public_token": "pk.x", "secret_token": "sk.x", "oops": "y"}},
        headers=admin_headers,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"


async def test_missing_required_field_is_rejected(
    client: AsyncClient, admin_headers: dict
) -> None:
    response = await client.put(
        "/admin/providers/mapbox",
        json={"values": {"public_token": "pk.x"}},
        headers=admin_headers,
    )
    assert response.status_code == 422


async def test_scope_must_match_provider_kind(
    client: AsyncClient, admin_headers: dict
) -> None:
    # Mapbox عقد عام — لا يُربط بدولة
    global_with_country = await client.put(
        "/admin/providers/mapbox",
        json={
            "country_code": "JO",
            "values": {"public_token": "pk.x", "secret_token": "sk.x"},
        },
        headers=admin_headers,
    )
    assert global_with_country.status_code == 422

    # Telr عقد لكل دولة — لا يُحفظ بلا دولة
    per_country_without_country = await client.put(
        "/admin/providers/telr",
        json={"values": {"store_id": "1", "auth_key": "k"}},
        headers=admin_headers,
    )
    assert per_country_without_country.status_code == 422


# ------------------------------------------------- تفعيل المزود يفعّل ميزته


async def test_activating_telr_enables_card_feature_for_its_country_only(
    client: AsyncClient, admin_headers: dict
) -> None:
    saved = await client.put(
        "/admin/providers/telr",
        json={
            "country_code": "JO",
            "values": {"store_id": "12345", "auth_key": "secret-key", "test_mode": True},
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert saved.status_code == 200, saved.text

    flags = (
        await client.get("/admin/settings/feature-flags", headers=admin_headers)
    ).json()
    by_country = {row["country_code"]: row["flags"] for row in flags}
    assert by_country["JO"]["card_enabled"] is True
    assert by_country["LY"]["card_enabled"] is False  # ليبيا كاش فقط

    deactivated = await client.post(
        f"/admin/providers/{saved.json()['id']}/deactivate", headers=admin_headers
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    flags = (
        await client.get("/admin/settings/feature-flags", headers=admin_headers)
    ).json()
    by_country = {row["country_code"]: row["flags"] for row in flags}
    assert by_country["JO"]["card_enabled"] is False


async def test_deleting_credential_disables_its_feature(
    client: AsyncClient, admin_headers: dict
) -> None:
    saved = await client.put(
        "/admin/providers/telr",
        json={
            "country_code": "JO",
            "values": {"store_id": "1", "auth_key": "k"},
            "is_active": True,
        },
        headers=admin_headers,
    )
    credential_id = saved.json()["id"]

    assert (
        await client.delete(f"/admin/providers/{credential_id}", headers=admin_headers)
    ).status_code == 204

    flags = (
        await client.get("/admin/settings/feature-flags", headers=admin_headers)
    ).json()
    by_country = {row["country_code"]: row["flags"] for row in flags}
    assert by_country["JO"]["card_enabled"] is False


async def test_provider_changes_are_audited_without_secrets(
    client: AsyncClient, admin_headers: dict
) -> None:
    await _save_mapbox(client, admin_headers)

    logs = (
        await client.get(
            "/admin/settings/audit-logs?entity_type=provider_credential",
            headers=admin_headers,
        )
    ).json()
    assert len(logs) == 1
    assert logs[0]["details"]["provider_key"] == "mapbox"
    assert sorted(logs[0]["details"]["changed_fields"]) == [
        "public_token",
        "secret_token",
    ]
    assert MAPBOX_SECRET not in json.dumps(logs[0]["details"])


# --------------------------------------------------------------- GET /config


async def test_config_is_public_and_hides_secrets(client: AsyncClient) -> None:
    response = await client.get("/config")
    assert response.status_code == 200

    body = response.json()
    assert body["app"] == "TAXO"
    assert body["auth"]["method"] == "password"
    assert {c["country_code"] for c in body["countries"]} == {"LY", "JO"}
    assert {c["country_code"]: c["currency"] for c in body["countries"]} == {
        "LY": "LYD",
        "JO": "JOD",
    }
    assert body["providers"]["mapbox"] == {}  # لا عقد محفوظ بعد


async def test_config_exposes_only_publishable_mapbox_token(
    client: AsyncClient, admin_headers: dict
) -> None:
    await _save_mapbox(client, admin_headers)

    body = (await client.get("/config")).json()
    assert body["providers"]["mapbox"] == {"public_token": MAPBOX_PUBLIC}
    assert MAPBOX_SECRET not in json.dumps(body)


async def test_inactive_provider_is_not_published(
    client: AsyncClient, admin_headers: dict
) -> None:
    await _save_mapbox(client, admin_headers, is_active=False)

    body = (await client.get("/config")).json()
    assert body["providers"]["mapbox"] == {}


async def test_config_reflects_feature_flags(
    client: AsyncClient, admin_headers: dict
) -> None:
    await client.put(
        "/admin/settings/feature-flags",
        json={"country_code": "JO", "feature_key": "cliq_enabled", "enabled": True},
        headers=admin_headers,
    )

    body = (await client.get("/config?country_code=JO")).json()
    assert len(body["countries"]) == 1
    assert body["countries"][0]["features"]["cliq_enabled"] is True
    assert body["countries"][0]["features"]["card_enabled"] is False


# ----------------------------------------- تفعيل مزود SMS يحوّل الدخول لـ OTP


async def test_activating_sms_provider_switches_auth_to_otp(
    client: AsyncClient, admin_headers: dict
) -> None:
    """نقطة التبديل الوحيدة: حالة العقد في القاعدة، لا متغير بيئة ولا تعديل endpoint."""
    assert (await client.get("/auth/method")).json()["method"] == "password"

    saved = await client.put(
        "/admin/providers/sms",
        json={
            "values": {
                "provider_name": "mock",
                "api_key": "sms-secret",
                "sender_id": "TAXO",
            },
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert saved.status_code == 200, saved.text

    assert (await client.get("/auth/method")).json()["method"] == "otp"
    assert (await client.get("/config")).json()["auth"]["method"] == "otp"

    # المرحلة 8 هي من تبني تدفق OTP — حتى ذلك الحين يرفض بوضوح لا بانهيار
    login = await client.post(
        "/auth/login",
        json={"phone": "0791234567", "password": "whatever1", "country_code": "JO"},
    )
    assert login.status_code == 501

    await client.post(
        f"/admin/providers/{saved.json()['id']}/deactivate", headers=admin_headers
    )
    assert (await client.get("/auth/method")).json()["method"] == "password"

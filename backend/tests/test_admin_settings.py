from __future__ import annotations

from httpx import AsyncClient


async def _register(client: AsyncClient, payload: dict) -> dict:
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _pricing_payload(**overrides) -> dict:
    return {
        "country_code": "JO",
        "vehicle_category": "economy",
        "base_fare": "0.800",
        "price_per_km": "0.350",
        "price_per_min": "0.050",
        "minimum_fare": "1.500",
        "cancellation_fee": "0.750",
    } | overrides


# ---------------------------------------------------------------- الصلاحيات


async def test_settings_require_authentication(client: AsyncClient) -> None:
    assert (await client.get("/admin/settings/pricing")).status_code == 401


async def test_rider_cannot_read_settings(
    client: AsyncClient, rider_payload: dict
) -> None:
    body = await _register(client, rider_payload)
    headers = {"Authorization": f"Bearer {body['tokens']['access_token']}"}

    response = await client.get("/admin/settings/pricing", headers=headers)
    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


async def test_support_reads_but_cannot_write(
    client: AsyncClient, support_headers: dict
) -> None:
    assert (
        await client.get("/admin/settings/pricing", headers=support_headers)
    ).status_code == 200

    blocked = await client.post(
        "/admin/settings/pricing", json=_pricing_payload(), headers=support_headers
    )
    assert blocked.status_code == 403


# ------------------------------------------------------------------ التسعير


async def test_admin_crud_pricing_rule(
    client: AsyncClient, admin_headers: dict
) -> None:
    created = await client.post(
        "/admin/settings/pricing", json=_pricing_payload(), headers=admin_headers
    )
    assert created.status_code == 201, created.text
    rule = created.json()
    assert rule["base_fare"] == "0.800"  # NUMERIC(12,3) يعود نصاً لا float

    rule_id = rule["id"]
    updated = await client.patch(
        f"/admin/settings/pricing/{rule_id}",
        json={"minimum_fare": "2.000"},
        headers=admin_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["minimum_fare"] == "2.000"
    assert updated.json()["base_fare"] == "0.800"  # لم تُمس بقية الحقول

    listed = await client.get(
        "/admin/settings/pricing?country_code=JO", headers=admin_headers
    )
    assert [r["id"] for r in listed.json()] == [rule_id]

    deleted = await client.delete(
        f"/admin/settings/pricing/{rule_id}", headers=admin_headers
    )
    assert deleted.status_code == 204
    assert (await client.get("/admin/settings/pricing", headers=admin_headers)).json() == []


async def test_pricing_rule_is_unique_per_country_and_category(
    client: AsyncClient, admin_headers: dict
) -> None:
    first = await client.post(
        "/admin/settings/pricing", json=_pricing_payload(), headers=admin_headers
    )
    assert first.status_code == 201

    duplicate = await client.post(
        "/admin/settings/pricing", json=_pricing_payload(), headers=admin_headers
    )
    assert duplicate.status_code == 409


async def test_pricing_rejects_negative_amounts(
    client: AsyncClient, admin_headers: dict
) -> None:
    response = await client.post(
        "/admin/settings/pricing",
        json=_pricing_payload(base_fare="-1.000"),
        headers=admin_headers,
    )
    assert response.status_code == 422


# ------------------------------------------------------------ مفاتيح الميزات


async def test_feature_flags_default_to_disabled(
    client: AsyncClient, admin_headers: dict
) -> None:
    response = await client.get("/admin/settings/feature-flags", headers=admin_headers)
    assert response.status_code == 200

    by_country = {row["country_code"]: row["flags"] for row in response.json()}
    assert set(by_country) == {"LY", "JO"}
    # غياب الصف = معطّل — لا يُفترض التفعيل أبداً
    assert not any(by_country["LY"].values())
    assert by_country["JO"]["cliq_enabled"] is False


async def test_admin_toggles_feature_flag(
    client: AsyncClient, admin_headers: dict
) -> None:
    response = await client.put(
        "/admin/settings/feature-flags",
        json={"country_code": "JO", "feature_key": "wallet_enabled", "enabled": True},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["flags"]["wallet_enabled"] is True

    off = await client.put(
        "/admin/settings/feature-flags",
        json={"country_code": "JO", "feature_key": "wallet_enabled", "enabled": False},
        headers=admin_headers,
    )
    assert off.json()["flags"]["wallet_enabled"] is False


async def test_unknown_feature_key_is_rejected(
    client: AsyncClient, admin_headers: dict
) -> None:
    response = await client.put(
        "/admin/settings/feature-flags",
        json={"country_code": "JO", "feature_key": "surge_pricing", "enabled": True},
        headers=admin_headers,
    )
    assert response.status_code == 422


# ------------------------------------------------------------------- العمولة


async def test_commission_starts_disabled_and_syncs_with_flag(
    client: AsyncClient, admin_headers: dict
) -> None:
    response = await client.patch(
        "/admin/settings/commission/JO",
        json={"commission_enabled": True, "commission_percent": "12.50"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["commission_enabled"] is True
    assert body["commission_percent"] == "12.50"
    assert body["applies_to"] == "all_rides"

    flags = await client.get("/admin/settings/feature-flags", headers=admin_headers)
    by_country = {row["country_code"]: row["flags"] for row in flags.json()}
    assert by_country["JO"]["commission_enabled"] is True
    assert by_country["LY"]["commission_enabled"] is False


async def test_flag_toggle_syncs_back_into_commission_setting(
    client: AsyncClient, admin_headers: dict
) -> None:
    await client.put(
        "/admin/settings/feature-flags",
        json={"country_code": "LY", "feature_key": "commission_enabled", "enabled": True},
        headers=admin_headers,
    )

    listed = await client.get("/admin/settings/commission", headers=admin_headers)
    by_country = {row["country_code"]: row for row in listed.json()}
    assert by_country["LY"]["commission_enabled"] is True


async def test_commission_percent_is_bounded(
    client: AsyncClient, admin_headers: dict
) -> None:
    response = await client.patch(
        "/admin/settings/commission/JO",
        json={"commission_percent": "120"},
        headers=admin_headers,
    )
    assert response.status_code == 422


# -------------------------------------------------------------- خطط الاشتراك


async def test_subscription_plan_currency_follows_country(
    client: AsyncClient, admin_headers: dict
) -> None:
    response = await client.post(
        "/admin/settings/subscription-plans",
        json={
            "country_code": "LY",
            "name": "اشتراك يومي",
            "duration_type": "daily",
            "price": "5.000",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    plan = response.json()
    assert plan["currency"] == "LYD"  # لا تُقبل من العميل — تُشتق من الدولة
    assert plan["is_active"] is True

    updated = await client.patch(
        f"/admin/settings/subscription-plans/{plan['id']}",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert updated.json()["is_active"] is False

    assert (
        await client.delete(
            f"/admin/settings/subscription-plans/{plan['id']}", headers=admin_headers
        )
    ).status_code == 204


async def test_plan_name_is_unique_per_country(
    client: AsyncClient, admin_headers: dict
) -> None:
    payload = {
        "country_code": "JO",
        "name": "اشتراك شهري",
        "duration_type": "monthly",
        "price": "30.000",
    }
    assert (
        await client.post(
            "/admin/settings/subscription-plans", json=payload, headers=admin_headers
        )
    ).status_code == 201

    duplicate = await client.post(
        "/admin/settings/subscription-plans", json=payload, headers=admin_headers
    )
    assert duplicate.status_code == 409

    # نفس الاسم في دولة أخرى مسموح
    other = await client.post(
        "/admin/settings/subscription-plans",
        json=payload | {"country_code": "LY"},
        headers=admin_headers,
    )
    assert other.status_code == 201


# -------------------------------------------------------------- سجل التدقيق


async def test_admin_actions_are_audited(
    client: AsyncClient, admin_headers: dict
) -> None:
    await client.post(
        "/admin/settings/pricing", json=_pricing_payload(), headers=admin_headers
    )

    logs = await client.get(
        "/admin/settings/audit-logs?entity_type=pricing_rule", headers=admin_headers
    )
    assert logs.status_code == 200
    entries = logs.json()
    assert len(entries) == 1
    assert entries[0]["action"] == "create"
    assert entries[0]["actor_id"] is not None

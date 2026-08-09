from __future__ import annotations

from httpx import AsyncClient


async def _register(client: AsyncClient, payload: dict) -> dict:
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_driver_can_read_own_profile(
    client: AsyncClient, driver_payload: dict
) -> None:
    body = await _register(client, driver_payload)
    response = await client.get("/drivers/me", headers=_auth(body["tokens"]))

    assert response.status_code == 200
    data = response.json()
    assert data["driver"]["status"] == "pending"
    assert data["user"]["phone"] == "+218917654321"
    assert data["vehicles"] == []
    assert data["documents"] == []


async def test_rider_cannot_read_driver_profile(
    client: AsyncClient, rider_payload: dict
) -> None:
    body = await _register(client, rider_payload)
    response = await client.get("/drivers/me", headers=_auth(body["tokens"]))
    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


async def test_driver_can_add_and_list_vehicle(
    client: AsyncClient, driver_payload: dict
) -> None:
    body = await _register(client, driver_payload)
    headers = _auth(body["tokens"])

    vehicle = {
        "make": "Toyota",
        "model": "Corolla",
        "year": 2019,
        "color": "أبيض",
        "plate_number": "tri-12345",
        "category": "economy",
    }
    created = await client.post("/drivers/me/vehicles", json=vehicle, headers=headers)
    assert created.status_code == 201, created.text
    assert created.json()["plate_number"] == "TRI-12345"  # يُخزَّن موحّداً

    listed = await client.get("/drivers/me/vehicles", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1


async def test_plate_number_is_unique(client: AsyncClient, driver_payload: dict) -> None:
    body = await _register(client, driver_payload)
    headers = _auth(body["tokens"])
    vehicle = {
        "make": "Kia",
        "model": "Rio",
        "year": 2020,
        "color": "أسود",
        "plate_number": "JO-77777",
        "category": "comfort",
    }
    assert (await client.post("/drivers/me/vehicles", json=vehicle, headers=headers)).status_code == 201

    second_driver = await _register(
        client, driver_payload | {"phone": "0918888888", "name": "كبتن آخر"}
    )
    conflict = await client.post(
        "/drivers/me/vehicles", json=vehicle, headers=_auth(second_driver["tokens"])
    )
    assert conflict.status_code == 409


async def test_vehicle_year_is_validated(client: AsyncClient, driver_payload: dict) -> None:
    body = await _register(client, driver_payload)
    response = await client.post(
        "/drivers/me/vehicles",
        json={
            "make": "Kia",
            "model": "Rio",
            "year": 1890,
            "color": "أحمر",
            "plate_number": "JO-11111",
            "category": "economy",
        },
        headers=_auth(body["tokens"]),
    )
    assert response.status_code == 422


async def test_vehicles_require_authentication(client: AsyncClient) -> None:
    assert (await client.get("/drivers/me/vehicles")).status_code == 401

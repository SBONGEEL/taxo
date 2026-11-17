"""**كليك في الأردن وحدَه** (أمرُ المالك ٢٠٢٦-١١-١٧: «Hide CliQ in Libya») — القفلُ في الخادم، والنسخُ من الأردن لا يحمله.

يسقط هذا الملفُّ إن حُذف سطرُ `cliq_enabled` من `payment_gateways.KEY_COUNTRIES`: الإشعالُ في ليبيا والجزائر يعود 200.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.exceptions import InvalidInput
from app.models.enums import CountryCode, FeatureKey
from app.services import payment_gateways, settings_service

FLAGS = "/admin/settings/feature-flags"


def test_cliq_is_jordanian_in_every_market_decision() -> None:
    # **كلُّ دولةٍ لها جوابٌ صريح** — سوقٌ يُضاف لاحقاً يسقط هنا حتى يُقرَّر له
    for country in CountryCode:
        assert payment_gateways.switch_allowed(FeatureKey.CLIQ_ENABLED.value, country) == (country == CountryCode.JO), country


async def test_cliq_cannot_be_switched_on_outside_jordan_but_can_be_switched_off(
    client: AsyncClient, admin_headers: dict
) -> None:
    for country in (CountryCode.LY, CountryCode.DZ):
        refused = await client.put(
            FLAGS, json={"country_code": country, "feature_key": "cliq_enabled", "enabled": True}, headers=admin_headers
        )
        assert refused.status_code == 422, refused.text
        off = await client.put(
            FLAGS, json={"country_code": country, "feature_key": "cliq_enabled", "enabled": False}, headers=admin_headers
        )
        assert off.status_code == 200, off.text
    jordan = await client.put(
        FLAGS, json={"country_code": "JO", "feature_key": "cliq_enabled", "enabled": True}, headers=admin_headers
    )
    assert jordan.status_code == 200, jordan.text


async def test_copying_jordan_switches_never_turns_cliq_on_elsewhere(client: AsyncClient, session_factory) -> None:
    async with session_factory() as session:
        await settings_service.set_flag(session, country_code=CountryCode.JO, feature_key=FeatureKey.CLIQ_ENABLED, enabled=True)
        await session.commit()
        jordan = await settings_service.get_flags(session, CountryCode.JO)
        assert jordan["cliq_enabled"] is True
        for target in (CountryCode.LY, CountryCode.DZ):
            # **النسخُ كما تفعله أدواتُ المطابقة**: كلُّ مشتعلٍ في الأردن يُكتب في الهدف بالباب نفسِه
            for key, on in jordan.items():
                if not on or key != FeatureKey.CLIQ_ENABLED.value:
                    continue
                with pytest.raises(InvalidInput):
                    await settings_service.set_flag(session, country_code=target, feature_key=key, enabled=True)
            await session.rollback()
            assert (await settings_service.get_flags(session, target)).get("cliq_enabled") is not True
        # **والأردنُ كما هو**
        assert (await settings_service.get_flags(session, CountryCode.JO))["cliq_enabled"] is True

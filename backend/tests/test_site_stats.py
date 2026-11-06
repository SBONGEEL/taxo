"""«الإحصاءات»: الصلاحيّةُ الحسّاسة، والعدُّ بلا IP، والعدُّ الذرّيُّ تحت التزامن، وإخفاءُ ما لا يُعرض، واستيرادُ Play."""

from __future__ import annotations

import asyncio
from datetime import date

from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.site_stats import PlayStatsDaily, SiteDaily, SiteDownloadDaily
from app.services import site_stats
from tests.conftest import _staff_headers


async def viewer(client: AsyncClient, admin_headers: dict, phone: str = "+962790000091") -> dict:
    headers = await _staff_headers("admin", phone, "قارئ الإحصاءات")
    me = (await client.get("/auth/me", headers=headers)).json()
    rows = (await client.get("/admin/permissions", headers=admin_headers)).json()
    row = next(item for item in rows if item["user_id"] == me["id"])
    assert "stats.view" not in row["permissions"], "الصلاحيةُ وصلت بالافتراض — وهي لا تُعطى إلا بالاسم"
    r = await client.put(f"/admin/permissions/{me['id']}",
                         json={"permissions": sorted(set(row["permissions"]) | {"stats.view"})}, headers=admin_headers)
    assert r.status_code == 200, r.text
    return headers


def test_classifiers_keep_nothing_identifying() -> None:
    assert site_stats.source_of("l.facebook.com") == "facebook"
    assert site_stats.source_of("www.google.dz") == "google"
    assert site_stats.source_of(None) == "direct"
    assert site_stats.source_of("evil.example") == "other"
    # **مسارٌ خارج القائمة لا يُحفظ** — فلا معرّفَ في مسارٍ يصل الجدول
    assert site_stats.path_of("/track/abc123?x=1") == "other"
    assert site_stats.path_of("/download.html?v=9") == "/download"
    assert site_stats.country_of("dz") == "DZ" and site_stats.country_of("XX") == "??" and site_stats.country_of(None) == "??"


async def test_plain_admin_is_refused(client: AsyncClient, admin_headers: dict) -> None:
    assert (await client.get("/admin/stats/report", headers=admin_headers)).status_code == 403


async def test_hits_count_atomically_under_concurrency(client: AsyncClient, session_factory) -> None:
    """**العدُّ ذرّيٌّ في القاعدة**: عشرون زيارةً معاً لصفٍّ واحدٍ = عشرون — قراءةٌ ثمّ كتابةٌ كانت ستضيع بعضَها."""
    body = {"path": "/", "ref": "m.facebook.com", "d": True, "w": False, "m": False}
    results = await asyncio.wait_for(asyncio.gather(*[
        client.post("/public/site/hit", json=body, headers={"CF-IPCountry": "DZ"}) for _ in range(20)
    ]), 60)
    assert {r.status_code for r in results} == {204}
    async with session_factory() as s:
        row = await s.get(SiteDaily, (site_stats.today(), "/", "facebook", "DZ"))
        assert row is not None and row.views == 20 and row.uniques_day == 20 and row.uniques_week == 0


async def test_downloads_and_clicks_are_separate(client: AsyncClient, session_factory) -> None:
    await client.post("/public/site/download/driver", headers={"CF-IPCountry": "JO"})
    await client.post("/public/site/click", json={"app": "driver"}, headers={"CF-IPCountry": "JO"})
    await client.post("/public/site/click", json={"app": "driver"}, headers={"CF-IPCountry": "JO"})
    async with session_factory() as s:
        row = await s.get(SiteDownloadDaily, (site_stats.today(), "driver", "JO"))
        assert (row.downloads, row.clicks) == (1, 2)


async def test_report_sums_site_and_play_and_hides_ly(client: AsyncClient, admin_headers: dict, session_factory) -> None:
    h = await viewer(client, admin_headers)
    await client.post("/public/site/download/rider", headers={"CF-IPCountry": "DZ"})
    await client.post("/public/site/download/rider", headers={"CF-IPCountry": "LY"})
    await client.post("/public/site/hit", json={"path": "/"}, headers={"CF-IPCountry": "LY"})
    async with session_factory() as s:
        await site_stats.store_play_rows(s, [
            {"day": site_stats.today(), "package": "ly.tajora.rider", "country": "DZ", "installs": 3, "uninstalls": 1, "active_devices": 9},
            {"day": site_stats.today(), "package": "ly.tajora.rider", "country": "LY", "installs": 5, "uninstalls": 0, "active_devices": 2},
        ])
        await s.commit()
    r = await client.get("/admin/stats/report", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["summary"]["rider"]["today"] == {"site": 1, "play": 3, "total": 4}
    # **ليبيا تُعدّ ولا تُعرض** — لا بلداً في القوائم ولا رقماً في المجاميع
    shown = {c["key"] for c in data["site_countries"] + data["download_countries"] + data["play_countries"]}
    assert "LY" not in shown


async def test_play_import_replaces_corrected_days(session_factory) -> None:
    csv_text = ("Date,Package name,Country,Daily Device Installs,Daily Device Uninstalls,Daily Device Upgrades,Total User Installs,"
                "Daily User Installs,Daily User Uninstalls,Active Device Installs,Install events,Update events,Uninstall events\n"
                "2026-10-30,ly.tajora.driver,DZ,2,0,0,0,0,0,7,0,1,0\n")
    rows = site_stats.parse_play_country_csv(csv_text.encode("utf-16"))
    # **وعلامةُ ترتيبٍ مضاعفة** أو UTF-8 بعلامة — الصيغُ التي قد ينشرها Play
    assert site_stats.parse_play_country_csv(("﻿" + csv_text).encode("utf-16")) == rows
    assert site_stats.parse_play_country_csv(csv_text.encode("utf-8-sig")) == rows
    assert rows == [{"day": date(2026, 10, 30), "package": "ly.tajora.driver", "country": "DZ",
                     "installs": 2, "uninstalls": 0, "active_devices": 7}]
    async with session_factory() as s:
        await site_stats.store_play_rows(s, rows)
        await site_stats.store_play_rows(s, [{**rows[0], "installs": 4}])  # Play صحّح اليوم في النسخة التالية
        await s.commit()
        assert await s.scalar(select(func.count()).select_from(PlayStatsDaily)) == 1
        assert (await s.get(PlayStatsDaily, (date(2026, 10, 30), "ly.tajora.driver", "DZ"))).installs == 4

"""استيرادُ أرقام Play (`stats/installs/…_country.csv`) من تقاريره الرسميّة في Cloud Storage — بحساب الخدمة نفسِه (`design/SITE-STATS.md`).

**المفتاحُ عقدٌ معمّى** في «عقود مزوّدي API» (`google_play_reports`) — لا في `.env` ولا في الشيفرة (`CLAUDE.md`، ثوابتُ المواصفة).
**والنطاقُ قراءةُ التخزين وحدَها** (`devstorage.read_only`): الحسابُ نفسُه يرفع الحزمَ من جهاز المطوّر، ولا يحتاج الخادمُ ذلك.

وPlay ينشر تقريرَ الشهر الجاري ويحدّثه كلَّ يومٍ تقريباً **بتأخّر يومين إلى أربعة** — فـ«آخرُ يومٍ في التقرير» يُعرض مع «آخر استيراد».
"""

from __future__ import annotations

import time
from datetime import date, timedelta
from urllib.parse import quote

import httpx
import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ProviderKey
from app.services import site_stats
from app.services.providers import credentials as provider_credentials

SCOPE = "https://www.googleapis.com/auth/devstorage.read_only"
OAUTH_ENDPOINT = "https://oauth2.googleapis.com/token"
TIMEOUT = httpx.Timeout(30.0)


class PlayReportsNotConfigured(Exception):
    pass


class PlayReportsError(Exception):
    pass


def _private_key(raw: str) -> str:
    """المفتاحُ يُلصق في حقلٍ من سطرٍ واحد — فيُقبل بأسطره أو بـ`\\n` مكتوبة."""
    return raw.replace("\\n", "\n").strip() + "\n"


async def _token(client: httpx.AsyncClient, email: str, key: str) -> str:
    now = int(time.time())
    assertion = jwt.encode({"iss": email, "scope": SCOPE, "aud": OAUTH_ENDPOINT, "iat": now, "exp": now + 600}, key, algorithm="RS256")
    r = await client.post(OAUTH_ENDPOINT, data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion})
    if r.status_code != 200:
        raise PlayReportsError(f"تبادلُ الرمز رُفض ({r.status_code})")
    return r.json()["access_token"]


def _months(today: date) -> list[str]:
    """الشهرُ الجاري والسابق — **فأيّامُ آخر الشهر الماضي تُصحَّح في أوّل الجاري**."""
    first = today.replace(day=1)
    return [(first - timedelta(days=1)).strftime("%Y%m"), first.strftime("%Y%m")]


async def run(session: AsyncSession) -> int:
    values = await provider_credentials.get_values(session, ProviderKey.GOOGLE_PLAY_REPORTS)
    if not values or not values.get("client_email") or not values.get("private_key") or not values.get("bucket"):
        raise PlayReportsNotConfigured
    bucket = values["bucket"].strip().removeprefix("gs://").split("/")[0]
    total = 0
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        token = await _token(client, values["client_email"].strip(), _private_key(values["private_key"]))
        headers = {"Authorization": f"Bearer {token}"}
        for package in site_stats.PACKAGES:
            for month in _months(site_stats.today()):
                name = f"stats/installs/installs_{package}_{month}_country.csv"
                url = f"https://storage.googleapis.com/storage/v1/b/{bucket}/o/{quote(name, safe='')}?alt=media"
                r = await client.get(url, headers=headers)
                if r.status_code == 404:
                    continue
                if r.status_code != 200:
                    raise PlayReportsError(f"قراءةُ التقرير رُفضت ({r.status_code})")
                total += await site_stats.store_play_rows(session, site_stats.parse_play_country_csv(r.content))
    return total

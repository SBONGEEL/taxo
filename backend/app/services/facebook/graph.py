"""نداءاتُ Graph API لصفحة «Taxo» — **صفحةٌ واحدة، ورمزٌ لا يُطبع** (SPEC §٩٤/١).

**كلُّ نداءٍ يذهب إلى `page_id` المكتوب في العقد** أو إلى منشورٍ يبدأ معرّفُه به؛ فلا يصل الرمزُ صفحةً أخرى ولو كان يملكها.
**والرمزُ لا يخرج في رسالة خطأ**: كلُّ نصٍّ يعود من فيسبوك يمرّ بـ`scrub` قبل أن يُكتب في صفٍّ أو سجلّ — والطلبُ نفسُه يحمله في
الجسم لا في العنوان حيث أمكن (POST)، وفي العنوان لـGET وحدَه، **ولا يُسجَّل عنوانٌ أبداً**.

**ولا حذفَ هنا**: لا دالّةَ تحذف منشوراً (قاعدةُ المالك «لا يُحذف منشور»).
"""

from __future__ import annotations

import json
import mimetypes
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ProviderKey
from app.services.providers import credentials as provider_credentials

API = "https://graph.facebook.com/v26.0/"
#: رفعُ الفيديو له مضيفُه عند فيسبوك
VIDEO_API = "https://graph-video.facebook.com/v26.0/"
TIMEOUT = httpx.Timeout(60.0, connect=15.0)
VIDEO_TIMEOUT = httpx.Timeout(300.0, connect=15.0)


class FacebookNotConfigured(Exception):
    """لا عقدَ صفحةٍ فعّالٌ في «عقود مزوّدي API»."""


class FacebookError(Exception):
    """فيسبوك ردّ بخطأ — النصُّ منظَّفٌ من الرمز."""

    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class Page:
    page_id: str
    token: str

    def scrub(self, text: str) -> str:
        return text.replace(self.token, "[TOKEN]") if self.token else text

    def owns(self, object_id: str) -> bool:
        """**أمنشورٌ من هذه الصفحة؟** — معرّفُ المنشور `{page}_{post}`، فلا يُنادى منشورٌ لصفحةٍ أخرى بهذا الرمز."""
        return object_id.startswith(f"{self.page_id}_")


async def page(session: AsyncSession) -> Page:
    values = await provider_credentials.get_values(session, ProviderKey.FACEBOOK_PAGE)
    if not values or not values.get("page_id") or not values.get("page_token"):
        raise FacebookNotConfigured()
    return Page(page_id=str(values["page_id"]).strip(), token=str(values["page_token"]).strip())


def _unix(at: datetime) -> str:
    return str(int(at.timestamp()))


async def _send(p: Page, method: str, path: str, *, params: dict[str, Any] | None = None,
                files: dict[str, tuple[str, bytes, str]] | None = None, video: bool = False) -> dict:
    data = {k: v for k, v in (params or {}).items() if v is not None}
    base = VIDEO_API if video else API
    try:
        async with httpx.AsyncClient(timeout=VIDEO_TIMEOUT if video else TIMEOUT) as client:
            if method == "GET":
                resp = await client.get(base + path, params={**data, "access_token": p.token})
            else:
                resp = await client.post(base + path, data={**data, "access_token": p.token}, files=files)
    except httpx.HTTPError as exc:
        # **نوعُ الخطأ وحدَه**: نصُّ httpx قد يحمل العنوانَ وفيه الرمز
        raise FacebookError(f"تعذّر الوصول إلى فيسبوك ({type(exc).__name__})") from None
    try:
        body = resp.json()
    except ValueError:
        raise FacebookError(f"ردٌّ غيرُ مفهوم من فيسبوك (HTTP {resp.status_code})") from None
    if isinstance(body, dict) and "error" in body:
        err = body["error"] or {}
        raise FacebookError(p.scrub(str(err.get("message") or "خطأ من فيسبوك")), err.get("code"))
    return body


def _file(path: Path) -> tuple[str, bytes, str]:
    return (path.name, path.read_bytes(), mimetypes.guess_type(path.name)[0] or "application/octet-stream")


def _full_id(p: Page, object_id: str) -> str:
    return object_id if "_" in object_id else f"{p.page_id}_{object_id}"


# ───────────────────────── الجدولة

async def schedule_photo(p: Page, image: Path, caption: str, at: datetime) -> str:
    r = await _send(p, "POST", f"{p.page_id}/photos",
                    params={"caption": caption, "published": "false", "scheduled_publish_time": _unix(at)},
                    files={"source": _file(image)})
    return _full_id(p, str(r.get("post_id") or r["id"]))


async def schedule_carousel(p: Page, images: list[Path], caption: str, at: datetime) -> str:
    media: list[str] = []
    for image in images:
        r = await _send(p, "POST", f"{p.page_id}/photos",
                        params={"published": "false", "temporary": "true"}, files={"source": _file(image)})
        media.append(str(r["id"]))
    params: dict[str, Any] = {"message": caption, "published": "false", "scheduled_publish_time": _unix(at)}
    for i, m in enumerate(media):
        params[f"attached_media[{i}]"] = json.dumps({"media_fbid": m})
    r = await _send(p, "POST", f"{p.page_id}/feed", params=params)
    return _full_id(p, str(r["id"]))


async def schedule_video(p: Page, video: Path, title: str, caption: str, at: datetime) -> str:
    r = await _send(p, "POST", f"{p.page_id}/videos", video=True,
                    params={"title": title, "description": caption, "published": "false",
                            "scheduled_publish_time": _unix(at)},
                    files={"source": _file(video)})
    return _full_id(p, str(r.get("post_id") or r["id"]))


async def reschedule(p: Page, fb_post_id: str, at: datetime) -> None:
    if not p.owns(fb_post_id):
        raise FacebookError("منشورٌ ليس من صفحة Taxo")
    await _send(p, "POST", fb_post_id, params={"scheduled_publish_time": _unix(at)})


# ───────────────────────── القراءة

_POST_FIELDS = "id,message,created_time,scheduled_publish_time,is_published,permalink_url,full_picture"
_STATS_FIELDS = "reactions.summary(total_count).limit(0),comments.summary(total_count).limit(0),shares"


async def scheduled_posts(p: Page) -> list[dict]:
    r = await _send(p, "GET", f"{p.page_id}/scheduled_posts", params={"fields": _POST_FIELDS, "limit": 100})
    return list(r.get("data") or [])


async def published_posts(p: Page, limit: int = 100) -> list[dict]:
    r = await _send(p, "GET", f"{p.page_id}/posts",
                    params={"fields": f"{_POST_FIELDS},{_STATS_FIELDS}", "limit": limit})
    return list(r.get("data") or [])


async def summary(p: Page) -> dict:
    return await _send(p, "GET", p.page_id, params={"fields": "name,username,followers_count,fan_count,link"})


def stats_of(item: dict) -> dict[str, int]:
    def total(key: str) -> int:
        return int(((item.get(key) or {}).get("summary") or {}).get("total_count") or 0)

    return {"reactions": total("reactions"), "comments": total("comments"),
            "shares": int((item.get("shares") or {}).get("count") or 0)}

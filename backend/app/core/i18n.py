"""**الترجمة في الخلفية** (SPEC §٧٣-هـ المرحلة ٥) — العربيّةُ والفرنسيّة، **والنصُّ العربيُّ هو المفتاح** كما في التطبيقين.

**العربيّةُ لا تُمسّ بالبناء**: `translate(نص, "ar")` تعيده حرفاً، ولا يُفتح القاموسُ إلا للفرنسيّة — فكلُّ اختبارٍ قائمٍ يقرأ رسالةً عربيّةً
يبقى شاهداً على أنها لم تتغيّر. **ونصٌّ بلا فرنسيّةٍ يخرج عربيّاً** ولا يخرج فارغاً.

**ولغةُ الطلب** من رأس `Accept-Language` الذي يرسله التطبيقان في كلِّ طلب (`LanguageMiddleware`): `fr…` ⇐ فرنسيّة، وكلُّ ما سواه
عربيّة كما كان — **واللوحةُ لا ترسل فرنسيّةً أبداً** (أمرُ المالك: اللوحةُ عربيّة). **ولغةُ الحساب** (`users.language`) لما يصل بلا طلب:
الإشعاراتُ ورسائلُها.

**والقالبُ** (`f"الحد الأدنى للسحب {الحد}"`) مفتاحُه بمواضع `{0}` `{1}` (`scripts/i18n_extract.py`): يُطابَق النصُّ المرسوم بنمطه،
**وتُنقل قيمُه كما هي** إلى مواضعها في الفرنسيّة.
"""

from __future__ import annotations

import json
import re
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path

LANGUAGES = ("ar", "fr")
DEFAULT = "ar"
_current: ContextVar[str] = ContextVar("request_language", default=DEFAULT)
_FR_FILE = Path(__file__).resolve().parents[1] / "i18n" / "fr.json"
_SLOT = re.compile(r"\{(\d+)\}")


def language_of_header(value: str | None) -> str:
    """**أوّلُ لغةٍ في الرأس** — `fr`/`fr-DZ`/`fr-FR,ar;q=0.8` ⇐ فرنسيّة، وما سواها عربيّة."""
    first = (value or "").split(",", 1)[0].strip().lower()
    return "fr" if first[:2] == "fr" else DEFAULT


def current_language() -> str:
    return _current.get()


def normalize(language: str | None) -> str:
    return language if language in LANGUAGES else DEFAULT


@lru_cache(maxsize=1)
def _dictionary() -> tuple[dict[str, str], list[tuple[re.Pattern[str], str]]]:
    try:
        raw: dict[str, str] = json.loads(_FR_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raw = {}
    exact: dict[str, str] = {}
    patterns: list[tuple[re.Pattern[str], str]] = []
    for ar, fr in raw.items():
        if _SLOT.search(ar):
            # **أطولُ القوالب أوّلاً** (أدناه) — فقالبٌ أعمُّ لا يبتلع ما هو أخصُّ منه
            regex = "".join(
                f"(?P<s{piece[1:-1]}>.+?)" if _SLOT.fullmatch(piece) else re.escape(piece)
                for piece in re.split(r"(\{\d+\})", ar)
                if piece
            )
            patterns.append((re.compile(f"^{regex}$", re.DOTALL), fr))
        exact[ar] = fr
    patterns.sort(key=lambda item: -len(item[0].pattern))
    return exact, patterns


def translate(text: str, language: str | None = None) -> str:
    """**النصُّ بلغةٍ** — والعربيّةُ حرفاً، والمجهولُ عربيّاً."""
    if normalize(language if language is not None else current_language()) != "fr" or not text:
        return text
    exact, patterns = _dictionary()
    hit = exact.get(text)
    if hit is not None:
        return hit
    for pattern, fr in patterns:
        match = pattern.match(text)
        if match:
            # **وقيمُ المواضع تُترجم هي أيضاً** — اسمُ الحقل («المبلغ») والفعلُ («يقلّ») مفاتيحُ في القاموس؛ والرقمُ يبقى رقماً
            values = {key: translate(value, "fr") for key, value in match.groupdict().items()}
            return _SLOT.sub(lambda m: values.get(f"s{m.group(1)}", m.group(0)), fr)
    return text


class LanguageMiddleware:
    """**لغةُ الطلب في سياقه** — وسيطٌ خامٌ (ASGI) لا `BaseHTTPMiddleware`: لا يلفّ الجسمَ ولا يغيّر شيئاً، يقرأ رأساً ويضبط متغيّراً."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        header = None
        for name, value in scope.get("headers") or ():
            if name == b"accept-language":
                header = value.decode("latin-1")
                break
        token = _current.set(language_of_header(header))
        try:
            await self.app(scope, receive, send)
        finally:
            _current.reset(token)

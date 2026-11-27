"""**رموزُ الدخول لا تُكتب في سجلّ الخادم** (بندٌ أمنيٌّ رآه عدُّ النسخ ٢٠٢٦-١١-٢٦، أمرُ المالك ٢٠٢٦-١١-٢٧).

**ما كان**: المقبسان يفتحان بـ`/api/v1/ws/{rider,driver}?token=…&device_id=…`، **وuvicorn يكتب المسارَ باستعلامه**
في سطر كلِّ اتصال — `"WebSocket /api/v1/ws/driver?token=eyJ…" [accepted]` في `uvicorn.error`، وسطرُ الوصول في
`uvicorn.access` لكلِّ طلبٍ عاديّ. **فمن قرأ `docker logs` قرأ رموزاً صالحةً** (صلاحيّتُها ربعُ ساعة) ومعرّفاتِ أجهزة.

**والإصلاحُ مرشِّحٌ على المسجِّلَين لا تغييرٌ في البروتوكول**: نقلُ الرمز إلى أوّل رسالةٍ بعد الفتح يغيّر التطبيقين
والغلافَ الأصليَّ وكلَّ نسخةٍ منشورة — **ونسخُ ١٤٥٢ و١٥٣٤ ما زالت تتّصل بالاستعلام** (عدُّ النسخ). فالمرشِّحُ يحجب
**قيمةَ** كلِّ معاملٍ مسمّى هنا ويُبقي اسمَه: السطرُ ما زال يقول «اتّصل كابتنٌ بمقبسه»، ولا يقول بماذا.

**ولماذا قيمةُ المعامل لا الاستعلامُ كلُّه**: معاملاتٌ بريئةٌ (`country`، `v`) تفيد التشخيص، وحذفُ الاستعلام جملةً
يُخفيها بلا سبب. **وما لا يَعِد به**: سرٌّ في معاملٍ باسمٍ لم يُكتب هنا يمرّ — والقائمةُ تُوسَّع حين يُضاف بابٌ برمز.

**والمرشِّحُ يُركَّب عند استيراد التطبيق** — uvicorn يضبط مسجِّلاته قبل أن يستورده (في كلِّ عاملٍ من `--workers`)،
فما يُضاف هنا يبقى، ولا يُعاد ضبطٌ بعده يمحوه.
"""

from __future__ import annotations

import logging
import re

#: **أسماءُ المعاملات التي تُحجب قيمُها** — رمزُ الدخول ورمزُ الحضور ومعرّفُ الجهاز وما يشبهها.
SECRET_PARAMS: tuple[str, ...] = (
    "token",
    "access_token",
    "refresh_token",
    "presence_token",
    "handoff",
    "device_id",
    "code",
)

#: المسجِّلان اللذان يكتب فيهما uvicorn المسار: الوصولُ للطلبات، و«الخطأ» لأسطر المقبس (`[accepted]`)
LOGGERS: tuple[str, ...] = ("uvicorn.access", "uvicorn.error")

_PATTERN = re.compile(
    r"(?P<lead>[?&])(?P<name>" + "|".join(re.escape(name) for name in SECRET_PARAMS) + r")=(?P<value>[^&\s\"']*)",
    re.IGNORECASE,
)
MASK = "…"


def redact(text: str) -> str:
    """يحجب قيمةَ كلِّ معاملٍ سرّيٍّ في نصٍّ فيه استعلام — **ويُبقي الاسمَ وما سواه كما هو**."""
    if "=" not in text:
        return text
    return _PATTERN.sub(lambda match: f"{match['lead']}{match['name']}={MASK}", text)


class QuerySecretFilter(logging.Filter):
    """يمرّر السطرَ دائماً — **بعد حجب ما فيه**، في الرسالة وفي معاملاتها (uvicorn يمرّر المسارَ معاملاً)."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(redact(arg) if isinstance(arg, str) else arg for arg in record.args)
        elif isinstance(record.args, dict):
            record.args = {key: redact(value) if isinstance(value, str) else value for key, value in record.args.items()}
        return True


_FILTER = QuerySecretFilter()


def install() -> None:
    """يركّب المرشِّحَ مرّةً واحدة على المسجِّلَين — **وتكرارُ الاستدعاء لا يضاعفه**."""
    for name in LOGGERS:
        logger = logging.getLogger(name)
        if _FILTER not in logger.filters:
            logger.addFilter(_FILTER)

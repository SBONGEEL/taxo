"""بابُ تقارير الأعطال — **مفتوحٌ بلا جلسة، ومحدودٌ بثلاثة سدود** (2026-09-20).

## ولمَ بلا جلسة

**لأن الشاشةَ التي تسقط أكثرَ من غيرها هي شاشةُ الدخول.** بابٌ يشترط توكناً
يجمع أعطالَ من دخل وحدَه، **ويعمى عن كلِّ عطبٍ يمنع الدخولَ أصلاً** — وهو
بالضبط العطبُ الذي لا يستطيع صاحبُه أن يبلّغ عنه بطريقٍ آخر.

## وثمنُ ذلك مدفوعٌ بثلاثة سدود لا واحد

| السدّ | لماذا |
|---|---|
| بالجهاز | هاتفٌ في حلقةِ رسمٍ لا يملأ الجدول |
| بالعنوان | عدّةُ أجهزةٍ خلف بوّابةٍ واحدة تُخدَم، وحاصدٌ واحدٌ يُوقَف |
| بالجملة | **قاطعٌ عام**: عطبٌ يصيب الأسطولَ كلَّه لا يكتب مليونَ صفّ |

**وأسماءُ الدِّلاء منفصلةٌ عن `login:`** — وهذا شرطٌ لا تفصيل: دلوٌ مشترَكٌ
يجعل **موجةَ أعطالٍ تستهلك نصيبَ الدخول**، فيُمنع الناسُ من الدخول لأن
تطبيقَهم يسقط. وهو عطبٌ يولّد عطباً.

## وعنوانُ الشبكة لا يُخزَّن ولا يُسجَّل

يُقرأ ليُشتقَّ منه مفتاحُ دلوٍ **مُعمّى**، ثم يُنسى. فلا هو في الجدول، ولا في
مفتاح Redis، ولا في سطر سجل — **وبغير ذلك يعود ما نُفيَ من الحمولة من الباب
الخلفيّ**: العنوانُ يقول أين صاحبُه، وقد نُفيت الإحداثيّةُ لهذا نفسِه.
"""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, status

from app.core import rate_limit
from app.core.deps import ClientIP, DbSession, RedisDep
from app.core.exceptions import RateLimited
from app.schemas.error_report import ErrorReportAccepted, ErrorReportIn
from app.services import error_reports

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

#: **سخيٌّ لجهازٍ صادقٍ، ضيّقٌ على حلقة**: عشرون تقريراً في عشر دقائق
DEVICE_LIMIT = 20
DEVICE_WINDOW_SECONDS = 600

#: أوسعُ من الجهاز: بوّابةٌ واحدةٌ قد تخفي عشراتِ الهواتف
IP_LIMIT = 60
IP_WINDOW_SECONDS = 600

#: **القاطعُ العام** — سقفٌ للنظام كلِّه في الساعة
GLOBAL_LIMIT = 2_000
GLOBAL_WINDOW_SECONDS = 3_600


def _ip_bucket(client_ip: str) -> str:
    """مفتاحُ دلوٍ لا يُقرأ منه عنوان — **ولا يُكتب العنوانُ في Redis**."""
    digest = hashlib.sha256(client_ip.encode("utf-8")).hexdigest()[:16]
    return f"errors:ip:{digest}"


@router.post(
    "/errors",
    response_model=ErrorReportAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="تقريرُ عطبٍ من تطبيق",
)
async def report_error(
    payload: ErrorReportIn,
    session: DbSession,
    redis: RedisDep,
    client_ip: ClientIP,
) -> ErrorReportAccepted:
    """يقبل ويقيّد — **و٢٠٢ لا ٢٠٠**.

    **والرمزُ يقول ما جرى**: «استلمتُه» لا «عالجتُه». والتطبيقُ لا ينتظر
    نتيجةً ولا يُبنى على ردٍّ: من يُبلّغ عن عطبٍ لا يُعطى عطباً ثانياً في
    طريق التبليغ.

    **و٤٢٩ تعني «توقّف» لا «أعد»** (والعميلُ مبنيٌّ عليها): إعادةُ المحاولة
    على سدٍّ هي كيف تصير حلقةُ رسمٍ في هاتفٍ واحدٍ إغراقاً للخادم.
    """
    for key, cap, window in (
        (f"errors:device:{payload.device_hash[:32]}", DEVICE_LIMIT, DEVICE_WINDOW_SECONDS),
        (_ip_bucket(client_ip), IP_LIMIT, IP_WINDOW_SECONDS),
        ("errors:global", GLOBAL_LIMIT, GLOBAL_WINDOW_SECONDS),
    ):
        limit = await rate_limit.hit(redis, key, limit=cap, window_seconds=window)
        if not limit.allowed:
            raise RateLimited(retry_after=limit.retry_after)

    await error_reports.record(session, payload)
    return ErrorReportAccepted()

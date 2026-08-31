"""بوابةُ واتساب الذاتية — **الملفُّ الوحيد الذي يعرف أسلاك البوابة**.

نفس دور `cloud_api.py` من الجهة الأخرى: عنوانُ البوابة ومفتاحُها وشكلُ جوابها
هنا وحدها، وما عداها يتكلم `base.WhatsAppOtpProvider`. فتبديلُ القناة بين
الرسمية والذاتية **حقلٌ في العقد** لا فرعٌ في مسار التحقق.

**ولماذا قناةٌ ذاتيةٌ أصلاً** (قرارُ المالك 2026-08-16): القناةُ الرسمية تحتاج
عقداً مع ميتا وقالباً معتمداً، وحتى يصل ذلك **لا أحدَ يستطيع التسجيل** — وهو
الحاجزُ الأولُ في قائمة ما قبل الإطلاق. والقناةُ الذاتيةُ تفتح البابَ اليوم،
والرسميةُ تبقى حيّةً في الواجهة نفسِها تُشعَل بحقلٍ متى وصل العقد.

**وثمنُها مكتوبٌ لا مُنكَر**: أتمتةُ حسابٍ عبر مكتبةٍ غير رسمية مخالفةٌ لشروط
واتساب، وعقوبتُها حظرُ الرقم. ولذلك ثلاثةُ حرّاسٍ في هذا الملف وحده — سقفٌ
لكل رقم، وسقفٌ بالساعة، وارتدادٌ فوريٌّ إلى القناة التالية — ورابعٌ في البوابة
(تباعدٌ عشوائي ونصٌّ واحدٌ بلا روابط). **وخطةُ الطوارئ في `CLAUDE.md`**: ما
يُفعل إن حُظر الرقم، وكم يستغرق التحويل.

**والسقوفُ هنا لا في البوابة**، والتباعدُ هناك لا هنا. ليس توزيعاً اعتباطياً:
السقفُ **سياسةٌ** تُقاس وتُختبر وتنجو من إعادة تشغيلٍ (Redis)، والتباعدُ
**إيقاعُ سلك**. وسقفٌ في ذاكرة عمليةٍ تُعاد كلَّ نشرٍ سقفٌ يمحوه أوّلُ انهيار.
"""

from __future__ import annotations

import httpx
from redis.asyncio import Redis

from app.core import rate_limit
from app.services.whatsapp.base import (
    REQUEST_TIMEOUT_SECONDS,
    WhatsAppError,
    WhatsAppNumberUnknown,
)

# مهلةُ البوابة أطولُ من مهلة ميتا: بينها وبين واتساب طابورُ تباعدٍ عشوائي
# (ثانيتان إلى ستّ)، فمهلةٌ بطول مهلة Graph تقطع نداءً ينتظر دورَه لا نداءً عالقاً
GATEWAY_TIMEOUT_SECONDS = REQUEST_TIMEOUT_SECONDS + 30.0

# **السقفان الافتراضيان**، ويُعدَّلان من حقلي العقد. والقيمُ محافظةٌ عمداً:
# رمزٌ واحدٌ لرقمٍ كلَّ ساعةٍ يكفي التسجيلَ واستعادةَ كلمة المرور معاً (ومهلةُ
# الإعادة في `services/otp.py` تحكم ما دونها)، ومئةٌ في الساعة سقفُ سوقٍ صغير
# **عشرون للرقم المستقبِل في الساعة** (قرارُ المالك 2026-08-17، رفعاً من ثلاثة).
#
# **وهو سقفٌ على الرقم الذي نرسل إليه لا على رقمنا المرسِل** — والفرقُ يهمّ:
# رقمُنا يحرسه `DEFAULT_HOURLY` العامّ (مئة). لكنّ الثلاثةَ كانت خانقةً على كل
# حال **بعد إطفاء عقد SMS**: لم تعد ثمّة قناةٌ ثانية في السلسلة (فيروبوت لا
# يولّد رمزاً عندنا)، فصار السقفُ **سقفاً بلا مخرج** — من استنفده ينتظر ساعة.
#
# **والحمايةُ الحقيقيةُ في سقوف المستخدم الثلاثة** (`otp_limits`): النافذةُ
# واليوميُّ وعمرُ التسجيل — وهي تعمل وتُقاس. وهذا السقفُ حارسُ **سلكٍ** لا
# حارسُ حساب. **ويُرفع تدريجياً مع الحجم** بقرار المالك نفسِه.
DEFAULT_PER_PHONE_HOURLY = 20
DEFAULT_HOURLY = 100

HOUR_SECONDS = 3600


class BaileysGatewayProvider:
    """يتكلم البوابةَ عبر HTTP داخل الشبكة — ولا يعرف شيئاً عن واتساب نفسه."""

    provider_name = "baileys"

    def __init__(
        self,
        *,
        base_url: str,
        gateway_key: str,
        redis: Redis,
        per_phone_hourly: int = DEFAULT_PER_PHONE_HOURLY,
        hourly: int = DEFAULT_HOURLY,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._key = gateway_key
        self._redis = redis
        self._per_phone_hourly = max(0, per_phone_hourly)
        self._hourly = max(0, hourly)

    # ------------------------------------------------------------ الأسلاك

    async def _call(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
    ) -> tuple[int, dict]:
        """نداءٌ واحد للبوابة — نقطةُ الحقن الوحيدة في الاختبارات.

        **ولا يرمي على حالةٍ غير ٢٠٠**: بعضُ الأبواب تجيب ٤٠٤ جواباً صحيحاً
        («لا رمزَ ربطٍ الآن»)، فالقرارُ لمن يعرف السؤال لا لمن ينقل الجواب.
        """
        url = f"{self._base}{path}"
        try:
            async with httpx.AsyncClient(timeout=GATEWAY_TIMEOUT_SECONDS) as http:
                response = await http.request(
                    method,
                    url,
                    headers={"X-Gateway-Key": self._key},
                    json=json,
                    params=params,
                )
                body = response.json() if response.content else {}
        except httpx.HTTPError as exc:
            # **البوابةُ ساقطةٌ حالٌ متوقعة لا مفاجأة**: حاويةٌ تُعاد أو جلسةٌ
            # تُربط من جديد. والارتدادُ إلى القناة التالية هو الجواب
            raise WhatsAppError("تعذّر الوصول إلى بوابة واتساب") from exc
        except ValueError as exc:
            raise WhatsAppError("جواب البوابة غير مقروء") from exc

        if not isinstance(body, dict):
            raise WhatsAppError("جواب البوابة غير مقروء")
        return response.status_code, body

    # ------------------------------------------------------------ السقوف

    async def _guard_limits(self, to: str) -> None:
        """سقفان قبل السلك — **ويُقاسان قبل النداء لا بعده**.

        سقفٌ يُفحص بعد الإرسال سقفٌ لا يحمي شيئاً. والرسالةُ صريحةٌ في الحالتين
        لأن الفرقَ يهمّ من يقرؤها: «طلبتَ كثيراً لهذا الرقم» شأنُ صاحبِه،
        و«القناةُ بلغت سقفَها» شأنُ المنصّة — وارتدادُ الثانية إلى الرسائل
        القصيرة صحيحٌ فوراً، بينما الأولى تعني الانتظار.
        """
        if self._per_phone_hourly:
            hit = await rate_limit.hit(
                self._redis,
                f"whatsapp:baileys:phone:{to}",
                limit=self._per_phone_hourly,
                window_seconds=HOUR_SECONDS,
            )
            if not hit.allowed:
                raise WhatsAppError(
                    "طُلب رمزُ واتساب لهذا الرقم مرات كثيرة — جرّب قناةً أخرى"
                )

        if self._hourly:
            hit = await rate_limit.hit(
                self._redis,
                "whatsapp:baileys:global",
                limit=self._hourly,
                window_seconds=HOUR_SECONDS,
            )
            if not hit.allowed:
                raise WhatsAppError(
                    "بلغت قناةُ واتساب سقفَها لهذه الساعة — جرّب قناةً أخرى"
                )

    # ------------------------------------------------------------ العقد

    async def send_code(
        self,
        to: str,
        code: str,
        *,
        ttl_minutes: int,
        # **الافتراضُ هنا تسامحٌ في النقل لا رخصةٌ في السياسة**: موضعُ التصريح
        # بالغرض هو البابُ (`routers/auth.py`)، وحارسُه اختبارٌ يقرأ الشجرة.
        # و`body` فارغاً يعني «تصوغ البوابةُ نصَّها» — مسارٌ مشروعٌ لا مخالفة،
        # ولذلك لا يُسجَّل سقوطاً (`chooseText(...).silent`).
        purpose: str = "registration",
        body: str = "",
    ) -> str:
        """يرسل الرمز عبر البوابة ويعيد مرجعَ الرسالة.

        **والنصُّ يُرسل من هنا منذ 2026-08-19، والحارسُ انتقل ولم يُحذف.** كان
        الوعدُ محروساً بأن البوابة تصوغ النصَّ؛ وهو الآن محروسٌ بأنها **تفحصه**
        قبل السلك وتسقط إلى نصّها المدمج إن خالف. والوعدُ المقصودُ لم يكن يوماً
        «البوابةُ تصوغ» بل «لا يخرج على السلك ما يخالف الشروط» — ومن يملك
        السلكَ ما زال هو الحارس.

        والشروطُ نفسُها تُفحص هنا أيضاً قبل الحفظ (`services/otp_templates.py`)
        من **ملفٍ واحدٍ يقرؤه الاثنان**، فلا يقبل المشرفُ نصّاً ترفضه البوابة.
        """
        await self._guard_limits(to)

        status, response = await self._call(
            "POST",
            "/send",
            json={
                "to": to,
                "code": code,
                "ttl_minutes": ttl_minutes,
                "purpose": purpose,
                "body": body,
                # **التصريحُ بالإرسال** (قرارُ المالك 2026-08-19): بابُ البوابة
                # افتراضُه ألّا يخرج شيءٌ على السلك، وهذا هو الموضعُ الوحيد في
                # المشروع الذي يقول «نعم، أوصِلها». وقياسٌ أو استكشافٌ لا يمرّ
                # من هنا لا يُخرج رسالةً إلى هاتفِ أحد.
                "deliver": True,
            },
        )
        if status == 200:
            return str(response.get("reference") or f"{self.provider_name}-accepted")

        detail = str(response.get("error") or f"HTTP {status}")
        # **«ليس على واتساب» خطأٌ يخصّ صاحبَ الرقم لا القناة**، ونصُّه يقوله له
        # صراحةً: من ينتظر رمزاً على رقمٍ بلا واتساب ينتظر ما لا يجيء
        if response.get("not_on_whatsapp"):
            raise WhatsAppError("هذا الرقم ليس على واتساب — جرّب الرسائل القصيرة")
        raise WhatsAppError(f"بوابة واتساب: {detail}")

    async def check_number(self, to: str) -> None:
        """**سؤالُ البوّابة بلا إرسال** — `GET /check`.

        **ولا منطقَ هنا**: البوّابةُ تملك المقبسَ وتسأل واتساب، **وهذا نقلُ
        جوابٍ لا حكمٌ ثانٍ**. وحكمٌ ثانٍ يفترق عن الأوّل يوماً.
        """
        status, response = await self._call("GET", "/check", params={"to": to})
        if status == 200:
            return
        detail = str(response.get("error") or f"HTTP {status}")
        if response.get("not_on_whatsapp"):
            raise WhatsAppNumberUnknown(detail)
        raise WhatsAppError(f"بوابة واتساب: {detail}")

    async def session_status(self) -> dict:
        """حالُ الجلسة كما تقرؤها اللوحة والمهمّةُ الدورية.

        **ولا ترمي**: بوابةٌ لا تُجيب حالةٌ تُعرض («تعذّر الوصول») لا استثناءٌ
        يُفشل شاشةً — وهي بعينها الحالُ التي يوجد التنبيهُ ليقولها.
        """
        try:
            status, body = await self._call("GET", "/status")
        except WhatsAppError as exc:
            return {
                "state": "unreachable",
                "last_error": exc.message,
                "needs_human": True,
            }
        if status != 200:
            return {
                "state": "unreachable",
                "last_error": str(body.get("error") or f"HTTP {status}"),
                "needs_human": True,
            }
        return body

    async def session_qr(self) -> str | None:
        """رمزُ الربط الخام — و`None` حين لا يكون هناك رمزٌ الآن."""
        status, body = await self._call("GET", "/qr")
        if status != 200:
            return None
        return str(body.get("qr") or "") or None

    async def session_logout(self) -> dict:
        """يفصل الجلسةَ ويمحوها — البابُ الوحيد لربط رقمٍ آخر."""
        status, body = await self._call("POST", "/logout")
        if status != 200:
            raise WhatsAppError(str(body.get("error") or f"HTTP {status}"))
        return body

    async def test_connection(self, test_phone: str | None = None) -> str:
        """اختبارٌ **لا يترك أثراً** ما لم يكتب المشرف رقماً.

        ويقيس ما يُخطئ فيه الإعداد فعلاً: هل البوابةُ مسموعة (عنوانٌ ومفتاح)،
        ثم **هل الجلسةُ مرتبطة** — وهو السؤالُ الذي لا يجيبه «الخدمةُ ترد».
        """
        state = await self.session_status()
        name = state.get("state")
        if name == "unreachable":
            raise WhatsAppError(
                f"لا وصول إلى البوابة: {state.get('last_error') or '؟'}"
            )
        if name == "awaiting_qr":
            raise WhatsAppError(
                "البوابةُ تعمل والجلسةُ غيرُ مربوطة — امسح رمزَ الربط أولاً"
            )
        if name != "linked":
            raise WhatsAppError(
                f"البوابةُ تعمل والجلسةُ «{name}» — {state.get('last_error') or 'تحاول العودة'}"
            )

        lines = [f"الجلسةُ مرتبطة بالرقم {state.get('phone') or '؟'}"]
        if state.get("since"):
            lines.append(f"منذ {state['since']}")
        if test_phone:
            reference = await self.send_code(test_phone, "000000", ttl_minutes=5)
            lines.append(f"أُرسلت رسالة اختبار — مرجع {reference}")
        else:
            lines.append("لم تُرسل رسالة — أضف رقم اختبار لتجربة إرسال فعلي")
        return " · ".join(lines)

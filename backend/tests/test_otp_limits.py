"""سقوفُ طلب رمز التحقق (قرارُ المالك 2026-08-16).

**والمقيسُ هنا هو الثلاثةُ وما بينها**، لا أن السقف يعمل:

* كلُّ سقفٍ **يمنع شيئاً لا يمنعه الآخر** — والنافذةُ لا تُغني عن اليوميِّ ولا
  عن عمرِ التسجيل، وإلا لكان واحدٌ يكفي.
* **والاستنفادُ يخصّ رقمَه وحدَه**: من بلغ سقفَه لا يُغلق البابَ على غيره —
  وهي القاعدةُ التي يكسرها أيُّ عدٍّ على IP، فيخنق مقهىً كاملاً بمسيءٍ واحد.
* **ولا يعطّل قناةً أخرى لمستخدمٍ آخر**: السقفُ على الرقم، والقناةُ قرارٌ آخر.
* **والرفضُ يقول متى**: `retry_after` غيرُ فارغٍ في كل رفض — بغيره يبقى الزرُّ
  يُضغط ولا شيءَ يقع، وهو ما وُجدت السقوفُ لتمنعه لا لتصنعه.
"""

from __future__ import annotations

import pytest

from app.core.exceptions import RateLimited
from app.core.redis_client import get_redis_client
from app.models.enums import CountryCode
from app.models.otp_setting import OtpSetting
from app.services import otp_limits

JO_PHONE = "+962790001111"
LY_PHONE = "+218910001111"
OTHER_PHONE = "+962790002222"


async def _policy(session_factory, country=CountryCode.JO, **values) -> None:
    """سياسةٌ تُكتب صفّاً كما تكتبها اللوحة — لا تُحقن في الخدمة."""
    async with session_factory() as session:
        row = await session.get(OtpSetting, country)
        if row is None:
            row = OtpSetting(country_code=country)
            session.add(row)
        for key, value in values.items():
            setattr(row, key, value)
        await session.commit()


@pytest.fixture(autouse=True)
async def _clean():
    redis = get_redis_client()
    for phone in (JO_PHONE, LY_PHONE, OTHER_PHONE):
        await otp_limits.reset(redis, phone)
    yield
    for phone in (JO_PHONE, LY_PHONE, OTHER_PHONE):
        await otp_limits.reset(redis, phone)


async def _request(session_factory, phone, country=CountryCode.JO) -> None:
    """طلبٌ واحد: الحارسُ ثم العدّ — بنفس ترتيب `otp.issue`."""
    redis = get_redis_client()
    async with session_factory() as session:
        await otp_limits.guard(session, redis, phone, country)
        await otp_limits.record(session, redis, phone, country)


async def _clear_resend(phone: str) -> None:
    """يتخطّى مهلةَ الإعادة وحدَها — فيُقاس السقفُ المقصود لا المهلة.

    وهو بابٌ مفتوحٌ عمداً في التصميم (`RESEND_KEY` عام) لنفس سببِ
    `otp.COOLDOWN_KEY`: اختبارٌ ينتظر ثلاثين ثانيةً حقيقيةً اختبارٌ لا يُشغَّل.
    """
    await get_redis_client().delete(otp_limits.RESEND_KEY.format(phone=phone))


# ------------------------------------------------------------ السقوف الثلاثة


async def test_the_window_cap_stops_a_burst_on_one_number(session_factory) -> None:
    """السقفُ الأول: رشقٌ آليٌّ على رقمٍ واحد."""
    await _policy(
        session_factory,
        max_per_window=3,
        max_per_day=0,
        max_per_registration=0,
        lockout_minutes=30,
    )

    for _ in range(3):
        await _request(session_factory, JO_PHONE)
        await _clear_resend(JO_PHONE)

    with pytest.raises(RateLimited) as caught:
        await _request(session_factory, JO_PHONE)
    # **و`retry_after` في `extra` لا خاصيةً على الاستثناء** — من هناك يقرؤه
    # مُعالِجُ الأخطاء فيضعه في ترويسة `Retry-After` وفي جسم الجواب
    assert caught.value.extra["retry_after"] > 0
    assert "كثير" in caught.value.message


async def test_the_daily_cap_stops_someone_who_waits_out_the_window(
    session_factory,
) -> None:
    """السقفُ الثاني: من يعاود كلَّ ساعةٍ طوالَ اليوم.

    ويُقاس بمحو **نافذةِ الساعة وحدَها** — وهو ما يفعله من ينتظر ساعةً ثم يعود.
    فلو كان اليوميُّ محسوباً بالنافذة نفسِها لما منع شيئاً، ولكان سقفاً بلا أثر.
    """
    redis = get_redis_client()
    await _policy(
        session_factory,
        max_per_window=2,
        max_per_day=4,
        max_per_registration=0,
        lockout_minutes=0,
    )

    for _ in range(4):
        await _request(session_factory, JO_PHONE)
        await _clear_resend(JO_PHONE)
        # انقضاءُ الساعة: تُمحى نافذتُها ويبقى اليوميّ
        await redis.delete(otp_limits.WINDOW_KEY.format(phone=JO_PHONE))

    with pytest.raises(RateLimited) as caught:
        await _request(session_factory, JO_PHONE)
    # **والمقارنةُ على الجذر بلا تشكيل**: نصُّ الرسالة مشكولٌ («اليوميَّ»)،
    # ومقارنةٌ تحمل حرفَ تشكيلٍ تكسر الاختبارَ بتحسينٍ لغويٍّ لا يمسّ المعنى
    assert "اليومي" in caught.value.message
    assert caught.value.extra["retry_after"] > 0


async def test_the_registration_cap_is_not_bought_by_waiting(
    session_factory,
) -> None:
    """السقفُ الثالث — **وهو الذي لا يُشترى بالصبر**.

    من طلب عشرةَ رموزٍ على رقمٍ ولم يُكمل تسجيلاً مرةً ليس مستخدماً متعثّراً،
    وانتظارُه يوماً لا يجعله كذلك: «التسجيلُ حدثٌ مرةً لا حدثٌ متكرر».
    فتُمحى النافذةُ واليوميُّ معاً — ويبقى الرفض.
    """
    redis = get_redis_client()
    await _policy(
        session_factory,
        max_per_window=0,
        max_per_day=0,
        max_per_registration=3,
        lockout_minutes=0,
    )

    for _ in range(3):
        await _request(session_factory, JO_PHONE)
        await _clear_resend(JO_PHONE)

    await redis.delete(
        otp_limits.WINDOW_KEY.format(phone=JO_PHONE),
        otp_limits.DAY_KEY.format(phone=JO_PHONE),
    )
    with pytest.raises(RateLimited) as caught:
        await _request(session_factory, JO_PHONE)
    assert "التسجيل" in caught.value.message

    # **وإنشاءُ الحساب يمحوه** — لأن موضوعَه زال: التسجيلُ وقع
    await otp_limits.clear_for_registration(redis, JO_PHONE)
    await _request(session_factory, JO_PHONE)


# ------------------------------------------------------------ العزل


async def test_one_exhausted_number_never_blocks_another(session_factory) -> None:
    """**العدُّ على الرقم لا على IP** — فمقهىً كاملاً لا يخنقه مسيءٌ واحد.

    وهي القاعدةُ نفسُها التي يقوم عليها سقفُ بثّ الموقع، والسببُ نفسُه: عقوبةٌ
    تُصيب من لم يفعل شيئاً تُقرأ عطباً في التطبيق لا حمايةً منه.
    """
    await _policy(
        session_factory,
        max_per_window=2,
        max_per_day=0,
        max_per_registration=0,
        lockout_minutes=30,
    )

    for _ in range(2):
        await _request(session_factory, JO_PHONE)
        await _clear_resend(JO_PHONE)
    with pytest.raises(RateLimited):
        await _request(session_factory, JO_PHONE)

    # ورقمٌ آخر يمرّ بلا أثرٍ من جاره — ولو كان في السوق نفسِه واللحظة نفسِها
    await _request(session_factory, OTHER_PHONE)


async def test_exhausting_one_market_does_not_touch_the_other(
    session_factory,
) -> None:
    """السقوفُ per-country، والعدُّ على الرقم — فسوقان لا يتقاسمان حاجزاً.

    **وهذا هو معنى «لا يعطّل قناةً أخرى لمستخدمٍ آخر»** في شكله المقيس: رقمٌ
    ليبيٌّ يُرسل له بواتساب لا يتأثر برقمٍ أردنيٍّ استنفد سقفَه على الرسائل.
    """
    await _policy(
        session_factory, CountryCode.JO, max_per_window=1, lockout_minutes=30,
        max_per_day=0, max_per_registration=0,
    )
    await _policy(
        session_factory, CountryCode.LY, max_per_window=5, lockout_minutes=0,
        max_per_day=0, max_per_registration=0,
    )

    await _request(session_factory, JO_PHONE, CountryCode.JO)
    await _clear_resend(JO_PHONE)
    with pytest.raises(RateLimited):
        await _request(session_factory, JO_PHONE, CountryCode.JO)

    await _request(session_factory, LY_PHONE, CountryCode.LY)
    await _clear_resend(LY_PHONE)
    await _request(session_factory, LY_PHONE, CountryCode.LY)


# ------------------------------------------------------------ المهلة والرؤية


async def test_the_resend_delay_grows_with_repetition_and_is_capped(
    session_factory,
) -> None:
    """٣٠ث ← دقيقة ← دقيقتان… ثم تقف عند سقفها.

    **والسقفُ ليس تجميلاً**: مهلةٌ تتضاعف بلا حدٍّ تبلغ ساعاتٍ فتصير منعاً
    دائماً **لم يقرّره أحد** — وهو أسوأُ من سقفٍ مكتوب، لأنه لا يُرى في إعداد.
    """
    await _policy(
        session_factory,
        max_per_window=0,
        max_per_day=0,
        max_per_registration=0,
        resend_base_seconds=30,
        resend_max_seconds=120,
    )
    redis = get_redis_client()

    seen = []
    async with session_factory() as session:
        for _ in range(5):
            seen.append(
                await otp_limits.record(session, redis, JO_PHONE, CountryCode.JO)
            )

    assert seen[:3] == [30, 60, 120]
    assert all(value <= 120 for value in seen)


async def test_a_refusal_always_carries_when_to_try_again(session_factory) -> None:
    """**رفضٌ بلا موعدٍ يترك زرّاً يُضغط ولا يفعل شيئاً** — وهو ما تمنعه السقوف.

    والتطبيقان يرسمان `resend_after`/`retry_after` عدّاداً، فرقمٌ فارغٌ هنا
    يعني شاشةً تقول «حاول لاحقاً» بلا أن تقول متى.
    """
    await _policy(
        session_factory,
        max_per_window=1,
        max_per_day=0,
        max_per_registration=0,
        lockout_minutes=15,
    )
    await _request(session_factory, JO_PHONE)
    await _clear_resend(JO_PHONE)

    with pytest.raises(RateLimited) as caught:
        await _request(session_factory, JO_PHONE)
    assert caught.value.extra.get("retry_after") is not None
    assert caught.value.extra["retry_after"] > 0


async def test_exhausted_numbers_are_visible_to_the_admin(session_factory) -> None:
    """تكرارٌ مشبوهٌ **يُرى قبل أن يحرق الرقم** لا بعده."""
    redis = get_redis_client()
    await _policy(
        session_factory,
        max_per_window=1,
        max_per_day=0,
        max_per_registration=0,
        lockout_minutes=5,
    )
    await _request(session_factory, JO_PHONE)
    await _clear_resend(JO_PHONE)
    with pytest.raises(RateLimited):
        await _request(session_factory, JO_PHONE)

    assert JO_PHONE in await otp_limits.exhausted_today(redis)
    assert OTHER_PHONE not in await otp_limits.exhausted_today(redis)


async def test_a_zero_means_no_cap_and_is_written_not_assumed(
    session_factory,
) -> None:
    """صفرٌ **مكتوبٌ** يرفع سقفاً؛ وصفٌّ غائبٌ يقرأ الافتراضاتِ الحارسة.

    وهذا عكسُ «غيابُ الصف = ميزةٌ معطّلة» بقصد: تلك تمنع فتحَ ميزةٍ بالسكوت،
    وهذه تمنع **إطفاءَ حارسٍ** به — والقاعدتان وجهان لمبدأ واحد.
    """
    await _policy(
        session_factory,
        max_per_window=0,
        max_per_day=0,
        max_per_registration=0,
    )
    for _ in range(8):
        await _request(session_factory, JO_PHONE)
        await _clear_resend(JO_PHONE)

    async with session_factory() as session:
        default = await otp_limits.policy_for(session, CountryCode.LY)
    assert default.max_per_window > 0
    assert default.max_per_day > 0
    assert default.max_per_registration > 0

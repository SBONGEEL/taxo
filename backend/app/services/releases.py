"""سجلُّ الإصدارات والتحديثُ الإلزاميّ — **البند ٨ (§39٫٨، §43)**.

**والقرارُ يُحسب هنا وحدَه.** ثلاثةُ تطبيقاتٍ تقارن رقمين بأنفسها **ثلاثُ نسخٍ
من قاعدةٍ واحدة**، تفترق أوّلَ ما تتغيّر — وهي §14 مطبَّقةً على حكمٍ لا على
مبلغ، كما في `SettlementState` و`LiveDriverOut.state`.

**والصفُّ الحاكم هو أعلى رقمٍ لكلِّ تطبيق** — لا الأحدثَ إنشاءً: مشرفٌ يصحّح
صفَّ إصدارٍ قديمٍ بعد إضافة الجديد **لا يُعيد سياسةَ الأمس**.
"""

from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, InvalidInput, NotFound
from app.models.app_release import AppRelease
from app.models.enums import ClientApp, ReleasePlatform, ReleaseSource

#: مهلةُ طرقِ رابط التحميل. **أقصرُ من مهلة المزوّدين**: هذه على مشرفٍ ينتظر
#: أمام نموذج، **ورابطٌ لا يجيب في عشر ثوانٍ ليس رابطاً يُعتمد عليه قفلُ ناس**.
LINK_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True, slots=True)
class VersionVerdict:
    """حكمُ الإقلاع — **محسوبٌ لا مقارَنٌ في التطبيق**."""

    state: str
    latest_build: int | None
    min_supported_build: int | None
    download_url: str | None
    release_notes: str | None
    reminder_hours: int | None
    #: **أيُرسم MapLibre في هذا الغلاف؟** (SPEC §١٠٥/٥) — لا سجلَّ أو لا حدَّ أو لا رقمَ = لا
    open_map: bool = False


#: **لا سجلَّ = لا تدخّل.** والغيابُ هنا يعطّل الحجبَ لا التطبيق.
#: **غلافُ الراكب بمفتاح الرفع القديم** (أمرُ المالك ٢٠٢٦-١١-٢٦، SPEC §١١٦) — صفحةُ التحميل خدمت حتى ١٩/١٠ حزماً موقَّعةً
#: بمفتاح الرفع (`3B:DC…`) وآخرُها **772**؛ وبعدها حزمُ Play بتوقيعه. **وأندرويد لا يثبّت حزمةً فوق أخرى بمفتاحٍ آخر**،
#: فصاحبُ 772 لا يتحدّث من Play ولا من الموقع — **وزرُّ «حمّل الآن» الذي يفتح الموقعَ يقوده إلى تثبيتٍ يُرفض**.
#: **وكلُّ ما على Play للراكب أعلى من 772** (الإنتاج 1452 · beta 932)، **إلا 496 في المسار الداخليّ** لمختبِرينا وحدَهم —
#: والرسالةُ عليه صحيحةٌ وإن لم تلزم: الحذفُ ثمّ Play يعطيه الإنتاج. **والكبتنُ لا يُمسّ**: مفتاحُه في الموقع مفتاحُ Play منذ ١٩/١٠،
#: ولا سؤالَ من غلاف كبتن ≤ 772 في السجلّ (٢٦/١١).
OLD_KEY_LAST_RIDER_BUILD = 772
RIDER_PLAY_URL = "https://play.google.com/store/apps/details?id=ly.tajora.rider"
#: **النصُّ يُرسم في نافذة 772 كما هو** — عنوانُها «تحديثٌ جديدٌ متاح» وزرّاها «حمّل الآن» و«لاحقاً» من شيفرتها هي لا من هنا
OLD_KEY_NOTES = (
    "نسختك من TAXO قديمة ولا تتحدّث تلقائياً.\n"
    "لتحصل على آخر نسخة: احذف التطبيق مرّة واحدة، ثم ثبّت TAXO من Google Play بزرّ «حمّل الآن».\n"
    "حسابك ومحفظتك ورحلاتك محفوظة كما هي — فقط سجّل الدخول من جديد."
)


def old_key_shell(app: ClientApp, platform: ReleasePlatform, build: int | None) -> bool:
    """**أهذا غلافُ راكبٍ لا يتحدّث من Play؟** — بلا رقمٍ = لا (لا رسالةَ بالظنّ)."""
    return (
        app == ClientApp.RIDER
        and platform == ReleasePlatform.ANDROID
        and build is not None
        and 0 < build <= OLD_KEY_LAST_RIDER_BUILD
    )


#: **القياسُ** (أمرُ المالك: «كم راكباً رآها، وكم انتقل إلى نسخة Play خلال ٧ أيام») — السؤالُ بلا جلسة، **فالجهازُ عنوانُه
#: مختوماً** (HMAC بسرّ الخادم، لا عنوانٌ صريح)، ويُمحى بعد ٣٠ يوماً. **وهو تقريبٌ ويُقال كذلك**: شبكةُ الهاتف تبدّل عنوانَه،
#: فالانتقالُ يُعدّ حين يسأل **العنوانُ نفسُه** بعدها بغلافٍ من Play — فيُنقص ولا يزيد.
OLD_KEY_SEEN = "taxo:oldkey:seen"
OLD_KEY_MOVED = "taxo:oldkey:moved"
OLD_KEY_ASKS = "taxo:oldkey:asks"
OLD_KEY_TTL_SECONDS = 30 * 24 * 3600


def _device_mark(ip: str, secret: str) -> str:
    return hmac.new(secret.encode(), f"oldkey:{ip}".encode(), hashlib.sha256).hexdigest()[:20]


async def note_old_key_audience(
    redis, *, ip: str, secret: str, app: ClientApp, platform: ReleasePlatform, build: int | None
) -> None:
    """يُعدّ من رأى الرسالة ومن عاد بعدها بغلافٍ من Play — **ولا يُسقط السؤالَ إن سقط هو**."""
    if app != ClientApp.RIDER or platform != ReleasePlatform.ANDROID or build is None or not ip:
        return
    mark = _device_mark(ip, secret)
    now = str(int(time.time()))
    try:
        if old_key_shell(app, platform, build):
            await redis.hsetnx(OLD_KEY_SEEN, mark, now)
            await redis.incr(OLD_KEY_ASKS)
            for key in (OLD_KEY_SEEN, OLD_KEY_ASKS):
                await redis.expire(key, OLD_KEY_TTL_SECONDS)
        elif build > OLD_KEY_LAST_RIDER_BUILD and await redis.hexists(OLD_KEY_SEEN, mark):
            await redis.hsetnx(OLD_KEY_MOVED, mark, now)
            await redis.expire(OLD_KEY_MOVED, OLD_KEY_TTL_SECONDS)
    except Exception:  # noqa: BLE001 — عدّادٌ لا يُسقط بابَ الإقلاع
        return


NO_POLICY = VersionVerdict(
    state="ok",
    latest_build=None,
    min_supported_build=None,
    download_url=None,
    release_notes=None,
    reminder_hours=None,
)


async def current(
    session: AsyncSession,
    app: ClientApp,
    platform: ReleasePlatform = ReleasePlatform.ANDROID,
    source: ReleaseSource = ReleaseSource.DEFAULT,
    *,
    fallback: bool = True,
) -> AppRelease | None:
    """الصفُّ الحاكم لتطبيقٍ على نظامٍ من متجر — **أعلى رقمٍ لا أحدثُ إنشاء**.

    **والنظامُ جزءٌ من السؤال** (2026-10-12): رقمُ iOS لا يُقارَن برقم أندرويد،
    **ورابطُ هذا الصفِّ هو ما يفتحه زرُّ «تحديث» على ذلك النظام**.

    **والمتجرُ كذلك** (٢٠٢٦-١١-٢٠): صفُّه يحكمه، **ومتجرٌ بلا صفٍّ يُحكم بصفِّ `default`** (`fallback`) — فلا يُفتح بابٌ
    لحزمةٍ قديمةٍ لأنّ متجرَها لم يُسجَّل بعد. **واللوحةُ تسأل بلا `fallback`**: «أهذا الصفُّ حاكمُ متجره؟» سؤالٌ عن صفوفه وحدها.
    """

    async def top(which: ReleaseSource) -> AppRelease | None:
        return await session.scalar(
            select(AppRelease)
            .where(
                AppRelease.app == app,
                AppRelease.platform == platform,
                AppRelease.source == which,
            )
            .order_by(AppRelease.build.desc())
            .limit(1)
        )

    row = await top(source)
    if row is None and fallback and source != ReleaseSource.DEFAULT:
        row = await top(ReleaseSource.DEFAULT)
    return row


async def verdict_for(
    session: AsyncSession,
    *,
    app: ClientApp,
    build: int | None,
    platform: ReleasePlatform = ReleasePlatform.ANDROID,
    source: ReleaseSource = ReleaseSource.DEFAULT,
) -> VersionVerdict:
    """ماذا يفعل التطبيقُ عند الإقلاع.

    **و`build` غائبةٌ تعني «لا حزمةَ تعرف رقمَها»** — متصفّحٌ أو غلافٌ لا يجيب
    ملحقُه. **ولا يُقفل من لا نعرف نسختَه**: القفلُ عقوبةٌ على قِدَمٍ مثبَت،
    **والظنُّ لا يقفل باباً**.
    """
    release = await current(session, app, platform, source)
    # **غلافُ المفتاح القديم: رسالةٌ اختياريّةٌ في كلِّ فتحٍ إلى Play** (SPEC §١١٦) — `reminder_hours = 0` يكتمها في الفتح نفسِه
    # بعد «لاحقاً» ويعيدها في الفتح التالي (شيفرةُ 772: «لاحقاً» يكتم حتى `الآن + الساعات`). **ولا تُقفل أحداً**: لا `forced`
    # ولو كان حدُّ اللوحة فوقه — فالقفلُ يقود إلى زرٍّ لا يُثبَّت ما ينزّله
    if old_key_shell(app, platform, build):
        return VersionVerdict(
            state="optional",
            latest_build=release.build if release else None,
            min_supported_build=release.min_supported_build if release else None,
            download_url=RIDER_PLAY_URL,
            release_notes=OLD_KEY_NOTES,
            reminder_hours=0,
            open_map=False,
        )
    if release is None:
        return NO_POLICY

    if build is None or build >= release.build:
        state = "ok"
    elif build < release.min_supported_build:
        state = "forced"
    else:
        state = "optional"

    return VersionVerdict(
        state=state,
        latest_build=release.build,
        min_supported_build=release.min_supported_build,
        download_url=release.download_url,
        release_notes=release.release_notes,
        reminder_hours=release.reminder_hours,
        open_map=open_map_allowed(release, build),
    )


def open_map_allowed(release: AppRelease, build: int | None) -> bool:
    """**أيُرسم MapLibre في هذا الغلاف؟** (SPEC §١٠٥/٥، ٢٠٢٦-١١-١٦).

    **بلا رقمٍ = لا**، عكسَ الحجب: الحجبُ عقوبةٌ لا تقع بالظنّ، **وهذه ميزةٌ لا تُعطى بالظنّ** — غلافٌ لا يعرف
    رقمَه قد يكون قديماً لم يُقَس عليه المحرّك. **وبلا حدٍّ في الصفِّ الحاكم = لا**: الخريطةُ المفتوحةُ لا تبلغ
    غلافاً حتى يُكتب في لوحة الإصدارات رقمُ أوّلِ غلافٍ قِيست عليه.
    """
    limit = release.open_map_min_build
    return limit is not None and build is not None and build >= limit


async def check_download_url(url: str) -> None:
    """يطرق الرابطَ قبل الحفظ — **ولا يُقفَل أحدٌ خارج تطبيقه بلا مخرج**.

    **`HEAD` ثمّ `GET` عند الرفض**: خوادمُ ملفّاتٍ كثيرةٌ تردّ `405` على `HEAD`
    وهي تخدم الملفَّ تماماً — **فرفضُ الرابط لأجل فعلٍ لا يدعمه الخادم رفضٌ
    للسليم**، وحارسٌ يصيح على السليم يُطفأ.

    **والمقروءُ حالةُ الردِّ لا محتواه**: لا تُحمَّل حزمةُ خمسةِ ميجابايتٍ في
    نداءِ لوحة — `GET` بترويسة مدىً يقرأ أوّلَ بايتٍ ويقطع.
    """
    try:
        async with httpx.AsyncClient(
            timeout=LINK_TIMEOUT_SECONDS, follow_redirects=True
        ) as http:
            response = await http.head(url)
            if response.status_code in (403, 405, 501):
                response = await http.get(url, headers={"Range": "bytes=0-0"})
    except httpx.HTTPError as error:  # pragma: no cover - شبكةٌ لا تُشتقّ
        raise InvalidInput(
            "تعذّر الوصول إلى رابط التحميل — ولا يُحفظ إصدارٌ برابطٍ لا يُفتح."
        ) from error

    if response.status_code >= 400:
        raise InvalidInput(
            "رابطُ التحميل ردَّ "
            f"{response.status_code} — ولا يُحفظ إصدارٌ برابطٍ لا يُفتح."
        )

    # **و`.apk` يجيب صفحةً ليس حزمة** (قِيس 2026-09-03): وُضع في هذا الحقل
    # `https://app.tajora.ly/downloads/taxo-rider.apk` — **وهو غلافُ تطبيق
    # الراكب لا صفحةُ التحميل** — فردّ **200 ومعه `text/html`**: تطبيقُ الويب
    # نفسُه. **فحالةُ الردِّ وحدَها تُخضِّر رابطاً يعطي صاحبَ الهاتف صفحةً
    # بدل الحزمة**. والمضيفُ الصحيح `taxo.tajora.ly` ردَّ
    # `application/vnd.android.package-archive` و404 لِما لا وجودَ له.
    #
    # **والشرطُ ضيّقٌ بقصد — مسارٌ ينتهي بـ`.apk` وحدَه**: رابطُ **صفحةِ**
    # تحميلٍ (لا ينتهي بـ`.apk`) يجيب HTML بحقّ، **وهو مخرجٌ صالحٌ لأن الزرَّ
    # يفتحه في المتصفّح** — فرفضُه صياحٌ على السليم. أما `.apk` يجيب صفحةً
    # **فخطأُ عنوانٍ بيقينٍ تقريبيّ**.
    kind = (response.headers.get("content-type") or "").split(";")[0].strip()
    if url.lower().split("?")[0].endswith(".apk") and kind == "text/html":
        raise InvalidInput(
            "الرابطُ ينتهي بـ.apk لكنه يردّ صفحةَ ويب (text/html) — "
            "غالباً عنوانُ التطبيق لا عنوانُ صفحة التحميل."
        )


async def _require_second_permission(
    session: AsyncSession,
    *,
    app: ClientApp,
    platform: ReleasePlatform,
    build: int,
    min_supported_build: int,
    confirmation: int | None,
    release_id: uuid.UUID | None = None,
    source: ReleaseSource = ReleaseSource.DEFAULT,
) -> None:
    """**الإذنُ الثاني حين يرتفع الحدُّ فعلاً** (§39٫٨: «يستأذن مرّتين»).

    **و«فعلاً» شرطان لا واحد**: أن يكون الصفُّ **حاكماً** (أعلى رقمٍ للتطبيق)،
    وأن يكون حدُّه **فوق الحدِّ القائم**. فصفُّ إصدارٍ قديمٍ يُصحَّح **لا يقفل
    أحداً**، وحدٌّ ينزل أو يبقى **لا يقفل من لم يكن مقفلاً**.

    **وورقةٌ تظهر حيث لا خطر تُفرَّغ من داخلها**: يصير التأكيدُ ضغطةً تلقائيةً
    فلا يعود يعني شيئاً **يومَ يعني** — وهي «بوّابةٌ تصيح حيث لا خطر» بحرفها.

    **وأوّلُ صفٍّ لتطبيقٍ يستأذن دائماً**: لا حدَّ قبله، **فكلُّ حدٍّ يكتبه
    يقفل من هو دونه** — وذاك أوسعُ فعلٍ في هذه الشاشة لا أهونُه.
    """
    live = await current(session, app, platform, source, fallback=False)
    if release_id is None:
        governs = live is None or build > live.build
    else:
        governs = live is not None and live.id == release_id
    if not governs:
        return

    standing = 0 if live is None else live.min_supported_build
    if min_supported_build <= standing:
        return
    if confirmation != min_supported_build:
        raise InvalidInput(
            "رفعُ الحدِّ يقفل التطبيقَ على كلِّ من حزمتُه أقلُّ من "
            f"{min_supported_build} — أعِد كتابة الرقم لتأكيده."
        )


async def create(
    session: AsyncSession,
    *,
    app: ClientApp,
    platform: ReleasePlatform = ReleasePlatform.ANDROID,
    build: int,
    min_supported_build: int,
    download_url: str,
    release_notes: str,
    reminder_hours: int,
    confirmation: int | None,
    open_map_min_build: int | None = None,
    source: ReleaseSource = ReleaseSource.DEFAULT,
) -> AppRelease:
    """يضيف إصداراً — **بعد أن يطرق رابطَه ويستأذن مرّتين**."""
    if min_supported_build > build:
        raise InvalidInput(
            "الحدُّ الأدنى فوق رقم الإصدار — يُقفل صاحبُ أحدث حزمةٍ بلا مخرج."
        )
    exists = await session.scalar(
        select(AppRelease).where(
            AppRelease.app == app,
            AppRelease.platform == platform,
            AppRelease.source == source,
            AppRelease.build == build,
        )
    )
    if exists is not None:
        raise Conflict(
            "هذا الرقم مسجَّلٌ لهذا التطبيق على هذا النظام وهذا المتجر — والرقمُ هو هويةُ الحزمة."
        )

    await _require_second_permission(
        session,
        app=app,
        platform=platform,
        build=build,
        min_supported_build=min_supported_build,
        confirmation=confirmation,
        source=source,
    )
    await check_download_url(download_url)

    release = AppRelease(
        app=app,
        platform=platform,
        source=source,
        build=build,
        min_supported_build=min_supported_build,
        download_url=download_url,
        release_notes=release_notes,
        reminder_hours=reminder_hours,
        open_map_min_build=open_map_min_build,
    )
    session.add(release)
    await session.flush()
    return release


async def get(session: AsyncSession, release_id: uuid.UUID) -> AppRelease:
    release = await session.get(AppRelease, release_id)
    if release is None:
        raise NotFound("الإصدار غير موجود")
    return release


async def update(
    session: AsyncSession,
    release: AppRelease,
    *,
    min_supported_build: int,
    download_url: str,
    release_notes: str,
    reminder_hours: int,
    confirmation: int | None,
    open_map_min_build: int | None = None,
) -> dict[str, dict[str, object]]:
    """يعدّل صفّاً قائماً — **ولا يُعدَّل رقمُ الإصدار ولا تطبيقُه ولا نظامُه**.

    **والرقمُ هويةُ حزمةٍ مبنيّةٍ موقَّعةٍ في يد الناس** — تغييرُه هنا يجعل
    السجلَّ يصف حزمةً غير التي وُصفت، **وهو تزويرُ سجلٍّ لا تصحيحُ حقل**.
    فالخطأُ في الرقم يُصحَّح بحذف الصفِّ وكتابة غيره.

    **ويعيد القيمةَ قبل وبعد** كما يفرض §40٫١ على كلِّ تعديلٍ في اللوحة.
    """
    if min_supported_build > release.build:
        raise InvalidInput(
            "الحدُّ الأدنى فوق رقم الإصدار — يُقفل صاحبُ أحدث حزمةٍ بلا مخرج."
        )
    await _require_second_permission(
        session,
        app=release.app,
        platform=release.platform,
        build=release.build,
        min_supported_build=min_supported_build,
        confirmation=confirmation,
        release_id=release.id,
        source=release.source,
    )
    if download_url != release.download_url:
        await check_download_url(download_url)

    changes: dict[str, dict[str, object]] = {}
    for field, value in (
        ("min_supported_build", min_supported_build),
        ("download_url", download_url),
        ("release_notes", release_notes),
        ("reminder_hours", reminder_hours),
        ("open_map_min_build", open_map_min_build),
    ):
        before = getattr(release, field)
        if before != value:
            changes[field] = {"before": before, "after": value}
            setattr(release, field, value)
    await session.flush()
    return changes


async def delete(session: AsyncSession, release: AppRelease) -> None:
    """يحذف صفّاً — **وهو من القليل الذي يُحذف** (§39٫٤).

    **ليس مالاً ولا شاهدَ نزاعٍ ولا نصّاً وافق عليه إنسان**: سجلُّ إصدارٍ
    **إعدادُ تشغيلٍ يصف حزمة**، وخطؤه يُصحَّح بمحوه لا بقيدٍ مقابل. **وأثرُه
    في التدقيق يبقى** بقيمته قبل الحذف.
    """
    await session.delete(release)
    await session.flush()

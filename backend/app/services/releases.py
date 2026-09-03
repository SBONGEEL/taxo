"""سجلُّ الإصدارات والتحديثُ الإلزاميّ — **البند ٨ (§39٫٨، §43)**.

**والقرارُ يُحسب هنا وحدَه.** ثلاثةُ تطبيقاتٍ تقارن رقمين بأنفسها **ثلاثُ نسخٍ
من قاعدةٍ واحدة**، تفترق أوّلَ ما تتغيّر — وهي §14 مطبَّقةً على حكمٍ لا على
مبلغ، كما في `SettlementState` و`LiveDriverOut.state`.

**والصفُّ الحاكم هو أعلى رقمٍ لكلِّ تطبيق** — لا الأحدثَ إنشاءً: مشرفٌ يصحّح
صفَّ إصدارٍ قديمٍ بعد إضافة الجديد **لا يُعيد سياسةَ الأمس**.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, InvalidInput, NotFound
from app.models.app_release import AppRelease
from app.models.enums import ClientApp

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


#: **لا سجلَّ = لا تدخّل.** والغيابُ هنا يعطّل الحجبَ لا التطبيق.
NO_POLICY = VersionVerdict(
    state="ok",
    latest_build=None,
    min_supported_build=None,
    download_url=None,
    release_notes=None,
    reminder_hours=None,
)


async def current(session: AsyncSession, app: ClientApp) -> AppRelease | None:
    """الصفُّ الحاكم لتطبيق — **أعلى رقمٍ لا أحدثُ إنشاء**."""
    return await session.scalar(
        select(AppRelease)
        .where(AppRelease.app == app)
        .order_by(AppRelease.build.desc())
        .limit(1)
    )


async def verdict_for(
    session: AsyncSession, *, app: ClientApp, build: int | None
) -> VersionVerdict:
    """ماذا يفعل التطبيقُ عند الإقلاع.

    **و`build` غائبةٌ تعني «لا حزمةَ تعرف رقمَها»** — متصفّحٌ أو غلافٌ لا يجيب
    ملحقُه. **ولا يُقفل من لا نعرف نسختَه**: القفلُ عقوبةٌ على قِدَمٍ مثبَت،
    **والظنُّ لا يقفل باباً**.
    """
    release = await current(session, app)
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
    )


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
    build: int,
    min_supported_build: int,
    confirmation: int | None,
    release_id: uuid.UUID | None = None,
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
    live = await current(session, app)
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
    build: int,
    min_supported_build: int,
    download_url: str,
    release_notes: str,
    reminder_hours: int,
    confirmation: int | None,
) -> AppRelease:
    """يضيف إصداراً — **بعد أن يطرق رابطَه ويستأذن مرّتين**."""
    if min_supported_build > build:
        raise InvalidInput(
            "الحدُّ الأدنى فوق رقم الإصدار — يُقفل صاحبُ أحدث حزمةٍ بلا مخرج."
        )
    exists = await session.scalar(
        select(AppRelease).where(AppRelease.app == app, AppRelease.build == build)
    )
    if exists is not None:
        raise Conflict("هذا الرقم مسجَّلٌ لهذا التطبيق — والرقمُ هو هويةُ الحزمة.")

    await _require_second_permission(
        session,
        app=app,
        build=build,
        min_supported_build=min_supported_build,
        confirmation=confirmation,
    )
    await check_download_url(download_url)

    release = AppRelease(
        app=app,
        build=build,
        min_supported_build=min_supported_build,
        download_url=download_url,
        release_notes=release_notes,
        reminder_hours=reminder_hours,
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
) -> dict[str, dict[str, object]]:
    """يعدّل صفّاً قائماً — **ولا يُعدَّل رقمُ الإصدار ولا تطبيقُه**.

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
        build=release.build,
        min_supported_build=min_supported_build,
        confirmation=confirmation,
        release_id=release.id,
    )
    if download_url != release.download_url:
        await check_download_url(download_url)

    changes: dict[str, dict[str, object]] = {}
    for field, value in (
        ("min_supported_build", min_supported_build),
        ("download_url", download_url),
        ("release_notes", release_notes),
        ("reminder_hours", reminder_hours),
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

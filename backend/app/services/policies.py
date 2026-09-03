"""السياساتُ والشروط — **البند ١٠ (§39٫١٠، §34، §45)**.

**والجداولُ نامت منذ `0060` بلا قارئ**، وسُدَّ شكلُها في `0068`. وهذا أوّلُ
كاتبٍ لها.

## ثلاثُ قواعدَ من §34، وكلُّها مفروضةٌ هنا لا موصوفة

**١) كلُّ حفظٍ صفٌّ جديدٌ برقمٍ أعلى — ولا يُحرَّر صفٌّ فوق نفسه.**
**والعلّةُ بنصِّ المالك**: «نصٌّ وُوفق عليه لا يُحرَّر فوق نفسه — لو بقيت
التصحيحاتُ على النسخة نفسِها لصار تصحيحُ فاصلةٍ قادراً على تغيير معنى نصٍّ
وافق عليه الناسُ بلا أثر، **والقاعدةُ تمنع محوَه ولا تمنع تبديلَه**».
**فلا بابَ تعديلٍ في هذه الخدمة أصلاً** — ومن أراد تصحيحَ حرفٍ كتب نسخةً.

**٢) والمنشورةُ واحدةٌ لكلِّ (سوق + نوع + تطبيق)**، يحرسها فهرسٌ جزئيٌّ في
القاعدة. **وهو جوابُ «أيُّ نسخةٍ واجبةٌ الآن» لا وسيلةٌ إليه**: لا يُحسب
`MAX(version)` ولا يُفترض أن أحدثَ رقمٍ هو المنشور. **فالنشرُ ينزع سابقَه في
المعاملة نفسِها** — وإلا رفض الفهرسُ الكتابةَ برسالة قاعدةٍ لا تقول ما العمل.

**٣) و`min_accepted_version` كاتبُه واحدٌ مسمّى** (§5-ج في العمود المحضَّر):
`_stamp_min_accepted` وحدَها، وتُنادى من `create_version` وحدَها لأنها الطريق
الوحيد الذي يولد به صفّ. **ويقيس ذلك اختبارٌ يمسح الشجرة بمُحلِّل بايثون**
ويسقط يومَ يُسنِد إليه موضعٌ آخر.

**والمعادلةُ بنصّها**: `requires_reconsent` ? نسخةُ الصفِّ نفسِه : قيمةُ
المنشورةِ التي قبله (أو نسخةُ الصفِّ نفسِه حين لا منشورةَ قبله). **ومعناها**:
«أدنى نسخةٍ تُبرئ» — من وافق عليها أو على ما بعدها فقد وافق على ما يكفي،
**فلا يُمشى رجوعاً في النسخ** ليُعرف ذلك.

## وما لا تفعله هذه الخدمة — بقرارٍ مكتوب

**لا شاشةَ قبولٍ في تطبيقٍ ولا بابَ «ما الذي يلزمني قبولُه»** (البند ١٠ يُسلَّم
**مسوّدةً** بنصِّ §39٫١٠). **ووثيقةٌ غيرُ منشورةٍ لا يُسأل عنها أحد**، فبابُ
قبولٍ اليومَ بابٌ لا يجيب إلا «لا شيء» — **وهو «بابٌ بلا زرّ» في اتجاهه
المعاكس**. ويُبنى يومَ يعتمد المالكُ النصوص.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, InvalidInput, NotFound
from app.models.enums import CountryCode, PolicyApp, PolicyDocType
from app.models.privacy import OrgProfile, PrivacyPolicy, UserPolicyConsent
from app.models.user import User


async def published(
    session: AsyncSession,
    *,
    country: CountryCode,
    doc_type: PolicyDocType,
    app: PolicyApp,
) -> PrivacyPolicy | None:
    """النسخةُ المنشورةُ الآن — **من الفهرس لا من `MAX(version)`**."""
    return await session.scalar(
        select(PrivacyPolicy).where(
            PrivacyPolicy.country_code == country,
            PrivacyPolicy.doc_type == doc_type,
            PrivacyPolicy.app == app,
            PrivacyPolicy.is_published.is_(True),
        )
    )


async def versions(
    session: AsyncSession,
    *,
    country: CountryCode | None = None,
    doc_type: PolicyDocType | None = None,
    app: PolicyApp | None = None,
) -> list[PrivacyPolicy]:
    """كلُّ النسخ مرتَّبةً — الأحدثُ أوّلاً داخل كلِّ ثلاثيّة."""
    stmt = select(PrivacyPolicy).order_by(
        PrivacyPolicy.country_code,
        PrivacyPolicy.doc_type,
        PrivacyPolicy.app,
        PrivacyPolicy.version.desc(),
    )
    if country is not None:
        stmt = stmt.where(PrivacyPolicy.country_code == country)
    if doc_type is not None:
        stmt = stmt.where(PrivacyPolicy.doc_type == doc_type)
    if app is not None:
        stmt = stmt.where(PrivacyPolicy.app == app)
    return list((await session.scalars(stmt)).all())


async def get(session: AsyncSession, policy_id: uuid.UUID) -> PrivacyPolicy:
    policy = await session.get(PrivacyPolicy, policy_id)
    if policy is None:
        raise NotFound("الوثيقة غير موجودة")
    return policy


async def _next_version(
    session: AsyncSession,
    *,
    country: CountryCode,
    doc_type: PolicyDocType,
    app: PolicyApp,
) -> int:
    """أعلى رقمٍ في الثلاثيّة زائدَ واحد.

    **ويعود الرقمُ بعد حذف مسوّدة، وهو مقصودٌ لا سهو**: المسوّدةُ لا تُنشر،
    **ولا تُحذف واحدةٌ وافق عليها أحد** — فذلك الرقمُ لم يصل إنساناً قطّ،
    **والتدقيقُ يفرّق الصفّين بمعرّفهما**. **وحفظُه كان يحتاج عدّاداً ثانياً**
    — بيتاً ثانياً للحقيقة يفترق عن الجدول أوّلَ حذفٍ يدويّ.
    """
    highest = await session.scalar(
        select(func.max(PrivacyPolicy.version)).where(
            PrivacyPolicy.country_code == country,
            PrivacyPolicy.doc_type == doc_type,
            PrivacyPolicy.app == app,
        )
    )
    return int(highest or 0) + 1


async def _stamp_min_accepted(
    session: AsyncSession, policy: PrivacyPolicy, *, requires_reconsent: bool
) -> None:
    """**الكاتبُ الوحيد لـ`min_accepted_version`** (§34، §5-ج).

    **والمعادلةُ بنصّها**: `requires_reconsent` ? نسخةُ الصفِّ نفسِه : قيمةُ
    المنشورةِ التي قبله. **وبلا منشورةٍ قبله فنسخةُ الصفِّ نفسِه** — أوّلُ
    وثيقةٍ في سوقٍ تُطلب موافقتُها ممّن لم يوافق على شيءٍ قطّ.

    **ويُقاس بمُحلِّل بايثون أن لا كاتبَ ثانيَ له** — لا بتعليقٍ يَعِد بذلك.
    """
    if requires_reconsent:
        policy.min_accepted_version = policy.version
        return
    live = await published(
        session,
        country=policy.country_code,
        doc_type=policy.doc_type,
        app=policy.app,
    )
    policy.min_accepted_version = (
        policy.version if live is None else live.min_accepted_version
    )


async def create_version(
    session: AsyncSession,
    *,
    country: CountryCode,
    doc_type: PolicyDocType,
    app: PolicyApp,
    body_ar: str,
    body_en: str | None,
    requires_reconsent: bool,
) -> PrivacyPolicy:
    """يكتب **نسخةً جديدةً مسوّدةً** — ولا يُحرِّر شيئاً قائماً.

    **وتولد مطفأة** (`is_published=False`): النشرُ فعلٌ ثانٍ بيدٍ ثانية،
    **وحفظٌ ينشر يجعل كلَّ تصحيحٍ إعلاناً**.
    """
    if not body_ar.strip():
        raise InvalidInput("نصُّ الوثيقة العربيُّ مطلوب — ولا تُحفظ وثيقةٌ فارغة.")

    policy = PrivacyPolicy(
        country_code=country,
        doc_type=doc_type,
        app=app,
        version=await _next_version(
            session, country=country, doc_type=doc_type, app=app
        ),
        min_accepted_version=0,  # يُختم فوراً أدناه، والكاتبُ واحد
        body_ar=body_ar,
        body_en=(body_en or None),
        requires_reconsent=requires_reconsent,
        is_published=False,
    )
    await _stamp_min_accepted(
        session, policy, requires_reconsent=requires_reconsent
    )
    session.add(policy)
    await session.flush()
    return policy


async def publish(
    session: AsyncSession, policy: PrivacyPolicy, *, actor: User
) -> PrivacyPolicy | None:
    """ينشر نسخةً — **وينزع سابقَها في المعاملة نفسِها**.

    **ويعيد النسخةَ التي نُزعت** ليُكتب في التدقيق ما حلَّ محلَّ ماذا: «نُشرت
    الرابعة» وحدَها لا تقول أنّ الثالثة أُطفئت.

    **والنزعُ قبل الرفع لا بعده**: الفهرسُ الجزئيُّ يرفض منشورتين في الثلاثيّة،
    **وترتيبٌ معكوسٌ يسقط برسالة قاعدةٍ لا تقول ما العمل**.
    """
    if policy.is_published:
        raise Conflict("هذه النسخة منشورةٌ أصلاً.")

    previous = await published(
        session,
        country=policy.country_code,
        doc_type=policy.doc_type,
        app=policy.app,
    )
    if previous is not None:
        if previous.version > policy.version:
            raise Conflict(
                "المنشورةُ الآن أحدثُ من هذه — ولا يُنشر نصٌّ أقدمُ فوق أحدث."
            )
        previous.is_published = False
        await session.flush()

    policy.is_published = True
    policy.published_at = datetime.now(UTC)
    policy.published_by = actor.id
    await session.flush()
    return previous


async def withdraw(session: AsyncSession, policy: PrivacyPolicy) -> None:
    """يسحب النشرَ — **فيعود السوقُ بلا وثيقةٍ قائمة**.

    **ولمَ بابٌ للرجوع أصلاً**: النشرُ حالٌ يُدخَل إليها، **وحالٌ تُدخَل ولا
    يُخرج منها هي «بابٌ بلا زرّ في اتجاهٍ واحد»** — وهي قاعدةٌ مكتوبةٌ في هذا
    المستودع عن مفتاحٍ بُني ليوقف الأذى ولا يُطفأ. **ومن نشر نصّاً في سوقٍ لم
    يُفتح بعد** لا يملك إلا أن ينشر فوقه نصّاً آخر — **فيبقى منشوراً على
    الناس شيءٌ لم يكن يريد نشرَه**.

    **ولا يُمحى شيء**: الصفُّ يبقى بنصِّه ورقمه وتاريخِ نشره الأول، **وموافقاتُ
    من وافق عليه تبقى كما هي** — والسحبُ يقول «لا وثيقةَ قائمةً الآن» لا «لم
    تكن».

    **ولا يُصفَّر `published_at`**: «نُشرت يومَ كذا ثمّ سُحبت» خبرٌ، **و«لم
    تُنشر قطّ» كذبٌ يمحو ما رآه الناس**.
    """
    if not policy.is_published:
        raise InvalidInput("هذه النسخة ليست منشورةً أصلاً.")
    policy.is_published = False
    await session.flush()


async def delete_draft(session: AsyncSession, policy: PrivacyPolicy) -> None:
    """يحذف **مسوّدةً لم توافق عليها نفس**.

    **والمنشورةُ لا تُحذف** (§39٫٤: «نصٌّ وافق عليه إنسانٌ لا يُمحى»)،
    **والموافقةُ تمنعه في القاعدة** بـ`RESTRICT` — فالرفضُ هنا يقول السببَ
    بالعربية بدل أن تقوله Postgres.
    """
    if policy.is_published:
        raise InvalidInput(
            "لا تُحذف نسخةٌ منشورة — انشُر غيرَها، ويبقى نصُّها شاهداً على من وافق."
        )
    consents = await session.scalar(
        select(func.count())
        .select_from(UserPolicyConsent)
        .where(UserPolicyConsent.policy_id == policy.id)
    )
    if consents:
        raise InvalidInput(
            f"وافق على هذه النسخة {consents} حساباً — ولا يُمحى نصٌّ وافق عليه أحد."
        )
    await session.delete(policy)
    await session.flush()


async def org(session: AsyncSession) -> OrgProfile | None:
    """بيانُ الجهة — **صفٌّ واحدٌ لا صفٌّ لكلِّ سوق**، و`None` حالٌ صحيحة."""
    return await session.scalar(select(OrgProfile).limit(1))


async def save_org(
    session: AsyncSession,
    *,
    legal_name: str | None,
    address: str | None,
    privacy_email: str | None,
) -> tuple[OrgProfile, dict[str, dict[str, object]]]:
    """يكتب بيانَ الجهة — **ويعيد القيمةَ قبل وبعد** (§40٫١).

    **وهذا الجدولُ يُحرَّر فوق نفسه بحقّ** خلافاً للوثائق: **عنوانُ شركةٍ
    ليس نصّاً وافق عليه أحد**، وتاريخُ تغييره لا يُسأل عنه بعد شهر — والتدقيقُ
    يحمل ما تغيّر.
    """
    row = await org(session)
    if row is None:
        row = OrgProfile()
        session.add(row)

    changes: dict[str, dict[str, object]] = {}
    for field, value in (
        ("legal_name", legal_name),
        ("address", address),
        ("privacy_email", privacy_email),
    ):
        before = getattr(row, field)
        after = (value or None) if value is None else (value.strip() or None)
        if before != after:
            changes[field] = {"before": before, "after": after}
            setattr(row, field, after)
    await session.flush()
    return row, changes

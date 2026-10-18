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

## وإعادةُ القبول (قرارُ المالك ٢٠٢٦-١٠-١٨، SPEC §٧٦-ع/٧ البند ٣)

**كان هنا «لا شاشةَ قبولٍ ولا بابَ ما يلزمني قبولُه»** — وبُنيت بوّابةُ التسجيل
يومَ اعتُمدت النصوص (٢٠٢٦-٠٩-٠٥)، **وبقي `min_accepted_version` يُكتب ولا يقرؤه
أحد**: فمن وافق على نسخةٍ قديمةٍ لم يُسأل عن الجديدة. **و`pending_for` قارئُه**:
وثيقةٌ منشورةٌ واجبةٌ لم يقبل المستخدمُ منها نسخةً ≥ `min_accepted_version` —
**ومن لم يقبل منها شيئاً قطُّ** (سجّل قبل النشر أو أُنشئ بسكربت) **لم يوافق**،
فهو منهم. **و`changed_lines` تقول ما تغيّر** من نصِّ ما قبله إلى نصِّ المنشورة —
**من النصّين لا من حقلٍ يُكتب بيد**، فلا يَعِد الملخّصُ بغير ما في النصّ.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, InvalidInput, NotFound
from app.models.enums import CountryCode, PolicyApp, PolicyDocType, UserRole
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
    body_fr: str | None = None,
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
        body_fr=(body_fr or None),
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
    session: AsyncSession, policy: PrivacyPolicy, *, actor: User | None
) -> PrivacyPolicy | None:
    """ينشر نسخةً — **وينزع سابقَها في المعاملة نفسِها**.

    **ويعيد النسخةَ التي نُزعت** ليُكتب في التدقيق ما حلَّ محلَّ ماذا: «نُشرت
    الرابعة» وحدَها لا تقول أنّ الثالثة أُطفئت.

    **والنزعُ قبل الرفع لا بعده**: الفهرسُ الجزئيُّ يرفض منشورتين في الثلاثيّة،
    **وترتيبٌ معكوسٌ يسقط برسالة قاعدةٍ لا تقول ما العمل**.
    """
    if policy.is_published:
        raise Conflict("هذه النسخة منشورةٌ أصلاً.")
    await _keep_trip_comms_line(session, policy, body_after=policy.body_ar)

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
    # **وفاعلٌ فارغٌ لسكربت المالك وحدَه** (SPEC §٧٤-ل/١): نشرٌ قرّره في المحادثة لا مشرفٌ في اللوحة — **وقيدٌ يسمّي من لم يفعل
    # أسوأُ من قيدٍ لا يسمّي أحداً**؛ والتدقيقُ يكتب الأمر
    policy.published_by = actor.id if actor is not None else None
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
    await _keep_trip_comms_line(session, policy, body_after=None)
    policy.is_published = False
    await session.flush()


async def _keep_trip_comms_line(
    session: AsyncSession, policy: PrivacyPolicy, *, body_after: str | None
) -> None:
    """**سطرُ المحادثة والمكالمة لا يُنزع وما يحفظه مشتعل** (SPEC §٦٦-ب/١١، §٦٦-ج/١٦).

    **وهنا لا في الراوتر**: النشرُ والسحبُ يمرّان بهذه الخدمة وحدَها، **فكلُّ بابٍ يُبنى غداً
    يرثه**. وشرطُ الإشعال (`trip_chat.require_published_line`) يُسأل مرّةً لحظةَ الإشعال —
    **وبلا هذا الوجه يُبطله نشرُ نسخةٍ بلا السطر أو سحبُ المنشورة بعده** (قِيس ٢٠٢٦-١٠-٠٨).
    """
    if policy.doc_type != PolicyDocType.PRIVACY_POLICY:
        return
    from app.services import trip_chat

    await trip_chat.require_line_kept(
        session,
        country=policy.country_code,
        app=policy.app,
        body_after=body_after,
        withdrawing=body_after is None,
    )


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


async def required_for(
    session: AsyncSession, *, country: CountryCode, app: PolicyApp
) -> list[PrivacyPolicy]:
    """**ما يلزم قبولُه الآن** لهذا التطبيق في هذا السوق.

    **والصفُّ الواجبُ = أحدثُ منشورٍ لكلِّ (نوع + تطبيق + سوق)** بنصِّ المالك
    (§34-٣)، **ويحرسه الفهرسُ الجزئيُّ نفسُه**: منشورةٌ واحدةٌ لا أكثر.
    **فلا يُحسب `MAX(version)` ولا يُفترض أن أحدثَ رقمٍ هو المنشور** —
    ونسخةٌ أحدثُ مسوّدةٌ لا تُطلب موافقتُها.

    **وقائمةٌ فارغةٌ حالٌ صحيحة**: سوقٌ لم تُنشر فيه وثيقةٌ بعد **لا يُسأل
    مستخدموه عن شيء** — وهو ما كان قائماً حتى ٢٠٢٦-٠٩-٠٥.
    """
    rows = []
    for doc_type in PolicyDocType:
        doc = await published(session, country=country, doc_type=doc_type, app=app)
        if doc is not None:
            rows.append(doc)
    return rows


async def record_consent(
    session: AsyncSession, *, user: User, policies: Sequence[PrivacyPolicy]
) -> int:
    """يكتب موافقةَ المستخدم على النسخ المعطاة — **ولا يكرّرها**.

    **والتكرارُ يمنعه القيدُ في القاعدة** (`user_policy_consent_once`)،
    **ويُسأل هنا قبله** فلا تُرمى `IntegrityError` في وجه مستخدمٍ يعيد المحاولة.

    **ولا يُحدَّث صفٌّ قائم**: «وافق يومَ كذا» خبرٌ، **وتحديثُ تاريخِه يمحو
    متى وافق فعلاً** — وهو من عائلة «الدفترُ لا يُعدَّل».
    """
    if not policies:
        return 0
    # **`ON CONFLICT DO NOTHING` لا «اسأل ثمّ اكتب»** (§٧٦-ع/٧): ضغطتان على «أوافق» معاً كانتا تقرآن «لم يوافق» كلتاهما
    # **فتسقط الثانيةُ بـ`IntegrityError`** في وجه من وافق — والقيدُ نفسُه هو الحكم، فيُسأل في الكتابة لا قبلها
    rows = await session.scalars(
        insert(UserPolicyConsent)
        .values([{"user_id": user.id, "policy_id": policy.id} for policy in policies])
        .on_conflict_do_nothing(constraint="user_policy_consent_once")
        .returning(UserPolicyConsent.id)
    )
    return len(rows.all())


# ═══════════════ إعادةُ القبول (§٧٦-ع/٧ البند ٣) ═══════════════

#: **الأرقامُ وحدَها** — سطرٌ لم يتغيّر منه إلا تاريخُه («آخر تحديث: …») ليس تغييراً في المضمون
_DIGITS = re.compile(r"[0-9٠-٩]+")


def _plain(line: str) -> str:
    return " ".join(line.split())


def changed_lines(before: str | None, after: str | None) -> list[str] | None:
    """**أسطرُ النصّ الجديد التي ليست في القديم** — بترتيبها في الجديد.

    **`None` حين لا قديمَ يُقارن** (لم يقبل شيئاً، أو لا نصَّ بهذه اللغة في إحدى النسختين) — لا قائمةٌ فارغة: الفارغةُ تقول «لم
    يتغيّر شيء» وهي دعوى. **وسطرٌ لم يتغيّر منه إلا أرقامُه يُترك** — تاريخُ التحديث يتغيّر في كلِّ نسخة، وعرضُه «تغييراً» يُغرق
    التغييرَ الحقَّ تحته. **ولا حكمَ على المعنى**: سطرٌ أُعيدت صياغتُه يظهر بصيغته الجديدة، وهو ما وافق عليه.
    """
    if not before or not after:
        return None
    old = {_plain(line) for line in before.splitlines() if line.strip()}
    old_undated = {_DIGITS.sub("", line) for line in old}
    out: list[str] = []
    for line in after.splitlines():
        text = _plain(line)
        if not text or text in old or _DIGITS.sub("", text) in old_undated:
            continue
        out.append(text)
    return out


@dataclass(frozen=True)
class Pending:
    """**وثيقةٌ منشورةٌ تنتظر قبولَه** — ومعها **آخرُ نسخةٍ قبلها منها** (`None` لمن لم يقبل منها شيئاً)."""

    policy: PrivacyPolicy
    accepted: PrivacyPolicy | None


async def _last_accepted(session: AsyncSession, *, user: User, doc: PrivacyPolicy) -> PrivacyPolicy | None:
    return await session.scalar(
        select(PrivacyPolicy)
        .join(UserPolicyConsent, UserPolicyConsent.policy_id == PrivacyPolicy.id)
        .where(
            UserPolicyConsent.user_id == user.id,
            PrivacyPolicy.country_code == doc.country_code,
            PrivacyPolicy.doc_type == doc.doc_type,
            PrivacyPolicy.app == doc.app,
        )
        .order_by(PrivacyPolicy.version.desc())
        .limit(1)
    )


async def pending_for(session: AsyncSession, *, user: User, app: PolicyApp) -> list[Pending]:
    """**ما يلزم هذا المستخدمَ قبولُه الآن** في هذا التطبيق — **قارئُ `min_accepted_version`**.

    **والسوقُ سوقُ حسابه** (`users.country_code`): النصُّ الذي يحكمه هو نصُّ سوقه. **وتطبيقُ الكبتن لمن له دورُ الكبتن**: راكبٌ
    يفتح تطبيقَ الكبتن لا يُسأل عن نصٍّ لا يعمل به. **ومن قبل نسخةً ≥ `min_accepted_version` برئ** — تصحيحُ فاصلةٍ بعد إعادة
    قبولٍ لا يسأله ثانيةً، لأن الناشرَ لم يطلب ذلك (`_stamp_min_accepted`).
    """
    if app == PolicyApp.DRIVER and not user.has_role(UserRole.DRIVER):
        return []
    out: list[Pending] = []
    for doc in await required_for(session, country=user.country_code, app=app):
        accepted = await _last_accepted(session, user=user, doc=doc)
        if accepted is not None and accepted.version >= doc.min_accepted_version:
            continue
        out.append(Pending(policy=doc, accepted=accepted))
    return out


async def accept_pending(
    session: AsyncSession, *, user: User, app: PolicyApp, policy_ids: Sequence[uuid.UUID]
) -> list[Pending]:
    """**«أوافق»** — يكتب قبولَ ما ينتظر **بتاريخه ونسخته** (`accepted_at` و`policy_id` ← النسخة)، ويعيد ما بقي.

    **ولا يُقبل إلا المنشورُ الآن**: معرّفٌ لنسخةٍ غيرِ منشورةٍ (نُشرت أحدثُ منها بين فتح الشاشة والضغط) **يُردّ ولا يُكتب** —
    فلا يُسجَّل قبولُ نصٍّ لم يعد قائماً، والشاشةُ تعيد السؤال. **ولا قبولَ جزئيّ**: الزرُّ واحدٌ للوثيقتين، فناقصٌ يُسمّى ويُردّ
    كما في التسجيل. **ومعرّفٌ قُبل من قبل يمرّ** — ضغطةٌ ثانيةٌ ليست خطأ.
    """
    current = {doc.id for doc in await required_for(session, country=user.country_code, app=app)}
    given = set(policy_ids)
    if given - current:
        raise InvalidInput("هذه النسخةُ لم تعد المنشورة — أُعيد فتحُ الشاشة بالنصّ الحاليّ.")
    pending = await pending_for(session, user=user, app=app)
    missing = [item.policy for item in pending if item.policy.id not in given]
    if missing:
        raise InvalidInput(f"لا يتمّ القبولُ بلا: {'، '.join(_title(doc) for doc in missing)}.")
    await record_consent(session, user=user, policies=[item.policy for item in pending])
    return await pending_for(session, user=user, app=app)


def _title(doc: PrivacyPolicy) -> str:
    return "سياسة الخصوصية" if doc.doc_type == PolicyDocType.PRIVACY_POLICY else "شروط الاستخدام"

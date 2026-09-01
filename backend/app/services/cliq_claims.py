"""«حوّلتُ» — **فعلٌ يُختم، لا يُشتقّ من فتح شاشة** (قرارُ المالك 2026-09-01).

## العلّةُ مقيسةٌ لا مفترَضة

**قائمةُ المشرف كانت تعرض كلَّ صفٍّ `created`** — أي **كلَّ من فتح الشاشة**.
ومن فتح ونسي لا ينتظر شيئاً، **ومن حوّل ينتظر تأكيداً لمالٍ خرج من حسابه**.
**فخلطُهما يجعل قائمةَ الانتظار طويلةً بمن لا ينتظر**، ويضيع فيها من ينتظر.

## وبابٌ واحدٌ للأغراض كلِّها

المطالبةُ اليدويّةُ اليومَ غرضان — **اشتراكٌ ودَين** — وقد يصير ثالثاً.
**وبابٌ لكلِّ غرضٍ يعني ثلاثةَ أبوابٍ تفترق أوّلَ تعديل**، وهو «موضعان
يحسبان شيئاً واحداً» بعينه. فالبابُ واحدٌ ومفتاحُه `cart_id`.

## والضغطةُ الثانيةُ لا تُنشئ شيئاً ولا تصيح

**ولا تصيح** بقصد: من ضغط ثانيةً لم يخطئ — **الشبكةُ بطيئةٌ أو الشاشةُ لم
تتحدّث**. فيُعاد الصفُّ نفسُه ويُقرأ منه أنه مسجَّل. **وخطأٌ هنا يعلّم صاحبَه
أنه أفسد شيئاً وهو لم يفعل.**
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import InvalidInput, NotFound
from app.models.enums import (
    CountryCode,
    ProviderOrderSource,
    ProviderOrderStatus,
)
from app.models.provider_order import ProviderOrder
from app.models.user import User


def _now() -> datetime:
    return datetime.now(UTC)


async def _locked_by_cart(
    session: AsyncSession, cart_id: str
) -> ProviderOrder:
    """الصفُّ **مقفولاً** قبل فحص حاله — كبقيّة انتقالات الحال في المشروع.

    **وبلا القفل تمرّ ضغطتان متزامنتان**: كلتاهما تقرأ `declared_paid_at`
    فارغاً، وكلتاهما تختم — **وهو ختمان لتحويلٍ واحد**، وأحدُهما يكتب وقتاً
    غيرَ الآخر فيرتّب المشرفُ قائمتَه بوقتٍ لم يقع.
    """
    order = await session.scalar(
        select(ProviderOrder)
        .where(ProviderOrder.cart_id == cart_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if order is None:
        raise NotFound("المطالبة غير موجودة")
    return order


async def declare_paid(
    session: AsyncSession, *, cart_id: str, user: User
) -> ProviderOrder:
    """يختم «حوّلتُ» على مطالبةٍ يدويّة — **مرّةً واحدةً ولو ضُغط مراراً**.

    **والملكيةُ تُفحص**: مرجعٌ يُخمَّن لا يفتح مطالبةَ غيره — وهو IDOR بعينه،
    والقاعدةُ مكتوبةٌ في المواصفة لكلِّ ما يمسّ رحلةً أو محفظة.

    **واليدويّةُ وحدَها**: القناةُ الآليّةُ يشهد عليها القابض، **وزرُّ «حوّلتُ»
    فيها يجعل قولَ صاحبِ المال شاهداً حيث يوجد شاهدٌ أفضلُ منه**.
    """
    order = await _locked_by_cart(session, cart_id)
    if order.user_id != user.id:
        # **٤٠٤ لا ٤٠٣**: وجودُ المطالبة نفسُه ليس معلومةً يستحقّها غيرُ صاحبها
        raise NotFound("المطالبة غير موجودة")
    if order.source is not ProviderOrderSource.MANUAL:
        raise InvalidInput("هذه القناة تُؤكَّد آلياً — لا يُعلَن الدفعُ فيها")
    if order.status is not ProviderOrderStatus.CREATED:
        raise InvalidInput("هذه المطالبة حُسمت — لا يُعلَن دفعُها الآن")

    # **الختمُ مرّةً**: الضغطةُ الثانيةُ تجد الحقلَ مختوماً فتُعيد الصفَّ كما هو
    if order.declared_paid_at is None:
        order.declared_paid_at = _now()
    return order


async def declared_pending(
    session: AsyncSession, *, country: CountryCode | None = None
) -> list[ProviderOrder]:
    """**من قال «حوّلتُ» وينتظر** — مرتَّبين بوقت الضغط، والأقدمُ أوّلاً.

    **والأقدمُ أوّلاً لأنه أطولُ انتظاراً** — وقائمةٌ ترتّب بالأحدث تدفن من
    ينتظر منذ الصباح تحت من ضغط قبل دقيقة.

    **ويُحمَّل صاحبُها معها** (`selectinload`): الصفحةُ تعرض اسمَه، **وقراءةٌ
    كسولةٌ لكلِّ صفٍّ تعني استعلاماً لكلِّ سطرٍ في القائمة**.
    """
    query = (
        select(ProviderOrder)
        .where(
            ProviderOrder.source == ProviderOrderSource.MANUAL,
            ProviderOrder.status == ProviderOrderStatus.CREATED,
            ProviderOrder.declared_paid_at.is_not(None),
        )
        .options(selectinload(ProviderOrder.user))
        .order_by(ProviderOrder.declared_paid_at)
    )
    if country is not None:
        query = query.where(ProviderOrder.country_code == country)
    return list(await session.scalars(query))


async def claim_row(session: AsyncSession, order: ProviderOrder) -> dict:
    """**بانٍ واحدٌ لِما تراه اللوحة** — يخدم القوائمَ والتأكيدَ والرفض.

    **وهو الشكلُ الثامن مقروءاً قبل وقوعه**: أربعةُ أبوابٍ تنشر المطالبةَ
    نفسَها، **وبانٍ لكلِّ بابٍ يملأ حقلاً وينسى آخر** — وقد وقع في هذا
    المشروع مرّتين (`qr_url` في مطالبة الاشتراك، و`commission_percent` في
    بابَي الكبتن واللوحة).

    ## ولمَ يجلب الدافعَ بنفسه ولا يقرأ `order.user`

    **قراءةُ العلاقة تُحمَّل كسولاً** — وبعد `flush` أو `commit` تقع **خارج
    السياق** فتُلقي `MissingGreenlet`. **وقِيس مرّتين في يومٍ واحد**
    (2026-09-01): مرّةً بعد الإيداع، ثم **مرّةً بعد نقل البناء قبله** — لأن
    `activate_paid_order` يُفرغ ما بينهما.

    **فلا يُترك الأمرُ لترتيب المستدعي**: `session.get` يُصيب خريطةَ الهويّة
    فلا يكلّف استعلاماً حين يكون محمَّلاً، **ويجلبه حين لا يكون**. **وحارسٌ
    يعتمد على أن يتذكّر كلُّ مستدعٍ ترتيبَه حارسٌ سقط.**
    """
    payer = await session.get(User, order.user_id)
    return {
        "id": order.id,
        "cart_id": order.cart_id,
        "user_id": order.user_id,
        "amount": order.amount,
        "currency": order.currency,
        "status": order.status,
        "source": order.source,
        "purpose": order.purpose,
        "failure_reason": order.failure_reason,
        "created_at": order.created_at,
        "payer_name": payer.name if payer is not None else None,
        "payer_phone": payer.phone if payer is not None else None,
        "declared_paid_at": order.declared_paid_at,
    }


async def reject(
    session: AsyncSession, *, order_id, reason: str
) -> ProviderOrder:
    """**رفضٌ بسببٍ مكتوبٍ يُعرض على صاحبه** (قرارُ المالك 2026-09-01).

    **ولا رفضَ صامت**: من حوّل مالاً ورُفض طلبُه **يستحق أن يعرف لماذا** —
    و«مرفوض» وحدَها تُنتج مكالمةَ دعمٍ لا جواباً. **والسببُ يسكن
    `failure_reason`** وهو الحقلُ الذي يعرضه التطبيقُ أصلاً، فلا حقلَ ثانٍ
    يُخترع لمعنىً قائم.
    """
    text = (reason or "").strip()
    if len(text) < 8:
        raise InvalidInput("سببُ الرفض مطلوب — اكتبه (8 أحرف على الأقل)")

    order = await session.scalar(
        select(ProviderOrder)
        .where(ProviderOrder.id == order_id)
        # **وصاحبُها يُحمَّل معها**: الجوابُ يحمل اسمَه ورقمَه، **وقراءةٌ
        # كسولةٌ بعد الإيداع تقع خارج السياق** — `MissingGreenlet` بعينه،
        # وهو فخُّ هذا المشروع المعروف. (قِيس هنا 2026-09-01.)
        .options(selectinload(ProviderOrder.user))
        .with_for_update(of=ProviderOrder)
        .execution_options(populate_existing=True)
    )
    if order is None:
        raise NotFound("المطالبة غير موجودة")
    if order.status is not ProviderOrderStatus.CREATED:
        raise InvalidInput("هذه المطالبة حُسمت أصلاً")

    order.status = ProviderOrderStatus.FAILED
    order.failure_reason = text
    return order


async def admins_of(session: AsyncSession, country: CountryCode) -> list[User]:
    """مشرفو هذا السوق — **ومن لا سوقَ له يُشمَل**.

    **والحظرُ يُستثنى**: حسابٌ محظورٌ لا يُوقَظ لعمل.
    """
    from app.models.enums import UserRole
    from app.models.user_role_grant import has_role_clause

    rows = await session.scalars(
        select(User).where(
            has_role_clause(UserRole.ADMIN),
            User.is_blocked.is_(False),
        )
    )
    return [row for row in rows if row.country_code == country]


def declared_notice(order: ProviderOrder) -> dict[str, str]:
    """حمولةُ إشعار «حوّل أحدُهم» — **قيمٌ خامٌ في `data`**.

    **والجملةُ في `body` وحدَها**: القاعدةُ المسجَّلة أن `title`/`body` للنظام
    حين يكون التطبيقُ مغلقاً، **وما ترسمه الشاشةُ بنفسها يُؤلَّف من `data`**.
    """
    return {
        "type": "cliq_claim_declared",
        "cart_id": order.cart_id,
        "amount": str(order.amount),
        "currency": order.currency.value,
        "purpose": order.purpose.value,
    }

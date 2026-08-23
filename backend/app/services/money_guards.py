"""حارسا المال: تجميدُ التسعير وإيقافُ الصرف (قرارُ المالك 2026-08-23).

**بيتٌ واحدٌ للاثنين** لأن سؤالَهما واحد: «أثمّة مفتاحٌ يوقف الأذى الذي تصنعه
هذه الشاشة؟» — ومن اثنتين وعشرين شاشةً في اللوحة **ثمانٍ تكتب مالاً** ولم
تكن **إلا شاشتان تقرآن مفتاحاً**. وهذان أشدُّها: الأولُ يُعيد تسعيرَ السوق
فوراً، والثاني يُخرج المالَ إلى طرفٍ ثالثٍ فلا يعود.

**والرفضُ يكتب قيدَه ثم يُلقي** — و«من حاول التسعيرَ وهو مجمَّد» سؤالٌ يُسأل،
**ورفضٌ صامتٌ يُخفي جوابَه**. ولأن القيدَ في معاملة الرفض نفسِها فإنه يُودَع
هنا صراحةً قبل الإلقاء، وإلا تراجع معه. **وهذا سليمٌ لأن الحارسَ يقع عند باب
المسار قبل أيِّ كتابةٍ أخرى** — فلا كتابةَ معلَّقةٌ يُودِعها معه.

`design/KILL-SWITCHES.md` يحمل التصميم، و`SPEC.md` §28.16 بقيّةَ الشاشات.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import FeatureDisabled
from app.models.audit import AuditAction
from app.models.enums import CountryCode, FeatureKey
from app.models.user import User
from app.services import audit, settings_service


class PricingFrozen(FeatureDisabled):
    """التسعيرُ مجمَّد — **الكتابةُ وحدَها**، والرحلاتُ تُسعَّر بالصفوف القائمة."""

    code = "pricing_writes_disabled"
    message = "التسعيرُ مجمَّدٌ الآن — لا يمكن تعديلُ الصفوف حتى يُرفع التجميد"


class WithdrawalPayoutStopped(FeatureDisabled):
    """الصرفُ موقوف — **المغادرةُ وحدَها**، والطلباتُ تُقبل وتُعتمد."""

    code = "withdrawal_payout_disabled"
    message = "صرفُ السحوبات موقوفٌ الآن — الطلبُ يبقى معتمَداً حتى يُستأنف"


async def _refuse(
    session: AsyncSession,
    *,
    actor: User | None,
    key: FeatureKey,
    country_code: CountryCode,
    entity_type: str,
    entity_id: uuid.UUID | None,
) -> None:
    """يكتب قيدَ المحاولة المرفوضة ويودعه — **قبل** أن يُلقي المُنادي."""
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type=entity_type,
        entity_id=entity_id,
        details={"refused_by_flag": key.value, "country_code": country_code.value},
    )
    await session.commit()


async def require_pricing_writes(
    session: AsyncSession,
    *,
    actor: User | None,
    country_code: CountryCode,
    entity_id: uuid.UUID | None = None,
) -> None:
    """يمنع الكتابةَ على `pricing` وحدَها. **لا يمسّ تسعيرَ رحلةٍ البتّة.**"""
    key = FeatureKey.PRICING_WRITES_ENABLED
    if await settings_service.is_feature_enabled(session, country_code, key):
        return
    await _refuse(
        session,
        actor=actor,
        key=key,
        country_code=country_code,
        entity_type="pricing_rule",
        entity_id=entity_id,
    )
    raise PricingFrozen()


async def require_withdrawal_payout(
    session: AsyncSession,
    *,
    actor: User | None,
    country_code: CountryCode,
    withdrawal_id: uuid.UUID,
) -> None:
    """يمنع **مغادرةَ المال** وحدَها — والطلبُ يبقى في طابوره `approved`.

    **ويُنادى عند باب المسار لا في وسطه**: `withdrawals.pay_via_provider` هو
    الاستثناءُ الوحيدُ المصرَّحُ به من «لا تُمسك قفلَ صفٍّ عبرَ نداءِ مزوّد»،
    لأن النداءَ **هو** حركةُ المال. فنداءٌ غادر يُكمَل ولا يُقطع: قطعُه يترك
    مالاً تحرّك عند طرفٍ ثالثٍ وصفّاً يقول إنه لم يتحرّك — **وهو أسوأُ من
    الصرف الخاطئ نفسِه**، لأن الخاطئ معروفٌ ومقيس.
    """
    key = FeatureKey.WITHDRAWAL_PAYOUT_ENABLED
    if await settings_service.is_feature_enabled(session, country_code, key):
        return
    await _refuse(
        session,
        actor=actor,
        key=key,
        country_code=country_code,
        entity_type="withdrawal_request",
        entity_id=withdrawal_id,
    )
    raise WithdrawalPayoutStopped()

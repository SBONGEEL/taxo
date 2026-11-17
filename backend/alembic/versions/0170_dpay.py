"""dpay: بوّابةُ الدفع الليبيّة Dpay — **مطفأةً ومخفيّة** (أمرُ المالك ٢٠٢٦-١١-١٧: «All Dpay switches stay OFF»)

Revision ID: 0170
Revises: 0169
Create Date: 2026-11-17

**ما تضيفه — ولا جدولَ مالٍ بينها** (نمطُ `0160` و`0166` حرفاً):
- قيمةٌ في نوع العقد (`provider_key`: `dpay`) — **تُختم قبل أيِّ استعمال**.
- **صفوفُ طرقٍ** في `payment_providers` (جدولُ إعداد الطرق، لا رصيدَ فيه ولا قيد) — **صفٌّ لكلِّ وسيلةٍ من وسائل Dpay**، فلكلٍّ مفتاحُه
  (`enabled`) وترتيبُه واسمُه العربيُّ وتعليماتُه في اللوحة:
  - **ليبيا** (شحنٌ واشتراك): البطاقةُ المحلّيّة (معاملات) «الدفع بالبطاقة (Dpay)» · سداد · إدفع لي · موبي كاش · مصرفي · يُسر · الصحارى ·
    والبطاقةُ الدوليّة (MPGS) **موقوفةً** حتى يُهيّئها Dpay للحساب.
  - **الأردن** (الاشتراكُ وحدَه): البطاقةُ الدوليّة عبر MPGS «الدفع بالبطاقة» — **حدُّها الأعلى 100 دينار** كأخواتها (حارسٌ لا سعر).
  **والحدُّ الأدنى 5** في ليبيا = أدنى ما تقبله وسائلُ Dpay (`min_deposit`) — حارسٌ لا سعر، يُعدَّل من اللوحة.
- **مفاتيحُ مطفأة** في `feature_flags`: ليبيا `dpay_topup_enabled` و`dpay_trip_enabled` و`dpay_subscription_enabled`، والأردن
  `dpay_subscription_enabled` — **يُشعلها المالكُ وحدَه** بعد الرخصة وقبولِ Dpay ومفاتيحِه الحيّة (وللأردن: تأكيدُ Dpay كتابةً ودفعةٌ حقيقيّة).

**فلا يظهر لأحدٍ شيء** حتى يُدخل المالكُ العقدَ في «العقود» ← «Dpay» ويشعل المفتاح. ولا مفتاحَ ولا سرَّ يُكتب هنا.
**والرسمُ على الدافع بنيةً** (`fee_bearer = user`): صفحةُ Dpay تضيف رسمَ الوسيلة فوق المبلغ وتعرضه قبل الدفع.

**والنزولُ لا يحذف صفّاً** (لا حذفَ على الإنتاج): يُطفئ الطرقَ والمفاتيح، وقيمةُ التعداد تبقى.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision = "0170"
down_revision = "0169"
branch_labels = None
depends_on = None

#: (الدولة، الكود، الاسم، التعليمات، مفعَّل، شحن، اشتراك، الترتيب، الأدنى، الأعلى)
METHODS: tuple[tuple[str, str, str, str, bool, bool, bool, int, str | None, str | None], ...] = (
    ("LY", "dpay_moamalat", "الدفع بالبطاقة (Dpay)",
     "ادفع ببطاقتك المصرفيّة الليبيّة (معاملات) في صفحة Dpay الآمنة — لا تُدخل بياناتِ بطاقتك إلا فيها. يظهر لك الرسمُ والإجماليُّ قبل الدفع.",
     True, True, True, 20, "5.000", None),
    ("LY", "dpay_sadad", "سداد (Dpay)",
     "ادفع من محفظة سداد في صفحة Dpay الآمنة برقم هاتفك ورمز التحقّق. يظهر لك الرسمُ والإجماليُّ قبل الدفع.",
     True, True, True, 21, "5.000", None),
    ("LY", "dpay_edfali", "إدفع لي (Dpay)",
     "ادفع من محفظة إدفع لي في صفحة Dpay الآمنة برقم هاتفك ورمز التحقّق. يظهر لك الرسمُ والإجماليُّ قبل الدفع.",
     True, True, True, 22, "5.000", None),
    ("LY", "dpay_mobicash", "موبي كاش (Dpay)",
     "ادفع من محفظة موبي كاش في صفحة Dpay الآمنة برقم هاتفك ورمز التحقّق. يظهر لك الرسمُ والإجماليُّ قبل الدفع.",
     True, True, True, 23, "5.000", None),
    ("LY", "dpay_masrefypay", "مصرفي (Dpay)",
     "ادفع من محفظة مصرفي في صفحة Dpay الآمنة برقم هاتفك ورمز التحقّق. يظهر لك الرسمُ والإجماليُّ قبل الدفع.",
     True, True, True, 24, "5.000", None),
    ("LY", "dpay_yousrpay", "يُسر (Dpay)",
     "ادفع من محفظة يُسر في صفحة Dpay الآمنة برقم هاتفك ورمز التحقّق. يظهر لك الرسمُ والإجماليُّ قبل الدفع.",
     True, True, True, 25, "5.000", None),
    ("LY", "dpay_saharapay", "الصحارى (Dpay)",
     "ادفع من محفظة الصحارى في صفحة Dpay الآمنة برقم هاتفك ورمز التحقّق. يظهر لك الرسمُ والإجماليُّ قبل الدفع.",
     True, True, True, 26, "5.000", None),
    ("LY", "dpay_mpgs", "البطاقة الدوليّة Visa / Mastercard (Dpay)",
     "ادفع ببطاقةٍ دوليّة في صفحة Dpay الآمنة — يُخصم بالدولار بسعر المصرف.",
     False, True, True, 27, "5.000", None),
    ("JO", "dpay_mpgs_jo", "الدفع بالبطاقة",
     "ادفع اشتراكَك ببطاقتك (Visa / Mastercard) في صفحة Dpay الآمنة. السعرُ بالدينار الأردنيّ، ويُخصم من بطاقتك بالدولار بسعر المصرف — "
     "المعروضُ بالدولار تقريبيّ.",
     True, False, True, 20, None, "100.000"),
)
FLAGS: tuple[tuple[str, str], ...] = (
    ("LY", "dpay_topup_enabled"),
    ("LY", "dpay_trip_enabled"),
    ("LY", "dpay_subscription_enabled"),
    ("JO", "dpay_subscription_enabled"),
)


def upgrade() -> None:
    op.execute("ALTER TYPE provider_key ADD VALUE IF NOT EXISTS 'dpay'")
    op.execute("COMMIT")
    bind = op.get_bind()
    for country, code, name, instructions, enabled, topup, subscription, order, low, high in METHODS:
        bind.execute(
            sa.text(
                "INSERT INTO payment_providers (id, country_code, kind, code, name, instructions, integration, enabled, for_topup,"
                " for_subscription, fee_bearer, sort_order, min_amount, max_amount)"
                " VALUES (:id, CAST(:country AS country_code), 'bank_transfer', :code, :name, :instructions, 'dpay', :enabled, :topup,"
                " :subscription, 'user', :order, CAST(:low AS NUMERIC(12,3)), CAST(:high AS NUMERIC(12,3)))"
                " ON CONFLICT (country_code, code) DO NOTHING"
            ),
            {
                "id": uuid.uuid4(), "country": country, "code": code, "name": name, "instructions": instructions,
                "enabled": enabled, "topup": topup, "subscription": subscription, "order": order, "low": low, "high": high,
            },
        )
    for country, flag in FLAGS:
        bind.execute(
            sa.text(
                "INSERT INTO feature_flags (id, country_code, feature_key, enabled)"
                " VALUES (:id, CAST(:country AS country_code), :flag, false) ON CONFLICT (country_code, feature_key) DO NOTHING"
            ),
            {"id": uuid.uuid4(), "country": country, "flag": flag},
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE payment_providers SET enabled = false WHERE integration = 'dpay'"))
    bind.execute(
        sa.text("UPDATE feature_flags SET enabled = false WHERE feature_key IN ('dpay_topup_enabled', 'dpay_trip_enabled',"
                " 'dpay_subscription_enabled')")
    )

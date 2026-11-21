"""**سياراتُ TAXO في الرئيسيّة** (أمرُ المالك ٢٠٢٦-١١-٢١، SPEC §١١١): مفتاحُ `home_cars` **مشتعلاً في الدول الثلاث** بقرار المالك.

* «السكوتُ إطفاء» (§٤) — والمالكُ قال «الافتراضُ بعد الرفع: مشتعلٌ في كلِّ الدول»، **فالإشعالُ صفٌّ صريحٌ يولد مع الرفع** لا قائمةُ
  `DEFAULT_ENABLED_FLAGS` (تلك للحرّاس وحدَها). **و`ON CONFLICT DO NOTHING`**: دولةٌ كتب لها المشرفُ صفّاً قبلها يبقى صفُّه كما هو.
* **عرضٌ وحدَه** — لا يمسّ أجرةً ولا اشتراكاً ولا عمولةً ولا جدولَ مال، ولا اسمَ فئة.

**والرجوعُ** يرفع صفوفَ المفتاح وحدَها: الشيفرةُ القديمةُ لا تعرفه، وغيابُه إطفاءٌ — الرئيسيّتان كما كانتا قبل الترحيلة حرفاً.

Revision ID: 0184
Revises: 0183
"""
from __future__ import annotations

from alembic import op

revision = "0184"
down_revision = "0183"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO feature_flags (id, country_code, feature_key, enabled, created_at, updated_at)
        SELECT gen_random_uuid(), c.code::country_code, 'home_cars', true, now(), now()
        FROM (VALUES ('LY'), ('JO'), ('DZ')) AS c(code)
        ON CONFLICT (country_code, feature_key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM feature_flags WHERE feature_key = 'home_cars'")

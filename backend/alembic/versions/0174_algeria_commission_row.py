"""صفُّ عمولة الجزائر **كما يسري اليوم** — مطفأةٌ بنسبة 0 (أمرُ المالك ٢٠٢٦-١١-١٨ الثاني، «عمولةُ الجزائر»).

**العلّة**: البذرُ كتب صفوفَ العمولة يومَ ٢٠٢٦-٠٨-٢٠ للأردن وليبيا، والجزائرُ أُضيفت إلى `CountryCode` في `0111` (`906e4f73`،
٢٠٢٦-١٠-١١) بلا صفّ — **فشاشةُ الإعدادات لم ترسم عمولتَها قطّ**، والخادمُ يعمل بالافتراض: صفر. **وقِيس على الإنتاج قراءةً** قبل هذه
الترحيلة: ١٠ رحلاتٍ جزائريّةٍ مكتملة، **كلُّها بنسبة 0، ولا قيدَ عمولةٍ ولا دَينَ عمولةٍ في الجزائر**.

**فالصفُّ لا يغيّر شيئاً على أحد**: مطفأٌ و0 كما يُقرأ غيابُه حرفاً (`tests/test_country_settings.py` يقيس ذلك). **والقيمةُ يضبطها المالك.**
**ولا يمسّ صفّاً قائماً** (`ON CONFLICT DO NOTHING`)، **ولا جدولَ مالٍ** (`commission_settings` إعدادٌ؛ والدفترُ والرحلاتُ لا تُلمس).

**والرجوعُ** يحذف الصفَّ **إن بقي كما كُتب** (مطفأً و0 ولم يُحدَّث) — وما ضبطه المالكُ بعدها لا يُحذف.

Revision ID: 0174
Revises: 0173
"""

from __future__ import annotations

from alembic import op

revision = "0174"
down_revision = "0173"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "INSERT INTO commission_settings (id, country_code, commission_enabled, commission_percent, applies_to) "
        "VALUES (gen_random_uuid(), 'DZ', false, 0.00, 'all_rides') ON CONFLICT (country_code) DO NOTHING"
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM commission_settings WHERE country_code = 'DZ' AND commission_enabled = false "
        "AND commission_percent = 0 AND updated_at = created_at"
    )

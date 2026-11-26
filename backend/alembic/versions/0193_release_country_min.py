"""حدُّ الإصدار لكلِّ دولة، و«في كلِّ فتح» للتنبيه الاختياريّ (SPEC §43، أمرُ المالك ٢٠٢٦-١١-٢٦ — تنبيهُ التحديث لما دون 1573).

- `app_releases.country_min_builds`: `{"JO": 1573}` — **حدٌّ أدنى لدولةٍ بعينها يحلّ محلَّ `min_supported_build` فيها وحدَها**،
  فيُجعل التحديثُ إلزاميّاً في سوقٍ ويبقى اختياريّاً في غيره. **والفارغُ (الافتراض) = الحدُّ العامُّ في كلِّ الدول** كما كان.
- `reminder_hours` يقبل **0** = «في كلِّ فتح»: «لاحقاً» يكتم التنبيهَ في الفتح نفسِه، ويعود في الإقلاع التالي (مسلكُ غلاف 772 بعينه).

**ولا جدولَ مالٍ هنا**: سجلُّ إصداراتٍ يصف حزماً.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0193"
down_revision = "0192"
branch_labels = None
depends_on = None


def _recheck(low: int) -> str:
    """**القيدُ بالاسم الذي في القاعدة لا بالمكتوب هنا**: يُقرأ من `pg_constraint` بتعريفه، فلا يفترق الاسمُ عن اصطلاح التسمية."""
    return (
        "DO $$ DECLARE c text; BEGIN "
        "SELECT conname INTO c FROM pg_constraint WHERE conrelid = 'app_releases'::regclass AND contype = 'c' "
        "AND pg_get_constraintdef(oid) LIKE '%reminder_hours%'; "
        "EXECUTE format('ALTER TABLE app_releases DROP CONSTRAINT %I', c); "
        "EXECUTE format('ALTER TABLE app_releases ADD CONSTRAINT %I CHECK (reminder_hours >= "
        + str(low)
        + " AND reminder_hours <= 720)', c); END $$;"
    )


def upgrade() -> None:
    op.add_column(
        "app_releases",
        sa.Column("country_min_builds", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.execute(_recheck(0))


def downgrade() -> None:
    # **«في كلِّ فتح» لا يعيش في القيد القديم** — يصير أقصرَ كتمٍ كان مسموحاً (ساعة)
    op.execute("UPDATE app_releases SET reminder_hours = 1 WHERE reminder_hours = 0")
    op.execute(_recheck(1))
    op.drop_column("app_releases", "country_min_builds")

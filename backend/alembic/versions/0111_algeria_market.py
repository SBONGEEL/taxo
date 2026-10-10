"""سوقُ الجزائر (SPEC §٧٣) — **`DZ` في نوع الدولة و`DZD` في نوع العملة، وصفُّ إخفائها معهما**.

**ما تضيفه**:
- `country_code`: **`DZ`** · `currency`: **`DZD`** — قيمتا تعداد، **لا عمودَ ولا صفَّ مالٍ يتغيّر**. وخاناتُ العملة (صفرٌ للجزائريّ) بيتُها
  `core/currency.py` لا القاعدة: **`NUMERIC(12,3)` يسع الدينارَ الصحيحَ بلا تغيير**.
- `feature_flags`: **صفُّ `country_visible = false` للجزائر** — لأن «السكوتُ ظهور» (§٢٤): ترحيلةٌ تضيف سوقاً بلا صفِّ إخفاءٍ **تُظهره في كلِّ
  تثبيتٍ لم يُبذر بعدها**، والإنتاجُ لا يُبذر في الرفع. **فالإخفاءُ يولد مع السوق** في اللحظة نفسِها.

**ولا جدولَ مالٍ يُمسّ قائمُه**: نوعُ `currency` تستعمله سبعةُ أعمدةٍ ماليّة، **وإضافةُ قيمةٍ إليه لا تغيّر صفّاً** (موافَقٌ عليها بأمر المالك
٢٠٢٦-١٠-١١).

**و`COMMIT` بعد `ALTER TYPE`** (سابقتُه `0018`): PostgreSQL لا يستعمل قيمةَ تعدادٍ في المعاملة التي أضافتها، و`env.py` يلفّ السلسلةَ كلَّها
في معاملةٍ واحدة. **وكلُّ ما بعده يُعاد بلا ضرر** (`ON CONFLICT DO NOTHING`).

**و`downgrade` مقيسٌ لا مقروء** (`tests/test_migrations.py`): قيمتا التعداد لا تُنزعان (PostgreSQL)، **ويُرفع صفُّ الإخفاء الذي كتبته هذه
وحدَه** — فالشيفرةُ القديمةُ لا تقرأ صفّاً بقيمةٍ لا تعرفها. **وأيُّ صفٍّ آخرَ بـ`DZ` أو `DZD` في أيِّ جدولٍ يُسقط النزولَ عمداً**: نزولٌ يترك
بياناتٍ بقيمةٍ لم تعد الشيفرةُ تعرفها أسوأُ من نزولٍ يقف (درسُ `0104`).

Revision ID: 0111
Revises: 0110
"""

from __future__ import annotations

from alembic import op

revision = "0111"
down_revision = "0110"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE country_code ADD VALUE IF NOT EXISTS 'DZ'")
    op.execute("ALTER TYPE currency ADD VALUE IF NOT EXISTS 'DZD'")
    # القيمةُ لا تُستعمل قبل أن تُثبَّت — وصفُّ الإخفاء أدناه يستعملها
    op.execute("COMMIT")

    # كلُّ ما بعد `COMMIT` بصيغةٍ تُعاد بلا ضرر
    op.execute(
        """
        INSERT INTO feature_flags (id, country_code, feature_key, enabled, created_at, updated_at)
        VALUES (gen_random_uuid(), 'DZ', 'country_visible', false, now(), now())
        ON CONFLICT (country_code, feature_key) DO NOTHING
        """
    )


def downgrade() -> None:
    # **يقف إن استُعملت القيمتان في غير صفِّ الإخفاء** — يُعدّ كلُّ عمودٍ من النوعين في المخطّط، لا قائمةٌ تُكتب بيد
    op.execute(
        """
        DO $$
        DECLARE
            col record;
            used bigint;
        BEGIN
            FOR col IN
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = current_schema() AND udt_name IN ('country_code', 'currency')
            LOOP
                EXECUTE format(
                    'SELECT count(*) FROM %I WHERE %I::text IN (''DZ'', ''DZD'')',
                    col.table_name, col.column_name
                ) INTO used;
                IF col.table_name = 'feature_flags' THEN
                    used := used - (
                        SELECT count(*) FROM feature_flags
                        WHERE country_code::text = 'DZ' AND feature_key = 'country_visible'
                    );
                END IF;
                IF used > 0 THEN
                    RAISE EXCEPTION 'النزولُ عن 0111 مرفوض: % صفّاً في %.% بـDZ أو DZD', used, col.table_name, col.column_name;
                END IF;
            END LOOP;
        END $$;
        """
    )
    op.execute(
        "DELETE FROM feature_flags WHERE country_code::text = 'DZ' AND feature_key = 'country_visible'"
    )

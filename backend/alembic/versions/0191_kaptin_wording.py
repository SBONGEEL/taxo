"""«كابتن» لا «كبتن» في النصوص المحفوظة في القاعدة (SPEC §١١٨، قرارُ المالك ٢٠٢٦-١١-٢٦).

**ما يُكتب في اللوحة ويُبذر في الترحيلات** لا تبلغه أداةُ الشيفرة: صفحةُ الموقع، والسياسات، وقوالبُ OTP، والفئات، والمرافق، ونصوصُ الإصدارات
والحملاتِ والشرائط. **فقائمةُ جداولَ مسمّاةٌ لا كنسٌ للقاعدة**: ما يكتبه الناسُ (المحادثاتُ وبلاغاتُ الدعم والتقييمات) كلامُهم لا يُعدَّل،
وما أُرسل (صندوقُ الإشعارات) سجلٌّ لا يُعاد كتابتُه. **ولا جدولَ مالٍ فيها**: لا رصيدَ ولا قيدَ ولا دفعَ ولا اشتراك.

**والسياساتُ في مكانها بلا نسخةٍ جديدة** (المعنى نفسُه، بلا إعادة قبول): الموافقةُ مربوطةٌ بـ`policy_id` لا بالنصّ، فلا تسقط.

**والأعمدةُ تُقرأ من القاعدة نفسِها** (`information_schema`): كلُّ عمودِ نصٍّ أو `jsonb` في الجداول المسمّاة — فعمودٌ يُضاف غداً يبلغه
التشغيلُ ولا يُنسى. **والعدُّ يُطبع** لكلِّ جدولٍ وعمود في سجلّ الرفع.

**وما يتجاوز حدَّ عموده بعد الاستبدال يُترك كما هو ويُعدّ** (عطبٌ مقيسٌ على الإنتاج ٢٠٢٦-١١-٢٦، الرفع 18 مرّتين): حملةٌ مُرسَلةٌ نصُّها
٥٠٠ حرفٍ بالضبط في `notification_campaigns.body` (`varchar(500)`) فصار ٥٠١ — **فسقطت الترحيلةُ كلُّها** بـ«value too long» وعادت
القاعدةُ إلى `0190` في معاملتها. **فلا تقصيرَ لنصٍّ ولا توسيعَ لعمود**: صفٌّ لا يتّسع يُتجاوز، والعددُ يُطبع.

**والنزولُ لا يعكس**: «كابتن» كانت تُكتب قبل هذا في مواضع، فالعكسُ الآليُّ يُفسد ما كان صحيحاً — **فهو بلا فعلٍ بقصد**، والنسخةُ قبل الرفع طريقُ الرجوع.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0191"
down_revision = "0190"
branch_labels = None
depends_on = None

OLD, NEW = "كبتن", "كابتن"

#: **ما يُكتب في اللوحة ويراه الناس** — مسمّاةٌ واحداً واحداً بعلّتها في رأس الملف
TABLES = (
    "site_settings",
    "privacy_policies",
    "otp_message_templates",
    "ride_categories",
    "facilities",
    "app_releases",
    "promo_banners",
    "notification_campaigns",
    "verification_campaigns",
    "broadcast_settings",
    "payment_providers",
)


def upgrade() -> None:
    bind = op.get_bind()
    columns = bind.execute(
        sa.text(
            "SELECT table_name, column_name, data_type, character_maximum_length FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = ANY(:tables) "
            "AND data_type IN ('text', 'character varying', 'jsonb', 'json')"
        ),
        {"tables": list(TABLES)},
    ).all()
    total = 0
    for table, column, data_type, max_length in columns:
        if data_type in ("jsonb", "json"):
            cast = data_type
            sql = (
                f'UPDATE "{table}" SET "{column}" = replace("{column}"::text, :old, :new)::{cast} '
                f'WHERE "{column}"::text LIKE :like'
            )
        else:
            sql = f'UPDATE "{table}" SET "{column}" = replace("{column}", :old, :new) WHERE "{column}" LIKE :like'
            if max_length is not None:
                # **ما لا يتّسع يُترك** — ويُعدّ أدناه
                fits = f'char_length(replace("{column}", :old, :new)) <= {int(max_length)}'
                skipped = bind.execute(
                    sa.text(f'SELECT count(*) FROM "{table}" WHERE "{column}" LIKE :like AND NOT ({fits})'),
                    {"old": OLD, "new": NEW, "like": f"%{OLD}%"},
                ).scalar_one()
                if skipped:
                    print(f"0191: {table}.{column} — {skipped} صفّاً لا يتّسع لـ«{NEW}» فتُرك")
                sql += f" AND {fits}"
        changed = bind.execute(sa.text(sql), {"old": OLD, "new": NEW, "like": f"%{OLD}%"}).rowcount
        if changed:
            total += changed
            print(f"0191: {table}.{column} — {changed} صفّاً")
    print(f"0191: المجموع {total} صفّاً")


def downgrade() -> None:
    # بلا فعلٍ بقصد — انظر رأسَ الملف
    pass

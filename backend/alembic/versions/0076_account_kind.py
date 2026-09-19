"""نوعُ الحساب — مفتاحٌ مركّب `(phone, account_kind)` بدل تفرّد الرقم (1-أ/3، الترحيلة 0076 على شجرة WSL).

**القرار** (`SPEC-DELIVERY.md` §D1.4 و§D9.1، قرارُ المالك 2026-09-19): حسابُ الزبون
وحسابُ التاجر **حسابان منفصلان تماماً** بالرقم نفسه — كلمةُ مرورٍ وحظرٌ وتجميدٌ
وسجلٌّ لا تلتقي. والراكبُ والكبتنُ **حسابٌ واحد** عبر تطبيقين كما كانا، فالنوعُ
`taxo` لهما ولكلِّ حسابٍ قائم (واللوحة).

## ما تفعله — خمسةُ أوامرَ بنيويّة، ولا `UPDATE` على صفّ

1. نوعُ postgres `account_kind` بثلاث قيم (`taxo · market · merchant` — Q40).
2. عمود `users.account_kind` — `NOT NULL DEFAULT 'taxo'`: **postgres يكتب
   القيمةَ الافتراضيةَ على كلِّ صفٍّ قائمٍ في الأمر نفسِه**، فلا يُعدَّل صفٌّ بيد.
3. `ix_users_phone` كان **فريداً** (الترحيلة `0002`) — يُعاد **عاديّاً** للبحث.
4. قيدٌ فريد `uq_users_phone_account_kind` على `(phone, account_kind)`.
   و`NULL` في الهاتف يبقى مسموحاً لحسابات اللوحة (postgres لا يعدّ `NULL` مكرَّراً).
5. `uq_users_email_verified` (الترحيلة `0065`) يُعاد على `(lower(email),
   account_kind)` بشرطه نفسِه.

## وحدُّ الرجوع — مكتوبٌ لا مفترض

`downgrade` يعكس الخمسة، **ويسقط** بعد أول رقمٍ بحسابين (أو بريدٍ مُثبَتٍ
بحسابين): القيدُ الفريدُ القديمُ لا يُبنى على رقمٍ مكرَّر، والترحيلةُ لا تحذف
صفّاً لتنجح. **فالرجوعُ بعدها إصلاحٌ إلى الأمام** — وهو ما أوقف المالكُ هذه
الخطوةَ لأجله قبل الإيداع.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0076"
down_revision = "0075"
branch_labels = None
depends_on = None

_KIND = postgresql.ENUM("taxo", "market", "merchant", name="account_kind")


def upgrade() -> None:
    _KIND.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "users",
        sa.Column(
            "account_kind",
            postgresql.ENUM(name="account_kind", create_type=False),
            nullable=False,
            server_default=sa.text("'taxo'"),
        ),
    )

    op.drop_index("ix_users_phone", table_name="users")
    op.create_index("ix_users_phone", "users", ["phone"], unique=False)
    op.create_unique_constraint(
        "uq_users_phone_account_kind", "users", ["phone", "account_kind"]
    )

    op.execute("DROP INDEX IF EXISTS uq_users_email_verified")
    op.execute(
        "CREATE UNIQUE INDEX uq_users_email_verified "
        "ON users (lower(email), account_kind) WHERE email_verified_at IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_users_email_verified")
    op.execute(
        "CREATE UNIQUE INDEX uq_users_email_verified "
        "ON users (lower(email)) WHERE email_verified_at IS NOT NULL"
    )

    op.drop_constraint("uq_users_phone_account_kind", "users", type_="unique")
    op.drop_index("ix_users_phone", table_name="users")
    op.create_index("ix_users_phone", "users", ["phone"], unique=True)

    op.drop_column("users", "account_kind")
    _KIND.drop(op.get_bind(), checkfirst=True)

"""البريدُ قناةً بديلةً حين تسقط واتساب — **والرقمُ يُحجز ولا يُملَك**
(قرارُ المالك 2026-08-31).

## ثلاثةُ أعمدةٍ لا اثنان

**`email`** و**`email_verified_at`** — والثاني هو ما يفرّق **عنواناً كُتب**
من **عنوانٍ أُثبت**. وعنوانٌ يكتبه صاحبُ الحساب عن نفسه ليس إثباتاً، **كما
أن `gender` المعلَنَ ليس وسماً**.

**و`phone_pending`** — وهو الذي يجعل الأولين آمنَين. من سجّل ببريده كتب
رقمَه ولم يُثبته: **فالرقمُ محجوزٌ** (لا يسجّل به غيرُه — الفهرسُ الفريدُ
قائمٌ كما هو) **ولا يملكه هو**.

> **ولمَ عمودٌ ثالثٌ ولا يُشتقّ من `phone_verified_at IS NULL`**: الفراغُ
> هناك له **معنيان اليومَ لا معنى واحد** — حسابٌ أُنشئ والمفتاحُ مطفأٌ
> للطوارئ (**كاملُ الصلاحية** موسومٌ للمتابعة)، وحسابٌ سجّل ببريده
> (**محدودٌ عمداً**). **وخلطُهما يفتح للثاني ما فُتح للأول** أو يغلق على
> الأول ما أُغلق على الثاني — وكلاهما عطبٌ صامتٌ في صلاحية.

## والبريدُ فريدٌ **بلا حساسيةِ حالة**، وللمُثبَت وحدَه

`Ali@X.com` و`ali@x.com` **صندوقٌ واحد** — وفهرسٌ يفرّق بينهما يسمح بحسابين
على بريدٍ واحد. فالفهرسُ على `lower(email)`.

**وللمُثبَت وحدَه** (`WHERE email_verified_at IS NOT NULL`): عنوانٌ كُتب ولم
يُثبَت **لا يحجز شيئاً** — وإلا لَحجب من كتب بريدَ غيره خطأً **صاحبَه
الحقيقيّ** عن التسجيل به، وهو حجزٌ يملكه من لا يملك الصندوق.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0065"
down_revision = "0064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # **`provider_key` تعدادٌ في بوستجرس** — وعقدُ المُرسِل عضوٌ جديدٌ فيه.
    #
    # **وفخّان معروفان في هذا المشروع يلتقيان هنا** (`CLAUDE.md`):
    # `ALTER TYPE … ADD VALUE` **لا يُستعمل في المعاملة نفسِها**، و`env.py`
    # يلفّ السلسلةَ كلَّها في معاملةٍ واحدة — **فيُثبَّت بـ`COMMIT` صريح**
    # كما فعلت `0018`. **وكلُّ ما بعده يُكتب بصيغةٍ تُعاد بلا ضرر**، لأن ذلك
    # الإيداعَ يعني أن سقوطاً لاحقاً لا يتراجع عنه.
    #
    # **⚠ وثالثٌ لا تمسكه ترحيلة**: asyncpg **يخزّن التعدادَ لكلِّ اتصال**،
    # فالخلفيةُ الحيّةُ تجيب `invalid input value for enum` بعد ترحيلةٍ ناجحة.
    # **العلاجُ إعادةُ إنشاء الحاوية لا `restart`** — وهو مكتوبٌ في `CLAUDE.md`
    # ووقع مقيساً في هذه الجولة نفسِها.
    op.execute("ALTER TYPE provider_key ADD VALUE IF NOT EXISTS 'email'")
    op.execute("COMMIT")

    # **وبصيغةٍ تُعاد بلا ضرر** — لأن ما بعد `COMMIT` لا يتراجع
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(320)")
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at "
        "TIMESTAMPTZ"
    )
    # **`server_default` لأن الصفوفَ القائمةَ لها جوابٌ معروف**: من سجّل قبل
    # اليوم أثبت رقمَه بالمسار القديم — **فرقمُه ليس معلَّقاً**. وعمودٌ بلا
    # افتراضٍ يترك ملايينَ الصفوفِ `NULL` تُقرأ «لا أعرف».
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_pending "
        "BOOLEAN NOT NULL DEFAULT false"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_verified "
        "ON users (lower(email)) WHERE email_verified_at IS NOT NULL"
    )


def downgrade() -> None:
    # **وقيمةُ التعداد لا تُنزع** — بوستجرس لا يحذف عضواً من نوع، **والنوعُ
    # نفسُه تُسقطه الترحيلةُ التي أنشأته**. و`IF NOT EXISTS` أعلاه هو ما
    # يجعل نزولاً جزئياً قابلاً للصعود ثانيةً.
    op.execute("DROP INDEX IF EXISTS uq_users_email_verified")
    op.drop_column("users", "phone_pending")
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "email")

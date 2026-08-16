"""ملءُ رموز الإحالة للحسابات القائمة (تعميمُ الإحالة، تكملةُ 0038).

**العطبُ الذي أغلقته**: `0038` نقلت `drivers.referral_code` إلى `users` — وهو كلُّ
ما كان موجوداً، إذ لم يكن للراكب رمزٌ أصلاً قبل التعميم. فبقي **كلُّ حسابٍ ليس
كبتناً بلا رمز**، وشاشةُ «ادعُ صديقك» ترسم صندوقاً فارغاً تحت عنوانٍ يقول «رمز
الدعوة الخاص بك»: زرّا «انسخ» و«شارك» يعملان وينسخان لا شيء.

ووُجد بفتح الشاشة في متصفّح، لا ببناءٍ ولا باختبار — فالاختباراتُ تُنشئ حساباتِها
بعد الترحيلة فتأخذ رمزَها من `create_account`، وهو بالضبط الشكلُ الذي لا يراه
شيءٌ إلا التشغيل على بياناتٍ قائمة.

**ولماذا ملءٌ في ترحيلةٍ لا توليدٌ عند أول قراءة؟** التوليدُ المتأخّر يحتاج قفلاً
على صفٍّ لا يُكتب فيه شيءٌ آخر، وبغيره تفتح ضغطتان الشاشةَ فيُولَّد رمزان
ويُكتب أحدُهما فوق الآخر — وقد يكون الأولُ نُسخ وأُرسل. وهي الحجّةُ نفسُها
المكتوبة في `services/auth/base.py` منذ 12-ح.

**والفرادةُ يحرسها الفهرس لا هذه الحلقة**: يُحاوَل، فإن اصطدم أُعيد. وأبجديةٌ من
٣١ محرفاً في ٨ خانات تجعل الاصطدامَ نادراً، لكن «نادر» ليس «مستحيلاً» — وترحيلةٌ
تسقط على مصادفةٍ أسوأُ من حلقةٍ فيها إعادةُ محاولة.
"""

from __future__ import annotations

import secrets

import sqlalchemy as sa
from alembic import op

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None

# **نسخةٌ من `services/referrals.ALPHABET` بقصد**: الترحيلاتُ لا تستورد من
# `app/` — كودُ التطبيق يتغيّر وترحيلةٌ ماضيةٌ يجب أن تبقى قابلةً للتشغيل كما
# كُتبت. وهو الاستثناءُ نفسُه الذي تعيش به بقيةُ الترحيلات.
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8


def _code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def upgrade() -> None:
    bind = op.get_bind()
    ids = [
        row[0]
        for row in bind.execute(
            sa.text("SELECT id FROM users WHERE referral_code IS NULL")
        )
    ]
    taken = {
        row[0]
        for row in bind.execute(
            sa.text("SELECT referral_code FROM users WHERE referral_code IS NOT NULL")
        )
    }

    for user_id in ids:
        candidate = _code()
        while candidate in taken:  # pragma: no cover - مصادفةٌ نادرة
            candidate = _code()
        taken.add(candidate)
        bind.execute(
            sa.text("UPDATE users SET referral_code = :code WHERE id = :id"),
            {"code": candidate, "id": user_id},
        )


def downgrade() -> None:
    """**لا تُمحى الرموز.**

    رمزٌ نُسخ وأُرسل إلى صديقٍ لم يسجّل بعد يصير رمزاً «غير صحيح» عند تسجيله —
    والتراجعُ عن ترحيلةٍ لا يجوز أن يُبطل ما بيد الناس. ولا شيءَ في المخطَّط
    يحتاج التراجعَ هنا أصلاً: العمودُ أنشأته `0038` وهي التي تُسقطه.
    """

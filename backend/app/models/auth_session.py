"""جلساتُ الدخول — **صفٌّ في القاعدة لا مفتاحٌ في Redis** (SPEC §60، قرارُ المالك ٢٠٢٦-١٠-٠٤).

**الجلسةُ تبقى حتى يخرج صاحبُها**: لا عمرَ لها ولا مهلةَ خمول. وما يُنهيها
**فعلٌ لا ساعة** — الخروجُ، وإنهاءُ الكلّ، وتغييرُ كلمة المرور، والحظر، وعودةُ
رمزٍ مستهلَك.

**ولمَ القاعدة لا Redis**: Redis للحدود والحضور، وسقوطُه كان يُخرج الجميع —
وهو الشرطُ الرابعُ من §60-ب بعينه. والقاعدةُ تُنسخ قبل كلِّ رفع.

**وما يحمله الصفّ:**

- `current_jti` و`current_issued_at` — **الرمزُ الحيُّ الوحيد ووقتُ سكّه**.
  والوقتُ مخزونٌ لأن الرمزَ **يُعاد سكُّه حرفاً**: من قدّم الرمزَ السابقَ في مهلة
  السماح (جوابٌ ضاع، أو تبويبان جدّدا في اللحظة نفسِها) **يُعطى الرمزَ الحاليَّ
  نفسَه** لا رمزاً ثالثاً — فلا تتفرّع السلسلةُ إلى فرعين يُقرأ أحدُهما سرقة.
- `previous_jti` — الرمزُ الذي استُبدل للتوّ. **وبعد المهلة يُقرأ عودتُه سرقة**.
- `revoked_at` و`revoked_reason` — **الإبطالُ ختمٌ لا حذف**: الصفُّ يبقى شاهداً
  لمَ انتهت الجلسة.

**و`ON DELETE CASCADE`** كرموز الأجهزة (`device_tokens`): بيانُ دخولٍ لا سجلٌّ
محاسبيّ، ولا معنى له بعد ذهاب صاحبه.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class AuthSession(UUIDMixin, Base):
    __tablename__ = "auth_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    current_jti: Mapped[str] = mapped_column(String(64), nullable=False)
    # **وقتُ سكّ الرمز الحاليّ بالثانية** — هو `iat` نفسُه، ومنه يُعاد السكُّ حرفاً
    current_issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    previous_jti: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # سببٌ نصّيٌّ قصير (`token_service.REVOKE_*`) — لا تعدادٌ في القاعدة: سببٌ جديدٌ
    # لا يستحقّ ترحيلةً تضيف قيمةً لا تُحذف
    revoked_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - للتشخيص
        state = f"revoked:{self.revoked_reason}" if self.revoked_at else "live"
        return f"<AuthSession {self.id} user={self.user_id} {state}>"

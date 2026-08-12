"""العامل الثاني لدخول اللوحة — TOTP (SPEC القسم 14.1، المرحلة 12-د).

**جدولان لا أعمدةٌ على `users`**، والسبب أداءٌ وأمانٌ في آن: `users` يُقرأ في
كل طلبٍ لكل مستخدم (`core/deps.get_current_user`)، فسرُّ العامل على صفّه يعني
تحميلَ سرِّ عاملٍ ثانٍ في كل نداءٍ في المنصة كلها — ولمن لا يملك عاملاً أصلاً.
وهذان الجدولان لا يُقرآن إلا في مسارَي الدخول والتسجيل.

**والسرُّ يُشفَّر، ورموزُ الاسترداد تُهشَّم** — والفرق ليس ذوقاً:

- التحقق من السرِّ يحتاج **قراءتَه**: نولّد منه رمزَ اللحظة ونقارن. فسرٌّ
  مهشَّمٌ لا يتحقق منه أحد، ومظروفُ Fernet (`core/crypto.py`، نفسُه الذي يحمي
  `provider_credentials`) هو الشكلُ الصحيح: مفتاحٌ دائمٌ يُقرأ ولا يُعرض.
- والتحقق من رمز الاسترداد **مقارنةٌ** لا استرجاع، فيُهشَّم. وجدولٌ يحفظها
  مقروءةً هو نسخةٌ ثانيةٌ من العامل الثاني بلا عاملٍ يحرسها.

**والتهشيم HMAC-SHA256 لا bcrypt** — خلافاً لكلمة المرور، ولسببين يعملان معاً:
الرموزُ عاليةُ العشوائية (خمسون بتاً من مولّدٍ تشفيري) فدالةٌ بطيئةٌ لا تشتري
مقاومةً لتخمينٍ غيرِ ممكنٍ أصلاً؛ والبصمةُ الحتمية تتيح **استعلاماً مفهرساً عن
الصفِّ الواحد** — وهو ما يجعل القفل على صفٍّ واحدٍ بدل قفلِ عشرةِ صفوفٍ
ومقارنتِها واحداً واحداً تحته. وهو نفسُ `services/otp.py::_digest`: بصمةٌ
بمفتاح الخدمة، فنسخةٌ من القاعدة وحدها لا تكفي للتحقق.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class UserTotp(UUIDMixin, TimestampMixin, Base):
    """عاملُ صاحب الحساب الثاني — صفٌّ واحدٌ له، وغيابُه «لا عامل»."""

    __tablename__ = "user_totp"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # مظروف Fernet: {"v": 1, "ciphertext": …} — لا السرُّ نفسه
    secret_encrypted: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # **تسجيلٌ غير مؤكَّد ليس عاملاً**: السرُّ يُنشأ قبل أن يُثبت صاحبه أنه وصل
    # تطبيقَه، فاعتبارُه عاملاً يقفل صاحبَه خارج اللوحة برمزٍ لا يملك مصدره
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # لحظةُ إثبات أن الاسترداد يعمل فعلاً — شرطُ إشعال مفتاح الإلزام
    # (القسم 14.1). والإثباتُ يستهلك رمزاً حقيقياً: مربَّعٌ يُؤشَّر لا يُثبت شيئاً
    recovery_codes_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # آخرُ خطوةِ زمنٍ قُبلت — **منعُ إعادة الاستخدام**: الرمزُ صالحٌ ثلاثين
    # ثانية، فمن قرأه من فوق كتف صاحبه يستعمله في النافذة نفسها. والقبولُ
    # مرةً واحدةً لكل خطوة، فالرمزُ المستعمل يموت بمجرد استعماله
    last_step: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    @property
    def is_confirmed(self) -> bool:
        return self.confirmed_at is not None

    @property
    def recovery_verified(self) -> bool:
        return self.recovery_codes_verified_at is not None

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        state = "confirmed" if self.is_confirmed else "pending"
        return f"<UserTotp {self.user_id} {state}>"


class UserRecoveryCode(UUIDMixin, TimestampMixin, Base):
    """رمزُ استردادٍ واحد — بصمتُه وحدها، ولمرةٍ واحدة.

    الاستهلاكُ يقفل الصفَّ قبل قراءة `used_at` (`services/totp.py`): بلا القفل
    يمرّ نداءان متزامنان ببصمةٍ واحدة فيُستعمل رمزُ «المرةِ الواحدة» مرتين.
    """

    __tablename__ = "user_recovery_codes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # بصمةُ HMAC-SHA256 بمفتاح الخدمة — ستٌّ وأربعون حرفاً hex... أي 64
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<UserRecoveryCode {self.user_id} used={self.is_used}>"

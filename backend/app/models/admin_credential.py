"""اعتمادُ دخولِ المشرف — **اسمُ مستخدمٍ لا رقمُ هاتف** (قرارُ المالك 2026-08-20).

**ولماذا جدولٌ لا عمودٌ على `users`؟** لأن اسمَ المستخدم **صفةُ حسابٍ إداريّ لا
صفةُ إنسان** — وهو تطبيقُ §22 حرفياً: الدلالةُ تتبع سياقَ الفعل. وعمودٌ على
`users` يجعل «هل للراكب اسمُ مستخدم؟» سؤالاً **ممكناً بالبناء**، ثم يحتاج حارساً
يمنع ما أتاحه البناءُ نفسُه — وهو الشكلُ الذي أنشأ «دورٌ صار مجموعةً» أصلاً.
هنا السؤالُ لا يُطرح: الجدولُ للمشرفين بحكم وجوده.

**والاسمُ يُخزَّن مطبَّعاً (lowercase)** ويُقارَن مطبَّعاً: مشرفٌ يكتب اسمَه
بحرفٍ كبيرٍ في هاتفه وصغيرٍ في حاسوبه إنسانٌ واحد، وفهرسٌ حسّاسٌ لحالة الأحرف
يجعلهما حسابين — أو يجعل `Ali` و`ali` اسمين مختلفين لشخصين، وهو أسوأ.

**وحسابُ الطوارئ (`is_break_glass`) صفٌّ عاديٌّ بعلامة**: مشرفٌ واحدٌ بلا رقمٍ
ولا بريدٍ ولا استعادةٍ ذاتية يعني أن **ضياعَ جهاز العامل الثاني يقفل اللوحة
كلَّها**. والثاني يبقى مغلقاً ولا يُستعمل يومياً، **ودخولُه يُكتب في التدقيق
بصفته** (`admin_break_glass_login`) — فيُعرف حين يُستعمل، لا بعد شهر.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class AdminCredential(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "admin_credentials"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    # **فريدٌ ومطبَّع** — والتطبيعُ عند الكتابة لا عند القراءة، فالفهرسُ يحرسه
    username: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    # **حسابُ طوارئ**: لا يُستعمل يومياً، ودخولُه حدثٌ يُسجَّل
    is_break_glass: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # آخرُ استعمالٍ — يُقرأ ليُعرف أن حساب الطوارئ نائمٌ فعلاً
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="admin_credential")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AdminCredential {self.username}>"


def normalize_username(raw: str) -> str:
    """**بيتٌ واحدٌ للتطبيع** — يُنادى عند الكتابة وعند البحث.

    ودالّتان تطبّعان بطريقتين تجعلان اسماً يُكتب ولا يُوجد.
    """
    return raw.strip().lower()

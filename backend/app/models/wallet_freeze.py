"""تجميدُ محفظةٍ بعينها — **صفٌّ للمجمَّد وحدَه** (1-أ/6، `SPEC-DELIVERY.md` §D6 و§D9.1).

**ما كان**: `users.wallet_frozen` عمودٌ على الحساب. وبعد أن صار للحساب الواحد
أكثرُ من محفظة (راكبٌ وكبتنٌ اليوم، والتاجرُ غداً) صار العمودُ يقول شيئاً واحداً
عن شيئين: **تجميدُ محفظةِ كبتنٍ مشبوهةٍ يمنع صاحبَها من دفع رحلته راكباً**،
وتجميدُ محفظةِ راكبٍ يوقف سحبَ أرباحه كبتناً. **وهو تجميدٌ لم يقرّره أحد.**

**ولماذا صفٌّ لا عمودٌ على جدول محافظ**: **لا جدولَ محافظ في النظام أصلاً** —
المحفظةُ مشتقّةٌ من الدفتر (`(owner_id, owner_type)` فوق `wallet_transactions`)
ولا عمودَ رصيدٍ في أيِّ مكان. فجدولُ محافظَ يُنشأ لأجل التجميد **يخترع مصدرَ
حقيقةٍ ثانياً يجب أن يوافق الدفترَ أبداً** — وكلُّ ما يُطلب هنا أن يُقال: هذه
المحفظةُ بعينها موقوفة.

**ووجودُ الصفِّ هو التجميد**: رفعُه حذفُه، وتاريخُه في `admin_audit_logs` كما
كان قبل هذا الجدول وبعده.

**ويتّسع بعمودٍ واحد** حين يأتي التاجرُ ومعه `merchant_id` (Q38 موقَّع): يُضاف
إلى القيد الفريد فيصير `(user_id, owner_type, merchant_id)` — ومالكُ محلّين
يُجمَّد أحدُهما دون الآخر.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, pg_enum
from app.models.enums import WalletOwnerType


class WalletFreeze(Base):
    """محفظةٌ واحدةٌ موقوفة. صفٌّ لكلِّ محفظةٍ مجمَّدة، لا عمودٌ يحمل الحساب كلَّه."""

    __tablename__ = "wallet_freezes"
    __table_args__ = (
        # **المحفظةُ لا تُجمَّد مرّتين**: صفّان لمحفظةٍ واحدةٍ يجعلان رفعَ
        # التجميد يترك نصفَه — وهي علّةُ `uq_user_roles_user_role` بعينها
        UniqueConstraint("user_id", "owner_type", name="uq_wallet_freezes_wallet"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_type: Mapped[WalletOwnerType] = mapped_column(
        pg_enum(WalletOwnerType, "wallet_owner_type"), nullable=False
    )
    # **سببُ التجميد القائم** — والتاريخُ كلُّه في الأرشيف: هذا ما يُقرأ اليوم
    # في اللوحة بجانب الشارة، لا سجلُّ ما مضى
    reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # **من جمّد** — `SET NULL` لأن مشرفاً يُحذف لا يرفع تجميداً عن محفظة
    frozen_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

"""أدوارُ الحساب — **مجموعةٌ لا عمود** (قرارُ المالك 2026-08-19).

**لماذا تحوّل النموذج**: `users.role` عمودٌ واحد، فالحسابُ راكبٌ **أو** كبتن ولا
يكون الاثنين. وذلك يجعل «تبديلاً بين التطبيقين بنفس الحساب» مستحيلاً بنيةً لا
واجهةً: `app_scope` يخدم كلُّ تطبيقٍ دورَه، و`deps` يقرأ الدورَ من الصفّ في كل
طلب — فجلسةٌ منقولةٌ لا تحمل دوراً لا يملكه صاحبُها.

**وما يبطل هذا القرار**: إن صار لكل دورٍ حسابُه المستقلُّ برقمه (لا حسابٌ واحدٌ
بدورين)، فالمجموعةُ تصير بيتاً ثانياً لحقيقةٍ يحملها الصفُّ نفسُه، وتُعاد
قراءتُها. وحتى ذلك اليوم: `users.phone` فريد، فالشخصُ الواحد حسابٌ واحد.

**والتوسيعُ لا يوسّع نطاقَ التطبيقات**: `app_scope` يبقى كما هو — كلُّ تطبيقٍ
يخدم دورَه، ومن لا يملك الدورَ يُرفض. ومنحُ دورِ الكبتن يبقى بمساره القائم
وحدَه (تسجيلٌ ومركبةٌ وموافقةُ إدارة)؛ لا مسارَ جديدَ يمنح دوراً.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, pg_enum
from app.models.enums import UserRole


class UserRoleGrant(Base):
    """دورٌ واحدٌ يملكه حساب. صفٌّ لكل دور، لا عمودٌ يحمل واحداً."""

    __tablename__ = "user_roles"
    __table_args__ = (
        # **الدورُ لا يُمنح مرتين**: صفّان بنفس الدور يجعلان «كم دوراً له؟»
        # سؤالاً بجوابين، ويجعلان سحبَ الدور يترك نصفَه
        UniqueConstraint("user_id", "role", name="uq_user_roles_user_role"),
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
    role: Mapped[UserRole] = mapped_column(
        pg_enum(UserRole, "user_role"), nullable=False
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


def has_role_clause(*roles):
    """شرطُ SQL لـ«يملك الدور» — **ويضمّ العمودَ كما يضمّه `User.roles`**.

    وهي القاعدةُ نفسُها في الموضعين لا اثنتان: صفٌّ أُنشئ خارج
    `services/auth/base.create_account` (بذرةٌ، أو ثابتُ اختبار، أو إدراجٌ
    إداريّ) يحمل العمودَ بلا صفٍّ في المجموعة — فمرشِّحٌ يقرأ المجموعةَ وحدَها
    **يُخفيه**، ويصير الحسابُ موجوداً في التخويل ومفقوداً في القوائم.

    وتضمينُ العمودِ حارسٌ ضدّ الفقد لا مصدرٌ ثانٍ: الترحيلةُ جعلتهما متطابقين،
    وكلُّ كتابةٍ جديدةٍ تكتبهما معاً. ويسقط يومَ يُحذف العمود.
    """
    from sqlalchemy import or_, select

    from app.models.user import User

    return or_(
        User.role.in_(roles),
        select(UserRoleGrant.id)
        .where(UserRoleGrant.user_id == User.id, UserRoleGrant.role.in_(roles))
        .exists(),
    )

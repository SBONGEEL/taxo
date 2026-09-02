"""صلاحيةٌ واحدةٌ يملكها مشرف — **صفٌّ لكلِّ صلاحية** (البند ٥، §39٫٥).

**ومجموعةٌ لا عمود**، للسبب الذي جعل الأدوارَ مجموعةً (§21): عمودٌ واحدٌ يحمل
«المستوى» **لا يقول ماذا يملك**، ومن يقرأ «الدرجة الثانية» بعد شهرٍ لا يعرف
أيفتح صفحةَ العقود أم لا.

## والغيابُ ليس منعاً — **بل «اقرأ افتراضَ دوره»**

**وهذا ما يجعل المصفوفةَ لا تبدّل سلوكاً قائماً في يومها الأول** (شرطُ المالك):
**لا صفَّ لأحدٍ اليوم**، فكلُّ مشرفٍ يُقرأ بافتراض دوره — `admin` يملك الكلَّ
و`support` يقرأ ويحسم النزاعات، **وهو ما يقع اليومَ حرفاً**.

**والصفوفُ تحكم حين تُوجد**: أوّلُ صفٍّ لمشرفٍ يجعل مجموعتَه **ما مُنح لا ما
يفترضه دورُه** — فمنحُ صلاحيةٍ واحدةٍ لا يعني «هذه فوق الافتراض» بل «هذه
وحدَها»، **وإلا صار نزعُ صلاحيةٍ مستحيلاً**.

**و`RESTRICT` لا `CASCADE` على من منح**: حسابُ مشرفٍ يُحذف لا يمحو أثرَ ما
منحه — **ومنحةٌ بلا مانحٍ خيرٌ من منحةٍ ممحوّة**.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, pg_enum
from app.models.enums import AdminPermission


class AdminPermissionGrant(Base):
    """صلاحيةٌ واحدةٌ ممنوحةٌ لحساب."""

    __tablename__ = "admin_permissions"
    __table_args__ = (
        # **لا تُمنح مرّتين**: صفّان بالصلاحية نفسِها يجعلان نزعَها يترك نصفَها
        UniqueConstraint(
            "user_id", "permission", name="uq_admin_permissions_user_permission"
        ),
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
    permission: Mapped[AdminPermission] = mapped_column(
        pg_enum(AdminPermission, "admin_permission"), nullable=False
    )
    granted_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

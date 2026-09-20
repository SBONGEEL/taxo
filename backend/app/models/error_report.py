"""تقاريرُ الأعطال — **جدولان يفترقان لأن السؤالين يفترقان** (§D10، 2026-09-20).

**العطبُ الذي بُنيت له الشاشةُ ليس حدثاً واحداً**: حلقةُ رسمٍ في تطبيق الكبتن
تُطلق مئاتِ الأحداث في دقيقة، **وكلُّها عطبٌ واحد**. فلو كان الجدولُ واحداً
لقرأ المشرفُ أربعين صفّاً متطابقاً ولم يعرف **أواحدٌ أصابه أربعون مرّةً أم
أربعون إنساناً أصابهم مرّةً** — وهما حالان يوجبان فعلين مختلفين تماماً.

**فالمجموعةُ تُجيب «ما هو»، والحدثُ يُجيب «متى ولمن»**، و`error_group_devices`
هو الثالثُ الذي يجعل «كم إنساناً» **عدّاً مضبوطاً لا تقديراً**.

## ولمَ جدولٌ ثالثٌ للأجهزة

`COUNT(DISTINCT device_hash)` على الأحداث يُجيب السؤالَ نفسَه — **ويصير أبطأ
كلَّما صدق التقرير**: مجموعةٌ فيها مئةُ ألف حدثٍ تُمسح كلُّها لتُعطي رقماً
واحداً في كلِّ فتحةِ شاشة. **وصفٌّ لكلِّ جهازٍ مرّةً واحدةً** (بقيدٍ فريد)
يجعل العدَّ عموداً يُقرأ، **والفرزَ بالمتأثرين فرزاً على عمودٍ لا على مسح**.

**وهو الفرزُ المقصود**: «٤٠ مرّةً لـ١٢ شخصاً» تُرتَّب بالاثني عشر لا بالأربعين
— وإلا تصدّرَت حلقةُ رسمٍ في هاتفٍ واحدٍ عطباً يمسّ نصفَ الأسطول.

## وما ليس هنا

**لا رقمَ هاتفٍ ولا مُعرِّفَ حسابٍ ولا إحداثيّة.** ما يصل هذا الجدولَ مرّ
بـ`core/scrub.py` قبله، **وهو الحارسُ لا هذا الملفّ** — والمكتوبُ هنا وصفٌ
لا ضمان.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin, pg_enum
from app.models.enums import ClientApp, ErrorKind, ErrorPlatform, ErrorStatus


class ErrorGroup(UUIDMixin, Base):
    """عطبٌ واحدٌ مهما تكرّر — **والبصمةُ هي التي تقول «واحد»**.

    **والإصدارُ خارجَ البصمة بقصد** (وهو أدقُّ قرارٍ هنا): لو دخل فيها
    لانقسمت المجموعةُ عند كلِّ نشرة، **فيضيع أنّ العطبَ يعيش منذ ثلاث نسخ**
    — وهو الخبرُ الذي يُبنى عليه القرار. فبقي الإصدارُ عمودين يُقرآن:
    `first_seen_release` و`last_seen_release`.
    """

    __tablename__ = "error_groups"

    #: بصمةُ التجميع — `sha256` لستّة عناصرَ، انظر `services/error_reports.py`
    fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    app: Mapped[ClientApp] = mapped_column(
        pg_enum(ClientApp, "client_app"), nullable=False, index=True
    )
    kind: Mapped[ErrorKind] = mapped_column(
        pg_enum(ErrorKind, "error_kind"), nullable=False
    )
    #: صنفُ الاستثناء (`TypeError`) — قصيرٌ ويُعرض عنواناً
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    #: أولُ سطرٍ من الرسالة بعد التنظيف — **معروضٌ لا مُجمَّعٌ عليه**
    title: Mapped[str] = mapped_column(String(500), nullable=False)

    status: Mapped[ErrorStatus] = mapped_column(
        pg_enum(ErrorStatus, "error_status"),
        nullable=False,
        default=ErrorStatus.OPEN,
        server_default=ErrorStatus.OPEN.value,
        index=True,
    )

    #: **عدّادان مُمسَكان لا محسوبان** — والفرزُ عليهما مباشرةً
    event_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    user_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", index=True
    )

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    first_seen_release: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_seen_release: Mapped[str | None] = mapped_column(String(40), nullable=True)

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    #: **`SET NULL` لا `CASCADE`**: حسابُ مشرفٍ يُحذف لا يمحو أنّ أحداً حسمها
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<ErrorGroup {self.app} {self.name} x{self.event_count}>"


class ErrorEvent(Base):
    """وقوعٌ واحدٌ بعينه — **ويُكنس بعد مدّته، والمجموعةُ تبقى**."""

    __tablename__ = "error_events"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("error_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    app: Mapped[ClientApp] = mapped_column(
        pg_enum(ClientApp, "client_app"), nullable=False
    )
    kind: Mapped[ErrorKind] = mapped_column(
        pg_enum(ErrorKind, "error_kind"), nullable=False
    )
    platform: Mapped[ErrorPlatform] = mapped_column(
        pg_enum(ErrorPlatform, "error_platform"), nullable=False
    )
    os_version: Mapped[str | None] = mapped_column(String(60), nullable=True)
    release: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    channel: Mapped[str | None] = mapped_column(String(20), nullable=True)

    #: **قالبُ المسار لا المسار** — `/rides/:rideId/pay` لا مُعرِّفَ رحلةٍ فيه
    route: Mapped[str | None] = mapped_column(String(200), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    stack: Mapped[str | None] = mapped_column(Text, nullable=True)
    component_stack: Mapped[str | None] = mapped_column(Text, nullable=True)
    breadcrumbs: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)

    #: **مُعمّىً بملحٍ يبقى في الخادم** — انظر `core/scrub.py`
    device_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    online: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    #: كم مرّةً تكرّر الحدثُ نفسُه في الجلسة قبل أن يُرسَل — صفٌّ واحدٌ لا أربعون
    repeat: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    #: **الخيطُ إلى سطرِ الخلفية** (المرحلة صفر) — آخرُ `X-Request-Id` رآه العميل
    request_id: Mapped[str | None] = mapped_column(
        String(32), nullable=True, index=True
    )

    user_reported: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", index=True
    )
    #: جملةُ صاحبِ الجهاز — **تُنظَّف في الخادم قبل أن تُخزَّن**
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<ErrorEvent {self.name}>"


class ErrorGroupDevice(Base):
    """جهازٌ أصابه هذا العطب — **صفٌّ واحدٌ مهما تكرّر**.

    القيدُ الفريدُ هو الأداة: الإدراجُ يقع بـ`ON CONFLICT DO NOTHING`،
    **و`user_count` يزيد فقط حين يُدرَج صفٌّ فعلاً** — فلا يُعدّ جهازٌ مرّتين
    ولو أرسل ألفَ حدث.
    """

    __tablename__ = "error_group_devices"
    __table_args__ = (
        UniqueConstraint("group_id", "device_hash", name="uq_error_group_devices_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("error_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

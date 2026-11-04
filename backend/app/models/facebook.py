"""قناةُ صفحة فيسبوك «Taxo» — **SPEC §٩٤/٢–٣**.

## صفٌّ لكلِّ منشورٍ بلغةٍ واحدة

**المنشورُ بالعربيّة ونسختُه بالفرنسيّة أو بالدارجة صفّان** (قرارُ المالك ٢٠٢٦-١١-٠٤: «كلُّ لغةٍ منشورٌ مستقلّ»): لكلٍّ موعدُه
ومعرّفُه على فيسبوك وحالُه. **و`group_key` يجمع ما يُراجَع معاً** (دفعةٌ أو فكرةٌ بلغاتها) فيوافَق عليه بضغطةٍ واحدة.

## الحالُ سلّمٌ واحد، **والمرفوضُ لا يُنشر أبداً**

`pending_review` ← (`approved` ← `scheduled` ← `published`) أو `changes_requested` أو `rejected`؛ و`failed` حين يردّ فيسبوك
بخطأ. **والموافقةُ وحدَها تُطلق الجدولة**؛ والجدولةُ تُنشئ المنشورَ على فيسبوك **غيرَ منشورٍ بموعده** فينشره فيسبوك وحدَه ولو
لم تكن جلسة. **ولا حذفَ على فيسبوك من هنا** (قاعدةُ المالك «لا يُحذف منشور»): ما صار مجدولاً هناك لا يُرفض من القناة.

## ولا مالَ هنا

جدولان جديدان للصفحة وحدَها، **لا مفتاحَ أجنبيّاً إلى غير `users`**، ولا عمودَ مال.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import FacebookPostStatus

#: سلّمُ الحال — **نصٌّ بقيدٍ لا نوعَ تعداد** في القاعدة: الحالُ تخصّ هذه القناةَ وحدَها، وإضافةُ حالٍ غداً قيدٌ يُبدَّل لا نوعٌ يُوسَّع.
POST_STATUSES = tuple(FacebookPostStatus)
#: الصيغةُ: صورةٌ واحدة، أو دوّارُ صور، أو فيديو
POST_KINDS = ("photo", "carousel", "video")
#: لغةُ المنشور: العربيّةُ الفصحى، والفرنسيّة، والدارجةُ الجزائريّة، والإنجليزيّة
POST_LANGS = ("ar", "fr", "dz", "en")
REQUEST_STATUSES = ("open", "done")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


class FacebookPost(UUIDMixin, TimestampMixin, Base):
    """منشورٌ واحدٌ بلغةٍ واحدة على صفحة «Taxo»."""

    __tablename__ = "facebook_posts"
    __table_args__ = (
        CheckConstraint(_in("status", POST_STATUSES), name="ck_facebook_posts_status"),
        CheckConstraint(_in("kind", POST_KINDS), name="ck_facebook_posts_kind"),
        CheckConstraint(_in("lang", POST_LANGS), name="ck_facebook_posts_lang"),
        # **منشورُ فيسبوك الواحدُ صفٌّ واحد** — فالمزامنةُ تُحدِّث ولا تكرّر
        UniqueConstraint("fb_post_id", name="uq_facebook_posts_fb_post_id"),
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    caption: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    lang: Mapped[str] = mapped_column(String(4), nullable=False, default="ar", server_default="ar")
    kind: Mapped[str] = mapped_column(String(12), nullable=False, default="photo", server_default="photo")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending_review", server_default="pending_review", index=True)
    #: يجمع ما يُراجَع معاً (دفعةٌ أو فكرةٌ بلغاتها) — موافقةٌ جماعيّةٌ بضغطة
    group_key: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    #: الموعدُ المقترح ثمّ المجدول — **بالتوقيت العالميّ**، واللوحةُ تعرضه بتوقيت الجزائر
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    #: ملفّاتُ الوسائط في `core.storage` (مجلّد `facebook`) بترتيبها
    media_paths: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    #: صورةٌ مصغّرةٌ للعرض — رابطُ فيسبوك لما استُورد منه، أو لا شيء لما رُفع هنا (تُعرض من التخزين)
    preview_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: ملاحظةُ المراجع مع «اطلب تعديلاً» أو «ارفض»
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: معرّفُ المنشور على فيسبوك (`{page}_{post}`) بعد الجدولة
    fb_post_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    permalink: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: آخرُ خطأٍ من فيسبوك بنصّه — **بلا رمز**: يُكتب بعد `graph.scrub`
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: أرقامُ التفاعل من آخر مزامنة: الإعجاباتُ والتعليقاتُ والمشاركاتُ والوصول
    stats: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    stats_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FacebookPostRequest(UUIDMixin, TimestampMixin, Base):
    """«اطلب منشوراتٍ جديدة» — طلبٌ من المالك بنصّه، يُقرأ ويُنفَّذ ثم يُعلَّم منجَزاً."""

    __tablename__ = "facebook_post_requests"
    __table_args__ = (CheckConstraint(_in("status", REQUEST_STATUSES), name="ck_facebook_post_requests_status"),)

    body: Mapped[str] = mapped_column(Text, nullable=False)
    #: كم منشوراً يطلب (اختياريّ)
    count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(8), nullable=False, default="open", server_default="open")
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    #: ما فُعل به — يكتبه من نفّذه
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)

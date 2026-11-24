"""**حملةُ إطلاق الكباتن** (أمرُ المالك ٢٠٢٦-١١-٢٤ السادس، الجزء ج؛ SPEC §١١٤-ج) — الترحيلة `0190`.

من اعتُمد **قبل** يوم الإطلاق: `pre_launch_free_days` يوماً مجّانيّةً بصفر عمولة **تبدأ يومَ الإطلاق**؛ ومن اعتُمد **بعده**:
`post_launch_free_days` **تبدأ من اعتماده**. **ومنحةٌ واحدةٌ لكلِّ كبتن** (`launch_campaign_grants.driver_id` فريد) — والاشتراكُ نفسُه صفٌّ
في `driver_subscriptions` بمبلغ صفرٍ وعمولة صفر، وقيدُ تدقيقٍ يقول لماذا. **والمفتاحُ مطفأٌ حتى يؤكّد المالك.**
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode

GRANT_PRE = "pre"
GRANT_POST = "post"


class LaunchCampaign(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "launch_campaigns"
    __table_args__ = (
        UniqueConstraint("country_code", name="uq_launch_campaigns_country"),
        CheckConstraint(
            "pre_launch_free_days BETWEEN 0 AND 365 AND post_launch_free_days BETWEEN 0 AND 365",
            name="launch_campaign_days",
        ),
    )

    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    #: **يومُ الإطلاق بتوقيت الدولة** — منتصفُ ليله بداية الأيّام المجّانيّة لمن سبقه
    launch_date: Mapped[date] = mapped_column(
        Date, nullable=False, default=date(2027, 1, 1), server_default=text("'2027-01-01'")
    )
    pre_launch_free_days: Mapped[int] = mapped_column(Integer, nullable=False, default=60, server_default=text("60"))
    post_launch_free_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7, server_default=text("7"))
    zero_commission: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    show_banner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))


class LaunchCampaignGrant(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "launch_campaign_grants"
    __table_args__ = (
        CheckConstraint("kind IN ('pre', 'post')", name="launch_campaign_grant_kind"),
        CheckConstraint("ends_at > starts_at", name="launch_campaign_grant_span"),
    )

    driver_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("drivers.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("driver_subscriptions.id", ondelete="RESTRICT"), nullable=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

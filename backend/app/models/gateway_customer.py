"""**عميلُ الدافع عند الوسيط** (SPEC §٧٦-ع/٢، أمرُ المالك ٢٠٢٦-١٠-١٧) — معرّفُه عند Chargily لمستخدم TAXO.

**لمَ يُحفظ**: صفحةُ Chargily تسأل الدافعَ اسمَه وبريدَه وهاتفَه في كلِّ دفعة؛ **وعميلٌ يُنشأ مرّةً ويُمرَّر معرّفُه** يُغني عن ذلك. **ولكلِّ
وضعٍ عميلُه** (`livemode`): مفتاحُ التجربة لا يرى عملاءَ المفتاح الحيّ ولا العكس.

**ولا مالَ هنا ولا بيانات**: المعرّفُ وحدَه — الاسمُ والهاتفُ عند صاحبهما في `users` وعند Chargily.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class GatewayCustomer(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "gateway_customers"
    __table_args__ = (
        UniqueConstraint("user_id", "integration", "livemode", name="uq_gateway_customers_user_integration_mode"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: اسمُ المحوِّل (`chargily`) — كما في `pay_methods.integration`
    integration: Mapped[str] = mapped_column(String(32), nullable=False)
    #: **عميلُ المفتاح الحيّ أم مفتاحِ التجربة** — لكلٍّ عملاؤه عند Chargily
    livemode: Mapped[bool] = mapped_column(Boolean, nullable=False)
    external_id: Mapped[str] = mapped_column(String(64), nullable=False)

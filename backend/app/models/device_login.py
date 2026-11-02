"""الدخولُ بالبصمة بعد الخروج (أمرُ المالك ٢٠٢٦-١١-٠٢) — **بيانُ جهازٍ يُصرف ببصمة، لا كلمةُ مرور ولا رمزُ جلسة**.

الخروجُ يُنهي الجلسةَ على الخادم كما كان (`token_service.revoke_session`)، **فرمزُ التجديد لا يصلح بعده للبصمة**. فلكلِّ جهازٍ
أشعل صاحبُه البصمةَ **سرٌّ عشوائيٌّ يسكن مخزنَ الجهاز الآمن** (Keystore على أندرويد)، **ولا يُقرأ إلا بعد أن تصدق البصمة**،
ويُقدَّم إلى `POST /auth/device-login` بدلَ كلمة المرور فتُفتح جلسةٌ جديدة.

- **في القاعدة بصمتُه لا هو** (`secret_hash`، sha256 لسرٍّ عشوائيٍّ بـ٢٥٦ بتّاً — لا قاموسَ يُخمَّن به فلا يلزمه ملح).
- **ويُدوَّر في كلِّ دخول**: السرُّ المصروفُ لا يعود.
- **ويُبطَل ختماً لا حذفاً** في كلِّ ما يُبطل الجلسات كلَّها — تغييرُ كلمة المرور واستعادتُها، والحظرُ، وطلبُ الحذف، وإنهاءُ الكلّ
  (`token_service.revoke_all_for_user`) — **وفي «الدخول بحساب آخر»**. **والخروجُ العاديُّ لا يمسّه**: هو ما بُني لأجله.
- **وحسابٌ بعاملٍ ثانٍ لا يُعطاه**: البصمةُ تقوم مقامَ كلمة المرور وحدَها، فلا تُغني عن العامل الثاني.

**و`ON DELETE CASCADE`** كالجلسات: بيانُ دخولٍ لا سجلٌّ محاسبيّ.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class DeviceLogin(UUIDMixin, Base):
    __tablename__ = "device_logins"
    __table_args__ = (
        # **بيانٌ حيٌّ واحدٌ لكلِّ (حساب، جهاز، تطبيق)** — الإشعالُ الثاني يُبطل الأوّلَ ولا يجاوره
        Index(
            "device_logins_live_unique",
            "user_id",
            "device_id",
            "app",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: مُعرِّفُ الجهاز نفسُه الذي تُسجَّل به الإشعاراتُ (`lib/device.ts`)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False)
    #: `rider` · `driver` — **لكلِّ تطبيقٍ بيانُه**، كما لكلٍّ مخزنُه الآمن
    app: Mapped[str] = mapped_column(String(8), nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)

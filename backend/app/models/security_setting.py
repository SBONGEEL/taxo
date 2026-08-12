"""سياسةُ دخول اللوحة — **صفٌّ واحدٌ عالمي** (SPEC القسم 14.1، المرحلة 12-د).

**عالميٌّ لا per-country** خلافاً لكل جداول الإعدادات في هذا المشروع: أمنُ لوحةٍ
مكتبية ليس سياسةَ سوق، ولا شيءَ في القسم 14 per-country. **والأخطرُ أن
per-country يفتح ثقباً**: حسابُ المشرف في دولةٍ واحدة واللوحةُ تخدم السوقين،
فإلزامٌ يُقرأ من دولة الحساب يُتجاوَز بحسابٍ دولتُه الأخرى.

**والافتراضُ `false` عكسَ `DEFAULT_ENABLED_FLAGS`، وليس نقضاً لها**: قاعدةُ
«غيابُ صفِّ حارسٍ يعني مفعّلاً» وُضعت حيث السكوتُ **يُطفئ** حماية. وهنا السكوتُ
لا يطفئ شيئاً بل **يُشعل قفلاً على بابٍ لا مفتاح له**: صفٌّ مفقودٌ يُقرأ
«إلزام» يقفل كلَّ مشرفٍ خارج اللوحة ولا أحدَ يستطيع إطفاءه من داخلها. والإلزامُ
فعلُ مالكٍ صريحٌ لا حالةٌ تقع بالسكوت.
"""

from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, Integer, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin

DEFAULT_IDLE_TIMEOUT_MINUTES = 30

# **السقفُ الأقصى في الكود لا في يد المشرف** (قرار المالك): اللوحة تفتح مفاتيح
# المزوّدين والدفع، فمهلةٌ يوسّعها مشرفٌ إلى يومٍ تُبطل الحارسَ من داخله. والحدُّ
# الأدنى ليس تجميلاً: مهلةُ دقيقةٍ تُخرج المشرفَ وهو يكتب، فيصير الحارسُ عطلاً
# يُطفأ لا حارساً يُحتمل.
MIN_IDLE_TIMEOUT_MINUTES = 5
MAX_IDLE_TIMEOUT_MINUTES = 60


class SecuritySetting(UUIDMixin, TimestampMixin, Base):
    """سياسةُ الدخول الإداري — صفٌّ واحدٌ يحرسه `singleton`."""

    __tablename__ = "security_settings"
    __table_args__ = (
        # صفٌّ واحدٌ لا أكثر: العمودُ ثابتُ القيمة وفريد، فالصفُّ الثاني يرتدّ
        # من القاعدة لا من نيّة المستدعي
        CheckConstraint("singleton IS TRUE", name="security_settings_singleton"),
        CheckConstraint(
            f"admin_idle_timeout_minutes BETWEEN {MIN_IDLE_TIMEOUT_MINUTES} "
            f"AND {MAX_IDLE_TIMEOUT_MINUTES}",
            name="security_idle_timeout_range",
        ),
    )

    # الافتراضات في القاعدة أيضاً لا في بايثون وحدها (كما `saved_places.icon`):
    # صفٌّ يُدخَل من `psql` في عطلٍ ليلاً يجب أن يخرج آمناً لا مُلزِماً
    singleton: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true"), default=True, unique=True
    )
    admin_totp_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), default=False
    )
    admin_idle_timeout_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text(str(DEFAULT_IDLE_TIMEOUT_MINUTES)),
        default=DEFAULT_IDLE_TIMEOUT_MINUTES,
    )

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return (
            f"<SecuritySetting totp_required={self.admin_totp_required} "
            f"idle={self.admin_idle_timeout_minutes}m>"
        )

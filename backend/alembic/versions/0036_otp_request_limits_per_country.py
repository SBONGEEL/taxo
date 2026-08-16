"""otp request limits per country

سقوفُ طلب رمز التحقق per-country (قرارُ المالك 2026-08-16): جدولٌ واحدٌ بسبعة
أرقام — نافذةٌ قصيرة، ويوميّ، وعمرُ تسجيل، وانتظارٌ بعد الاستنفاد، ومهلةُ إعادةٍ
تتزايد بأساسها وسقفها.

**والعدّاداتُ نفسُها ليست هنا**: تعيش في Redis (`services/otp_limits.py`) لأنها
عدّاداتُ نافذةٍ تنتهي بنفسها — صفٌّ في القاعدة لكل طلبِ رمزٍ جدولٌ ينمو بلا
قارئ. وهذا الجدولُ **السياسةُ** وحدها.

**وقيمُه الافتراضيةُ حارسةٌ لا مفتوحة**: هذه سقوفٌ تحمي، وغيابُ ضبطٍ يجب أن
يحمي لا أن يفتح — عكسُ قاعدة «غيابُ الصف = ميزةٌ معطّلة»، ولنفس سببها.

Revision ID: 0036
Revises: 0035
Create Date: 2026-08-16 13:46:15.642629
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# النوعُ أنشأته ترحيلةٌ سابقة — و`create_type=False` يمنع «type already exists»
COUNTRY = postgresql.ENUM("LY", "JO", name="country_code", create_type=False)


revision: str = '0036'
down_revision: str | None = '0035'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('otp_settings',
    sa.Column('country_code', COUNTRY, nullable=False),
    sa.Column('window_minutes', sa.Integer(), server_default=sa.text('60'), nullable=False),
    sa.Column('max_per_window', sa.Integer(), server_default=sa.text('5'), nullable=False),
    sa.Column('max_per_day', sa.Integer(), server_default=sa.text('10'), nullable=False),
    sa.Column('max_per_registration', sa.Integer(), server_default=sa.text('10'), nullable=False),
    sa.Column('lockout_minutes', sa.Integer(), server_default=sa.text('60'), nullable=False),
    sa.Column('resend_base_seconds', sa.Integer(), server_default=sa.text('30'), nullable=False),
    sa.Column('resend_max_seconds', sa.Integer(), server_default=sa.text('600'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('country_code', name=op.f('pk_otp_settings'))
    )


def downgrade() -> None:
    op.drop_table('otp_settings')

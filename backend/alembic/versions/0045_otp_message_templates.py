"""قوالبُ رسالة رمز التحقق — جدولٌ عالميٌّ بصفٍّ لكل غرض.

**بلا عمود دولة، وذلك قرارٌ لا سهو** (المالك، 2026-08-19): عقدُ واتساب عالميٌّ
ورقمٌ واحدٌ يخدم السوقين، فالقالبُ صفةُ الرقم لا صفةُ السوق. وشرطُ ما يبطله
مكتوبٌ في `app/models/otp_template.py`.

Revision ID: 0045
Revises: 0044
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "otp_message_templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column("purpose", sa.String(32), nullable=False, unique=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "updated_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    # **ولا تُبذر صفوفٌ هنا**: غيابُ الصفّ يقرأ «لم يُحرَّر بعد» ويُستعمل النصُّ
    # المدمج في `services/otp_templates.py` — وصفٌّ مبذورٌ يجعل «الافتراضي»
    # قيمةً في جدولٍ يمكن أن تُحرَّر إلى فراغ، فيضيع الافتراضيُّ الحقيقي.


def downgrade() -> None:
    op.drop_table("otp_message_templates")

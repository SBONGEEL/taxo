"""driver document files and user notification inbox

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-10 16:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '0014'
down_revision: str | None = '0013'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---------------------------------------------------- مستندات الكبتن
    # الجدول قائم منذ `0002` ولم يكن له مسارٌ يكتبه (المرحلة 9-ب). العمودان
    # الجديدان يصفان الملف كما استُنتج من **بايتاته** لا من ترويسة العميل،
    # فتُخدم القراءة بلا استنتاجٍ ثانٍ في كل طلب.
    #
    # `server_default` مؤقت: الجدول فارغ في كل بيئة (لا مسار كان يكتبه)،
    # لكن العمود NOT NULL على جدولٍ قائم يحتاج قيمةً للصفوف الموجودة — ثم
    # يُرفع الافتراضي فلا يمر صفٌّ جديد بلا نوعٍ وحجمٍ حقيقيين.
    op.add_column(
        'driver_documents',
        sa.Column(
            'content_type',
            sa.String(length=100),
            nullable=False,
            server_default='application/octet-stream',
        ),
    )
    op.add_column(
        'driver_documents',
        sa.Column('size_bytes', sa.Integer(), nullable=False, server_default='0'),
    )
    op.alter_column('driver_documents', 'content_type', server_default=None)
    op.alter_column('driver_documents', 'size_bytes', server_default=None)

    # صفٌّ واحد لكل نوع: رفعُ نفس النوع مرةً أخرى استبدالٌ لا صفٌّ ثانٍ —
    # وإلا صار سؤال «هل رخصتُه مقبولة؟» بلا جواب واحد
    op.create_unique_constraint(
        'uq_driver_documents_driver_doc_type',
        'driver_documents',
        ['driver_id', 'doc_type'],
    )

    # ------------------------------------------------- صندوق وارد المستخدم
    # أثرٌ دائم لإشعارٍ كان عابراً: قبله كانت `services/notifications.py`
    # تبثّ وتبعث ثم تنسى، فمن أُغلق تطبيقُه ساعةً لا يعرف ما جرى.
    op.create_table(
        'user_notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        # نصٌّ لا ENUM: الأنواع تُضاف مع كل حدثٍ جديد، وترحيلةٌ لكل نصٍّ
        # جديد ثمنٌ بلا مقابل — نفس اعتبار `feature_flags.feature_key`
        sa.Column('kind', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=120), nullable=False),
        sa.Column('body', sa.String(length=500), nullable=False),
        sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        # سجلُّ عرضٍ لا سجلٌّ مالي: يذهب مع صاحبه كما `device_tokens`
        sa.ForeignKeyConstraint(
            ['user_id'],
            ['users.id'],
            name=op.f('fk_user_notifications_user_id_users'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_user_notifications')),
    )
    # القراءة دائماً «إشعارات فلانٍ أحدثُها أولاً»
    op.create_index(
        'ix_user_notifications_user_id_created_at',
        'user_notifications',
        ['user_id', 'created_at'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        'ix_user_notifications_user_id_created_at', table_name='user_notifications'
    )
    op.drop_table('user_notifications')

    op.drop_constraint(
        'uq_driver_documents_driver_doc_type', 'driver_documents', type_='unique'
    )
    op.drop_column('driver_documents', 'size_bytes')
    op.drop_column('driver_documents', 'content_type')

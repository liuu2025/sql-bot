"""073_ai_model_preset

模型配置方案表：保存「服务地址 + 密钥 + 模型」的多份命名快照，
支持一键切换，避免在官方与中转站之间反复重填。

Revision ID: d41a7c9b25e8
Revises: f898322341a5

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

# revision identifiers, used by Alembic.
revision = 'd41a7c9b25e8'
down_revision = 'f898322341a5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ai_model_preset',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('supplier', sa.Integer(), nullable=False),
        sa.Column('model_type', sa.Integer(), nullable=False),
        sa.Column('base_model', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('api_domain', sa.Text(), nullable=False),
        sa.Column('api_key', sa.Text(), nullable=True),
        sa.Column('protocol', sa.Integer(), nullable=False),
        sa.Column('config', sa.Text(), nullable=False),
        sa.Column('create_time', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('ai_model_preset')

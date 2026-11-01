"""001_ddl

Revision ID: 5348b743b05f
Revises: 
Create Date: 2025-04-25 16:26:19.135926

"""


# revision identifiers, used by Alembic.
revision = '5348b743b05f'
down_revision = None
branch_labels = None
depends_on = None


from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.sql import table, column
from sqlalchemy import String, Integer, BigInteger
import hashlib
import os
def upgrade():
    # Never commit a reusable bootstrap password. The local deployment must
    # provide DEFAULT_PWD through its private environment configuration.
    default_password = os.environ.get("DEFAULT_PWD", "")
    if not default_password:
        raise RuntimeError("DEFAULT_PWD must be set before initializing SQLBot")
    default_password_hash = hashlib.md5(default_password.encode("utf-8")).hexdigest()

    op.create_table(
        'sys_user',
        sa.Column('id', sa.BIGINT, primary_key=True),
        sa.Column('account', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('password', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255)),
        sa.Column('oid', sa.BIGINT, nullable=False),
        sa.Column('status', sa.Integer, nullable=False),
        sa.Column('create_time', sa.BIGINT, nullable=False),
    )
    
    accounts_table = table(
        "sys_user",
        column("id", BigInteger),
        column("account", String),
        column("name", String),
        column("password", String),
        column("email", String),
        column("oid", BigInteger),
        column("status", Integer),
        column("create_time", BigInteger),
    )

    op.bulk_insert(
        accounts_table,
        [
            {
                "id": 1,
                "account": "admin",
                "name": "Administrator",
                "password": default_password_hash,
                "email": "admin@example.invalid",
                "oid": 1,
                "status": 1,
                "create_time": 1672531199000
            }
        ]
    )

def downgrade():
    op.drop_table('sys_user')

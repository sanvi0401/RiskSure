"""Widen columns that overflowed on PostgreSQL.

Encrypted TOTP secrets are ~100 characters (VARCHAR(64) was too small) and
policy documents can exceed 500 characters.
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_widen_secret_columns"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.alter_column("totp_secret", type_=sa.String(255), existing_nullable=True)
        batch.alter_column("totp_pending_secret", type_=sa.String(255), existing_nullable=True)
    with op.batch_alter_table("policies") as batch:
        batch.alter_column("terms_document", type_=sa.Text(), existing_nullable=True)


def downgrade():
    with op.batch_alter_table("policies") as batch:
        batch.alter_column("terms_document", type_=sa.String(500), existing_nullable=True)
    with op.batch_alter_table("users") as batch:
        batch.alter_column("totp_pending_secret", type_=sa.String(64), existing_nullable=True)
        batch.alter_column("totp_secret", type_=sa.String(64), existing_nullable=True)

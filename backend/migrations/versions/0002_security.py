"""Security schema updates: token invalidation and wider encrypted/document fields."""
from alembic import op
import sqlalchemy as sa

revision = "0002_security"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))
        batch.alter_column("totp_secret", existing_type=sa.String(length=64), type_=sa.String(length=255), existing_nullable=True)
        batch.alter_column("totp_pending_secret", existing_type=sa.String(length=64), type_=sa.String(length=255), existing_nullable=True)
    with op.batch_alter_table("policies") as batch:
        batch.alter_column("terms_document", existing_type=sa.String(length=500), type_=sa.Text(), existing_nullable=True)

def downgrade():
    with op.batch_alter_table("policies") as batch:
        batch.alter_column("terms_document", existing_type=sa.Text(), type_=sa.String(length=500), existing_nullable=True)
    with op.batch_alter_table("users") as batch:
        batch.alter_column("totp_pending_secret", existing_type=sa.String(length=255), type_=sa.String(length=64), existing_nullable=True)
        batch.alter_column("totp_secret", existing_type=sa.String(length=255), type_=sa.String(length=64), existing_nullable=True)
        batch.drop_column("token_version")

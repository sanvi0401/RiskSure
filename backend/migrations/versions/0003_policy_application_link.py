"""Link policies back to the application that produced them."""
from alembic import op
import sqlalchemy as sa

revision = "0003_policy_application_link"
down_revision = ("0002_security", "0002_widen_secret_columns")
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("policies") as batch:
        batch.add_column(sa.Column("application_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_policies_application_id", "applications", ["application_id"], ["id"])
        batch.create_index("ix_policies_application_id", ["application_id"])


def downgrade():
    with op.batch_alter_table("policies") as batch:
        batch.drop_index("ix_policies_application_id")
        batch.drop_constraint("fk_policies_application_id", type_="foreignkey")
        batch.drop_column("application_id")

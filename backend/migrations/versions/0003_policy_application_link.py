"""Link policies back to the application that produced them."""
from alembic import op
import sqlalchemy as sa

revision = "0003_policy_application_link"
down_revision = ("0002_security", "0002_widen_secret_columns")
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("policies")}
    indexes = {index["name"] for index in inspector.get_indexes("policies")}
    linked = any(foreign_key["constrained_columns"] == ["application_id"]
                 for foreign_key in inspector.get_foreign_keys("policies"))
    with op.batch_alter_table("policies") as batch:
        if "application_id" not in columns:
            batch.add_column(sa.Column("application_id", sa.Integer(), nullable=True))
        if not linked:
            batch.create_foreign_key("fk_policies_application_id", "applications", ["application_id"], ["id"])
        if "ix_policies_application_id" not in indexes:
            batch.create_index("ix_policies_application_id", ["application_id"])


def downgrade():
    with op.batch_alter_table("policies") as batch:
        batch.drop_index("ix_policies_application_id")
        batch.drop_constraint("fk_policies_application_id", type_="foreignkey")
        batch.drop_column("application_id")

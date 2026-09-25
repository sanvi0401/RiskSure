"""Initial RiskSure schema migration.

This revision mirrors the SQLAlchemy models currently in production.
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("users",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("email",sa.String(255),nullable=False),
        sa.Column("password_hash",sa.String(255),nullable=False),
        sa.Column("role",sa.String(40),nullable=False),
        sa.Column("totp_secret",sa.String(64)),
        sa.Column("totp_enabled",sa.Boolean(),nullable=False),
        sa.Column("recovery_codes_hash",sa.Text()),
        sa.Column("totp_pending_secret",sa.String(64)),
        sa.Column("recovery_codes_used",sa.Text()),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),
    )
    op.create_index("ix_users_email","users",["email"],unique=True); op.create_index("ix_users_role","users",["role"])
    op.create_table("customer_profiles",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),sa.Column("full_name",sa.String(160),nullable=False),sa.Column("phone",sa.String(30)),sa.Column("date_of_birth",sa.Date()),sa.Column("address",sa.Text()),sa.Column("city",sa.String(100)),sa.Column("state",sa.String(100)),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_customer_profiles_user_id","customer_profiles",["user_id"],unique=True)
    op.create_table("providers",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id")),sa.Column("provider_type",sa.String(40),nullable=False),sa.Column("name",sa.String(180),nullable=False),sa.Column("license_number",sa.String(100)),sa.Column("phone",sa.String(30)),sa.Column("address",sa.Text()),sa.Column("city",sa.String(100)),sa.Column("state",sa.String(100)),sa.Column("status",sa.String(30),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_providers_user_id","providers",["user_id"],unique=True);op.create_unique_constraint("uq_providers_license","providers",["license_number"])
    op.create_table("policies",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("policy_number",sa.String(80),nullable=False),sa.Column("customer_id",sa.Integer(),sa.ForeignKey("customer_profiles.id"),nullable=False),sa.Column("provider_id",sa.Integer(),sa.ForeignKey("providers.id")),sa.Column("policy_type",sa.String(80),nullable=False),sa.Column("status",sa.String(30),nullable=False),sa.Column("coverage_limit",sa.Float(),nullable=False),sa.Column("premium_amount",sa.Float(),nullable=False),sa.Column("start_date",sa.Date()),sa.Column("end_date",sa.Date()),sa.Column("terms_document",sa.String(500)),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_unique_constraint("uq_policies_number","policies",["policy_number"]);op.create_index("ix_policies_number","policies",["policy_number"]);op.create_index("ix_policies_customer","policies",["customer_id"])
    op.create_table("applications",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("customer_id",sa.Integer(),sa.ForeignKey("customer_profiles.id")),sa.Column("name",sa.String(120),nullable=False),sa.Column("age",sa.Integer()),sa.Column("sex",sa.String(20)),sa.Column("bmi",sa.Float()),sa.Column("children",sa.Integer()),sa.Column("smoker",sa.String(20)),sa.Column("region",sa.String(30)),sa.Column("risk_score",sa.Float(),nullable=False),sa.Column("rule_adjustment",sa.Float(),nullable=False),sa.Column("final_risk",sa.Float(),nullable=False),sa.Column("decision",sa.String(50),nullable=False),sa.Column("premium",sa.Float(),nullable=False),sa.Column("review_status",sa.String(40),nullable=False),sa.Column("decision_reason",sa.Text()),sa.Column("reviewed_at",sa.DateTime(timezone=True)),sa.Column("assigned_underwriter_id",sa.Integer(),sa.ForeignKey("users.id")),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_applications_customer","applications",["customer_id"])
    op.create_table("claims",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("claim_number",sa.String(80),nullable=False),sa.Column("customer_id",sa.Integer(),sa.ForeignKey("customer_profiles.id"),nullable=False),sa.Column("policy_id",sa.Integer(),sa.ForeignKey("policies.id"),nullable=False),sa.Column("provider_id",sa.Integer(),sa.ForeignKey("providers.id")),sa.Column("status",sa.String(40),nullable=False),sa.Column("claimed_amount",sa.Float(),nullable=False),sa.Column("approved_amount",sa.Float()),sa.Column("assigned_officer_id",sa.Integer(),sa.ForeignKey("users.id")),sa.Column("incident_date",sa.Date()),sa.Column("description",sa.Text()),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_claims_claim_number","claims",["claim_number"],unique=True);op.create_index("ix_claims_customer","claims",["customer_id"]);op.create_index("ix_claims_policy","claims",["policy_id"])
    op.create_table("billing_transactions",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("customer_id",sa.Integer(),sa.ForeignKey("customer_profiles.id"),nullable=False),sa.Column("policy_id",sa.Integer(),sa.ForeignKey("policies.id")),sa.Column("claim_id",sa.Integer(),sa.ForeignKey("claims.id")),sa.Column("transaction_type",sa.String(40),nullable=False),sa.Column("amount",sa.Float(),nullable=False),sa.Column("status",sa.String(30),nullable=False),sa.Column("reference",sa.String(120)),sa.Column("description",sa.Text()),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_unique_constraint("uq_billing_reference","billing_transactions",["reference"]);op.create_index("ix_billing_customer","billing_transactions",["customer_id"])
    op.create_table("audit_logs",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id")),sa.Column("action",sa.String(120),nullable=False),sa.Column("entity_type",sa.String(80)),sa.Column("entity_id",sa.Integer()),sa.Column("details",sa.Text()),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_audit_user","audit_logs",["user_id"])

def downgrade():
    for table in ["audit_logs","billing_transactions","claims","applications","policies","providers","customer_profiles","users"]:
        op.drop_table(table)

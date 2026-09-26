from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from database import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(40), nullable=False, default="customer", index=True)
    totp_secret = db.Column(db.String(64), nullable=True)
    totp_enabled = db.Column(db.Boolean, nullable=False, default=False)
    recovery_codes_hash = db.Column(db.Text, nullable=True)
    totp_pending_secret = db.Column(db.String(64), nullable=True)
    recovery_codes_used = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "totp_enabled": self.totp_enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CustomerProfile(db.Model):
    __tablename__ = "customer_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    full_name = db.Column(db.String(160), nullable=False)
    phone = db.Column(db.String(30))
    date_of_birth = db.Column(db.Date)
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", backref=db.backref("customer_profile", uselist=False))


class Provider(db.Model):
    __tablename__ = "providers"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=True)
    provider_type = db.Column(db.String(40), nullable=False, default="hospital")
    name = db.Column(db.String(180), nullable=False)
    license_number = db.Column(db.String(100), unique=True)
    phone = db.Column(db.String(30))
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    status = db.Column(db.String(30), nullable=False, default="active")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", backref=db.backref("provider_profile", uselist=False))


class Policy(db.Model):
    __tablename__ = "policies"

    id = db.Column(db.Integer, primary_key=True)
    policy_number = db.Column(db.String(80), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer_profiles.id"), nullable=False, index=True)
    provider_id = db.Column(db.Integer, db.ForeignKey("providers.id"), nullable=True)
    policy_type = db.Column(db.String(80), nullable=False, default="health")
    status = db.Column(db.String(30), nullable=False, default="active")
    coverage_limit = db.Column(db.Float, nullable=False, default=0.0)
    premium_amount = db.Column(db.Float, nullable=False, default=0.0)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    terms_document = db.Column(db.String(500))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    customer = db.relationship("CustomerProfile", backref="policies")
    provider = db.relationship("Provider", backref="policies")


class Application(db.Model):
    __tablename__ = "applications"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer_profiles.id"), nullable=True, index=True)
    name = db.Column(db.String(120), nullable=False, default="Unknown")
    age = db.Column(db.Integer)
    sex = db.Column(db.String(20))
    bmi = db.Column(db.Float)
    children = db.Column(db.Integer)
    smoker = db.Column(db.String(20))
    region = db.Column(db.String(30))
    risk_score = db.Column(db.Float, nullable=False, default=0.0)
    rule_adjustment = db.Column(db.Float, nullable=False, default=0.0)
    final_risk = db.Column(db.Float, nullable=False, default=0.0)
    decision = db.Column(db.String(50), nullable=False, default="Unknown")
    premium = db.Column(db.Float, nullable=False, default=0.0)
    review_status = db.Column(db.String(40), nullable=False, default="pending")
    decision_reason = db.Column(db.Text, nullable=True)
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    assigned_underwriter_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    customer = db.relationship("CustomerProfile", backref="applications")
    assigned_underwriter = db.relationship("User", foreign_keys=[assigned_underwriter_id])


    def to_dict(self):
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "name": self.name,
            "age": self.age,
            "sex": self.sex,
            "bmi": self.bmi,
            "children": self.children,
            "smoker": self.smoker,
            "region": self.region,
            "risk_score": self.risk_score,
            "rule_adjustment": self.rule_adjustment,
            "final_risk": self.final_risk,
            "decision": self.decision,
            "premium": self.premium,
            "review_status": self.review_status,
            "decision_reason": self.decision_reason,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "assigned_underwriter_id": self.assigned_underwriter_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Claim(db.Model):
    __tablename__ = "claims"

    id = db.Column(db.Integer, primary_key=True)
    claim_number = db.Column(db.String(80), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer_profiles.id"), nullable=False, index=True)
    policy_id = db.Column(db.Integer, db.ForeignKey("policies.id"), nullable=False, index=True)
    provider_id = db.Column(db.Integer, db.ForeignKey("providers.id"), nullable=True)
    status = db.Column(db.String(40), nullable=False, default="submitted")
    claimed_amount = db.Column(db.Float, nullable=False, default=0.0)
    approved_amount = db.Column(db.Float, nullable=True)
    assigned_officer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    incident_date = db.Column(db.Date)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    customer = db.relationship("CustomerProfile", backref="claims")
    policy = db.relationship("Policy", backref="claims")
    provider = db.relationship("Provider", backref="claims")
    assigned_officer = db.relationship("User", foreign_keys=[assigned_officer_id])


class BillingTransaction(db.Model):
    __tablename__ = "billing_transactions"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer_profiles.id"), nullable=False, index=True)
    policy_id = db.Column(db.Integer, db.ForeignKey("policies.id"), nullable=True)
    claim_id = db.Column(db.Integer, db.ForeignKey("claims.id"), nullable=True)
    transaction_type = db.Column(db.String(40), nullable=False)
    amount = db.Column(db.Float, nullable=False, default=0.0)
    status = db.Column(db.String(30), nullable=False, default="pending")
    reference = db.Column(db.String(120), unique=True)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    customer = db.relationship("CustomerProfile", backref="billing_transactions")
    policy = db.relationship("Policy", backref="billing_transactions")
    claim = db.relationship("Claim", backref="billing_transactions")


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    action = db.Column(db.String(120), nullable=False)
    entity_type = db.Column(db.String(80))
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", backref="audit_logs")

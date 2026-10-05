from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from database import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(40), nullable=False, default="customer")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    first_name = db.Column(db.String(120), default="")
    last_name = db.Column(db.String(120), default="")
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    applications = db.relationship("Application", back_populates="user", cascade="all, delete-orphan")
    audit_logs = db.relationship("AuditLog", back_populates="user")
    underwriter_assignments = db.relationship("UnderwriterAssignment", back_populates="underwriter")
    decisions = db.relationship("UnderwritingDecision", foreign_keys="UnderwritingDecision.underwriter_id", back_populates="underwriter")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Application(db.Model):
    __tablename__ = "applications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False, default="Unknown")
    age = db.Column(db.Integer)
    sex = db.Column(db.String(20))
    bmi = db.Column(db.Float)
    children = db.Column(db.Integer)
    smoker = db.Column(db.String(20))
    region = db.Column(db.String(30))
    status = db.Column(db.String(32), nullable=False, default="draft")
    risk_category = db.Column(db.String(20), nullable=False, default="LOW")
    risk_score = db.Column(db.Float, nullable=False, default=0.0)
    rule_adjustment = db.Column(db.Float, nullable=False, default=0.0)
    final_risk = db.Column(db.Float, nullable=False, default=0.0)
    decision = db.Column(db.String(50), nullable=False, default="Unknown")
    premium = db.Column(db.Float, nullable=False, default=0.0)
    application_data = db.Column(db.JSON, default=dict)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship("User", back_populates="applications")
    decisions = db.relationship("UnderwritingDecision", back_populates="application", cascade="all, delete-orphan")
    assignments = db.relationship("UnderwriterAssignment", back_populates="application", cascade="all, delete-orphan")
    assessments = db.relationship("RiskAssessment", back_populates="application", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "age": self.age,
            "sex": self.sex,
            "bmi": self.bmi,
            "children": self.children,
            "smoker": self.smoker,
            "region": self.region,
            "status": self.status,
            "risk_category": self.risk_category,
            "risk_score": self.risk_score,
            "rule_adjustment": self.rule_adjustment,
            "final_risk": self.final_risk,
            "decision": self.decision,
            "premium": self.premium,
            "application_data": self.application_data or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class UnderwritingDecision(db.Model):
    __tablename__ = "underwriting_decisions"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("applications.id"), nullable=False, index=True)
    underwriter_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    decision = db.Column(db.String(30), nullable=False)
    reason = db.Column(db.String(255), nullable=False, default="")
    notes = db.Column(db.Text, default="")
    previous_status = db.Column(db.String(32), default="draft")
    new_status = db.Column(db.String(32), default="pending")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    application = db.relationship("Application", back_populates="decisions")
    underwriter = db.relationship("User", foreign_keys=[underwriter_id], back_populates="decisions")

    def to_dict(self):
        return {
            "id": self.id,
            "application_id": self.application_id,
            "underwriter_id": self.underwriter_id,
            "decision": self.decision,
            "reason": self.reason,
            "notes": self.notes,
            "previous_status": self.previous_status,
            "new_status": self.new_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class RiskAssessment(db.Model):
    __tablename__ = "risk_assessments"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("applications.id"), nullable=False, index=True)
    risk_score = db.Column(db.Float, nullable=False, default=0.0)
    risk_category = db.Column(db.String(20), nullable=False, default="LOW")
    premium = db.Column(db.Float, nullable=False, default=0.0)
    details = db.Column(db.JSON, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    application = db.relationship("Application", back_populates="assessments")

    def to_dict(self):
        return {
            "id": self.id,
            "application_id": self.application_id,
            "risk_score": self.risk_score,
            "risk_category": self.risk_category,
            "premium": self.premium,
            "details": self.details or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class UnderwriterAssignment(db.Model):
    __tablename__ = "underwriter_assignments"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("applications.id"), nullable=False, index=True)
    underwriter_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    assignment_status = db.Column(db.String(32), default="assigned")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    application = db.relationship("Application", back_populates="assignments")
    underwriter = db.relationship("User", back_populates="underwriter_assignments")

    def to_dict(self):
        return {
            "id": self.id,
            "application_id": self.application_id,
            "underwriter_id": self.underwriter_id,
            "assignment_status": self.assignment_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    role = db.Column(db.String(40), nullable=False, default="customer")
    action = db.Column(db.String(80), nullable=False)
    resource = db.Column(db.String(80), nullable=False)
    resource_id = db.Column(db.Integer, nullable=True)
    event_metadata = db.Column("metadata", db.JSON, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", back_populates="audit_logs")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "role": self.role,
            "action": self.action,
            "resource": self.resource,
            "resource_id": self.resource_id,
            "metadata": self.event_metadata or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

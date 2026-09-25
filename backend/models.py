from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from database import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(40), nullable=False, default="customer")
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Application(db.Model):
    __tablename__ = "applications"

    id = db.Column(db.Integer, primary_key=True)
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
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self):
        return {
            "id": self.id,
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
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

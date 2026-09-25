from datetime import datetime, timezone

from database import db


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

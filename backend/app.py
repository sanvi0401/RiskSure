from datetime import timedelta
import os
import sqlite3
from typing import Any, Dict

from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager, create_access_token, jwt_required

from database import db
from models import Application, AuditLog, RiskAssessment, UnderwriterAssignment, UnderwritingDecision, User
from services.ai_underwriter_service import ai_underwriter_service
from services.neo4j_service import neo4j_service
from services.risk_service import risk_service
from services.statistical_analysis_service import statistical_analysis_service

jwt = JWTManager()


def _log_event(user: User | None, action: str, resource: str, resource_id: int | None = None, **metadata):
    if user is None:
        return
    event = AuditLog(
        user_id=user.id,
        role=user.role,
        action=action,
        resource=resource,
        resource_id=resource_id,
        event_metadata=metadata,
    )
    db.session.add(event)
    db.session.commit()


def _current_user_from_jwt():
    from flask_jwt_extended import get_jwt_identity

    identity = get_jwt_identity()
    if identity is None:
        return None
    try:
        user_id = int(identity)
    except (TypeError, ValueError):
        return None
    return db.session.get(User, user_id)


def _require_role(user: User | None, allowed_roles, access_label: str):
    if user is None:
        return jsonify({"error": "Authentication required"}), 401
    if user.role not in allowed_roles:
        return jsonify({"error": f"{access_label} access required"}), 403
    return None


def _serialize_applications(applications):
    return [application.to_dict() for application in applications]


def _build_auth_token(user: User):
    from flask_jwt_extended import get_jwt_identity
    return create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role, "email": user.email, "auth_state": "authenticated"},
        expires_delta=timedelta(hours=12),
    )


def _reset_legacy_sqlite_if_needed(database_url: str):
    if not database_url.startswith("sqlite://") or database_url.startswith("sqlite:///:memory:"):
        return

    raw_path = database_url.replace("sqlite:///", "", 1)
    raw_path = raw_path.replace("sqlite://", "", 1)
    if not raw_path:
        return
    db_path = raw_path if os.path.isabs(raw_path) else os.path.abspath(os.path.join(os.path.dirname(__file__), raw_path))
    if not os.path.exists(db_path):
        return
    try:
        with sqlite3.connect(db_path) as connection:
            columns = connection.execute("PRAGMA table_info(users)").fetchall()
            column_names = [column[1] for column in columns]
        if "is_active" not in column_names:
            os.remove(db_path)
    except Exception:
        pass


def create_app(test_config: Dict[str, Any] | None = None):
    app = Flask(__name__)
    default_db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "instance", "risksure.db"))
    database_url = os.getenv("DATABASE_URL", f"sqlite:///{default_db_path}")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    _reset_legacy_sqlite_if_needed(database_url)

    app.config.update(
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY=os.getenv("JWT_SECRET_KEY", "dev-only-change-this-secret"),
        JWT_ACCESS_TOKEN_EXPIRES=timedelta(hours=12),
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    jwt.init_app(app)

    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET,PUT,POST,DELETE,OPTIONS"
        return response

    def seed_demo_data():
        if User.query.first() is not None:
            return

        customer = User(email="customer@risksure.com", role="customer", first_name="Jane", last_name="Customer")
        customer.set_password("CustomerPass123!")
        underwriter = User(email="underwriter@risksure.com", role="underwriter", first_name="Alex", last_name="Reviewer")
        underwriter.set_password("UnderwriterPass123!")
        admin = User(email="admin@risksure.com", role="admin", first_name="Riley", last_name="Admin")
        admin.set_password("AdminPass123!")
        db.session.add_all([customer, underwriter, admin])
        db.session.commit()

        application_one = Application(
            user_id=customer.id,
            name="Sample Policyholder A",
            age=42,
            sex="female",
            bmi=31.2,
            children=2,
            smoker="yes",
            region="southeast",
            status="submitted",
            risk_category="HIGH",
            risk_score=0.82,
            final_risk=0.82,
            decision="manual_review",
            premium=42000.0,
            application_data={"coverage_amount": 250000},
        )
        application_two = Application(
            user_id=customer.id,
            name="Sample Policyholder B",
            age=34,
            sex="male",
            bmi=26.1,
            children=1,
            smoker="no",
            region="northwest",
            status="approved",
            risk_category="LOW",
            risk_score=0.31,
            final_risk=0.31,
            decision="approved",
            premium=17000.0,
            application_data={"coverage_amount": 150000},
        )
        db.session.add_all([application_one, application_two])
        db.session.commit()

        db.session.add(
            RiskAssessment(
                application_id=application_one.id,
                risk_score=0.82,
                risk_category="HIGH",
                premium=42000.0,
                details={"important_features": ["smoker", "bmi", "coverage_amount"]},
            )
        )
        db.session.add(
            UnderwriterAssignment(
                application_id=application_one.id,
                underwriter_id=underwriter.id,
                assignment_status="assigned",
            )
        )
        db.session.add(
            UnderwritingDecision(
                application_id=application_one.id,
                underwriter_id=underwriter.id,
                decision="REQUEST_MORE_INFO",
                reason="Elevated risk needs clarification on smoking and prior claims history.",
                notes="Waiting for updated health declarations and prior claims records.",
                previous_status="submitted",
                new_status="more_info_required",
            )
        )
        db.session.commit()

    with app.app_context():
        db.create_all()
        if not app.config.get("TESTING") and not database_url.startswith("sqlite:///:memory:"):
            seed_demo_data()

    @app.route("/")
    def home():
        return jsonify({"status": "ok", "message": "RiskSure backend is running."})

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify(
            {
                "status": "ok",
                "model_loaded": risk_service.model_loaded,
                "application_count": Application.query.count(),
                "neo4j_enabled": neo4j_service.is_enabled(),
            }
        )

    @app.route("/api/auth/register", methods=["POST"])
    @app.route("/auth/register", methods=["POST"])
    def register():
        data = request.get_json() or {}
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))
        first_name = str(data.get("first_name", "")).strip()
        last_name = str(data.get("last_name", "")).strip()
        requested_role = str(data.get("role", "customer")).strip().lower()
        role = requested_role if requested_role in {"customer", "underwriter", "admin"} else "customer"

        if not email or not password:
            return jsonify({"error": "Email and password are required"}), 400
        if len(password) < 8:
            return jsonify({"error": "Password must be at least 8 characters"}), 400
        if User.query.filter_by(email=email).first():
            return jsonify({"error": "An account with this email already exists"}), 409

        user = User(email=email, role=role, first_name=first_name, last_name=last_name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        _log_event(user, "register", "user", user.id, role=role)
        return jsonify({"message": "Account created", "user": user.to_dict()}), 201

    @app.route("/api/auth/login", methods=["POST"])
    @app.route("/auth/login", methods=["POST"])
    def login():
        data = request.get_json() or {}
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))
        user = User.query.filter_by(email=email).first()

        if user is None or not user.check_password(password):
            return jsonify({"error": "Invalid email or password"}), 401
        if not user.is_active:
            return jsonify({"error": "This account is inactive"}), 403

        token = _build_auth_token(user)
        _log_event(user, "login", "user", user.id)
        return jsonify({"access_token": token, "user": user.to_dict()})

    @app.route("/api/auth/me", methods=["GET"])
    @app.route("/auth/me", methods=["GET"])
    @jwt_required()
    def current_user():
        user = _current_user_from_jwt()
        if user is None:
            return jsonify({"error": "User not found"}), 404
        return jsonify({"user": user.to_dict()})

    @app.route("/api/auth/logout", methods=["POST"])
    @app.route("/auth/logout", methods=["POST"])
    @jwt_required()
    def logout():
        user = _current_user_from_jwt()
        if user:
            _log_event(user, "logout", "user", user.id)
        return jsonify({"message": "Logged out successfully"})

    @app.route("/api/auth/staff-only", methods=["GET"])
    @app.route("/auth/staff-only", methods=["GET"])
    @jwt_required()
    def staff_only():
        user = _current_user_from_jwt()
        if user is None:
            return jsonify({"error": "Authentication required"}), 401
        if user.role not in {"underwriter", "admin"}:
            return jsonify({"error": "Staff access required"}), 403
        return jsonify({"message": "Staff access granted", "role": user.role})

    @app.route("/api/customer/dashboard", methods=["GET"])
    @app.route("/customer/dashboard", methods=["GET"])
    @jwt_required()
    def customer_dashboard():
        user = _current_user_from_jwt()
        role_error = _require_role(user, {"customer"}, "Customer")
        if role_error is not None:
            return role_error
        applications = Application.query.filter_by(user_id=user.id).order_by(Application.created_at.desc()).all()
        return jsonify({
            "user": user.to_dict(),
            "summary": {
                "total_applications": len(applications),
                "active_applications": sum(1 for app in applications if app.status not in {"approved", "rejected", "draft"}),
                "pending": sum(1 for app in applications if app.status in {"draft", "submitted", "pending", "more_info_required"}),
                "approved": sum(1 for app in applications if app.status == "approved"),
                "rejected": sum(1 for app in applications if app.status == "rejected"),
                "high_risk": sum(1 for app in applications if app.risk_category == "HIGH"),
                "average_premium": round(sum(app.premium for app in applications) / len(applications), 2) if applications else 0.0,
            },
            "applications": _serialize_applications(applications),
        })

    @app.route("/api/customer/applications", methods=["GET", "POST"])
    @app.route("/customer/applications", methods=["GET", "POST"])
    @jwt_required()
    def customer_applications():
        user = _current_user_from_jwt()
        role_error = _require_role(user, {"customer"}, "Customer")
        if role_error is not None:
            return role_error

        if request.method == "POST":
            data = request.get_json() or {}
            status_value = str(data.get("status", "draft")).strip() or "draft"
            application = Application(
                user_id=user.id,
                name=str(data.get("name", "Unknown")).strip() or "Unknown",
                age=data.get("age"),
                sex=str(data.get("sex", "")).strip(),
                bmi=data.get("bmi"),
                children=data.get("children"),
                smoker=str(data.get("smoker", "no")).strip(),
                region=str(data.get("region", "")).strip(),
                status=status_value,
                risk_category=str(data.get("risk_category", "LOW")).strip().upper() or "LOW",
                decision=str(data.get("decision", "pending")).strip(),
                premium=float(data.get("premium", 0.0) or 0.0),
                risk_score=float(data.get("risk_score", 0.0) or 0.0),
                rule_adjustment=float(data.get("rule_adjustment", 0.0) or 0.0),
                final_risk=float(data.get("final_risk", 0.0) or 0.0),
                application_data=data.get("application_data", {}) or {},
            )
            db.session.add(application)
            db.session.commit()
            _log_event(user, "application_created", "application", application.id, status=status_value)
            return jsonify({"message": "Application created", "application": application.to_dict()}), 201

        applications = Application.query.filter_by(user_id=user.id).order_by(Application.created_at.desc()).all()
        return jsonify(_serialize_applications(applications))

    @app.route("/api/customer/applications/<int:application_id>", methods=["GET", "PATCH", "POST"])
    @app.route("/customer/applications/<int:application_id>", methods=["GET", "PATCH", "POST"])
    @jwt_required()
    def customer_application_detail(application_id):
        user = _current_user_from_jwt()
        role_error = _require_role(user, {"customer"}, "Customer")
        if role_error is not None:
            return role_error
        application = db.session.get(Application, application_id)
        if application is None:
            return jsonify({"error": "Application not found"}), 404
        if application.user_id != user.id:
            return jsonify({"error": "You do not have access to this application"}), 403

        if request.method in {"PATCH", "POST"}:
            data = request.get_json() or {}
            for field in ["name", "age", "sex", "bmi", "children", "smoker", "region", "status", "decision", "risk_score", "premium", "final_risk", "risk_category", "rule_adjustment", "application_data"]:
                if field in data:
                    setattr(application, field, data[field])
            db.session.commit()
            _log_event(user, "application_updated", "application", application.id, fields=list(data.keys()))
        return jsonify({"application": application.to_dict()})

    @app.route("/api/applications", methods=["GET"])
    @app.route("/applications", methods=["GET"])
    @jwt_required()
    def list_applications():
        user = _current_user_from_jwt()
        if user is None:
            return jsonify({"error": "Authentication required"}), 401
        if user.role == "customer":
            applications = Application.query.filter_by(user_id=user.id).all()
        elif user.role in {"underwriter", "admin"}:
            applications = Application.query.order_by(Application.created_at.desc()).all()
        else:
            applications = []
        return jsonify(_serialize_applications(applications))

    @app.route("/api/applications/<int:application_id>", methods=["GET"])
    @app.route("/applications/<int:application_id>", methods=["GET"])
    @jwt_required()
    def get_application_for_role(application_id):
        user = _current_user_from_jwt()
        if user is None:
            return jsonify({"error": "Authentication required"}), 401
        application = db.session.get(Application, application_id)
        if application is None:
            return jsonify({"error": "Application not found"}), 404
        if user.role == "customer" and application.user_id != user.id:
            return jsonify({"error": "You do not have access to this application"}), 403
        return jsonify({"application": application.to_dict()})

    @app.route("/api/underwriter/dashboard", methods=["GET"])
    @app.route("/underwriter/dashboard", methods=["GET"])
    @jwt_required()
    def underwriter_dashboard():
        user = _current_user_from_jwt()
        if user is None:
            return jsonify({"error": "Authentication required"}), 401
        if user.role not in {"underwriter", "admin"}:
            return jsonify({"error": "Underwriter access required"}), 403
        applications = Application.query.order_by(Application.created_at.desc()).all()
        assigned = UnderwriterAssignment.query.filter_by(underwriter_id=user.id).all() if user.role == "underwriter" else UnderwriterAssignment.query.all()
        return jsonify({
            "user": user.to_dict(),
            "summary": {
                "total_applications": len(applications),
                "pending_reviews": sum(1 for app in applications if app.status in {"submitted", "pending", "manual_review"}),
                "high_risk": sum(1 for app in applications if app.risk_category == "HIGH"),
                "medium_risk": sum(1 for app in applications if app.risk_category == "MEDIUM"),
                "low_risk": sum(1 for app in applications if app.risk_category == "LOW"),
            },
            "assigned_applications": [entry.to_dict() for entry in assigned],
            "applications": _serialize_applications(applications),
        })

    @app.route("/api/underwriter/applications", methods=["GET"])
    @app.route("/underwriter/applications", methods=["GET"])
    @jwt_required()
    def underwriter_applications():
        user = _current_user_from_jwt()
        if user is None:
            return jsonify({"error": "Authentication required"}), 401
        if user.role not in {"underwriter", "admin"}:
            return jsonify({"error": "Underwriter access required"}), 403
        return jsonify(_serialize_applications(Application.query.order_by(Application.created_at.desc()).all()))

    @app.route("/api/underwriter/applications/<int:application_id>", methods=["GET", "POST"])
    @app.route("/underwriter/applications/<int:application_id>", methods=["GET", "POST"])
    @jwt_required()
    def underwriter_application_detail(application_id):
        user = _current_user_from_jwt()
        if user is None:
            return jsonify({"error": "Authentication required"}), 401
        if user.role not in {"underwriter", "admin"}:
            return jsonify({"error": "Underwriter access required"}), 403
        application = db.session.get(Application, application_id)
        if application is None:
            return jsonify({"error": "Application not found"}), 404

        if request.method == "POST":
            data = request.get_json() or {}
            decision = str(data.get("decision", "REQUEST_MORE_INFO")).strip().upper()
            reason = str(data.get("reason", "Manual review recommendation")).strip()
            notes = str(data.get("notes", "")).strip()
            previous_status = application.status
            new_status = str(data.get("new_status", "more_info_required")).strip() or "more_info_required"
            application.status = new_status
            application.decision = decision
            decision_record = UnderwritingDecision(
                application_id=application.id,
                underwriter_id=user.id,
                decision=decision,
                reason=reason,
                notes=notes,
                previous_status=previous_status,
                new_status=new_status,
            )
            db.session.add(decision_record)
            db.session.commit()
            _log_event(user, "underwriting_decision", "application", application.id, decision=decision, reason=reason)
            return jsonify({"message": "Decision recorded", "decision": decision_record.to_dict()})

        return jsonify({"application": application.to_dict()})

    @app.route("/api/admin/dashboard", methods=["GET"])
    @app.route("/admin/dashboard", methods=["GET"])
    @jwt_required()
    def admin_dashboard():
        user = _current_user_from_jwt()
        if user is None:
            return jsonify({"error": "Authentication required"}), 401
        if user.role != "admin":
            return jsonify({"error": "Admin access required"}), 403

        applications = Application.query.order_by(Application.created_at.desc()).all()
        users = User.query.order_by(User.created_at.desc()).all()
        return jsonify({
            "user": user.to_dict(),
            "summary": {
                "total_users": len(users),
                "customers": sum(1 for user_item in users if user_item.role == "customer"),
                "underwriters": sum(1 for user_item in users if user_item.role == "underwriter"),
                "applications": len(applications),
                "pending_applications": sum(1 for app in applications if app.status in {"draft", "submitted", "pending"}),
                "approved_applications": sum(1 for app in applications if app.status == "approved"),
                "rejected_applications": sum(1 for app in applications if app.status == "rejected"),
                "high_risk_applications": sum(1 for app in applications if app.risk_category == "HIGH"),
                "medium_risk_applications": sum(1 for app in applications if app.risk_category == "MEDIUM"),
                "low_risk_applications": sum(1 for app in applications if app.risk_category == "LOW"),
            },
            "users": [item.to_dict() for item in users],
            "applications": _serialize_applications(applications),
        })

    @app.route("/api/admin/users", methods=["GET", "POST"])
    @app.route("/admin/users", methods=["GET", "POST"])
    @jwt_required()
    def admin_users():
        user = _current_user_from_jwt()
        if user is None:
            return jsonify({"error": "Authentication required"}), 401
        if user.role != "admin":
            return jsonify({"error": "Admin access required"}), 403

        if request.method == "POST":
            data = request.get_json() or {}
            email = str(data.get("email", "")).strip().lower()
            password = str(data.get("password", ""))
            role = str(data.get("role", "underwriter")).strip().lower()
            if not email or not password:
                return jsonify({"error": "Email and password are required"}), 400
            if role not in {"underwriter", "admin"}:
                role = "underwriter"
            created = User(email=email, role=role)
            created.set_password(password)
            db.session.add(created)
            db.session.commit()
            _log_event(user, "user_created", "user", created.id, role=role)
            return jsonify({"message": "User created", "user": created.to_dict()}), 201

        return jsonify([item.to_dict() for item in User.query.order_by(User.created_at.desc()).all()])

    @app.route("/api/admin/audit", methods=["GET"])
    @app.route("/admin/audit", methods=["GET"])
    @jwt_required()
    def admin_audit():
        user = _current_user_from_jwt()
        if user is None:
            return jsonify({"error": "Authentication required"}), 401
        if user.role != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return jsonify({"logs": [entry.to_dict() for entry in AuditLog.query.order_by(AuditLog.created_at.desc()).all()]})

    @app.route("/api/risk/score", methods=["POST"])
    @app.route("/risk/score", methods=["POST"])
    @jwt_required()
    def score_risk():
        payload = request.get_json() or {}
        return jsonify(risk_service.score(payload))

    @app.route("/api/risk/application/<int:application_id>", methods=["GET"])
    @app.route("/risk/application/<int:application_id>", methods=["GET"])
    @jwt_required()
    def risk_for_application(application_id):
        application = db.session.get(Application, application_id)
        if application is None:
            return jsonify({"error": "Application not found"}), 404
        payload = {
            "age": application.age or 0,
            "sex": application.sex or "male",
            "bmi": application.bmi or 0.0,
            "children": application.children or 0,
            "smoker": application.smoker or "no",
            "region": application.region or "southwest",
        }
        return jsonify(risk_service.score(payload))

    @app.route("/api/statistics/dashboard", methods=["GET"])
    @app.route("/statistics/dashboard", methods=["GET"])
    @jwt_required()
    def statistics_dashboard():
        user = _current_user_from_jwt()
        if user is None:
            return jsonify({"error": "Authentication required"}), 401
        if user.role not in {"underwriter", "admin"}:
            return jsonify({"error": "Underwriter or admin access required"}), 403
        apps = [application.to_dict() for application in Application.query.all()]
        return jsonify(statistical_analysis_service.summarize(apps))

    @app.route("/api/graph/overview", methods=["GET"])
    @app.route("/graph/overview", methods=["GET"])
    @jwt_required()
    def graph_overview():
        user = _current_user_from_jwt()
        if user is None:
            return jsonify({"error": "Authentication required"}), 401
        if user.role != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return jsonify({"graph": neo4j_service.get_graph_summary()})

    @app.route("/api/ai/underwriter-summary", methods=["POST"])
    @app.route("/ai/underwriter-summary", methods=["POST"])
    @jwt_required()
    def ai_underwriter_summary():
        user = _current_user_from_jwt()
        if user is None:
            return jsonify({"error": "Authentication required"}), 401
        if user.role not in {"underwriter", "admin"}:
            return jsonify({"error": "Underwriter access required"}), 403

        data = request.get_json() or {}
        application_id = int(data.get("application_id", 0) or 0)
        application = db.session.get(Application, application_id)
        if application is None:
            return jsonify({"error": "Application not found"}), 404
        risk_summary = risk_service.score({
            "age": application.age or 0,
            "sex": application.sex or "male",
            "bmi": application.bmi or 0.0,
            "children": application.children or 0,
            "smoker": application.smoker or "no",
            "region": application.region or "southwest",
        })
        summary = ai_underwriter_service.summarize_application(application.to_dict(), risk_summary)
        _log_event(user, "ai_analysis_requested", "application", application.id, summary=summary)
        return jsonify({"analysis": summary})

    @app.route("/process", methods=["POST"])
    @jwt_required()
    def process():
        payload = request.get_json() or {}
        return jsonify(risk_service.score(payload))

    @app.route("/save", methods=["POST"])
    @jwt_required()
    def save():
        data = request.get_json() or {}
        user = _current_user_from_jwt()
        if user is None:
            return jsonify({"error": "Authentication required"}), 401
        if user.role != "customer":
            return jsonify({"error": "Customer access required"}), 403

        application = Application(
            user_id=user.id,
            name=str(data.get("name", "Unknown")).strip() or "Unknown",
            age=data.get("age"),
            sex=str(data.get("sex", "")).strip(),
            bmi=data.get("bmi"),
            children=data.get("children"),
            smoker=str(data.get("smoker", "no")).strip(),
            region=str(data.get("region", "")).strip(),
            status=str(data.get("status", "draft")).strip(),
            risk_score=float(data.get("risk_score", 0.0) or 0.0),
            rule_adjustment=float(data.get("rule_adjustment", 0.0) or 0.0),
            final_risk=float(data.get("final_risk", 0.0) or 0.0),
            decision=str(data.get("decision", "Unknown")).strip(),
            premium=float(data.get("premium", 0.0) or 0.0),
        )
        db.session.add(application)
        db.session.commit()
        _log_event(user, "application_saved", "application", application.id)
        return jsonify({"message": "Application saved successfully", "application": application.to_dict()})

    @app.route("/applications", methods=["GET"])
    @jwt_required()
    def legacy_get_applications():
        return list_applications()

    @app.route("/applications/<int:application_id>", methods=["GET"])
    @jwt_required()
    def legacy_get_application(application_id):
        return get_application_for_role(application_id)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)

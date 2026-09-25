import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import timedelta
from functools import wraps

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from cryptography.fernet import Fernet, InvalidToken
from flask_jwt_extended import JWTManager, create_access_token, get_jwt_identity, jwt_required
import os
import json
import pyotp
from werkzeug.security import generate_password_hash, check_password_hash

from database import db
from integrations import neo4j_upsert_claim, neo4j_claim_graph, index_policy_chunks, retrieve_policy_chunks, hf_request
from models import (
    Application,
    AuditLog,
    BillingTransaction,
    Claim,
    CustomerProfile,
    Policy,
    Provider,
    User,
)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": os.getenv("FRONTEND_ORIGIN", "*")}}, supports_credentials=False)

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("NEON_DATABASE_URL") or "sqlite:///risksure.db"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
JWT_SECRET = os.getenv("JWT_SECRET_KEY") or os.getenv("TOTP_ENCRYPTION_KEY") or "risksure-vercel-jwt-bootstrap-change-in-production"
app.config["JWT_SECRET_KEY"] = JWT_SECRET
jwt = JWTManager(app)
db.init_app(app)
migrate = Migrate(app, db)
limiter = Limiter(key_func=get_remote_address, app=app, default_limits=["300 per minute"])

with app.app_context():
    if os.getenv("AUTO_CREATE_TABLES", "false").lower() == "true":
        db.create_all()


VALID_ROLES = {"customer", "underwriter", "claims_officer", "provider", "admin"}
STAFF_ROLES = {"underwriter", "claims_officer", "provider", "admin"}
TOTP_REQUIRED_ROLES = STAFF_ROLES

def _fernet():
    key = os.getenv("TOTP_ENCRYPTION_KEY", "").strip()
    if not key:
        return None
    return Fernet(key.encode())

def _encrypt_secret(secret):
    f = _fernet()
    if f is None:
        if os.getenv("FLASK_ENV") == "production":
            raise RuntimeError("TOTP_ENCRYPTION_KEY must be configured in production")
        return secret
    return f.encrypt(secret.encode()).decode()

def _decrypt_secret(secret):
    if not secret:
        return None
    f = _fernet()
    if f is None:
        return secret
    try:
        return f.decrypt(secret.encode()).decode()
    except InvalidToken:
        return secret



def generate_recovery_codes():
    return [os.urandom(6).hex().upper() for _ in range(8)]


def recovery_hashes(user):
    return json.loads(user.recovery_codes_hash) if user.recovery_codes_hash else []


def auth_token(user):
    return create_access_token(identity=str(user.id), additional_claims={"role": user.role})


def current_user_record():
    identity = get_jwt_identity()
    try:
        user_id = int(identity)
    except (TypeError, ValueError):
        return None
    return db.session.get(User, user_id)


def roles_required(*allowed_roles):
    allowed = set(allowed_roles)

    def decorator(view):
        @wraps(view)
        @jwt_required()
        def wrapped(*args, **kwargs):
            user = current_user_record()
            if user is None:
                return jsonify({"error": "User not found"}), 404
            if user.role not in allowed:
                return jsonify({"error": "Insufficient permissions"}), 403
            return view(*args, **kwargs)

        return wrapped

    return decorator


def customer_for_user(user):
    return CustomerProfile.query.filter_by(user_id=user.id).first()


def audit(user_id, action, entity_type=None, entity_id=None, details=None):
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=json.dumps(details) if isinstance(details, (dict, list)) else details,
    )
    db.session.add(entry)


def claim_to_dict(claim):
    return {
        "id": claim.id,
        "claim_number": claim.claim_number,
        "customer_id": claim.customer_id,
        "policy_id": claim.policy_id,
        "provider_id": claim.provider_id,
        "status": claim.status,
        "claimed_amount": claim.claimed_amount,
        "approved_amount": claim.approved_amount,
        "assigned_officer_id": claim.assigned_officer_id,
        "incident_date": claim.incident_date.isoformat() if claim.incident_date else None,
        "description": claim.description,
        "created_at": claim.created_at.isoformat() if claim.created_at else None,
        "updated_at": claim.updated_at.isoformat() if claim.updated_at else None,
    }


def provider_for_user(user):
    return Provider.query.filter_by(user_id=user.id).first()



MODEL_DIR = os.path.join(os.path.dirname(__file__), "model")
model_loaded = False
model = None
explainer = None
feature_names = ["age", "sex", "bmi", "children", "smoker", "region"]
min_charge = 1000.0
max_charge = 50000.0

print("ML model packages are kept outside the Vercel runtime to keep the function within size limits.")
model_loaded = False
model = None
explainer = None


@app.route("/")
def home():
    status = "LOADED" if model_loaded else "FAILED"
    return f"Backend is running.<br><br>ML Model Status: {status}"


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "model_loaded": model_loaded,
        "saved_applications": Application.query.count(),
        "claims": Claim.query.count(),
        "policies": Policy.query.count(),
    })


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    requested_role = str(data.get("role", "customer")).strip().lower()

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    if requested_role != "customer":
        return jsonify({"error": "Public registration can only create customer accounts"}), 403
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "An account with this email already exists"}), 409

    user = User(email=email, role="customer")
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    audit(user.id, "account_created", "user", user.id)
    db.session.commit()
    return jsonify({"message": "Account created", "user": user.to_dict()}), 201


@app.route("/auth/login", methods=["POST"])
@limiter.limit("10 per minute")
def login():
    data = request.get_json() or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    user = User.query.filter_by(email=email).first()

    if user is None or user.role not in VALID_ROLES or not user.check_password(password):
        return jsonify({"error": "Invalid email or password"}), 401

    if user.role in TOTP_REQUIRED_ROLES and not user.totp_enabled:
        setup_token = create_access_token(identity=str(user.id), additional_claims={"role": user.role, "auth_stage": "totp_setup"})
        return jsonify({"totp_setup_required": True, "setup_token": setup_token, "user": user.to_dict()})
    if user.totp_enabled:
        challenge_token = create_access_token(identity=str(user.id), expires_delta=timedelta(minutes=5), additional_claims={"role": user.role, "auth_stage": "totp_challenge"})
        return jsonify({"requires_totp": True, "challenge_token": challenge_token, "user": user.to_dict()})
    return jsonify({"access_token": auth_token(user), "user": user.to_dict()})



@app.route("/auth/totp/setup", methods=["POST"])
@jwt_required()
def totp_setup():
    claims = get_jwt()
    if claims.get("auth_stage") != "totp_setup":
        return jsonify({"error": "TOTP setup session required"}), 403
    user = current_user_record()
    if user is None:
        return jsonify({"error": "User not found"}), 404
    secret = pyotp.random_base32()
    user.totp_pending_secret = _encrypt_secret(secret)
    db.session.commit()
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="RiskSure")
    return jsonify({"secret": secret, "otpauth_uri": uri})


@app.route("/auth/totp/verify-setup", methods=["POST"])
@jwt_required()
def verify_totp_setup():
    claims = get_jwt()
    if claims.get("auth_stage") != "totp_setup":
        return jsonify({"error": "TOTP setup session required"}), 403
    user = current_user_record()
    code = str((request.get_json() or {}).get("code", "")).replace(" ", "")
    if user is None or not user.totp_pending_secret:
        return jsonify({"error": "No pending TOTP setup"}), 400
    if not pyotp.TOTP(_decrypt_secret(user.totp_pending_secret)).verify(code, valid_window=1):
        return jsonify({"error": "Invalid authenticator code"}), 400
    codes = generate_recovery_codes()
    user.totp_secret = user.totp_pending_secret
    user.totp_pending_secret = None
    user.totp_enabled = True
    user.recovery_codes_hash = json.dumps([generate_password_hash(x) for x in codes])
    user.recovery_codes_used = json.dumps([])
    audit(user.id, "totp_enabled", "user", user.id)
    db.session.commit()
    return jsonify({"access_token": auth_token(user), "user": user.to_dict(), "recovery_codes": codes})


@app.route("/auth/login/verify-totp", methods=["POST"])
@limiter.limit("10 per minute")
@jwt_required()
def verify_login_totp():
    claims = get_jwt()
    if claims.get("auth_stage") != "totp_challenge":
        return jsonify({"error": "TOTP challenge required"}), 403
    user = current_user_record()
    code = str((request.get_json() or {}).get("code", "")).replace(" ", "")
    if user is None or not user.totp_enabled or not user.totp_secret:
        return jsonify({"error": "TOTP verification unavailable"}), 400
    if not pyotp.TOTP(_decrypt_secret(user.totp_secret)).verify(code, valid_window=1):
        return jsonify({"error": "Invalid authenticator code"}), 401
    return jsonify({"access_token": auth_token(user), "user": user.to_dict()})


@app.route("/auth/login/recovery", methods=["POST"])
@limiter.limit("5 per minute")
@jwt_required()
def login_recovery():
    claims = get_jwt()
    if claims.get("auth_stage") != "totp_challenge":
        return jsonify({"error": "TOTP challenge required"}), 403
    user = current_user_record()
    code = str((request.get_json() or {}).get("recovery_code", "")).strip().upper()
    if user is None or not user.totp_enabled:
        return jsonify({"error": "Recovery unavailable"}), 400
    hashes = recovery_hashes(user)
    for i, hashed in enumerate(hashes):
        if check_password_hash(hashed, code):
            hashes.pop(i)
            user.recovery_codes_hash = json.dumps(hashes)
            audit(user.id, "totp_recovery_used", "user", user.id)
            db.session.commit()
            return jsonify({"access_token": auth_token(user), "user": user.to_dict()})
    return jsonify({"error": "Invalid or already used recovery code"}), 401


@app.route("/auth/totp/disable", methods=["POST"])
@jwt_required()
def disable_totp():
    user = current_user_record()
    code = str((request.get_json() or {}).get("code", "")).replace(" ", "")
    if user is None or not user.totp_enabled or not pyotp.TOTP(_decrypt_secret(user.totp_secret)).verify(code, valid_window=1):
        return jsonify({"error": "Valid authenticator code required"}), 400
    user.totp_enabled = False
    user.totp_secret = None
    user.totp_pending_secret = None
    user.recovery_codes_hash = None
    user.recovery_codes_used = None
    audit(user.id, "totp_disabled", "user", user.id)
    db.session.commit()
    return jsonify({"message": "TOTP disabled"})


@app.route("/auth/me", methods=["GET"])
@jwt_required()
def current_user():
    user = current_user_record()
    if user is None:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"user": user.to_dict()})


@app.route("/auth/staff-only", methods=["GET"])
@roles_required(*STAFF_ROLES)
def staff_only():
    user = current_user_record()
    return jsonify({"message": "Staff access granted", "role": user.role})


@app.route("/process", methods=["POST"])
@roles_required("customer", "underwriter", "admin")
def process():
    data = request.get_json() or {}

    try:
        age = float(data.get("age", 0))
        sex_raw = data.get("sex", "male")
        bmi = float(data.get("bmi", 0.0))
        children = float(data.get("children", 0))
        smoker_raw = data.get("smoker", "no")
        region_raw = data.get("region", "southwest")
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid underwriting input"}), 400

    sex = 1 if str(sex_raw).lower() == "male" else 0
    smoker = 1 if str(smoker_raw).lower() in ["yes", "true", "1"] else 0
    region_map = {"southwest": 0, "southeast": 1, "northwest": 2, "northeast": 3}
    region = region_map.get(str(region_raw).lower(), 0)
    if model_loaded and model is not None:
        prediction = float(model.predict([[age, sex, bmi, children, smoker, region]])[0])
        model_status = "xgboost"
    else:
        prediction = 3500.0 + age * 35.0 + bmi * 80.0 + children * 250.0 + smoker * 6500.0 + region * 250.0
        model_status = "deterministic_fallback"
    risk_score = (prediction - min_charge) / max(max_charge - min_charge, 1.0)
    risk_score = max(0.0, min(1.0, float(risk_score)))

    rule_adjustments = []
    rule_adjustment = 0.0
    if smoker == 1:
        rule_adjustment += 0.20
        rule_adjustments.append({"rule": "smoker", "adjustment": 0.20, "reason": "Smoking status increases modeled risk."})
    if bmi > 30:
        rule_adjustment += 0.05
        rule_adjustments.append({"rule": "high_bmi", "adjustment": 0.05, "reason": "BMI is above 30."})
    if children > 2:
        rule_adjustment += 0.05
        rule_adjustments.append({"rule": "dependents", "adjustment": 0.05, "reason": "More than two dependents are present."})

    final_risk = min(1.0, risk_score + rule_adjustment)
    if final_risk < 0.5:
        decision = "Approved"
    elif final_risk <= 0.9:
        decision = "Approved with Conditions"
    else:
        decision = "Manual Review"

    premium = 5000.0 * (1.0 + final_risk)
    shap_explanation = []
    if explainer is not None and model is not None:
        shap_values = explainer([[age, sex, bmi, children, smoker, region]])
        contributions = list(shap_values.values[0])
        for name, contribution in zip(feature_names, contributions):
            shap_explanation.append({
                "feature": name,
                "contribution": round(float(contribution), 4),
                "direction": "increases" if contribution > 0 else "decreases" if contribution < 0 else "neutral",
            })
        shap_explanation.sort(key=lambda item: abs(item["contribution"]), reverse=True)

    return jsonify({
        "predicted_charge": prediction,
        "risk_score": round(risk_score, 4),
        "rule_adjustment": round(rule_adjustment, 4),
        "applied_rules": rule_adjustments,
        "final_risk": round(final_risk, 4),
        "decision": decision,
        "premium": round(premium, 2),
        "model_status": model_status,
        "explanation": {"method": "SHAP", "features": shap_explanation},
    })


@app.route("/save", methods=["POST"])
@roles_required("customer", "underwriter", "admin")
def save():
    data = request.get_json() or {}
    user = current_user_record()

    customer_id = None
    if user.role == "customer":
        profile = customer_for_user(user)
        if profile is None:
            profile = CustomerProfile(user_id=user.id, full_name=str(data.get("name", "Unknown")))
            db.session.add(profile)
            db.session.flush()
        customer_id = profile.id
    elif data.get("customer_id"):
        customer_id = int(data["customer_id"])

    application = Application(
        customer_id=customer_id,
        name=data.get("name", "Unknown"),
        age=data.get("age"),
        sex=data.get("sex"),
        bmi=data.get("bmi"),
        children=data.get("children"),
        smoker=data.get("smoker"),
        region=data.get("region"),
        risk_score=float(data.get("risk_score", 0.0)),
        rule_adjustment=float(data.get("rule_adjustment", 0.0)),
        final_risk=float(data.get("final_risk", 0.0)),
        decision=str(data.get("decision", "Unknown")),
        premium=float(data.get("premium", 0.0)),
    )

    db.session.add(application)
    db.session.flush()
    audit(user.id, "application_created", "application", application.id)
    db.session.commit()
    return jsonify({"message": "Application saved successfully", "application": application.to_dict()})


@app.route("/applications", methods=["GET"])
@jwt_required()
def get_applications():
    user = current_user_record()
    if user is None:
        return jsonify({"error": "User not found"}), 404

    query = Application.query
    if user.role == "customer":
        profile = customer_for_user(user)
        if profile is None:
            return jsonify([])
        query = query.filter_by(customer_id=profile.id)
    elif user.role not in {"underwriter", "admin"}:
        return jsonify({"error": "Insufficient permissions"}), 403

    applications = query.order_by(Application.created_at.desc()).all()
    return jsonify([application.to_dict() for application in applications])


@app.route("/underwriting/queue", methods=["GET"])
@roles_required("underwriter", "admin")
def underwriting_queue():
    applications = Application.query.order_by(Application.created_at.desc()).all()
    return jsonify([{
        "id": a.id, "name": a.name, "age": a.age, "bmi": a.bmi, "smoker": a.smoker,
        "final_risk": a.final_risk, "decision": a.decision, "premium": a.premium,
        "review_status": a.review_status, "assigned_underwriter_id": a.assigned_underwriter_id,
        "decision_reason": a.decision_reason,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    } for a in applications])


@app.route("/underwriting/applications/<int:application_id>/assign", methods=["PUT"])
@roles_required("underwriter", "admin")
def assign_underwriting(application_id):
    user = current_user_record()
    application = db.session.get(Application, application_id)
    if application is None:
        return jsonify({"error": "Application not found"}), 404
    data = request.get_json() or {}
    assignee_id = int(data.get("underwriter_id", user.id))
    assignee = db.session.get(User, assignee_id)
    if assignee is None or assignee.role not in {"underwriter", "admin"}:
        return jsonify({"error": "Invalid underwriter"}), 400
    application.assigned_underwriter_id = assignee.id
    application.review_status = "in_review"
    audit(user.id, "underwriting_assigned", "application", application.id, {"underwriter_id": assignee.id})
    db.session.commit()
    return jsonify({"message": "Application assigned", "application_id": application.id, "underwriter_id": assignee.id})


@app.route("/underwriting/applications/<int:application_id>/decision", methods=["PUT"])
@roles_required("underwriter", "admin")
def underwriting_decision(application_id):
    user = current_user_record()
    application = db.session.get(Application, application_id)
    if application is None:
        return jsonify({"error": "Application not found"}), 404
    if application.assigned_underwriter_id not in {None, user.id} and user.role != "admin":
        return jsonify({"error": "Application is assigned to another underwriter"}), 403
    data = request.get_json() or {}
    decision = str(data.get("decision", "")).strip()
    if decision not in {"Approved", "Approved with Conditions", "Manual Review", "Rejected"}:
        return jsonify({"error": "Invalid underwriting decision"}), 400
    reason = str(data.get("reason", "")).strip()
    if not reason:
        return jsonify({"error": "A decision reason is required"}), 400
    application.decision = decision
    application.decision_reason = reason
    application.review_status = "completed" if decision != "Manual Review" else "manual_review"
    application.reviewed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    application.assigned_underwriter_id = user.id if application.assigned_underwriter_id is None else application.assigned_underwriter_id
    audit(user.id, "underwriting_decision", "application", application.id, {"decision": decision, "reason": reason})
    db.session.commit()
    return jsonify({"message": "Underwriting decision recorded", "application": {
        "id": application.id, "decision": application.decision, "decision_reason": application.decision_reason,
        "review_status": application.review_status, "reviewed_at": application.reviewed_at.isoformat() if application.reviewed_at else None
    }})


@app.route("/applications/<int:application_id>", methods=["GET"])
@jwt_required()
def get_application(application_id):
    user = current_user_record()
    if user is None:
        return jsonify({"error": "User not found"}), 404

    application = db.session.get(Application, application_id)
    if application is None:
        return jsonify({"error": "Application not found"}), 404

    if user.role == "customer":
        profile = customer_for_user(user)
        if profile is None or application.customer_id != profile.id:
            return jsonify({"error": "Insufficient permissions"}), 403
    elif user.role not in {"underwriter", "admin"}:
        return jsonify({"error": "Insufficient permissions"}), 403

    return jsonify(application.to_dict())


@app.route("/claims", methods=["GET"])
@roles_required("customer", "claims_officer", "admin", "provider")
def get_claims():
    user = current_user_record()
    query = Claim.query

    if user.role == "customer":
        profile = customer_for_user(user)
        if profile is None:
            return jsonify([])
        query = query.filter_by(customer_id=profile.id)
    elif user.role == "provider":
        provider = provider_for_user(user)
        if provider is None:
            return jsonify([])
        query = query.filter_by(provider_id=provider.id)

    return jsonify([claim_to_dict(c) for c in query.order_by(Claim.created_at.desc()).all()])


@app.route("/claims", methods=["POST"])
@roles_required("customer", "claims_officer", "admin", "provider")
def create_claim():
    data = request.get_json() or {}
    user = current_user_record()

    try:
        policy_id = int(data["policy_id"])
        claimed_amount = float(data.get("claimed_amount", 0))
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "policy_id and a valid claimed_amount are required"}), 400

    policy = db.session.get(Policy, policy_id)
    if policy is None:
        return jsonify({"error": "Policy not found"}), 404

    customer_id = data.get("customer_id")
    provider_id = data.get("provider_id")

    if user.role == "customer":
        profile = customer_for_user(user)
        if profile is None or policy.customer_id != profile.id:
            return jsonify({"error": "Policy does not belong to this customer"}), 403
        customer_id = profile.id
    elif user.role == "provider":
        provider = provider_for_user(user)
        if provider is None:
            return jsonify({"error": "Provider profile not found"}), 403
        provider_id = provider.id

    if not customer_id:
        customer_id = policy.customer_id

    claim = Claim(
        claim_number=f"RS-{os.urandom(5).hex().upper()}",
        customer_id=int(customer_id),
        policy_id=policy_id,
        provider_id=int(provider_id) if provider_id else policy.provider_id,
        claimed_amount=claimed_amount,
        status="submitted",
        description=str(data.get("description", "")),
    )
    db.session.add(claim)
    db.session.flush()
    audit(user.id, "claim_created", "claim", claim.id)
    db.session.commit()
    return jsonify({"message": "Claim submitted", "claim": claim_to_dict(claim)}), 201


@app.route("/claims/<int:claim_id>", methods=["GET"])
@roles_required("customer", "claims_officer", "admin", "provider")
def get_claim(claim_id):
    user = current_user_record()
    claim = db.session.get(Claim, claim_id)
    if claim is None:
        return jsonify({"error": "Claim not found"}), 404

    if user.role == "customer":
        profile = customer_for_user(user)
        if profile is None or claim.customer_id != profile.id:
            return jsonify({"error": "Insufficient permissions"}), 403
    elif user.role == "provider":
        provider = provider_for_user(user)
        if provider is None or claim.provider_id != provider.id:
            return jsonify({"error": "Insufficient permissions"}), 403

    return jsonify(claim_to_dict(claim))


@app.route("/claims/<int:claim_id>", methods=["PUT"])
@roles_required("claims_officer", "admin")
def update_claim(claim_id):
    user = current_user_record()
    claim = db.session.get(Claim, claim_id)
    if claim is None:
        return jsonify({"error": "Claim not found"}), 404

    data = request.get_json() or {}
    if "status" in data:
        claim.status = str(data["status"])
    if "approved_amount" in data:
        claim.approved_amount = float(data["approved_amount"])
    if "assigned_officer_id" in data:
        officer = db.session.get(User, int(data["assigned_officer_id"]))
        if officer is None or officer.role != "claims_officer":
            return jsonify({"error": "Invalid claims officer"}), 400
        claim.assigned_officer_id = officer.id
    audit(user.id, "claim_updated", "claim", claim.id, data)
    db.session.commit()
    return jsonify({"message": "Claim updated", "claim": claim_to_dict(claim)})


@app.route("/providers/me", methods=["GET"])
@roles_required("provider")
def provider_me():
    provider = provider_for_user(current_user_record())
    if provider is None:
        return jsonify({"error": "Provider profile not found"}), 404
    return jsonify({
        "id": provider.id,
        "name": provider.name,
        "provider_type": provider.provider_type,
        "license_number": provider.license_number,
        "status": provider.status,
        "phone": provider.phone,
        "address": provider.address,
        "city": provider.city,
        "state": provider.state,
    })


@app.route("/providers/me/claims", methods=["GET"])
@roles_required("provider")
def provider_claims():
    provider = provider_for_user(current_user_record())
    if provider is None:
        return jsonify([])
    claims = Claim.query.filter_by(provider_id=provider.id).order_by(Claim.created_at.desc()).all()
    return jsonify([claim_to_dict(c) for c in claims])


@app.route("/admin/users", methods=["GET"])
@roles_required("admin")
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify([user.to_dict() for user in users])


@app.route("/admin/users/<int:user_id>/role", methods=["PUT"])
@roles_required("admin")
def admin_update_role(user_id):
    admin = current_user_record()
    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json() or {}
    role = str(data.get("role", "")).strip().lower()
    if role not in VALID_ROLES:
        return jsonify({"error": "Invalid role"}), 400
    if user.id == admin.id and role != "admin":
        return jsonify({"error": "An admin cannot remove their own admin role"}), 400

    user.role = role
    audit(admin.id, "user_role_changed", "user", user.id, {"role": role})
    db.session.commit()
    return jsonify({"message": "Role updated", "user": user.to_dict()})


@app.route("/admin/audit-logs", methods=["GET"])
@roles_required("admin")
def admin_audit_logs():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
    return jsonify([{
        "id": log.id,
        "user_id": log.user_id,
        "action": log.action,
        "entity_type": log.entity_type,
        "entity_id": log.entity_id,
        "details": log.details,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    } for log in logs])


@app.route("/admin/overview", methods=["GET"])
@roles_required("admin")
def admin_overview():
    return jsonify({
        "users": User.query.count(),
        "customers": CustomerProfile.query.count(),
        "providers": Provider.query.count(),
        "policies": Policy.query.count(),
        "applications": Application.query.count(),
        "claims": Claim.query.count(),
        "billing_transactions": BillingTransaction.query.count(),
    })



def policy_to_dict(policy):
    return {"id":policy.id,"policy_number":policy.policy_number,"customer_id":policy.customer_id,"provider_id":policy.provider_id,"policy_type":policy.policy_type,"status":policy.status,"coverage_limit":policy.coverage_limit,"premium_amount":policy.premium_amount,"start_date":policy.start_date.isoformat() if policy.start_date else None,"end_date":policy.end_date.isoformat() if policy.end_date else None,"terms_document":policy.terms_document}

@app.route("/policies",methods=["GET"])
@roles_required("customer","admin","underwriter","claims_officer","provider")
def list_policies():
    u=current_user_record(); q=Policy.query
    if u.role=="customer":
        p=customer_for_user(u); q=q.filter_by(customer_id=p.id) if p else q.filter_by(id=-1)
    if u.role=="provider":
        p=provider_for_user(u); q=q.filter_by(provider_id=p.id) if p else q.filter_by(id=-1)
    return jsonify([policy_to_dict(p) for p in q.order_by(Policy.created_at.desc()).all()])

@app.route("/policies/<int:policy_id>/document",methods=["PUT"])
@roles_required("admin","underwriter","claims_officer")
def policy_document(policy_id):
    p=db.session.get(Policy,policy_id)
    if not p:return jsonify({"error":"Policy not found"}),404
    text=str((request.get_json() or {}).get("document_text","")).strip()
    if not text:return jsonify({"error":"document_text is required"}),400
    p.terms_document=text;audit(current_user_record().id,"policy_document_indexed","policy",p.id,{"characters":len(text)});db.session.commit()
    return jsonify({"message":"Policy document indexed","policy":policy_to_dict(p)})

@app.route("/policies/<int:policy_id>/intelligence",methods=["POST"])
@roles_required("customer","admin","underwriter","claims_officer","provider")
def policy_intelligence(policy_id):
    p=db.session.get(Policy,policy_id)
    if not p:return jsonify({"error":"Policy not found"}),404
    d=request.get_json() or {};text=str(d.get("document_text") or p.terms_document or "").strip();q=str(d.get("question") or "").strip()
    if not text:return jsonify({"error":"No policy document text available"}),400
    parts=[v.strip() for v in text.replace("\r","").split("\n") if v.strip()];words={w.lower() for w in q.split() if len(w)>2};hits=sorted(parts,key=lambda v:sum(w in v.lower() for w in words),reverse=True)[:3]
    indexed = index_policy_chunks(p.id, parts)
    retrieved = retrieve_policy_chunks(p.id, q) if q else []
    context = retrieved or [{"text":v,"section":i+1} for i,v in enumerate(hits)]
    generated = hf_request("Answer the insurance policy question using only this policy text. If the answer is not specified, say so. Question: " + q + "\\nPolicy text:\\n" + "\\n".join(x["text"] for x in context)) if q else None
    audit(current_user_record().id,"policy_intelligence_query","policy",p.id,{"question":q});db.session.commit()
    return jsonify({"policy":policy_to_dict(p),"question":q,"answer":generated or " ".join(x["text"] for x in context)[:4000],"sources":context,"retrieval":"Chroma + Hugging Face" if retrieved else "RiskSure policy retrieval","indexed_chunks":indexed})

@app.route("/fraud/investigation/<int:claim_id>",methods=["GET"])
@roles_required("claims_officer","underwriter","admin")
def fraud_investigation(claim_id):
    c=db.session.get(Claim,claim_id)
    if not c:return jsonify({"error":"Claim not found"}),404
    related=Claim.query.filter((Claim.customer_id==c.customer_id)|(Claim.provider_id==c.provider_id)).all();signals=[]
    if len([x for x in related if x.customer_id==c.customer_id])>=3:signals.append({"type":"repeat_customer","severity":"medium"})
    if c.provider_id and len([x for x in related if x.provider_id==c.provider_id])>=3:signals.append({"type":"repeat_provider","severity":"medium"})
    if (c.claimed_amount or 0)>100000:signals.append({"type":"high_amount","severity":"high"})
    score=min(1.0,.2*len(signals)+.05*max(0,len(related)-1))
    audit(current_user_record().id,"fraud_investigation_viewed","claim",c.id,{"anomaly_score":score});db.session.commit()
    neo4j_upsert_claim({"customer_id":c.customer_id,"claim_id":c.id,"claim_number":c.claim_number,"amount":c.claimed_amount,"status":c.status,"provider_id":c.provider_id})
    graph_from_neo4j=neo4j_claim_graph(c.id)
    nodes=graph_from_neo4j["nodes"] or [{"id":"customer-"+str(c.customer_id),"type":"customer"},{"id":"claim-"+str(c.id),"type":"claim"}]
    edges=graph_from_neo4j["edges"] or [{"source":"customer-"+str(c.customer_id),"target":"claim-"+str(c.id),"relationship":"submitted"}]
    if c.provider_id:nodes.append({"id":"provider-"+str(c.provider_id),"type":"provider"});edges.append({"source":"provider-"+str(c.provider_id),"target":"claim-"+str(c.id),"relationship":"submitted_to"})
    return jsonify({"claim":claim_to_dict(c),"graph":{"nodes":nodes,"edges":edges},"anomaly_score":round(score,3),"signals":signals,"recommendation":"Human investigation recommended." if signals else "No configured anomaly signal detected."})

@app.route("/billing",methods=["GET"])
@roles_required("customer","admin")
def billing_list():
    u=current_user_record();q=BillingTransaction.query
    if u.role=="customer":
        p=customer_for_user(u);q=q.filter_by(customer_id=p.id) if p else q.filter_by(id=-1)
    return jsonify([{"id":x.id,"policy_id":x.policy_id,"claim_id":x.claim_id,"transaction_type":x.transaction_type,"amount":x.amount,"status":x.status,"reference":x.reference,"description":x.description,"created_at":x.created_at.isoformat() if x.created_at else None} for x in q.order_by(BillingTransaction.created_at.desc()).all()])

@app.route("/billing",methods=["POST"])
@roles_required("customer","admin")
def billing_create():
    u=current_user_record();d=request.get_json() or {}
    try:amount=float(d["amount"])
    except(KeyError,TypeError,ValueError):return jsonify({"error":"Valid amount is required"}),400
    p=customer_for_user(u) if u.role=="customer" else db.session.get(CustomerProfile,int(d.get("customer_id",0)))
    if not p:return jsonify({"error":"Customer profile not found"}),404
    t=BillingTransaction(customer_id=p.id,policy_id=d.get("policy_id"),claim_id=d.get("claim_id"),transaction_type=str(d.get("transaction_type","premium")),amount=amount,status=str(d.get("status","pending")),reference="RS-BILL-"+os.urandom(5).hex().upper(),description=str(d.get("description","")))
    db.session.add(t);db.session.flush();audit(u.id,"billing_transaction_created","billing_transaction",t.id);db.session.commit();return jsonify({"message":"Billing transaction created","id":t.id,"reference":t.reference}),201

@app.route("/customer/portal",methods=["GET"])
@roles_required("customer")
def customer_portal():
    u=current_user_record();p=customer_for_user(u)
    if not p:return jsonify({"error":"Customer profile not found"}),404
    return jsonify({"profile":{"id":p.id,"full_name":p.full_name,"phone":p.phone,"city":p.city,"state":p.state},"policies":[policy_to_dict(x) for x in Policy.query.filter_by(customer_id=p.id).all()],"claims":[claim_to_dict(x) for x in Claim.query.filter_by(customer_id=p.id).all()],"applications":[x.to_dict() for x in Application.query.filter_by(customer_id=p.id).all()]})

@app.route("/cases/<int:application_id>/intelligence",methods=["GET"])
@roles_required("underwriter","claims_officer","admin")
def unified_case_intelligence(application_id):
    a=db.session.get(Application,application_id)
    if not a:return jsonify({"error":"Application not found"}),404
    claims=Claim.query.filter_by(customer_id=a.customer_id).all() if a.customer_id else [];p=Policy.query.filter_by(customer_id=a.customer_id).first() if a.customer_id else None
    signals=[{"claim_id":c.id,"provider_id":c.provider_id} for c in claims if c.provider_id]
    consistency=["High-value claim requires human review."] if any((c.claimed_amount or 0)>100000 for c in claims) else []
    return jsonify({"application":a.to_dict(),"risk":{"model_score":a.risk_score,"final_risk":a.final_risk,"decision":a.decision},"policy":policy_to_dict(p) if p else None,"claims":[claim_to_dict(c) for c in claims],"relationship_signals":signals,"document_consistency":consistency,"human_review_required":bool(consistency or a.review_status in {"manual_review","in_review"})})

@app.route("/graph/claim/<int:claim_id>",methods=["GET"])
@roles_required("claims_officer","underwriter","admin")
def claim_graph(claim_id):
    c=db.session.get(Claim,claim_id)
    if not c:return jsonify({"error":"Claim not found"}),404
    related=Claim.query.filter((Claim.customer_id==c.customer_id)|(Claim.provider_id==c.provider_id)).all()
    nodes=[];edges=[]
    def add(n,t): 
        if not any(x["id"]==n for x in nodes):nodes.append({"id":n,"type":t})
    add("customer-"+str(c.customer_id),"customer")
    for x in related:
        add("claim-"+str(x.id),"claim");edges.append({"source":"customer-"+str(c.customer_id),"target":"claim-"+str(x.id),"relationship":"submitted"})
        if x.provider_id:
            add("provider-"+str(x.provider_id),"provider");edges.append({"source":"provider-"+str(x.provider_id),"target":"claim-"+str(x.id),"relationship":"submitted_to"})
    return jsonify({"nodes":nodes,"edges":edges})

@app.route("/claims/<int:claim_id>/intelligence",methods=["POST"])
@roles_required("claims_officer","underwriter","admin")
def claim_intelligence(claim_id):
    c=db.session.get(Claim,claim_id)
    if not c:return jsonify({"error":"Claim not found"}),404
    d=request.get_json() or {};text=str(d.get("document_text","")).strip()
    extracted={"claim_number":c.claim_number,"claimed_amount":c.claimed_amount,"document_present":bool(text)}
    signals=[]
    if text and c.claimed_amount and str(c.claimed_amount) not in text:signals.append("Claimed amount was not found verbatim in supplied document.")
    if c.claimed_amount and c.claimed_amount>100000:signals.append("High-value claim requires human review.")
    return jsonify({"claim":claim_to_dict(c),"extracted":extracted,"signals":signals,"human_review_required":bool(signals)})

@app.route("/claims/<int:claim_id>/image-intelligence",methods=["POST"])
@roles_required("claims_officer","underwriter","admin")
def claim_image_intelligence(claim_id):
    c=db.session.get(Claim,claim_id)
    if not c:return jsonify({"error":"Claim not found"}),404
    d=request.get_json() or {}
    path=str(d.get("image_path","")).strip()
    if not path:return jsonify({"error":"image_path is required"}),400
    return jsonify({"claim":claim_to_dict(c),"image_analysis":analyze_claim_image(path)})

@app.route("/cases/<int:application_id>/review",methods=["GET"])
@roles_required("underwriter","claims_officer","admin")
def case_review(application_id):
    a=db.session.get(Application,application_id)
    if not a:return jsonify({"error":"Application not found"}),404
    intelligence=unified_case_intelligence(application_id)
    return intelligence

@app.route("/health/detailed",methods=["GET"])
def detailed_health():
    return jsonify({"status":"ok","database":db.session.execute(db.text("SELECT 1")).scalar()==1,"model_loaded":model is not None,"environment":os.getenv("FLASK_ENV","development")})

@app.route("/integrations/status",methods=["GET"])
@roles_required("admin")
def integrations_status():
    return jsonify({
        "postgres": bool(os.getenv("DATABASE_URL") or os.getenv("NEON_DATABASE_URL")),
        "neo4j": bool(os.getenv("NEO4J_URI") and os.getenv("NEO4J_USERNAME") and os.getenv("NEO4J_PASSWORD")),
        "huggingface": bool(os.getenv("HUGGINGFACE_API_TOKEN")),
        "chroma": bool(os.getenv("CHROMA_HOST")),
        "frontend_origin": bool(os.getenv("FRONTEND_ORIGIN"))
    })

if __name__ == "__main__":
    print("Starting Flask server...")
    print(f"Model loaded: {model_loaded}")
    app.run(host="0.0.0.0", port=5000, debug=True)

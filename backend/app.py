from functools import wraps

from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager, create_access_token, get_jwt, get_jwt_identity, jwt_required
import joblib
import numpy as np
import os
import json

from database import db
from models import Application, User, CustomerProfile

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///risksure.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "dev-only-change-this-secret")
jwt = JWTManager(app)
db.init_app(app)

with app.app_context():
    db.create_all()


VALID_ROLES = {"customer", "underwriter", "claims_officer", "provider", "admin"}
STAFF_ROLES = {"underwriter", "claims_officer", "provider", "admin"}


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


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,PUT,POST,DELETE,OPTIONS"
    return response


MODEL_DIR = os.path.join(os.path.dirname(__file__), "model")
model_loaded = False
model = None
explainer = None
feature_names = ["age", "sex", "bmi", "children", "smoker", "region"]
min_charge = 1000.0
max_charge = 50000.0

print("Attempting to load ML model...")
try:
    import sklearn

    print("--- ENVIRONMENT DEBUG ---")
    print(f"NumPy Version: {np.__version__}")
    print(f"Scikit-Learn Version: {sklearn.__version__}")
    print("-------------------------")

    from xgboost import XGBRegressor
    import shap

    model = XGBRegressor()
    model.load_model(os.path.join(MODEL_DIR, "insurance_xgb_model.json"))
    explainer = shap.TreeExplainer(model)
    risk_bounds = joblib.load(os.path.join(MODEL_DIR, "risk_bounds.pkl"))

    min_charge = risk_bounds.get("min_charge", 0) if isinstance(risk_bounds, dict) else risk_bounds[0]
    max_charge = risk_bounds.get("max_charge", 1) if isinstance(risk_bounds, dict) else risk_bounds[1]

    metadata_path = os.path.join(MODEL_DIR, "feature_metadata.json")
    if os.path.exists(metadata_path):
        with open(metadata_path, "r", encoding="utf-8") as metadata_file:
            feature_names = json.load(metadata_file).get("features", feature_names)

    model_loaded = True
    print("XGBoost underwriting model loaded successfully")
except Exception as error:
    print("ERROR loading ML model:", error)
    model_loaded = False


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
    db.session.commit()
    return jsonify({"message": "Account created", "user": user.to_dict()}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    user = User.query.filter_by(email=email).first()

    if user is None or user.role not in VALID_ROLES or not user.check_password(password):
        return jsonify({"error": "Invalid email or password"}), 401

    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
    return jsonify({"access_token": token, "user": user.to_dict()})


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

    input_array = np.array([[age, sex, bmi, children, smoker, region]], dtype=float)

    if not model_loaded:
        return jsonify({"error": "XGBoost underwriting model not loaded", "model_status": "failed"}), 503

    prediction = float(model.predict(input_array)[0])
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
    if explainer is not None:
        shap_values = explainer(input_array)
        contributions = np.asarray(shap_values.values[0], dtype=float)
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
        "model_status": "xgboost",
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


if __name__ == "__main__":
    print("Starting Flask server...")
    print(f"Model loaded: {model_loaded}")
    app.run(host="0.0.0.0", port=5000, debug=True)

from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager, create_access_token, get_jwt, get_jwt_identity, jwt_required
import joblib
import numpy as np
import os

from database import db
from models import Application, User

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


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,PUT,POST,DELETE,OPTIONS"
    return response


MODEL_DIR = os.path.join(os.path.dirname(__file__), "model")
model_loaded = False
model = None
scaler = None
min_charge = 1000.0
max_charge = 50000.0

print("Attempting to load ML model...")
try:
    import sklearn

    print("--- ENVIRONMENT DEBUG ---")
    print(f"NumPy Version: {np.__version__}")
    print(f"Scikit-Learn Version: {sklearn.__version__}")
    print("-------------------------")

    model = joblib.load(os.path.join(MODEL_DIR, "insurance_model.pkl"))
    scaler = joblib.load(os.path.join(MODEL_DIR, "insurance_scaler.pkl"))
    risk_bounds = joblib.load(os.path.join(MODEL_DIR, "risk_bounds.pkl"))

    min_charge = risk_bounds.get("min_charge", 0) if isinstance(risk_bounds, dict) else risk_bounds[0]
    max_charge = risk_bounds.get("max_charge", 1) if isinstance(risk_bounds, dict) else risk_bounds[1]

    model_loaded = True
    print("ML Model loaded successfully")
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

    if user is None or not user.check_password(password):
        return jsonify({"error": "Invalid email or password"}), 401

    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
    return jsonify({"access_token": token, "user": user.to_dict()})


@app.route("/auth/me", methods=["GET"])
@jwt_required()
def current_user():
    user = db.session.get(User, int(get_jwt_identity()))
    if user is None:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"user": user.to_dict()})


@app.route("/auth/staff-only", methods=["GET"])
@jwt_required()
def staff_only():
    role = get_jwt().get("role")
    if role not in {"underwriter", "claims_officer", "provider", "admin"}:
        return jsonify({"error": "Staff access required"}), 403
    return jsonify({"message": "Staff access granted", "role": role})


@app.route("/process", methods=["POST"])
def process():
    data = request.get_json()

    age = data.get("age", 0)
    sex_raw = data.get("sex", "male")
    bmi = data.get("bmi", 0.0)
    children = data.get("children", 0)
    smoker_raw = data.get("smoker", "no")
    region_raw = data.get("region", "southwest")

    sex = 1 if str(sex_raw).lower() == "male" else 0
    smoker = 1 if str(smoker_raw).lower() in ["yes", "true", "1"] else 0

    region_map = {"southwest": 0, "southeast": 1, "northwest": 2, "northeast": 3}
    region = region_map.get(str(region_raw).lower(), 0)

    input_array = np.array([[age, sex, bmi, children, smoker, region]])
    if model_loaded is False:
        return jsonify({"error": "ML model not loaded", "model_status": "failed"}), 503

    print("Running real ML prediction...")
    scaled_input = scaler.transform(input_array)
    prediction = model.predict(scaled_input)[0]

    risk_score = (prediction - min_charge) / (max_charge - min_charge)
    risk_score = max(0.0, min(1.0, float(risk_score)))

    rule_adjustment = 0.0
    if smoker == 1:
        rule_adjustment += 0.20
    if bmi > 30:
        rule_adjustment += 0.05
    if children > 2:
        rule_adjustment += 0.05

    final_risk = risk_score + rule_adjustment

    if final_risk < 0.5:
        decision = "Approved"
    elif 0.5 <= final_risk <= 0.9:
        decision = "Approved with Conditions"
    else:
        decision = "Manual Review"

    base_premium = 5000.0
    premium = base_premium * (1.0 + risk_score + rule_adjustment)

    return jsonify({
        "predicted_charge": float(prediction),
        "risk_score": float(risk_score),
        "rule_adjustment": float(rule_adjustment),
        "final_risk": float(final_risk),
        "decision": decision,
        "premium": float(premium),
        "model_status": "real",
    })


@app.route("/save", methods=["POST"])
@jwt_required()
def save():
    data = request.get_json()

    application = Application(
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

    return jsonify({
        "message": "Application saved successfully",
        "application": application.to_dict(),
    })


@app.route("/applications", methods=["GET"])
@jwt_required()
def get_applications():
    applications = Application.query.order_by(Application.created_at.desc()).all()
    return jsonify([application.to_dict() for application in applications])


@app.route("/applications/<int:application_id>", methods=["GET"])
@jwt_required()
def get_application(application_id):
    application = db.session.get(Application, application_id)
    if application is None:
        return jsonify({"error": "Application not found"}), 404
    return jsonify(application.to_dict())


if __name__ == "__main__":
    print("Starting Flask server...")
    print(f"Model loaded: {model_loaded}")
    app.run(host="0.0.0.0", port=5000, debug=True)

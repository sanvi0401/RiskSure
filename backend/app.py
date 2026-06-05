from flask import Flask, jsonify, request
import joblib
import numpy as np
import os

app = Flask(__name__)


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,PUT,POST,DELETE,OPTIONS"
    return response


applications = []
application_counter = 1

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
        "saved_applications": len(applications),
    })


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
def save():
    global application_counter

    data = request.get_json()

    application = {
        "id": application_counter,
        "name": data.get("name", "Unknown"),
        "risk_score": float(data.get("risk_score", 0.0)),
        "rule_adjustment": float(data.get("rule_adjustment", 0.0)),
        "final_risk": float(data.get("final_risk", 0.0)),
        "decision": str(data.get("decision", "Unknown")),
        "premium": float(data.get("premium", 0.0)),
    }

    applications.append(application)
    application_counter += 1

    return jsonify({"message": "Application saved successfully", "application": application})


@app.route("/applications", methods=["GET"])
def get_applications():
    return jsonify(applications)


if __name__ == "__main__":
    print("Starting Flask server...")
    print(f"Model loaded: {model_loaded}")
    app.run(host="0.0.0.0", port=5000, debug=True)

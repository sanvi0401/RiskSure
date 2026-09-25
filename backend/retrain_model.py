import json
import os

import joblib
import numpy as np
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor

# Synthetic training data matching the current RiskSure application schema.
# This keeps the repository self-contained while the production training pipeline
# is being connected to validated insurer data.
np.random.seed(42)
N = 5000

age = np.random.randint(18, 75, N)
sex = np.random.randint(0, 2, N)
bmi = np.random.uniform(15.0, 45.0, N)
children = np.random.randint(0, 5, N)
smoker = np.random.randint(0, 2, N)
region = np.random.randint(0, 4, N)

X = np.column_stack([age, sex, bmi, children, smoker, region]).astype(float)

# Non-linear synthetic target: intentionally includes interactions so the
# underwriting model has meaningful feature contributions to explain.
charges = (
    1800
    + (age * 210)
    + (bmi * 105)
    + (children * 430)
    + (smoker * 18500)
    + (smoker * bmi * 120)
    + np.maximum(age - 50, 0) ** 2 * 18
    + np.random.normal(0, 1200, N)
)
charges = np.maximum(charges, 1000)

X_train, X_test, y_train, y_test = train_test_split(
    X, charges, test_size=0.2, random_state=42
)

model = XGBRegressor(
    n_estimators=350,
    max_depth=5,
    learning_rate=0.05,
    subsample=0.9,
    colsample_bytree=0.9,
    objective="reg:squarederror",
    eval_metric="rmse",
    random_state=42,
)

model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

MODEL_DIR = os.path.join(os.path.dirname(__file__), "model")
os.makedirs(MODEL_DIR, exist_ok=True)

model.save_model(os.path.join(MODEL_DIR, "insurance_xgb_model.json"))

risk_bounds = {
    "min_charge": float(np.min(y_train)),
    "max_charge": float(np.max(y_train)),
}

joblib.dump(risk_bounds, os.path.join(MODEL_DIR, "risk_bounds.pkl"))

feature_metadata = {
    "features": ["age", "sex", "bmi", "children", "smoker", "region"],
    "categorical_mappings": {
        "sex": {"female": 0, "male": 1},
        "smoker": {"no": 0, "yes": 1},
        "region": {"southwest": 0, "southeast": 1, "northwest": 2, "northeast": 3},
    },
}

with open(os.path.join(MODEL_DIR, "feature_metadata.json"), "w", encoding="utf-8") as file:
    json.dump(feature_metadata, file, indent=2)

print("XGBoost underwriting model trained successfully.")
print(f"Saved model to: {os.path.join(MODEL_DIR, 'insurance_xgb_model.json')}")

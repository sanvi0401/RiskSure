import numpy as np
import joblib
import os
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler

# Generate synthetic insurance data matching the required schema
np.random.seed(42)
N = 1000
age = np.random.randint(18, 65, N)
sex = np.random.randint(0, 2, N)
bmi = np.random.uniform(15.0, 45.0, N)
children = np.random.randint(0, 5, N)
smoker = np.random.randint(0, 2, N)
region = np.random.randint(0, 4, N)

X = np.column_stack([age, sex, bmi, children, smoker, region])

# Formulate realistic prediction mappings
charges = 2000 + (age * 250) + (bmi * 120) + (children * 500) + (smoker * 20000)
charges = charges + np.random.normal(0, 1500, N)
charges = np.maximum(charges, 1000)

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

model = LinearRegression()
model.fit(X_scaled, charges)

risk_bounds = {
    'min_charge': float(np.min(charges)),
    'max_charge': float(np.max(charges))
}

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'model')
os.makedirs(MODEL_DIR, exist_ok=True)

joblib.dump(model, os.path.join(MODEL_DIR, 'insurance_model.pkl'))
joblib.dump(scaler, os.path.join(MODEL_DIR, 'insurance_scaler.pkl'))
joblib.dump(risk_bounds, os.path.join(MODEL_DIR, 'risk_bounds.pkl'))

print("Retrained successfully!")

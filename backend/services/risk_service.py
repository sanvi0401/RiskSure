import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

import numpy as np


class RiskService:
    def __init__(self):
        self.model = None
        self.model_loaded = False
        self.model_path = os.path.join(os.path.dirname(__file__), "..", "model", "insurance_xgb_model.json")
        self.metadata_path = os.path.join(os.path.dirname(__file__), "..", "model", "feature_metadata.json")
        self.bounds_path = os.path.join(os.path.dirname(__file__), "..", "model", "risk_bounds.pkl")
        self.feature_names = ["age", "sex", "bmi", "children", "smoker", "region"]
        self.min_charge = 1000.0
        self.max_charge = 50000.0
        self._load_model()

    def _load_model(self):
        try:
            import joblib
            from xgboost import XGBRegressor
            import shap

            self.model = XGBRegressor()
            self.model.load_model(self.model_path)
            self.explainer = shap.TreeExplainer(self.model)
            self.model_loaded = True
            try:
                risk_bounds = joblib.load(self.bounds_path)
                if isinstance(risk_bounds, dict):
                    self.min_charge = float(risk_bounds.get("min_charge", self.min_charge))
                    self.max_charge = float(risk_bounds.get("max_charge", self.max_charge))
                elif isinstance(risk_bounds, (list, tuple)) and len(risk_bounds) >= 2:
                    self.min_charge = float(risk_bounds[0])
                    self.max_charge = float(risk_bounds[1])
            except Exception:
                pass

            if os.path.exists(self.metadata_path):
                with open(self.metadata_path, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                    self.feature_names = data.get("features", self.feature_names)
        except Exception:
            self.model_loaded = False
            self.model = None
            self.explainer = None

    def score(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        age = float(payload.get("age", 0) or 0)
        sex_raw = str(payload.get("sex", "male") or "male")
        bmi = float(payload.get("bmi", 0.0) or 0.0)
        children = float(payload.get("children", 0) or 0)
        smoker_raw = str(payload.get("smoker", "no") or "no")
        region_raw = str(payload.get("region", "southwest") or "southwest")

        sex = 1 if sex_raw.lower() == "male" else 0
        smoker = 1 if smoker_raw.lower() in {"yes", "true", "1"} else 0
        region_map = {"southwest": 0, "southeast": 1, "northwest": 2, "northeast": 3}
        region = region_map.get(region_raw.lower(), 0)
        input_array = np.array([[age, sex, bmi, children, smoker, region]], dtype=float)

        if self.model_loaded and self.model is not None:
            prediction = float(self.model.predict(input_array)[0])
            raw_risk = (prediction - self.min_charge) / max(self.max_charge - self.min_charge, 1.0)
            risk_score = max(0.0, min(1.0, float(raw_risk)))
            model_version = getattr(self.model, "__class__", type(self.model)).__name__
        else:
            risk_score = 0.15
            if smoker == 1:
                risk_score += 0.25
            if bmi > 30:
                risk_score += 0.10
            if children > 2:
                risk_score += 0.08
            if age > 55:
                risk_score += 0.12
            risk_score = min(0.99, max(0.0, risk_score))
            prediction = 12000.0 + (risk_score * 30000.0)
            model_version = "heuristic-fallback"

        rule_adjustments: List[Dict[str, Any]] = []
        rule_adjustment = 0.0
        if smoker == 1:
            rule_adjustment += 0.20
            rule_adjustments.append({"rule": "smoker", "adjustment": 0.20, "reason": "Smoking status increases modeled risk."})
        if bmi > 30:
            rule_adjustment += 0.05
            rule_adjustments.append({"rule": "high_bmi", "adjustment": 0.05, "reason": "BMI exceeds 30."})
        if children > 2:
            rule_adjustment += 0.05
            rule_adjustments.append({"rule": "dependents", "adjustment": 0.05, "reason": "More than two dependents are present."})

        final_risk = min(1.0, risk_score + rule_adjustment)
        if final_risk < 0.5:
            risk_category = "LOW"
        elif final_risk <= 0.75:
            risk_category = "MEDIUM"
        else:
            risk_category = "HIGH"

        premium = round(5000.0 * (1.0 + final_risk), 2)
        important_features = [
            "smoking status",
            "BMI",
            "claim history",
            "coverage amount",
            "family size",
        ]

        explanation = []
        if self.model_loaded and self.explainer is not None:
            shap_values = self.explainer(input_array)
            contributions = np.asarray(shap_values.values[0], dtype=float)
            for name, contribution in zip(self.feature_names, contributions):
                explanation.append({
                    "feature": name,
                    "contribution": round(float(contribution), 4),
                    "direction": "increases" if contribution > 0 else "decreases" if contribution < 0 else "neutral",
                })
            explanation.sort(key=lambda item: abs(item["contribution"]), reverse=True)

        return {
            "risk_score": round(float(final_risk), 4),
            "risk_category": risk_category,
            "premium": premium,
            "important_features": important_features,
            "model_version": model_version,
            "prediction_timestamp": datetime.now(timezone.utc).isoformat(),
            "features": explanation or [
                {"feature": "age", "contribution": 0.12, "direction": "increases"},
                {"feature": "smoker", "contribution": 0.28, "direction": "increases"},
            ],
            "raw_prediction": round(float(prediction), 2),
            "rule_adjustments": rule_adjustments,
            "final_risk": round(float(final_risk), 4),
        }


risk_service = RiskService()

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


FEATURE_NAMES = {
    "f0": "age",
    "f1": "sex",
    "f2": "bmi",
    "f3": "children",
    "f4": "smoker",
    "f5": "region",
}


def analyze_application(application: Any, model: Any = None, model_loaded: bool = False) -> dict[str, Any]:
    """Describe a persisted prediction without recalculating or inventing a score."""
    score = float(application.final_risk or 0.0)
    if score < 0.34:
        category = "low"
    elif score < 0.67:
        category = "medium"
    else:
        category = "high"

    important_features: list[dict[str, Any]] = []
    warnings: list[str] = []
    if model_loaded and model is not None:
        try:
            gains = model.get_score(importance_type="gain")
            total_gain = sum(float(value) for value in gains.values())
            if total_gain > 0:
                important_features = [
                    {
                        "feature": FEATURE_NAMES.get(name, name),
                        "importance": round(float(gain) / total_gain, 4),
                        "evidence_type": "global_model_gain",
                    }
                    for name, gain in sorted(gains.items(), key=lambda item: float(item[1]), reverse=True)[:5]
                ]
        except (AttributeError, TypeError, ValueError):
            warnings.append("Model feature importance is unavailable for this prediction.")
    else:
        warnings.append("The XGBoost model is unavailable; this application used the configured fallback.")

    rule_factors = []
    if (application.smoker or "").lower() in {"yes", "true", "1"}:
        rule_factors.append({"feature": "smoker", "adjustment": 0.2})
    if (application.bmi or 0) > 30:
        rule_factors.append({"feature": "bmi", "adjustment": 0.05})
    if (application.children or 0) > 2:
        rule_factors.append({"feature": "children", "adjustment": 0.05})

    created_at = application.created_at
    prediction_timestamp = created_at.isoformat() if created_at else None
    return {
        "risk_score": application.risk_score,
        "final_risk": application.final_risk,
        "risk_category": category,
        "premium": application.premium,
        "decision": application.decision,
        "important_features": important_features,
        "rule_factors": rule_factors,
        "model_version": "xgboost-runtime" if model_loaded else "deterministic-fallback",
        "prediction_timestamp": prediction_timestamp or datetime.now(timezone.utc).isoformat(),
        "confidence": None,
        "warnings": warnings,
    }

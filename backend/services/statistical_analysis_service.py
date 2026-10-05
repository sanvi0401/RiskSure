from __future__ import annotations

import math
from statistics import mean, median, pstdev
from typing import Any, Iterable


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _pearson(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < 3:
        return None
    left = [pair[0] for pair in pairs]
    right = [pair[1] for pair in pairs]
    left_sd, right_sd = pstdev(left), pstdev(right)
    if left_sd == 0 or right_sd == 0:
        return None
    return round(sum((x - mean(left)) * (y - mean(right)) for x, y in pairs) / len(pairs) / left_sd / right_sd, 4)


def analyze_applications(applications: Iterable[Any], subject: Any | None = None) -> dict[str, Any]:
    rows = list(applications)
    scores = [value for row in rows if (value := _number(getattr(row, "final_risk", None))) is not None]
    premiums = [value for row in rows if (value := _number(getattr(row, "premium", None))) is not None]
    groups: dict[str, list[Any]] = {"low": [], "medium": [], "high": []}
    for row in rows:
        score = _number(getattr(row, "final_risk", None))
        if score is not None:
            groups["low" if score < 0.34 else "medium" if score < 0.67 else "high"].append(row)

    distributions = {
        name: {
            "count": len(group),
            "mean_risk": round(mean([float(row.final_risk) for row in group]), 4) if group else None,
            "mean_premium": round(mean([float(row.premium) for row in group]), 2) if group else None,
        }
        for name, group in groups.items()
    }
    subject_comparison: dict[str, Any] | None = None
    outliers: list[dict[str, Any]] = []
    if subject is not None:
        subject_score = _number(getattr(subject, "final_risk", None))
        if subject_score is not None:
            category = "low" if subject_score < 0.34 else "medium" if subject_score < 0.67 else "high"
            subject_comparison = {
                "risk_category": category,
                "cohort_size": len(groups[category]),
                "cohort_mean_risk": distributions[category]["mean_risk"],
                "cohort_mean_premium": distributions[category]["mean_premium"],
            }
        for feature in ("age", "bmi", "children", "premium", "final_risk"):
            values = [value for row in rows if (value := _number(getattr(row, feature, None))) is not None]
            current = _number(getattr(subject, feature, None))
            if current is None or len(values) < 4:
                continue
            ordered = sorted(values)
            midpoint = len(ordered) // 2
            lower = median(ordered[:midpoint]) if midpoint else ordered[0]
            upper = median(ordered[(len(ordered) + 1) // 2:])
            iqr = upper - lower
            if current < lower - 1.5 * iqr or current > upper + 1.5 * iqr:
                outliers.append({"feature": feature, "value": current, "method": "1.5x IQR"})

    correlations = {}
    for feature in ("age", "bmi", "children", "premium"):
        pairs = [
            (value, score)
            for row in rows
            if (value := _number(getattr(row, feature, None))) is not None
            and (score := _number(getattr(row, "final_risk", None))) is not None
        ]
        correlation = _pearson(pairs)
        if correlation is not None:
            correlations[f"{feature}_vs_final_risk"] = correlation

    return {
        "sample_size": len(scores),
        "risk_distribution": {name: group["count"] for name, group in distributions.items()},
        "risk_score_summary": {
            "mean": round(mean(scores), 4) if scores else None,
            "median": round(median(scores), 4) if scores else None,
            "min": min(scores) if scores else None,
            "max": max(scores) if scores else None,
        },
        "premium_summary": {
            "mean": round(mean(premiums), 2) if premiums else None,
            "median": round(median(premiums), 2) if premiums else None,
        },
        "risk_groups": distributions,
        "subject_comparison": subject_comparison,
        "outliers": outliers,
        "correlations": correlations,
        "limitations": [] if len(scores) >= 30 else ["Small cohort; statistics are descriptive and should not be treated as inferential evidence."],
    }

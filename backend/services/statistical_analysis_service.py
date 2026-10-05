from __future__ import annotations

from statistics import mean
from typing import Any, Dict, List


class StatisticalAnalysisService:
    def summarize(self, applications: List[Dict[str, Any]]) -> Dict[str, Any]:
        scores = [float(item.get("risk_score", 0) or 0) for item in applications]
        if not scores:
            return {"total_applications": 0, "average_risk_score": 0.0, "high_risk_count": 0, "risk_distribution": {"LOW": 0, "MEDIUM": 0, "HIGH": 0}}

        summary = {
            "total_applications": len(applications),
            "average_risk_score": round(mean(scores), 2),
            "high_risk_count": sum(1 for score in scores if score >= 0.75),
            "risk_distribution": {
                "LOW": sum(1 for score in scores if score < 0.5),
                "MEDIUM": sum(1 for score in scores if 0.5 <= score < 0.75),
                "HIGH": sum(1 for score in scores if score >= 0.75),
            },
        }
        return summary


statistical_analysis_service = StatisticalAnalysisService()

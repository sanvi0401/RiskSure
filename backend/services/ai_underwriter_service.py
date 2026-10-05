from __future__ import annotations

from typing import Any, Dict, List

from services.rag_service import rag_service


class AIUnderwriterService:
    def summarize_application(self, application: Dict[str, Any], risk_summary: Dict[str, Any]) -> Dict[str, Any]:
        related_factors = risk_summary.get("important_features", [])
        rules = rag_service.retrieve_rules("high risk insurance underwriting")
        policy_context = rag_service.retrieve_policy_context("risk score and underwriting")

        reasons = [
            "The modeled risk score indicates elevated exposure when compared with baseline underwriting thresholds.",
            "The applicant profile includes elevated risk indicators recognized by the underwriting model.",
            "Policy guidance supports manual review when the signal is driven by multiple known risk factors.",
        ]

        return {
            "summary": "This application shows elevated underwriting risk driven by known factors across the model, underwriting rules, and policy guidance.",
            "risk_factors": related_factors,
            "evidence": reasons,
            "policy_context": policy_context,
            "rules": rules,
            "recommended_action": "MANUAL REVIEW",
            "assistant_disclaimer": "This assistant does not approve or reject an application; a human underwriter must make the final decision.",
        }


ai_underwriter_service = AIUnderwriterService()

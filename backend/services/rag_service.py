from __future__ import annotations

import os
from typing import Any, Dict, List


class RAGService:
    def __init__(self):
        self.vector_index = os.getenv("VECTOR_INDEX_NAME", "risk_underwriting_demo")

    def retrieve_policy_context(self, query: str) -> List[Dict[str, Any]]:
        return [
            {
                "source": "underwriting_policy_demo",
                "title": "Smoking and high-risk coverage guidance",
                "summary": "Applications with smoking-related risk factors require additional documentation and manual review when risk exceeds the threshold.",
                "match_score": 0.91,
            }
        ]

    def retrieve_rules(self, query: str) -> List[Dict[str, Any]]:
        return [
            {
                "rule": "high_risk_manual_review",
                "text": "Any risk score above 0.75 should be escalated for manual underwriting review.",
            }
        ]


rag_service = RAGService()

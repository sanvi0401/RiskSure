from __future__ import annotations

import json
from typing import Any

from integrations import hf_request


class AIUnderwriterService:
    def summarize(self, evidence: dict[str, Any]) -> dict[str, Any]:
        if not evidence:
            return {
                "available": False,
                "summary": None,
                "warning": "No case evidence was supplied to the assistant.",
                "human_decision_required": True,
            }

        application = evidence.get("application") or {}
        graph = evidence.get("graph_evidence") or {}
        minimized_evidence = {
            "application_id": application.get("id"),
            "applicant_risk_inputs": {
                key: application.get(key)
                for key in ("age", "sex", "bmi", "children", "smoker", "region")
                if application.get(key) is not None
            },
            "risk": evidence.get("risk"),
            "statistics": evidence.get("statistics"),
            "relationship_evidence": {
                "source": graph.get("source"),
                "node_types": sorted({node.get("type") for node in graph.get("nodes", []) if node.get("type")}),
                "relationships": sorted({edge.get("relationship") for edge in graph.get("edges", []) if edge.get("relationship")}),
                "node_count": len(graph.get("nodes", [])),
                "relationship_count": len(graph.get("edges", [])),
            },
            "policy_evidence": evidence.get("policy_evidence", []),
            "decision_history": evidence.get("decision_history", []),
        }
        prompt = (
            "You are a decision-support assistant for a human insurance underwriter. "
            "Use only the supplied JSON evidence. Do not infer missing facts, invent policy terms, "
            "or approve, reject, bind, issue, or finalize insurance. State when evidence is missing. "
            "Summarize verified risk factors, statistical limitations, graph and policy evidence, "
            "then suggest investigation questions for the human reviewer. "
            "Return concise plain text. Evidence JSON:\n"
            + json.dumps(minimized_evidence, ensure_ascii=True, default=str)
        )
        try:
            summary = hf_request(prompt, max_tokens=500)
        except Exception:
            summary = None
        if not summary:
            return {
                "available": False,
                "summary": None,
                "warning": "AI provider is unavailable or not configured; no AI explanation was generated.",
                "human_decision_required": True,
            }
        return {
            "available": True,
            "summary": summary.strip(),
            "warning": "AI output is unverified decision support and must not be used as an automated decision.",
            "human_decision_required": True,
        }


ai_underwriter_service = AIUnderwriterService()

from __future__ import annotations

import json
import re
from typing import Any

from integrations import hf_request


def _graph_facts(graph: dict[str, Any]) -> dict[str, Any]:
    allowed_properties = {
        "application": ("id", "review_status", "risk_category", "decision"),
        "claim": ("id", "status", "amount", "claimed_amount"),
        "policy": ("id", "status", "policy_type"),
        "provider": ("id", "status", "provider_type"),
        "riskfactor": ("name", "value", "source"),
        "underwriter": ("id",),
        "decision": ("decision", "review_status", "reviewed_at"),
        "location": ("region", "city", "state"),
        "customer": ("id",),
    }
    nodes = []
    for node in graph.get("nodes", []):
        if not isinstance(node, dict):
            continue
        kind = str(node.get("type") or "").lower()
        properties = node.get("properties") or {}
        if not isinstance(properties, dict):
            properties = {}
        nodes.append({
            "id": node.get("id"),
            "type": kind,
            "properties": {
                key: properties[key]
                for key in allowed_properties.get(kind, ())
                if properties.get(key) is not None
            },
        })
    edges = [
        {
            "source": edge.get("source"),
            "target": edge.get("target"),
            "relationship": edge.get("relationship"),
        }
        for edge in graph.get("edges", [])
        if isinstance(edge, dict)
    ]
    return {
        "source": graph.get("source", "unavailable"),
        "nodes": nodes,
        "relationships": edges,
    }


def _parse_response(response: str) -> dict[str, Any] | None:
    text = response.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


class AIUnderwriterService:
    def summarize(self, evidence: dict[str, Any], question: str = "") -> dict[str, Any]:
        if not evidence:
            return {
                "available": False,
                "summary": None,
                "warning": "No case evidence was supplied to the assistant.",
                "warnings": ["No case evidence was supplied."],
                "human_decision_required": True,
            }

        application = evidence.get("application") or {}
        risk = evidence.get("risk") or {}
        statistics = evidence.get("statistics") or {}
        graph = _graph_facts(evidence.get("graph_evidence") or {})
        policy_evidence = [
            {
                "text": item["text"],
                "section": item.get("section"),
                "source": item.get("source"),
                "retrieval": item.get("retrieval"),
            }
            for item in evidence.get("policy_evidence", [])
            if isinstance(item, dict) and isinstance(item.get("text"), str) and item["text"].strip()
        ]
        source_warnings = []
        if not risk:
            source_warnings.append("Model evidence is unavailable.")
        if not statistics or not statistics.get("sample_size"):
            source_warnings.append("Statistical evidence is unavailable or has no cohort observations.")
        if not graph["nodes"]:
            source_warnings.append("No relationship graph evidence is available.")
        if not policy_evidence:
            source_warnings.append("No matching policy document evidence was retrieved.")

        minimized_evidence = {
            "application": {
                "application_id": application.get("id"),
                "applicant_risk_inputs": {
                    key: application.get(key)
                    for key in ("age", "sex", "bmi", "children", "smoker", "region")
                    if application.get(key) is not None
                },
                "review_status": application.get("review_status"),
            },
            "model_evidence": {
                key: risk.get(key)
                for key in ("risk_score", "final_risk", "risk_category", "premium", "model_version", "important_features", "rule_factors", "warnings")
                if risk.get(key) is not None
            },
            "statistical_evidence": statistics,
            "graph_evidence": graph,
            "policy_evidence": policy_evidence,
            "decision_history": evidence.get("decision_history", []),
            "question": question.strip()[:500] or "Summarize the evidence and identify investigation questions.",
        }
        prompt = (
            "You are a decision-support assistant for a human insurance underwriter. "
            "Use only the supplied JSON facts. Never infer missing facts, invent policy terms, "
            "or recommend approving/rejecting/binding/issuing a policy. Separate facts by source. "
            "Return only a JSON object with string fields `summary` and `risk_assessment`, "
            "array-of-string fields `key_risk_factors` and `recommended_investigation`, and "
            "a string-array `warnings`. If information is missing, state that it is unavailable. "
            "The summary is advisory interpretation, not a decision. Evidence JSON:\n"
            + json.dumps(minimized_evidence, ensure_ascii=True, default=str)
        )
        response = hf_request(prompt, max_tokens=700)
        if not response:
            return {
                "available": False,
                "summary": None,
                "warning": "AI provider is unavailable or not configured; no AI interpretation was generated.",
                "warnings": source_warnings,
                "model_evidence": minimized_evidence["model_evidence"],
                "statistical_evidence": statistics,
                "graph_evidence": graph,
                "policy_evidence": policy_evidence,
                "human_decision_required": True,
            }

        parsed = _parse_response(response)
        if parsed is None:
            summary = response.strip()
            ai_warnings = ["The AI response was not valid structured JSON; its interpretation is shown as plain text."]
            risk_assessment = None
            key_risk_factors: list[str] = []
            recommended_investigation: list[str] = []
        else:
            summary = parsed.get("summary") if isinstance(parsed.get("summary"), str) else ""
            risk_assessment = parsed.get("risk_assessment") if isinstance(parsed.get("risk_assessment"), str) else None
            key_risk_factors = [item for item in parsed.get("key_risk_factors", []) if isinstance(item, str)] if isinstance(parsed.get("key_risk_factors"), list) else []
            recommended_investigation = [item for item in parsed.get("recommended_investigation", []) if isinstance(item, str)] if isinstance(parsed.get("recommended_investigation"), list) else []
            ai_warnings = [item for item in parsed.get("warnings", []) if isinstance(item, str)] if isinstance(parsed.get("warnings"), list) else []
        warnings = source_warnings + ai_warnings
        return {
            "available": True,
            "summary": summary or None,
            "risk_assessment": risk_assessment,
            "key_risk_factors": key_risk_factors,
            "model_evidence": minimized_evidence["model_evidence"],
            "statistical_evidence": statistics,
            "graph_evidence": graph,
            "policy_evidence": policy_evidence,
            "recommended_investigation": recommended_investigation,
            "warnings": warnings,
            "warning": "AI output is unverified decision support. The human underwriter must make every final decision.",
            "confidence": None,
            "human_decision_required": True,
        }


ai_underwriter_service = AIUnderwriterService()

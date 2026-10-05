from __future__ import annotations

import re
from typing import Any

from integrations import retrieve_policy_chunks


def _chunks(document: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n\s*\n|(?<=[.!?])\s+(?=[A-Z])", document) if part.strip()]


class RAGService:
    def retrieve_policy_context(self, policy: Any, query: str, limit: int = 4) -> list[dict[str, Any]]:
        document = (policy.terms_document or "").strip()
        question = query.strip()
        if not document or not question or limit <= 0:
            return []

        try:
            indexed = retrieve_policy_chunks(policy.id, question, n_results=limit)
        except Exception:
            indexed = []
        if indexed:
            return [
                {
                    "text": item["text"],
                    "section": item.get("section"),
                    "source": f"policy:{policy.policy_number}",
                    "retrieval": "vector",
                }
                for item in indexed
                if item.get("text")
            ][:limit]

        terms = {term.lower() for term in re.findall(r"\w+", question) if len(term) > 2}
        paragraphs = _chunks(document)
        ranked = sorted(
            enumerate(paragraphs, start=1),
            key=lambda entry: sum(term in entry[1].lower() for term in terms),
            reverse=True,
        )
        matches = [
            {
                "text": paragraph,
                "section": section,
                "source": f"policy:{policy.policy_number}",
                "retrieval": "document_keyword",
            }
            for section, paragraph in ranked
            if any(term in paragraph.lower() for term in terms)
        ]
        return matches[:limit]


rag_service = RAGService()

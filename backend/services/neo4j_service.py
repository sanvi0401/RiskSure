from __future__ import annotations

import os
from typing import Any, Iterable

from integrations import neo4j_claim_graph, neo4j_upsert_claim


def _append_node(nodes: list[dict[str, Any]], seen: set[str], node_id: str, kind: str, properties: dict[str, Any]) -> None:
    if node_id not in seen:
        seen.add(node_id)
        nodes.append({"id": node_id, "type": kind, "properties": properties})


def _append_edge(edges: list[dict[str, str]], seen: set[tuple[str, str, str]], source: str, target: str, relationship: str) -> None:
    key = (source, target, relationship)
    if key not in seen:
        seen.add(key)
        edges.append({"source": source, "target": target, "relationship": relationship})


def application_graph(application: Any, claims: Iterable[Any], policy: Any | None = None) -> dict[str, Any]:
    """Build a case-scoped graph from PostgreSQL facts and available Neo4j relationships."""
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    seen_nodes: set[str] = set()
    seen_edges: set[tuple[str, str, str]] = set()
    customer_id = application.customer_id
    _append_node(nodes, seen_nodes, f"application-{application.id}", "application", {
        "id": application.id,
        "review_status": application.review_status,
        "risk_category": "high" if (application.final_risk or 0) >= 0.67 else "medium" if (application.final_risk or 0) >= 0.34 else "low",
    })
    if customer_id is not None:
        _append_node(nodes, seen_nodes, f"customer-{customer_id}", "customer", {"id": customer_id})
        _append_edge(edges, seen_edges, f"customer-{customer_id}", f"application-{application.id}", "submitted")
    if policy is not None:
        _append_node(nodes, seen_nodes, f"policy-{policy.id}", "policy", {
            "id": policy.id,
            "policy_number": policy.policy_number,
            "status": policy.status,
        })
        if customer_id is not None:
            _append_edge(edges, seen_edges, f"customer-{customer_id}", f"policy-{policy.id}", "holds")

    neo4j_used = False
    for claim in claims:
        payload = {
            "customer_id": claim.customer_id,
            "claim_id": claim.id,
            "claim_number": claim.claim_number,
            "amount": claim.claimed_amount,
            "status": claim.status,
            "provider_id": claim.provider_id,
        }
        try:
            neo4j_upsert_claim(payload)
            graph = neo4j_claim_graph(claim.id)
        except Exception:
            graph = {"nodes": [], "edges": []}
        if graph.get("nodes"):
            neo4j_used = True
            for node in graph["nodes"]:
                _append_node(nodes, seen_nodes, node["id"], node["type"], node.get("properties") or {})
            for edge in graph["edges"]:
                _append_edge(edges, seen_edges, edge["source"], edge["target"], edge["relationship"])
        else:
            _append_node(nodes, seen_nodes, f"claim-{claim.id}", "claim", {
                "id": claim.id,
                "claim_number": claim.claim_number,
                "status": claim.status,
                "amount": claim.claimed_amount,
            })
            if customer_id is not None:
                _append_edge(edges, seen_edges, f"customer-{customer_id}", f"claim-{claim.id}", "submitted")
            if claim.provider_id is not None:
                _append_node(nodes, seen_nodes, f"provider-{claim.provider_id}", "provider", {"id": claim.provider_id})
                _append_edge(edges, seen_edges, f"provider-{claim.provider_id}", f"claim-{claim.id}", "handles")
        _append_edge(edges, seen_edges, f"customer-{customer_id}", f"claim-{claim.id}", "has_claim") if customer_id is not None else None

    configured = all(os.getenv(name) for name in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"))
    return {
        "source": "neo4j" if neo4j_used else "postgres",
        "neo4j_configured": bool(configured),
        "nodes": nodes,
        "edges": edges,
    }

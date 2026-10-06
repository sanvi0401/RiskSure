from __future__ import annotations

import os
from itertools import combinations
from typing import Any, Iterable

from integrations import (
    neo4j_application_graph,
    neo4j_system_graph,
    neo4j_sync_system_projection,
    neo4j_upsert_application,
    neo4j_upsert_claim,
    neo4j_upsert_customer,
    neo4j_upsert_policy,
    neo4j_upsert_provider,
    neo4j_upsert_risk_factors,
    neo4j_upsert_underwriter,
)

_NEO4J_LABELS = ("Customer", "Application", "RiskFactor", "Underwriter", "Decision", "Policy", "Claim", "Provider", "Location")


def _add_node(nodes: dict[str, dict[str, Any]], node_id: str, kind: str, properties: dict[str, Any]) -> None:
    nodes[node_id] = {"id": node_id, "type": kind, "properties": properties}


def _add_edge(edges: dict[tuple[str, str, str], dict[str, str]], source: str, target: str, relationship: str) -> None:
    edges[(source, target, relationship)] = {
        "source": source,
        "target": target,
        "relationship": relationship.lower(),
    }


def _risk_factors(application: Any) -> list[dict[str, Any]]:
    factors = []
    for name in ("age", "sex", "bmi", "children", "smoker", "region"):
        value = getattr(application, name, None)
        if value is not None:
            factors.append({
                "key": f"application-{application.id}:{name}:{str(value).strip().lower()}",
                "name": name,
                "value": value,
            })
    return factors


def _application_payload(application: Any) -> dict[str, Any]:
    return {
        "application_id": application.id,
        "name": application.name,
        "review_status": application.review_status,
        "risk_score": application.risk_score,
        "final_risk": application.final_risk,
        "premium": application.premium,
        "decision": application.decision,
        "decision_reason": application.decision_reason,
        "created_at": application.created_at.isoformat() if application.created_at else None,
        "customer_id": application.customer_id,
        "underwriter_id": application.assigned_underwriter_id,
        "reviewed_at": application.reviewed_at.isoformat() if application.reviewed_at else None,
        "region": application.region,
    }


def sync_application(application: Any) -> bool:
    """Best-effort graph projection of committed PostgreSQL application facts."""
    payload = _application_payload(application)
    customer = getattr(application, "customer", None)
    if customer is not None:
        neo4j_upsert_customer({
            "customer_id": customer.id,
            "name": customer.full_name,
            "city": customer.city,
            "state": customer.state,
        })
    underwriter = getattr(application, "assigned_underwriter", None)
    if underwriter is not None:
        neo4j_upsert_underwriter({"id": underwriter.id, "email": underwriter.email})
    synced = neo4j_upsert_application(payload)
    if synced:
        synced = neo4j_upsert_risk_factors(application.id, _risk_factors(application)) and synced
    return synced


def sync_claim(claim: Any) -> bool:
    provider = getattr(claim, "provider", None)
    if provider is not None:
        neo4j_upsert_provider({
            "id": provider.id,
            "name": provider.name,
            "provider_type": provider.provider_type,
            "status": provider.status,
        })
    policy = getattr(claim, "policy", None)
    if policy is not None:
        neo4j_upsert_policy({
            "policy_id": policy.id,
            "customer_id": policy.customer_id,
            "application_id": getattr(policy, "application_id", None),
            "policy_number": policy.policy_number,
            "status": policy.status,
            "policy_type": policy.policy_type,
        })
    application_id = getattr(policy, "application_id", None) if policy is not None else None
    return neo4j_upsert_claim({
        "customer_id": claim.customer_id,
        "claim_id": claim.id,
        "claim_number": claim.claim_number,
        "amount": claim.claimed_amount,
        "status": claim.status,
        "provider_id": claim.provider_id,
        "policy_id": claim.policy_id,
        "application_id": application_id,
    })


def application_graph(
    application: Any,
    claims: Iterable[Any],
    policy: Any | None = None,
    related_applications: Iterable[Any] = (),
) -> dict[str, Any]:
    """Build an application-bounded graph from persisted facts and read its Neo4j projection."""
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[tuple[str, str, str], dict[str, str]] = {}
    application_id = application.id
    application_node = f"application-{application_id}"
    customer_id = application.customer_id
    _add_node(nodes, application_node, "application", {
        "id": application_id,
        "name": application.name,
        "review_status": application.review_status,
        "risk_score": application.risk_score,
        "final_risk": application.final_risk,
        "premium": application.premium,
        "decision": application.decision,
        "created_at": application.created_at.isoformat() if application.created_at else None,
    })
    if customer_id is not None:
        customer_node = f"customer-{customer_id}"
        _add_node(nodes, customer_node, "customer", {"id": customer_id})
        _add_edge(edges, customer_node, application_node, "submitted")

    for factor in _risk_factors(application):
        factor_id = f"riskfactor-{factor['key']}"
        _add_node(nodes, factor_id, "riskfactor", {
            "name": factor["name"],
            "value": factor["value"],
            "source": "application",
        })
        _add_edge(edges, application_node, factor_id, "has_risk_factor")

    if application.region:
        location_id = f"location-{str(application.region).lower()}"
        _add_node(nodes, location_id, "location", {"region": application.region})
        _add_edge(edges, application_node, location_id, "associated_with")

    if application.assigned_underwriter_id is not None and application.reviewed_at is not None:
        underwriter_id = f"underwriter-{application.assigned_underwriter_id}"
        _add_node(nodes, underwriter_id, "underwriter", {"id": application.assigned_underwriter_id})
        _add_edge(edges, application_node, underwriter_id, "reviewed_by")

    if application.decision and application.decision != "Unknown":
        decision_id = f"decision-{application_id}"
        _add_node(nodes, decision_id, "decision", {
            "application_id": application_id,
            "decision": application.decision,
            "reason": application.decision_reason,
            "reviewed_at": application.reviewed_at.isoformat() if application.reviewed_at else None,
        })
        _add_edge(edges, application_node, decision_id, "resulted_in")

    if policy is not None:
        neo4j_upsert_policy({
            "policy_id": policy.id,
            "customer_id": policy.customer_id,
            "application_id": getattr(policy, "application_id", None) or application_id,
            "policy_number": policy.policy_number,
            "status": policy.status,
            "policy_type": policy.policy_type,
        })
        policy_id = f"policy-{policy.id}"
        _add_node(nodes, policy_id, "policy", {
            "id": policy.id,
            "policy_number": policy.policy_number,
            "status": policy.status,
            "policy_type": policy.policy_type,
        })
        _add_edge(edges, application_node, policy_id, "has_policy")
        if customer_id is not None:
            _add_edge(edges, f"customer-{customer_id}", policy_id, "has_policy")

    for related in related_applications:
        if related.id == application_id:
            continue
        related_id = f"application-{related.id}"
        _add_node(nodes, related_id, "application", {
            "id": related.id,
            "review_status": related.review_status,
            "final_risk": related.final_risk,
            "decision": related.decision,
            "created_at": related.created_at.isoformat() if related.created_at else None,
        })
        if customer_id is not None:
            _add_edge(edges, f"customer-{customer_id}", related_id, "submitted")
        if tuple(getattr(application, key, None) for key in ("age", "sex", "bmi", "children", "smoker", "region")) == tuple(
            getattr(related, key, None) for key in ("age", "sex", "bmi", "children", "smoker", "region")
        ):
            _add_edge(edges, application_node, related_id, "similar_to")

    for claim in claims:
        claim_id = f"claim-{claim.id}"
        _add_node(nodes, claim_id, "claim", {
            "id": claim.id,
            "claim_number": claim.claim_number,
            "status": claim.status,
            "amount": claim.claimed_amount,
        })
        if customer_id is not None and claim.customer_id == customer_id:
            _add_edge(edges, f"customer-{customer_id}", claim_id, "has_claim")
            _add_edge(edges, application_node, claim_id, "has_claim")
        if claim.provider_id is not None:
            provider_id = f"provider-{claim.provider_id}"
            provider = getattr(claim, "provider", None)
            _add_node(nodes, provider_id, "provider", {
                "id": claim.provider_id,
                "name": provider.name if provider is not None else None,
                "provider_type": provider.provider_type if provider is not None else None,
            })
            _add_edge(edges, claim_id, provider_id, "associated_with")
        if claim.policy_id is not None:
            claim_policy_id = f"policy-{claim.policy_id}"
            claim_policy = getattr(claim, "policy", None)
            _add_node(nodes, claim_policy_id, "policy", {
                "id": claim.policy_id,
                "policy_number": claim_policy.policy_number if claim_policy is not None else None,
                "status": claim_policy.status if claim_policy is not None else None,
            })
            _add_edge(edges, claim_policy_id, claim_id, "has_claim")
        sync_claim(claim)

    synced = sync_application(application)
    neo4j_graph = neo4j_application_graph(application_id, allowed_node_ids=set(nodes)) if synced else {"nodes": [], "edges": []}
    configured = all(os.getenv(name) for name in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"))
    if neo4j_graph["nodes"]:
        return {
            "source": "neo4j",
            "neo4j_configured": bool(configured),
            "nodes": neo4j_graph["nodes"],
            "edges": neo4j_graph["edges"],
        }
    return {
        "source": "postgres",
        "neo4j_configured": bool(configured),
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
    }


def system_graph(
    applications: Iterable[Any],
    claims: Iterable[Any],
    policies: Iterable[Any],
    profiles: Iterable[Any],
    providers: Iterable[Any],
    underwriters: Iterable[Any],
) -> dict[str, Any]:
    """Construct the bounded admin graph from PostgreSQL, preferring the Neo4j projection."""
    applications = list(applications)
    claims = list(claims)
    policies = list(policies)
    profiles = list(profiles)
    providers = list(providers)
    underwriters = list(underwriters)
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[tuple[str, str, str], dict[str, str]] = {}
    policy_application: dict[int, int] = {
        policy.id: policy.application_id
        for policy in policies
        if getattr(policy, "application_id", None) is not None
    }
    for profile in profiles:
        _add_node(nodes, f"customer-{profile.id}", "customer", {
            "id": profile.id,
            "name": profile.full_name,
            "city": profile.city,
            "state": profile.state,
        })
    for underwriter in underwriters:
        _add_node(nodes, f"underwriter-{underwriter.id}", "underwriter", {"id": underwriter.id, "email": underwriter.email})
    for application in applications:
        app_id = f"application-{application.id}"
        _add_node(nodes, app_id, "application", {
            "id": application.id,
            "name": application.name,
            "review_status": application.review_status,
            "risk_score": application.risk_score,
            "final_risk": application.final_risk,
            "decision": application.decision,
            "created_at": application.created_at.isoformat() if application.created_at else None,
        })
        if application.customer_id is not None:
            customer_id = f"customer-{application.customer_id}"
            _add_node(nodes, customer_id, "customer", {"id": application.customer_id})
            _add_edge(edges, customer_id, app_id, "submitted")
        if application.assigned_underwriter_id is not None and application.reviewed_at is not None:
            underwriter_id = f"underwriter-{application.assigned_underwriter_id}"
            _add_node(nodes, underwriter_id, "underwriter", {"id": application.assigned_underwriter_id})
            _add_edge(edges, app_id, underwriter_id, "reviewed_by")
        if application.decision and application.decision != "Unknown":
            decision_id = f"decision-{application.id}"
            _add_node(nodes, decision_id, "decision", {
                "application_id": application.id,
                "decision": application.decision,
                "reason": application.decision_reason,
            })
            _add_edge(edges, app_id, decision_id, "resulted_in")
        if application.region:
            location_id = f"location-{str(application.region).lower()}"
            _add_node(nodes, location_id, "location", {"region": application.region})
            _add_edge(edges, app_id, location_id, "associated_with")
        for factor in _risk_factors(application):
            factor_id = f"riskfactor-{factor['key']}"
            _add_node(nodes, factor_id, "riskfactor", {"name": factor["name"], "value": factor["value"], "source": "application"})
            _add_edge(edges, app_id, factor_id, "has_risk_factor")
    for policy in policies:
        policy_id = f"policy-{policy.id}"
        _add_node(nodes, policy_id, "policy", {
            "id": policy.id,
            "policy_number": policy.policy_number,
            "status": policy.status,
            "policy_type": policy.policy_type,
            "application_id": getattr(policy, "application_id", None),
        })
        customer_id = f"customer-{policy.customer_id}"
        _add_node(nodes, customer_id, "customer", {"id": policy.customer_id})
        _add_edge(edges, customer_id, policy_id, "has_policy")
        if getattr(policy, "application_id", None) is not None:
            _add_edge(edges, f"application-{policy.application_id}", policy_id, "has_policy")
    for claim in claims:
        claim_id = f"claim-{claim.id}"
        _add_node(nodes, claim_id, "claim", {
            "id": claim.id,
            "claim_number": claim.claim_number,
            "status": claim.status,
            "amount": claim.claimed_amount,
        })
        customer_id = f"customer-{claim.customer_id}"
        _add_node(nodes, customer_id, "customer", {"id": claim.customer_id})
        _add_edge(edges, customer_id, claim_id, "has_claim")
        policy_id = f"policy-{claim.policy_id}"
        _add_node(nodes, policy_id, "policy", {"id": claim.policy_id})
        _add_edge(edges, policy_id, claim_id, "has_claim")
        if (application_id := policy_application.get(claim.policy_id)) is not None:
            _add_edge(edges, f"application-{application_id}", claim_id, "has_claim")
        if claim.provider_id is not None:
            provider_id = f"provider-{claim.provider_id}"
            provider = getattr(claim, "provider", None)
            _add_node(nodes, provider_id, "provider", {
                "id": claim.provider_id,
                "name": provider.name if provider is not None else None,
                "provider_type": provider.provider_type if provider is not None else None,
            })
            _add_edge(edges, claim_id, provider_id, "associated_with")

    application_groups: dict[tuple[Any, ...], list[int]] = {}
    for application in applications:
        signature = tuple(getattr(application, key, None) for key in ("age", "sex", "bmi", "children", "smoker", "region"))
        if any(value is not None for value in signature):
            application_groups.setdefault(signature, []).append(application.id)
    similar_applications = []
    for ids in application_groups.values():
        for source_id, target_id in combinations(sorted(ids), 2):
            similar_applications.append({"source_id": source_id, "target_id": target_id})
            _add_edge(edges, f"application-{source_id}", f"application-{target_id}", "similar_to")
            if len(similar_applications) >= 5000:
                break
        if len(similar_applications) >= 5000:
            break

    projection = {
        "customers": [{
            "id": profile.id,
            "name": profile.full_name,
            "city": profile.city,
            "state": profile.state,
        } for profile in profiles],
        "underwriters": [{"id": staff.id, "email": staff.email} for staff in underwriters],
        "providers": [{
            "id": provider.id,
            "name": provider.name,
            "provider_type": provider.provider_type,
            "status": provider.status,
        } for provider in providers],
        "applications": [_application_payload(application) for application in applications],
        "risk_factors": [
            {"application_id": application.id, **factor}
            for application in applications
            for factor in _risk_factors(application)
        ],
        "similar_applications": similar_applications,
        "policies": [{
            "policy_id": policy.id,
            "customer_id": policy.customer_id,
            "application_id": getattr(policy, "application_id", None),
            "policy_number": policy.policy_number,
            "status": policy.status,
            "policy_type": policy.policy_type,
        } for policy in policies],
        "claims": [{
            "customer_id": claim.customer_id,
            "claim_id": claim.id,
            "claim_number": claim.claim_number,
            "amount": claim.claimed_amount,
            "status": claim.status,
            "provider_id": claim.provider_id,
            "policy_id": claim.policy_id,
            "application_id": policy_application.get(claim.policy_id),
        } for claim in claims],
    }
    neo4j_sync_system_projection(projection)

    neo4j_graph = neo4j_system_graph()
    configured = all(os.getenv(name) for name in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"))
    if neo4j_graph["nodes"]:
        nodes.update({node["id"]: node for node in neo4j_graph["nodes"]})
        edges.update({
            (edge["source"], edge["target"], edge["relationship"]): edge
            for edge in neo4j_graph["edges"]
        })
        return {
            "source": "neo4j+postgres",
            "neo4j_configured": configured,
            "nodes": list(nodes.values()),
            "edges": list(edges.values()),
        }
    return {"source": "postgres", "neo4j_configured": configured, "nodes": list(nodes.values()), "edges": list(edges.values())}


def filter_graph(
    graph: dict[str, Any],
    search: str = "",
    node_type: str = "",
    expand_node_id: str = "",
) -> dict[str, Any]:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    if expand_node_id:
        neighbor_ids = {expand_node_id}
        for edge in edges:
            if edge["source"] == expand_node_id:
                neighbor_ids.add(edge["target"])
            elif edge["target"] == expand_node_id:
                neighbor_ids.add(edge["source"])
        nodes = [node for node in nodes if node["id"] in neighbor_ids]
        edges = [edge for edge in edges if edge["source"] in neighbor_ids and edge["target"] in neighbor_ids]
    elif search.strip() or node_type:
        needle = search.strip().lower()
        matching = {
            node["id"]
            for node in nodes
            if (not node_type or node.get("type", "").lower() == node_type.lower())
            and (not needle or needle in f"{node.get('id')} {node.get('type')} {node.get('properties', {})}".lower())
        }
        visible_ids = set(matching)
        for edge in edges:
            if edge["source"] in matching or edge["target"] in matching:
                visible_ids.update((edge["source"], edge["target"]))
        nodes = [node for node in nodes if node["id"] in visible_ids]
        edges = [edge for edge in edges if edge["source"] in visible_ids and edge["target"] in visible_ids]
    return {**graph, "nodes": nodes, "edges": edges}

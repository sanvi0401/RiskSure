"""Optional production integrations for RiskSure.

These integrations are configuration-driven and never prevent the Flask app
from starting when an optional service or package is unavailable.
"""
import os
import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)


def _configured(*names: str) -> bool:
    return all(bool(os.getenv(name, "").strip()) for name in names)


def _neo4j_session(driver):
    # Aura and multi-database servers may name the database explicitly.
    database = os.getenv("NEO4J_DATABASE", "").strip()
    return driver.session(database=database) if database else driver.session()


def neo4j_driver():
    if not _configured("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"):
        return None
    try:
        from neo4j import GraphDatabase
        return GraphDatabase.driver(
            os.environ["NEO4J_URI"],
            auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
        )
    except Exception:
        return None


def neo4j_upsert_claim(claim: dict[str, Any]) -> bool:
    driver = neo4j_driver()
    if driver is None:
        return False
    query = """
    MERGE (c:Customer {id: $customer_id})
    MERGE (cl:Claim {id: $claim_id})
    SET cl.claim_number=$claim_number, cl.amount=$amount, cl.status=$status
    MERGE (c)-[:HAS_CLAIM]->(cl)
    FOREACH (_ IN CASE WHEN $policy_id IS NULL THEN [] ELSE [1] END |
      MERGE (p:Policy {id: $policy_id})
      MERGE (p)-[:COVERS]->(cl)
    )
    WITH cl
    FOREACH (_ IN CASE WHEN $provider_id IS NULL THEN [] ELSE [1] END |
      MERGE (p:Provider {id: $provider_id})
      MERGE (p)-[:HANDLES]->(cl)
    )
    """
    try:
        with _neo4j_session(driver) as session:
            parameters = {"policy_id": None, **claim}
            session.run(query, **parameters).consume()
        return True
    except Exception:
        logger.warning("Neo4j claim synchronization failed")
        return False
    finally:
        driver.close()


def neo4j_claim_graph(claim_id: int, allowed_claim_ids: list[int] | None = None) -> dict[str, list]:
    driver = neo4j_driver()
    if driver is None:
        return {"nodes": [], "edges": []}
    query = """
    MATCH (c:Claim {id: $claim_id})
    OPTIONAL MATCH (customer:Customer)-[:HAS_CLAIM|SUBMITTED]->(c)
    OPTIONAL MATCH (provider:Provider)-[:HANDLES]->(c)
    OPTIONAL MATCH (customer)-[:HAS_CLAIM|SUBMITTED]->(related:Claim)
    WHERE related.id IN $allowed_claim_ids
    RETURN c, customer, provider, related
    """
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_nodes: set[str] = set()
    seen_edges: set[tuple[str, str, str]] = set()
    permitted_claim_ids = set(allowed_claim_ids or [])
    permitted_claim_ids.add(claim_id)
    try:
        with _neo4j_session(driver) as session:
            for row in session.run(query, claim_id=claim_id, allowed_claim_ids=list(permitted_claim_ids)):
                for node, kind in (
                    (row["c"], "claim"),
                    (row["customer"], "customer"),
                    (row["provider"], "provider"),
                    (row["related"], "claim"),
                ):
                    if node is None:
                        continue
                    node_id = f"{kind}-{node.get('id')}"
                    if node_id not in seen_nodes:
                        seen_nodes.add(node_id)
                        nodes.append({"id": node_id, "type": kind, "properties": dict(node)})
                customer = row["customer"]
                provider = row["provider"]
                related = row["related"]
                if customer is not None:
                    edge = (f"customer-{customer.get('id')}", f"claim-{claim_id}", "submitted")
                    if edge not in seen_edges:
                        seen_edges.add(edge)
                        edges.append({"source": edge[0], "target": edge[1], "relationship": edge[2]})
                if provider is not None:
                    edge = (f"provider-{provider.get('id')}", f"claim-{claim_id}", "handles")
                    if edge not in seen_edges:
                        seen_edges.add(edge)
                        edges.append({"source": edge[0], "target": edge[1], "relationship": edge[2]})
                if related is not None and customer is not None:
                    edge = (f"customer-{customer.get('id')}", f"claim-{related.get('id')}", "submitted")
                    if edge not in seen_edges:
                        seen_edges.add(edge)
                        edges.append({"source": edge[0], "target": edge[1], "relationship": edge[2]})
        return {"nodes": nodes, "edges": edges}
    except Exception:
        logger.warning("Neo4j claim graph read failed")
        return {"nodes": [], "edges": []}
    finally:
        driver.close()


def neo4j_upsert_application(application: dict[str, Any]) -> bool:
    """Synchronize persisted application facts without replacing PostgreSQL as source of truth."""
    driver = neo4j_driver()
    if driver is None:
        return False
    query = """
    MERGE (a:Application {id: $application_id})
    SET a.name=$name, a.review_status=$review_status, a.risk_score=$risk_score,
        a.final_risk=$final_risk, a.premium=$premium, a.decision=$decision,
        a.decision_reason=$decision_reason, a.created_at=$created_at,
        a.customer_id=$customer_id, a.assigned_underwriter_id=$underwriter_id
    FOREACH (_ IN CASE WHEN $customer_id IS NULL THEN [] ELSE [1] END |
      MERGE (c:Customer {id: $customer_id})
      MERGE (c)-[:SUBMITTED]->(a)
    )
    FOREACH (_ IN CASE WHEN $underwriter_id IS NULL THEN [] ELSE [1] END |
      MERGE (u:Underwriter {id: $underwriter_id})
      FOREACH (__ IN CASE WHEN $reviewed_at IS NULL THEN [] ELSE [1] END |
        MERGE (u)-[:REVIEWED]->(a)
      )
    )
    FOREACH (_ IN CASE WHEN $decision IS NULL OR $decision = 'Unknown' THEN [] ELSE [1] END |
      MERGE (d:Decision {application_id: $application_id})
      SET d.value=$decision, d.reason=$decision_reason, d.reviewed_at=$reviewed_at
      MERGE (a)-[:RESULTED_IN]->(d)
    )
    FOREACH (_ IN CASE WHEN $region IS NULL THEN [] ELSE [1] END |
      MERGE (l:Location {region: $region})
      MERGE (a)-[:ASSOCIATED_WITH]->(l)
    )
    """
    try:
        with _neo4j_session(driver) as session:
            session.run(query, **application).consume()
        return True
    except Exception:
        logger.warning("Neo4j application synchronization failed")
        return False
    finally:
        driver.close()


def neo4j_upsert_risk_factors(application_id: int, factors: list[dict[str, Any]]) -> bool:
    driver = neo4j_driver()
    if driver is None:
        return False
    query = """
    MATCH (a:Application {id: $application_id})
    UNWIND $factors AS factor
    MERGE (rf:RiskFactor {key: factor.key})
    SET rf.name=factor.name, rf.value=factor.value
    MERGE (a)-[:HAS_RISK_FACTOR]->(rf)
    """
    try:
        with _neo4j_session(driver) as session:
            session.run(query, application_id=application_id, factors=factors).consume()
        return True
    except Exception:
        logger.warning("Neo4j risk-factor synchronization failed")
        return False
    finally:
        driver.close()


def neo4j_link_application_policy(application_id: int, policy: dict[str, Any]) -> bool:
    driver = neo4j_driver()
    if driver is None:
        return False
    query = """
    MATCH (a:Application {id: $application_id})
    MERGE (p:Policy {id: $policy_id})
    SET p.policy_number=$policy_number, p.status=$status, p.policy_type=$policy_type
    MERGE (a)-[:HAS_POLICY]->(p)
    """
    try:
        with _neo4j_session(driver) as session:
            session.run(query, application_id=application_id, **policy).consume()
        return True
    except Exception:
        logger.warning("Neo4j policy synchronization failed")
        return False
    finally:
        driver.close()


def neo4j_upsert_policy(policy: dict[str, Any]) -> bool:
    driver = neo4j_driver()
    if driver is None:
        return False
    query = """
    MERGE (c:Customer {id: $customer_id})
    MERGE (p:Policy {id: $policy_id})
    SET p.policy_number=$policy_number, p.status=$status, p.policy_type=$policy_type
    MERGE (c)-[:HAS_POLICY]->(p)
    """
    try:
        with _neo4j_session(driver) as session:
            session.run(query, **policy).consume()
        return True
    except Exception:
        logger.warning("Neo4j policy synchronization failed")
        return False
    finally:
        driver.close()


def neo4j_upsert_customer(customer: dict[str, Any]) -> bool:
    driver = neo4j_driver()
    if driver is None:
        return False
    query = """
    MERGE (c:Customer {id: $customer_id})
    SET c.name=$name, c.city=$city, c.state=$state
    """
    try:
        with _neo4j_session(driver) as session:
            session.run(query, **customer).consume()
        return True
    except Exception:
        logger.warning("Neo4j customer synchronization failed")
        return False
    finally:
        driver.close()


def neo4j_upsert_underwriter(underwriter: dict[str, Any]) -> bool:
    driver = neo4j_driver()
    if driver is None:
        return False
    try:
        with _neo4j_session(driver) as session:
            session.run(
                "MERGE (u:Underwriter {id: $id}) SET u.email=$email",
                **underwriter,
            ).consume()
        return True
    except Exception:
        logger.warning("Neo4j underwriter synchronization failed")
        return False
    finally:
        driver.close()


def neo4j_upsert_provider(provider: dict[str, Any]) -> bool:
    driver = neo4j_driver()
    if driver is None:
        return False
    try:
        with _neo4j_session(driver) as session:
            session.run(
                "MERGE (p:Provider {id: $id}) SET p.name=$name, p.provider_type=$provider_type, p.status=$status",
                **provider,
            ).consume()
        return True
    except Exception:
        logger.warning("Neo4j provider synchronization failed")
        return False
    finally:
        driver.close()


def neo4j_sync_system_projection(projection: dict[str, list[dict[str, Any]]]) -> bool:
    """Batch-upsert PostgreSQL facts using fixed Cypher and stable entity keys."""
    driver = neo4j_driver()
    if driver is None:
        return False
    statements = (
        (
            "UNWIND $items AS item MERGE (c:Customer {id:item.id}) SET c.name=item.name, c.city=item.city, c.state=item.state",
            "customers",
        ),
        (
            "UNWIND $items AS item MERGE (u:Underwriter {id:item.id}) SET u.email=item.email",
            "underwriters",
        ),
        (
            "UNWIND $items AS item MERGE (p:Provider {id:item.id}) SET p.name=item.name, p.provider_type=item.provider_type, p.status=item.status",
            "providers",
        ),
        (
            """
            UNWIND $items AS item
            MERGE (a:Application {id:item.application_id})
            SET a.name=item.name, a.review_status=item.review_status, a.risk_score=item.risk_score,
                a.final_risk=item.final_risk, a.premium=item.premium, a.decision=item.decision,
                a.decision_reason=item.decision_reason, a.created_at=item.created_at,
                a.customer_id=item.customer_id, a.assigned_underwriter_id=item.underwriter_id
            FOREACH (_ IN CASE WHEN item.customer_id IS NULL THEN [] ELSE [1] END |
              MERGE (c:Customer {id:item.customer_id})
              MERGE (c)-[:SUBMITTED]->(a)
            )
            FOREACH (_ IN CASE WHEN item.underwriter_id IS NULL OR item.reviewed_at IS NULL THEN [] ELSE [1] END |
              MERGE (u:Underwriter {id:item.underwriter_id})
              MERGE (u)-[:REVIEWED]->(a)
            )
            FOREACH (_ IN CASE WHEN item.decision IS NULL OR item.decision = 'Unknown' THEN [] ELSE [1] END |
              MERGE (d:Decision {application_id:item.application_id})
              SET d.value=item.decision, d.reason=item.decision_reason, d.reviewed_at=item.reviewed_at
              MERGE (a)-[:RESULTED_IN]->(d)
            )
            FOREACH (_ IN CASE WHEN item.region IS NULL THEN [] ELSE [1] END |
              MERGE (l:Location {region:item.region})
              MERGE (a)-[:ASSOCIATED_WITH]->(l)
            )
            """,
            "applications",
        ),
        (
            """
            UNWIND $items AS item
            MATCH (a:Application {id:item.application_id})
            MERGE (rf:RiskFactor {key:item.key})
            SET rf.name=item.name, rf.value=item.value
            MERGE (a)-[:HAS_RISK_FACTOR]->(rf)
            """,
            "risk_factors",
        ),
        (
            """
            UNWIND $items AS item
            MATCH (a:Application {id:item.source_id})
            MATCH (b:Application {id:item.target_id})
            MERGE (a)-[:SIMILAR_TO]->(b)
            """,
            "similar_applications",
        ),
        (
            """
            UNWIND $items AS item
            MERGE (c:Customer {id:item.customer_id})
            MERGE (p:Policy {id:item.policy_id})
            SET p.policy_number=item.policy_number, p.status=item.status, p.policy_type=item.policy_type
            MERGE (c)-[:HAS_POLICY]->(p)
            """,
            "policies",
        ),
        (
            """
            UNWIND $items AS item
            MERGE (c:Customer {id:item.customer_id})
            MERGE (cl:Claim {id:item.claim_id})
            SET cl.claim_number=item.claim_number, cl.amount=item.amount, cl.status=item.status
            MERGE (c)-[:HAS_CLAIM]->(cl)
            FOREACH (_ IN CASE WHEN item.policy_id IS NULL THEN [] ELSE [1] END |
              MERGE (p:Policy {id:item.policy_id})
              MERGE (p)-[:COVERS]->(cl)
            )
            FOREACH (_ IN CASE WHEN item.provider_id IS NULL THEN [] ELSE [1] END |
              MERGE (p:Provider {id:item.provider_id})
              MERGE (p)-[:HANDLES]->(cl)
            )
            """,
            "claims",
        ),
    )
    try:
        with _neo4j_session(driver) as session:
            for query, key in statements:
                items = projection.get(key, [])
                if items:
                    session.run(query, items=items).consume()
        return True
    except Exception:
        logger.warning("Neo4j system projection synchronization failed")
        return False
    finally:
        driver.close()


def _graph_node(node: Any) -> dict[str, Any]:
    labels = list(node.labels)
    kind = labels[0].lower() if labels else "entity"
    properties = dict(node)
    identifier = properties.get("id")
    if identifier is None and kind == "location":
        identifier = properties.get("region")
    if identifier is None and kind == "riskfactor":
        identifier = properties.get("key")
    if identifier is None and kind == "decision":
        identifier = properties.get("application_id")
    node_id = f"{kind}-{identifier}"
    return {"id": node_id, "type": kind, "properties": properties}


def _graph_relationship(relationship: Any, start: Any, end: Any) -> dict[str, str]:
    source = _graph_node(start)["id"]
    target = _graph_node(end)["id"]
    return {"source": source, "target": target, "relationship": str(relationship.type).lower()}


def neo4j_application_graph(application_id: int) -> dict[str, list]:
    """Read only the application-centered component; no user-supplied Cypher or labels."""
    driver = neo4j_driver()
    if driver is None:
        return {"nodes": [], "edges": []}
    query = """
    MATCH (a:Application {id: $application_id})
    OPTIONAL MATCH (a)-[r1]-(n1)
    WHERE n1 IS NULL OR any(label IN labels(n1) WHERE label IN
      ['Customer','RiskFactor','Policy','Decision','Location','Underwriter','Claim','Provider','Application'])
    OPTIONAL MATCH (n1)-[r2]-(n2)
    WHERE n2 IS NULL OR any(label IN labels(n2) WHERE label IN
      ['Customer','RiskFactor','Policy','Decision','Location','Underwriter','Claim','Provider','Application'])
    RETURN a, r1, n1, r2, n2
    LIMIT 500
    """
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[tuple[str, str, str], dict[str, str]] = {}
    try:
        with _neo4j_session(driver) as session:
            for row in session.run(query, application_id=application_id):
                for node in (row["a"], row["n1"], row["n2"]):
                    if node is not None:
                        item = _graph_node(node)
                        nodes[item["id"]] = item
                for relationship, start, end in (
                    (row["r1"], row["a"], row["n1"]),
                    (row["r2"], row["n1"], row["n2"]),
                ):
                    if relationship is not None and start is not None and end is not None:
                        item = _graph_relationship(relationship, start, end)
                        edges[(item["source"], item["target"], item["relationship"])] = item
        return {"nodes": list(nodes.values()), "edges": list(edges.values())}
    except Exception:
        logger.warning("Neo4j application graph read failed")
        return {"nodes": [], "edges": []}
    finally:
        driver.close()


def neo4j_system_graph() -> dict[str, list]:
    """Read a bounded set of known RiskSure labels for administrator investigation."""
    driver = neo4j_driver()
    if driver is None:
        return {"nodes": [], "edges": []}
    query = """
    MATCH (n)
    WHERE any(label IN labels(n) WHERE label IN
      ['Customer','Application','RiskFactor','Underwriter','Decision','Policy','Claim','Provider','Location'])
    WITH n LIMIT 10000
    OPTIONAL MATCH (n)-[r]-(m)
    WHERE any(label IN labels(m) WHERE label IN
      ['Customer','Application','RiskFactor','Underwriter','Decision','Policy','Claim','Provider','Location'])
    RETURN n, r, m
    LIMIT 30000
    """
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[tuple[str, str, str], dict[str, str]] = {}
    try:
        with _neo4j_session(driver) as session:
            for row in session.run(query):
                for node in (row["n"], row["m"]):
                    if node is not None:
                        item = _graph_node(node)
                        nodes[item["id"]] = item
                relationship, start, end = row["r"], row["n"], row["m"]
                if relationship is not None and start is not None and end is not None:
                    item = _graph_relationship(relationship, start, end)
                    edges[(item["source"], item["target"], item["relationship"])] = item
        return {"nodes": list(nodes.values()), "edges": list(edges.values())}
    except Exception:
        logger.warning("Neo4j system graph read failed")
        return {"nodes": [], "edges": []}
    finally:
        driver.close()


def hf_request(prompt: str, *, max_tokens: int = 500) -> str | None:
    token = os.getenv("HUGGINGFACE_API_TOKEN", "").strip()
    model = os.getenv("HUGGINGFACE_MODEL", "").strip()
    if not token or not model:
        return None
    try:
        response = requests.post(
            f"https://api-inference.huggingface.co/models/{model}",
            headers={"Authorization": f"Bearer {token}"},
            json={"inputs": prompt, "parameters": {"max_new_tokens": max_tokens, "return_full_text": False}},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            return payload[0].get("generated_text") or payload[0].get("text")
    except (requests.RequestException, ValueError):
        pass
    return None


def hf_embeddings(texts: list[str]) -> list[list[float]] | None:
    token = os.getenv("HUGGINGFACE_API_TOKEN", "").strip()
    model = os.getenv("HUGGINGFACE_EMBEDDING_MODEL", "").strip()
    if not token or not model:
        return None
    try:
        response = requests.post(
            f"https://api-inference.huggingface.co/models/{model}",
            headers={"Authorization": f"Bearer {token}"},
            json={"inputs": texts, "options": {"wait_for_model": True}},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list) and payload and isinstance(payload[0], list):
            return payload
    except (requests.RequestException, ValueError):
        pass
    return None


def chroma_collection():
    host = os.getenv("CHROMA_HOST", "").strip()
    if not host:
        return None
    try:
        import chromadb
        port = int(os.getenv("CHROMA_PORT", "8000"))
        kwargs: dict[str, Any] = {"host": host, "port": port}
        api_key = os.getenv("CHROMA_API_KEY", "").strip()
        if api_key:
            kwargs["headers"] = {"Authorization": f"Bearer {api_key}"}
        return chromadb.HttpClient(**kwargs).get_or_create_collection(
            name=os.getenv("CHROMA_COLLECTION", "risksure_policies")
        )
    except (ImportError, ValueError, TypeError):
        return None
    except Exception:
        return None


def index_policy_chunks(policy_id: int, chunks: list[str]) -> int:
    collection = chroma_collection()
    if collection is None or not chunks:
        return 0
    embeddings = hf_embeddings(chunks)
    kwargs: dict[str, Any] = {
        "ids": [f"policy-{policy_id}-{i}" for i in range(len(chunks))],
        "documents": chunks,
        "metadatas": [{"policy_id": policy_id, "section": i + 1} for i in range(len(chunks))],
    }
    if embeddings:
        kwargs["embeddings"] = embeddings
    try:
        collection.upsert(**kwargs)
        return len(chunks)
    except Exception:
        return 0


def retrieve_policy_chunks(policy_id: int, question: str, n_results: int = 4) -> list[dict]:
    collection = chroma_collection()
    if collection is None or not question.strip():
        return []
    embeddings = hf_embeddings([question])
    kwargs: dict[str, Any] = {"where": {"policy_id": policy_id}, "n_results": n_results}
    if embeddings:
        kwargs["query_embeddings"] = embeddings
    else:
        kwargs["query_texts"] = [question]
    try:
        result = collection.query(**kwargs)
    except Exception:
        return []
    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    return [{"text": d, "section": (m or {}).get("section")} for d, m in zip(docs, metas)]


def analyze_claim_document(text: str) -> dict:
    import re
    extracted_text = text or ""
    if not extracted_text:
        return {"text": "", "ocr_used": False, "amounts": [], "claim_numbers": []}
    amounts = [
        float(x.replace(",", ""))
        for x in re.findall(r"(?:₹|INR|Rs\.?)[ ]*([0-9][0-9,]*(?:\.\d+)?)", extracted_text, re.I)
    ]
    claim_numbers = re.findall(r"\b(?:CLM|CLAIM)[- ]?[A-Z0-9-]{3,}\b", extracted_text, re.I)
    return {"text": extracted_text[:12000], "ocr_used": False, "amounts": amounts, "claim_numbers": claim_numbers}


def analyze_claim_image(image_path: str) -> dict:
    model_path = os.getenv("YOLO_MODEL_PATH", "").strip()
    if not model_path:
        return {"cv_available": False, "detections": [], "reason": "YOLO_MODEL_PATH is not configured"}
    try:
        from ultralytics import YOLO
        model = YOLO(model_path)
        result = model(image_path, verbose=False)[0]
        detections = [
            {"class": result.names[int(box.cls[0])], "confidence": round(float(box.conf[0]), 4)}
            for box in result.boxes
        ]
        return {"cv_available": True, "detections": detections}
    except Exception as exc:
        return {"cv_available": False, "detections": [], "reason": "Image analysis is unavailable."}

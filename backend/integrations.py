"""Optional production integrations for RiskSure.

All clients are lazy and configuration-driven. Missing credentials never prevent
the Flask application from starting; endpoints report a clear integration error.
"""
import os
from typing import Any

import requests


def _configured(*names: str) -> bool:
    return all(bool(os.getenv(name, "").strip()) for name in names)


def neo4j_driver():
    if not _configured("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"):
        return None
    try:
        from neo4j import GraphDatabase
    except ImportError:
        return None
    return GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
    )


def neo4j_upsert_claim(claim: dict[str, Any]) -> bool:
    driver = neo4j_driver()
    if driver is None:
        return False
    query = """
    MERGE (c:Customer {id: $customer_id})
    MERGE (cl:Claim {id: $claim_id})
    SET cl.claim_number=$claim_number, cl.amount=$amount, cl.status=$status
    MERGE (c)-[:SUBMITTED]->(cl)
    WITH cl
    FOREACH (_ IN CASE WHEN $provider_id IS NULL THEN [] ELSE [1] END |
      MERGE (p:Provider {id: $provider_id})
      MERGE (p)-[:HANDLES]->(cl)
    )
    """
    try:
        with driver.session() as session:
            session.run(query, **claim).consume()
        return True
    except Exception:
        return False
    finally:
        driver.close()


def neo4j_claim_graph(claim_id: int) -> dict[str, list]:
    driver = neo4j_driver()
    if driver is None:
        return {"nodes": [], "edges": []}
    query = """
    MATCH (c:Claim {id: $claim_id})
    OPTIONAL MATCH (customer:Customer)-[r1:SUBMITTED]->(c)
    OPTIONAL MATCH (provider:Provider)-[r2:HANDLES]->(c)
    OPTIONAL MATCH (customer)-[r3:SUBMITTED]->(related:Claim)
    RETURN c, customer, provider, related
    """
    nodes, edges, seen_nodes, seen_edges = [], [], set(), set()
    try:
        with driver.session() as session:
            for row in session.run(query, claim_id=claim_id):
            for node, kind in ((row["c"], "claim"), (row["customer"], "customer"),
                               (row["provider"], "provider"), (row["related"], "claim")):
                if node is None:
                    continue
                node_id = f"{kind}-{node.get('id')}"
                if node_id not in seen_nodes:
                    seen_nodes.add(node_id)
                    nodes.append({"id": node_id, "type": kind, "properties": dict(node)})
            if row["customer"] is not None:
                edge=("customer-"+str(row["customer"].get("id")), "claim-"+str(claim_id), "submitted")
                if edge not in seen_edges:
                    seen_edges.add(edge); edges.append({"source":edge[0],"target":edge[1],"relationship":edge[2]})
            if row["provider"] is not None:
                edge=("provider-"+str(row["provider"].get("id")), "claim-"+str(claim_id), "handles")
                if edge not in seen_edges:
                    seen_edges.add(edge); edges.append({"source":edge[0],"target":edge[1],"relationship":edge[2]})
            if row["related"] is not None and row["customer"] is not None:
                edge=("customer-"+str(row["customer"].get("id")), "claim-"+str(row["related"].get("id")), "submitted")
                if edge not in seen_edges:
                    seen_edges.add(edge); edges.append({"source":edge[0],"target":edge[1],"relationship":edge[2]})
    except Exception:
        return {"nodes": [], "edges": []}
    finally:
        driver.close()
    return {"nodes": nodes, "edges": edges}


def hf_request(prompt: str, *, max_tokens: int = 500) -> str | None:
    token = os.getenv("HUGGINGFACE_API_TOKEN", "").strip()
    model = os.getenv("HUGGINGFACE_MODEL", "").strip()
    if not token or not model:
        return None
    url = f"https://api-inference.huggingface.co/models/{model}"
    try:
        response = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}"},
        json={"inputs": prompt, "parameters": {"max_new_tokens": max_tokens, "return_full_text": False}},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            return payload[0].get("generated_text") or payload[0].get("text")
    except (requests.RequestException, ValueError):
        return None
    return None


def hf_embeddings(texts: list[str]) -> list[list[float]] | None:
    token = os.getenv("HUGGINGFACE_API_TOKEN", "").strip()
    model = os.getenv("HUGGINGFACE_EMBEDDING_MODEL", "").strip()
    if not token or not model:
        return None
    url = f"https://api-inference.huggingface.co/models/{model}"
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}"},
        json={"inputs": texts, "options": {"wait_for_model": True}},
        timeout=60,
    )
    response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list) and payload and isinstance(payload[0], list):
            return payload
    except (requests.RequestException, ValueError):
        return None
    return None


def chroma_collection():
    host = os.getenv("CHROMA_HOST", "").strip()
    if not host:
        return None
    try:
        import chromadb
    except ImportError:
        return None
    port = int(os.getenv("CHROMA_PORT", "8000"))
    kwargs = {"host": host, "port": port}
    api_key = os.getenv("CHROMA_API_KEY", "").strip()
    if api_key:
        kwargs["headers"] = {"Authorization": f"Bearer {api_key}"}
    try:
        client = chromadb.HttpClient(**kwargs)
        return client.get_or_create_collection(name=os.getenv("CHROMA_COLLECTION", "risksure_policies"))
    except Exception:
        return None


def index_policy_chunks(policy_id: int, chunks: list[str]) -> int:
    collection = chroma_collection()
    if collection is None:
        return 0
    embeddings = hf_embeddings(chunks)
    ids = [f"policy-{policy_id}-{i}" for i in range(len(chunks))]
    metadata = [{"policy_id": policy_id, "section": i + 1} for i in range(len(chunks))]
    kwargs = {"ids": ids, "documents": chunks, "metadatas": metadata}
    if embeddings:
        kwargs["embeddings"] = embeddings
    try:
        collection.upsert(**kwargs)
        return len(chunks)
    except Exception:
        return 0


def retrieve_policy_chunks(policy_id: int, question: str, n_results: int = 4) -> list[dict]:
    collection = chroma_collection()
    if collection is None:
        return []
    embeddings = hf_embeddings([question])
    where = {"policy_id": policy_id}
    kwargs = {"where": where, "n_results": n_results}
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
    """OCR/document consistency layer. Uses Tesseract when installed."""
    import re
    extracted_text = text or ""
    ocr_used = False
    if not extracted_text:
        return {"text": "", "ocr_used": False, "amounts": [], "claim_numbers": []}
    amounts = [float(x.replace(",", "")) for x in re.findall(r"(?:₹|INR|Rs\.?)[ ]*([0-9][0-9,]*(?:\.\d+)?)", extracted_text, re.I)]
    claim_numbers = re.findall(r"\b(?:CLM|CLAIM)[- ]?[A-Z0-9-]{3,}\b", extracted_text, re.I)
    return {"text": extracted_text[:12000], "ocr_used": ocr_used, "amounts": amounts, "claim_numbers": claim_numbers}

def analyze_claim_image(image_path: str) -> dict:
    """Optional CV/YOLO hook. No model is bundled; configure YOLO_MODEL_PATH when available."""
    model_path = os.getenv("YOLO_MODEL_PATH", "").strip()
    if not model_path:
        return {"cv_available": False, "detections": [], "reason": "YOLO_MODEL_PATH is not configured"}
    try:
        from ultralytics import YOLO
        model = YOLO(model_path)
        result = model(image_path, verbose=False)[0]
        names = result.names
        detections = [{"class": names[int(box.cls[0])], "confidence": round(float(box.conf[0]), 4)}
                      for box in result.boxes]
        return {"cv_available": True, "detections": detections}
    except Exception as exc:
        return {"cv_available": False, "detections": [], "reason": str(exc)}

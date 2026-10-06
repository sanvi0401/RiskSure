"""Probe configured services without printing credentials or private records."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

from dotenv import load_dotenv
import requests
import sqlalchemy as sa

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def postgres():
    url = (os.getenv("DATABASE_URL") or os.getenv("NEON_DATABASE_URL") or "").strip()
    for prefix in ("postgres://", "postgresql://", "postgresql+psycopg2://"):
        if url.startswith(prefix):
            url = "postgresql+psycopg://" + url[len(prefix):]
            break
    engine = sa.create_engine(url, connect_args={"connect_timeout": 10})
    try:
        with engine.connect() as connection:
            connection.execute(sa.text("SELECT 1"))
        return {"status": "pass", "tables": sa.inspect(engine).get_table_names()}
    finally:
        engine.dispose()


def neo4j():
    from integrations import neo4j_driver, _neo4j_session
    driver = neo4j_driver()
    if driver is None:
        return {"status": "missing_configuration"}
    try:
        driver.verify_connectivity()
        with _neo4j_session(driver) as session:
            count = session.run("MATCH (n) RETURN count(n) AS count").single()["count"]
            relationships = [row["type"] for row in session.run(
                "MATCH ()-[r]->() RETURN DISTINCT type(r) AS type")]
        return {"status": "pass", "node_count": count, "relationship_types": relationships}
    finally:
        driver.close()


def huggingface():
    token = os.getenv("HUGGINGFACE_API_TOKEN", "").strip()
    if not token:
        return {"status": "missing_configuration"}
    response = requests.get("https://huggingface.co/api/whoami-v2",
                            headers={"Authorization": "Bearer " + token}, timeout=20)
    if response.status_code != 200:
        return {"status": "fail", "http_status": response.status_code}
    model = os.getenv("HUGGINGFACE_MODEL", "").strip()
    if not model:
        return {"status": "token_verified_model_missing"}
    response = requests.post("https://router.huggingface.co/v1/chat/completions",
                             headers={"Authorization": "Bearer " + token},
                             json={"model": model, "messages": [{"role": "user", "content":
                                   'Return only this JSON: {"connection_verified":true}'}],
                                   "max_tokens": 40, "stream": False}, timeout=60)
    if response.status_code != 200:
        return {"status": "inference_failed", "http_status": response.status_code,
                "detail": redact(response.text[:1000])}
    return {"status": "pass" if response.json().get("choices") else "invalid_response"}


def chroma():
    if not os.getenv("CHROMA_HOST", "").strip():
        return {"status": "not_configured", "retrieval": "stored_policy_document"}
    from integrations import chroma_collection
    collection = chroma_collection()
    return {"status": "pass" if collection is not None else "fail"}


def probe(name, callback):
    try:
        result = callback()
    except Exception as error:
        result = {"status": "fail", "error_type": type(error).__name__, "detail": redact(str(error))}
    print(json.dumps({name: result}), flush=True)
    return name, result


def redact(message):
    for name, value in os.environ.items():
        if any(word in name for word in ("PASSWORD", "TOKEN", "KEY", "DATABASE_URL", "NEO4J_URI", "AURA_INSTANCE")):
            if len(value) > 3:
                message = message.replace(value, "[redacted]")
            if "://" in value:
                hostname = urlsplit(value).hostname
                if hostname:
                    message = message.replace(hostname, "[host]")
    return message[:1000]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--model")
    parser.add_argument("--certifi-ca", action="store_true")
    args = parser.parse_args()
    load_dotenv(args.env_file, override=False)
    if args.certifi_ca:
        import certifi
        os.environ["SSL_CERT_FILE"] = certifi.where()
    if args.model:
        os.environ["HUGGINGFACE_MODEL"] = args.model
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = dict(pool.map(lambda item: probe(*item), (
            ("postgresql", postgres), ("neo4j", neo4j),
            ("huggingface", huggingface), ("chroma", chroma))))
    print(json.dumps(results, indent=2))

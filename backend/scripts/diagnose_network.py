"""Check Aura DNS and the Hugging Face router without revealing configuration."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
import socket
from urllib.parse import urlsplit

from dotenv import load_dotenv
import requests


def dns_probe(resolver, hostname):
    try:
        response = requests.get(resolver, params={"name": hostname, "type": "A"},
                                headers={"Accept": "application/dns-json"}, timeout=15)
        body = response.json()
        return {"resolver": urlsplit(resolver).hostname, "http_status": response.status_code,
                "dns_status": body.get("Status"), "answer_count": len(body.get("Answer", []))}
    except Exception as error:
        return {"resolver": urlsplit(resolver).hostname, "error_type": type(error).__name__}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True)
    args = parser.parse_args()
    load_dotenv(args.env_file)
    uri = urlsplit(os.getenv("NEO4J_URI", ""))
    hostname = uri.hostname or ""
    instance_id = os.getenv("AURA_INSTANCEID", "").strip()
    expected_host = instance_id + ".databases.neo4j.io" if instance_id else ""
    print(json.dumps({"aura_uri": {
        "tls_scheme": uri.scheme == "neo4j+s", "valid_aura_suffix": hostname.endswith(".databases.neo4j.io"),
        "matches_instance_id": hostname == expected_host, "has_whitespace": any(c.isspace() for c in hostname),
    }}), flush=True)
    resolvers = ("https://dns.google/resolve", "https://cloudflare-dns.com/dns-query")
    with ThreadPoolExecutor(max_workers=2) as pool:
        for result in pool.map(lambda resolver: dns_probe(resolver, hostname), resolvers):
            print(json.dumps({"aura_dns": result}), flush=True)
    try:
        socket.getaddrinfo(hostname, 7687)
        print(json.dumps({"system_dns": "pass"}), flush=True)
    except OSError as error:
        print(json.dumps({"system_dns": "fail", "error_code": error.errno}), flush=True)
    try:
        response = requests.get("https://router.huggingface.co/v1/models", timeout=20)
        models = [entry.get("id") for entry in response.json().get("data", [])]
        print(json.dumps({"huggingface_router": {"http_status": response.status_code,
                                                "configured_model_listed": os.getenv("HUGGINGFACE_MODEL") in models,
                                                "model_count": len(models),
                                                "candidate_models": [model for model in models if model and
                                                                     any(prefix in model for prefix in ("gpt-oss-20b", "Llama-3.1-8B", "Qwen3-4B", "Qwen3-8B"))]}}), flush=True)
    except Exception as error:
        print(json.dumps({"huggingface_router": {"error_type": type(error).__name__}}), flush=True)


if __name__ == "__main__":
    main()

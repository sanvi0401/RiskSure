"""Exercise production roles with clearly labelled verification accounts."""
import argparse
import json
from pathlib import Path
import secrets
import sys
import time

from dotenv import load_dotenv
import pyotp
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def prepare(env_file, state_path):
    load_dotenv(env_file)
    import app as backend
    state = {"accounts": {}}
    suffix = secrets.token_hex(5)
    with backend.app.app_context():
        backend.ensure_schema()
        for name, role in (("customer", "customer"), ("underwriter", "underwriter"),
                           ("other_underwriter", "underwriter"), ("admin", "admin")):
            email = f"release-{name}-{suffix}@example.invalid"
            password = secrets.token_urlsafe(24)
            user = backend.User(email=email, role=role)
            user.set_password(password)
            backend.db.session.add(user)
            backend.db.session.flush()
            if role == "customer":
                backend.db.session.add(backend.CustomerProfile(user_id=user.id,
                    full_name="RiskSure Release Verification"))
            backend.audit(user.id, "release_verification_account_created", "user", user.id)
            state["accounts"][name] = {"email": email, "password": password, "id": user.id}
        backend.db.session.commit()
    save_state(state_path, state)
    print("Prepared isolated release-verification accounts; credentials stored only in ignored artifacts.", flush=True)


def save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2))


def request(base_url, method, path, expected=200, token=None, **kwargs):
    headers = {"Authorization": "Bearer " + token} if token else {}
    response = requests.request(method, base_url.rstrip("/") + path,
                                headers=headers, timeout=120, **kwargs)
    print(f"{method} {path}: {response.status_code}", flush=True)
    if response.status_code != expected:
        raise RuntimeError(f"{method} {path}: expected {expected}, received {response.status_code}")
    return response.json()


def login(base_url, account):
    result = request(base_url, "POST", "/auth/login", json={
        "email": account["email"], "password": account["password"]})
    if result.get("totp_setup_required"):
        secret = request(base_url, "POST", "/auth/totp/setup", token=result["setup_token"])["secret"]
        result = request(base_url, "POST", "/auth/totp/verify-setup", token=result["setup_token"],
                         json={"code": pyotp.TOTP(secret).now()})
        account["totp_secret"] = secret
    elif result.get("requires_totp"):
        result = request(base_url, "POST", "/auth/login/verify-totp", token=result["challenge_token"],
                         json={"code": pyotp.TOTP(account["totp_secret"]).now()})
    account["token"] = result["access_token"]
    account["user"] = result["user"]
    request(base_url, "GET", "/auth/me", token=account["token"])
    refresh = request(base_url, "POST", "/auth/refresh", token=result["refresh_token"])
    assert refresh.get("access_token")


def verify(base_url, state_path):
    state = json.loads(state_path.read_text())
    health = request(base_url, "GET", "/health")
    assert health["model_loaded"], "The deployed XGBoost model is not loaded"
    for account in state["accounts"].values():
        login(base_url, account)
        save_state(state_path, state)
    customer = state["accounts"]["customer"]["token"]
    underwriter = state["accounts"]["underwriter"]["token"]
    admin = state["accounts"]["admin"]["token"]
    other = state["accounts"]["other_underwriter"]["token"]
    applicant = {"name": "RiskSure Release Verification", "age": 36, "sex": "female",
                 "bmi": 23.5, "children": 1, "smoker": "no", "region": "southeast"}
    if not state.get("application_id"):
        result = request(base_url, "POST", "/save", token=customer, json=applicant)
        state["application_id"] = result["application"]["id"]
        save_state(state_path, state)
    application_id = state["application_id"]
    request(base_url, "GET", "/customer/portal", token=customer)
    request(base_url, "GET", "/applications", token=customer)
    request(base_url, "GET", f"/applications/{application_id}/risk-analysis", token=customer)
    request(base_url, "GET", f"/graph?application_id={application_id}", expected=403, token=customer)
    request(base_url, "GET", "/admin/users", expected=403, token=customer)
    request(base_url, "GET", "/underwriting/queue", token=underwriter)
    request(base_url, "PUT", f"/underwriting/applications/{application_id}/assign", token=underwriter, json={})
    request(base_url, "GET", f"/graph?application_id={application_id}", expected=403, token=other)
    graph = request(base_url, "GET", f"/graph?application_id={application_id}", token=underwriter)
    print(f"Scoped graph source: {graph['source']}; nodes: {len(graph['nodes'])}", flush=True)
    evidence = request(base_url, "GET", f"/cases/{application_id}/intelligence", token=underwriter)
    assert evidence["risk"] and evidence["statistics"] and evidence["graph_evidence"]
    ai = request(base_url, "POST", f"/cases/{application_id}/assistant", token=underwriter,
                 json={"question": "Summarize supplied risk evidence and identify missing policy evidence."})
    assert ai["human_decision_required"] is True
    print(f"AI available: {ai['available']}; human decision required: true", flush=True)
    if not state.get("decision_verified"):
        request(base_url, "PUT", f"/underwriting/applications/{application_id}/decision", token=underwriter,
                json={"decision": "Approved", "reason": "Release verification of human decision workflow."})
        state["decision_verified"] = True
        save_state(state_path, state)
    request(base_url, "GET", f"/applications/{application_id}", token=customer)
    policies = request(base_url, "GET", "/policies", token=customer)
    policy_rows = policies if isinstance(policies, list) else policies.get("policies", [])
    policy = next(row for row in policy_rows if row.get("application_id") == application_id)
    if not state.get("document_verified"):
        request(base_url, "PUT", f"/policies/{policy['id']}/document", token=underwriter, json={
            "document_text": "Release verification document. Eligibility requires human underwriting review. "
                              "Exclusions and coverage are subject to the signed policy terms."})
        state["document_verified"] = True
        save_state(state_path, state)
    evidence = request(base_url, "GET", f"/cases/{application_id}/intelligence", token=underwriter)
    print(f"Policy evidence passages: {len(evidence['policy_evidence'])}", flush=True)
    assert evidence["policy_evidence"] and evidence["decision_history"]
    for path in ("/admin/overview", "/admin/users", "/applications", "/admin/audit-logs"):
        request(base_url, "GET", path, token=admin)
    system_graph = request(base_url, "GET", "/admin/graph", token=admin)
    print(f"Admin graph source: {system_graph['source']}; nodes: {len(system_graph['nodes'])}", flush=True)
    state["verification"] = {"base_url": base_url, "verified_at": int(time.time()),
                              "neo4j": graph["source"] == "neo4j" and system_graph["source"] == "neo4j",
                              "ai": ai["available"], "policy_retrieval": bool(evidence["policy_evidence"])}
    save_state(state_path, state)
    print(json.dumps(state["verification"], indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--base-url")
    args = parser.parse_args()
    if args.prepare:
        prepare(args.env_file, args.state)
    if args.base_url:
        verify(args.base_url, args.state)

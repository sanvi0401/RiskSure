"""End-to-end smoke tests. Run from backend/: python -m pytest tests"""
import os
from datetime import datetime, timezone

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-long-enough")

import pyotp  # noqa: E402
import pytest  # noqa: E402

import app as backend  # noqa: E402

APPLICANT = {"age": 45, "sex": "male", "bmi": 33, "children": 2, "smoker": "no", "region": "southeast"}


@pytest.fixture(scope="module")
def client():
    with backend.app.app_context():
        backend.ensure_schema()
    return backend.app.test_client()


@pytest.fixture(scope="module")
def session(client):
    client.post("/auth/register", json={"full_name": "Smoke User", "email": "smoke@example.com", "password": "password123"})
    setup = client.post("/auth/login", json={"email": "smoke@example.com", "password": "password123"}).json
    headers = {"Authorization": "Bearer " + setup["setup_token"]}
    secret = client.post("/auth/totp/setup", headers=headers).json["secret"]
    done = client.post("/auth/totp/verify-setup", headers=headers, json={"code": pyotp.TOTP(secret).now()})
    assert done.status_code == 200, done.json
    return {"secret": secret, **done.json}


def test_health(client):
    assert client.get("/health").json["status"] == "ok"


def test_registration_creates_customer_profile(client):
    response = client.post("/auth/register", json={
        "full_name": "Registration Test",
        "email": "registration@example.com",
        "password": "password123",
    })
    assert response.status_code == 201, response.json
    user = response.json["user"]
    assert user["role"] == "customer"

    login = client.post("/auth/login", json={
        "email": "registration@example.com",
        "password": "password123",
    })
    assert login.status_code == 200, login.json
    assert login.json["totp_setup_required"] is True

    headers = {"Authorization": "Bearer " + login.json["setup_token"]}
    setup = client.post("/auth/totp/setup", headers=headers)
    assert setup.status_code == 200, setup.json


def test_partial_tokens_cannot_access_protected_routes(client, session):
    login = client.post("/auth/login", json={"email": "smoke@example.com", "password": "password123"}).json
    challenge = {"Authorization": "Bearer " + login["challenge_token"]}
    assert client.get("/applications", headers=challenge).status_code == 401
    assert client.get("/auth/me", headers=challenge).status_code == 401


def test_underwriting_flow(client, session, monkeypatch):
    assert session["refresh_token"]
    headers = {"Authorization": "Bearer " + session["access_token"]}
    result = client.post("/process", headers=headers, json=APPLICANT)
    assert result.status_code == 200
    body = result.json
    assert 0 <= body["final_risk"] <= 1
    saved = client.post("/save", headers=headers, json={"name": "Smoke", **APPLICANT, **{
        k: body[k] for k in ("risk_score", "final_risk", "decision", "premium", "rule_adjustment")}})
    assert saved.status_code == 200
    application_id = saved.json["application"]["id"]
    applications = client.get("/applications", headers=headers).json
    assert any(application["id"] == application_id and application["review_status"] == "pending" for application in applications)

    with backend.app.app_context():
        underwriter = backend.User(email="workflow-underwriter@example.com", role="underwriter")
        underwriter.set_password("test-password-123")
        admin = backend.User(email="workflow-admin@example.com", role="admin")
        admin.set_password("test-password-123")
        backend.db.session.add_all([underwriter, admin])
        backend.db.session.commit()
        underwriter_token = backend.auth_token(underwriter)
        admin_token = backend.auth_token(admin)
    underwriter_headers = {"Authorization": "Bearer " + underwriter_token}
    admin_headers = {"Authorization": "Bearer " + admin_token}
    overview = client.get("/admin/overview", headers=admin_headers)
    assert overview.status_code == 200
    assert overview.json["approved_applications"] == 0
    assigned = client.put(f"/underwriting/applications/{application_id}/assign", headers=underwriter_headers, json={})
    assert assigned.status_code == 200, assigned.json

    graph_service = backend.application_graph.__module__
    import importlib
    service = importlib.import_module(graph_service)
    monkeypatch.setattr(service, "sync_application", lambda application: False)
    monkeypatch.setattr(service, "sync_claim", lambda claim: False)
    monkeypatch.setattr(service, "neo4j_upsert_policy", lambda policy: False)
    monkeypatch.setattr(service, "neo4j_application_graph", lambda current_id: {"nodes": [], "edges": []})
    monkeypatch.setattr(backend, "neo4j_link_application_policy", lambda application_id, policy: False)
    assistant_service = importlib.import_module("services.ai_underwriter_service")
    monkeypatch.setattr(assistant_service, "hf_request", lambda prompt, max_tokens=500: None)
    monkeypatch.setattr(backend.rag_service, "retrieve_policy_context", lambda policy, query: [])

    evidence = client.get(f"/cases/{application_id}/intelligence", headers=underwriter_headers)
    assert evidence.status_code == 200, evidence.json
    assert evidence.json["risk"]["risk_score"] == pytest.approx(body["risk_score"])
    assert evidence.json["statistics"]["sample_size"] >= 1
    assert evidence.json["human_review_required"] is True
    assistant = client.post(
        f"/cases/{application_id}/assistant",
        headers=underwriter_headers,
        json={"question": "What policy and claim evidence is available?"},
    )
    assert assistant.status_code == 200, assistant.json
    assert assistant.json["available"] is False
    assert assistant.json["human_decision_required"] is True
    decision = client.put(
        f"/underwriting/applications/{application_id}/decision",
        headers=underwriter_headers,
        json={"decision": "Approved with Conditions", "reason": "Review the submitted risk evidence."},
    )
    assert decision.status_code == 200, decision.json
    customer_applications = client.get("/applications", headers=headers).json
    completed = next(item for item in customer_applications if item["id"] == application_id)
    assert completed["review_status"] == "completed"
    assert completed["decision"] == "Approved with Conditions"
    assert client.get("/admin/overview", headers=admin_headers).json["approved_applications"] == 1
    with backend.app.app_context():
        policy = backend.Policy.query.filter_by(application_id=application_id).one()
        assert policy.customer_id == completed["customer_id"]
    admin_audit = client.get(
        "/admin/audit-logs?action=underwriting_decision",
        headers={"Authorization": "Bearer " + admin_token},
    )
    assert admin_audit.status_code == 200
    assert any(entry["entity_id"] == application_id for entry in admin_audit.json)

    tampered = client.post("/save", headers=headers, json={"name":"Tampered", **APPLICANT, "risk_score":0,"final_risk":0,"decision":"Approved","premium":1,"rule_adjustment":0})
    assert tampered.status_code == 200
    assert tampered.json["application"]["decision"] != "Approved" or tampered.json["application"]["premium"] != 1
    assert client.get("/admin/overview", headers=admin_headers).json["approved_applications"] == 1


@pytest.mark.skipif(not backend.model_loaded, reason="xgboost native library unavailable")
def test_model_predictions_are_plausible():
    import numpy as np
    for row in ([18, 0, 20, 0, 0, 0], [45, 1, 33, 2, 0, 1], [45, 1, 33, 2, 1, 1]):
        prediction = float(backend.model.inplace_predict(np.array([row], dtype=np.float32))[0])
        assert prediction > 1000, (row, prediction)

def test_relationship_graph_is_role_scoped(client, session):
    customer_headers = {"Authorization": "Bearer " + session["access_token"]}
    assert client.get("/graph", headers=customer_headers).status_code == 403

    with backend.app.app_context():
        user = backend.User.query.filter_by(email="smoke@example.com").one()
        profile = backend.CustomerProfile.query.filter_by(user_id=user.id).one()
        application = backend.Application(
            customer_id=profile.id,
            name="Scoped graph test",
            age=APPLICANT["age"],
            sex=APPLICANT["sex"],
            bmi=APPLICANT["bmi"],
            children=APPLICANT["children"],
            smoker=APPLICANT["smoker"],
            region=APPLICANT["region"],
        )
        backend.db.session.add(application)
        user.role = "underwriter"
        backend.db.session.commit()
        underwriter_token = backend.auth_token(user)
        application_id = application.id

    headers = {"Authorization": "Bearer " + underwriter_token}
    response = client.get("/graph", headers=headers)
    assert response.status_code == 400, response.json
    response = client.get(f"/graph?application_id={application_id}", headers=headers)
    assert response.status_code == 200, response.json
    body = response.json
    assert body["source"] in {"neo4j", "postgres"}
    assert isinstance(body["nodes"], list)
    assert isinstance(body["edges"], list)
    assert any(node["id"] == f"application-{application_id}" for node in body["nodes"])

    with backend.app.app_context():
        user = backend.User.query.filter_by(email="smoke@example.com").one()
        user.role = "customer"
        backend.db.session.commit()


def test_application_and_admin_graph_authorization(client, monkeypatch):
    graph_service = backend.application_graph.__module__
    import importlib
    service = importlib.import_module(graph_service)
    monkeypatch.setattr(service, "sync_application", lambda application: False)
    monkeypatch.setattr(service, "sync_claim", lambda claim: False)
    monkeypatch.setattr(service, "neo4j_upsert_policy", lambda policy: False)
    monkeypatch.setattr(service, "neo4j_application_graph", lambda application_id: {"nodes": [], "edges": []})
    monkeypatch.setattr(service, "neo4j_system_graph", lambda: {"nodes": [], "edges": []})
    monkeypatch.setattr(service, "neo4j_sync_system_projection", lambda projection: False)
    monkeypatch.setattr(backend, "neo4j_upsert_claim", lambda claim: False)

    with backend.app.app_context():
        def create_user(email, role):
            user = backend.User(email=email, role=role)
            user.set_password("test-password-123")
            backend.db.session.add(user)
            backend.db.session.flush()
            return user

        customer_a = create_user("graph-customer-a@example.com", "customer")
        customer_b = create_user("graph-customer-b@example.com", "customer")
        underwriter_a = create_user("graph-underwriter-a@example.com", "underwriter")
        underwriter_b = create_user("graph-underwriter-b@example.com", "underwriter")
        provider_user_a = create_user("graph-provider-a@example.com", "provider")
        provider_user_b = create_user("graph-provider-b@example.com", "provider")
        officer_a = create_user("graph-officer-a@example.com", "claims_officer")
        officer_b = create_user("graph-officer-b@example.com", "claims_officer")
        admin = create_user("graph-admin@example.com", "admin")
        profile_a = backend.CustomerProfile(user_id=customer_a.id, full_name="Graph Customer A")
        profile_b = backend.CustomerProfile(user_id=customer_b.id, full_name="Graph Customer B")
        backend.db.session.add_all([profile_a, profile_b])
        backend.db.session.flush()
        provider = backend.Provider(name="Graph Provider A", user_id=provider_user_a.id)
        provider_b = backend.Provider(name="Graph Provider B", user_id=provider_user_b.id)
        policy_a = backend.Policy(policy_number="GRAPH-POL-A", customer_id=profile_a.id)
        backend.db.session.add_all([provider, provider_b, policy_a])
        backend.db.session.flush()
        application_a = backend.Application(
            customer_id=profile_a.id,
            name="Graph App A",
            age=40,
            sex="female",
            bmi=27.5,
            children=1,
            smoker="no",
            region="northwest",
            decision="Approved",
            review_status="completed",
            assigned_underwriter_id=underwriter_a.id,
            reviewed_at=datetime.now(timezone.utc),
        )
        application_b = backend.Application(
            customer_id=profile_b.id,
            name="Graph App B",
            age=50,
            sex="male",
            bmi=31.0,
            children=0,
            smoker="no",
            region="southeast",
            assigned_underwriter_id=underwriter_b.id,
            review_status="in_review",
        )
        restricted_related_application = backend.Application(
            customer_id=profile_a.id,
            name="Restricted Related App",
            age=40,
            sex="female",
            bmi=27.5,
            children=1,
            smoker="no",
            region="northwest",
            decision="Rejected",
            review_status="completed",
            assigned_underwriter_id=underwriter_b.id,
            reviewed_at=datetime.now(timezone.utc),
        )
        backend.db.session.add_all([application_a, application_b, restricted_related_application])
        backend.db.session.flush()
        policy_a.application_id = application_a.id
        claim = backend.Claim(
            claim_number="GRAPH-CLAIM-A",
            customer_id=profile_a.id,
            policy_id=policy_a.id,
            provider_id=provider.id,
            claimed_amount=1250,
            assigned_officer_id=officer_a.id,
        )
        other_provider_claim = backend.Claim(
            claim_number="GRAPH-CLAIM-B",
            customer_id=profile_a.id,
            policy_id=policy_a.id,
            provider_id=provider_b.id,
            claimed_amount=2750,
            assigned_officer_id=officer_b.id,
        )
        backend.db.session.add_all([claim, other_provider_claim])
        backend.db.session.commit()
        customer_a_token = backend.auth_token(customer_a)
        underwriter_a_token = backend.auth_token(underwriter_a)
        admin_token = backend.auth_token(admin)
        provider_token = backend.auth_token(provider_user_a)
        officer_token = backend.auth_token(officer_a)
        app_a_id, app_b_id = application_a.id, application_b.id
        underwriter_a_id = underwriter_a.id
        restricted_related_id = restricted_related_application.id
        claim_a_id, claim_b_id = claim.id, other_provider_claim.id

    customer_headers = {"Authorization": f"Bearer {customer_a_token}"}
    underwriter_headers = {"Authorization": f"Bearer {underwriter_a_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    provider_headers = {"Authorization": f"Bearer {provider_token}"}
    officer_headers = {"Authorization": f"Bearer {officer_token}"}

    assert client.get(f"/applications/{app_a_id}", headers=customer_headers).status_code == 200
    assert client.get(f"/applications/{app_a_id}/risk-analysis", headers=customer_headers).status_code == 200
    assert client.get(f"/applications/{app_b_id}", headers=customer_headers).status_code == 403
    assert client.get(f"/applications/{app_b_id}/risk-analysis", headers=customer_headers).status_code == 403
    assert client.get("/graph", headers=customer_headers).status_code == 403
    assert client.get("/admin/audit-logs", headers=customer_headers).status_code == 403

    assert client.get(f"/applications/{app_a_id}", headers=underwriter_headers).status_code == 200
    assert client.get(f"/applications/{app_b_id}", headers=underwriter_headers).status_code == 403
    assert all(
        application["id"] != app_b_id
        for application in client.get("/applications", headers=underwriter_headers).json
    )
    assert all(
        application["id"] != app_b_id
        for application in client.get("/underwriting/queue", headers=underwriter_headers).json
    )
    assert client.get(f"/graph?application_id={app_b_id}", headers=underwriter_headers).status_code == 403
    assert client.get(f"/cases/{app_b_id}/intelligence", headers=underwriter_headers).status_code == 403
    assert client.post(f"/cases/{app_b_id}/assistant", headers=underwriter_headers, json={"question": "test"}).status_code == 403
    assert client.get("/admin/graph", headers=underwriter_headers).status_code == 403
    assert client.get("/admin/audit-logs", headers=underwriter_headers).status_code == 403
    assign = client.put(f"/underwriting/applications/{app_b_id}/assign", headers=underwriter_headers, json={})
    assert assign.status_code == 403, assign.json
    decision = client.put(
        f"/underwriting/applications/{app_b_id}/decision",
        headers=underwriter_headers,
        json={"decision": "Rejected", "reason": "Unauthorized decision attempt."},
    )
    assert decision.status_code == 403, decision.json

    scoped = client.get(f"/graph?application_id={app_a_id}", headers=underwriter_headers)
    assert scoped.status_code == 200, scoped.json
    graph = scoped.json
    graph_edges = {(edge["source"], edge["relationship"], edge["target"]) for edge in graph["edges"]}
    assert any(node["type"] == "riskfactor" for node in graph["nodes"])
    assert any(node["type"] == "decision" for node in graph["nodes"])
    assert any(node["type"] == "claim" for node in graph["nodes"])
    assert any(node["type"] == "policy" for node in graph["nodes"])
    assert any(node["type"] == "provider" for node in graph["nodes"])
    assert (f"application-{app_a_id}", "reviewed_by", f"underwriter-{underwriter_a_id}") in graph_edges
    assert any(source == f"application-{app_a_id}" and rel == "has_policy" for source, rel, _ in graph_edges)
    assert any(source == f"application-{app_a_id}" and rel == "has_claim" for source, rel, _ in graph_edges)
    assert any(source == f"claim-{claim_a_id}" and rel == "associated_with" for source, rel, _ in graph_edges)
    assert all(node["id"] != f"application-{restricted_related_id}" for node in graph["nodes"])

    def scoped_claim_graph(claim_id, allowed_claim_ids=None):
        allowed = set(allowed_claim_ids or [])
        assert claim_id in allowed
        return {
            "nodes": [
                {"id": f"claim-{visible_id}", "type": "claim", "properties": {"id": visible_id}}
                for visible_id in sorted(allowed)
            ],
            "edges": [],
        }

    monkeypatch.setattr(backend, "neo4j_claim_graph", scoped_claim_graph)
    provider_graph = client.get("/graph", headers=provider_headers)
    assert provider_graph.status_code == 200
    assert all(node["id"] != f"claim-{claim_b_id}" for node in provider_graph.json["nodes"])
    assert client.get(f"/graph/claim/{claim_b_id}", headers=provider_headers).status_code == 403
    officer_graph = client.get("/graph", headers=officer_headers)
    assert officer_graph.status_code == 200
    assert all(node["id"] != f"claim-{claim_b_id}" for node in officer_graph.json["nodes"])

    assert client.get(f"/graph?application_id={app_a_id}", headers=admin_headers).status_code == 200
    assert client.get("/admin/users", headers=admin_headers).status_code == 200
    admin_graph = client.get("/admin/graph", headers=admin_headers)
    assert admin_graph.status_code == 200, admin_graph.json
    assert any(node["id"] == f"application-{app_b_id}" for node in admin_graph.json["nodes"])
    admin_edges = {(edge["source"], edge["relationship"], edge["target"]) for edge in admin_graph.json["edges"]}
    assert any(source == f"application-{app_a_id}" and rel == "has_policy" for source, rel, _ in admin_edges)
    assert any(source == f"application-{app_a_id}" and rel == "has_claim" for source, rel, _ in admin_edges)
    expanded = client.get(f"/admin/graph?expand_node_id=application-{app_a_id}", headers=admin_headers)
    assert expanded.status_code == 200
    assert any(node["id"] == f"application-{app_a_id}" for node in expanded.json["nodes"])
    assert client.get("/admin/graph?expand_node_id=__import__", headers=admin_headers).status_code == 400
    admin_audit = client.get("/admin/audit-logs?search=admin_graph_investigation", headers=admin_headers)
    assert admin_audit.status_code == 200
    assert any(entry["action"] == "admin_graph_investigation" for entry in admin_audit.json)

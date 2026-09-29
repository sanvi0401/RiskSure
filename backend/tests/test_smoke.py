"""End-to-end smoke tests. Run from backend/: python -m pytest tests"""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(tempfile.mkdtemp(), "test.db"))
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-long-enough")

import pyotp  # noqa: E402
import pytest  # noqa: E402

import app as backend  # noqa: E402

APPLICANT = {"age": 45, "sex": "male", "bmi": 33, "children": 2, "smoker": "no", "region": "southeast"}


@pytest.fixture(scope="module")
def client():
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


def test_underwriting_flow(client, session):
    assert session["refresh_token"]
    headers = {"Authorization": "Bearer " + session["access_token"]}
    result = client.post("/process", headers=headers, json=APPLICANT)
    assert result.status_code == 200
    body = result.json
    assert 0 <= body["final_risk"] <= 1
    saved = client.post("/save", headers=headers, json={"name": "Smoke", **APPLICANT, **{
        k: body[k] for k in ("risk_score", "final_risk", "decision", "premium", "rule_adjustment")}})
    assert saved.status_code == 200
    assert len(client.get("/applications", headers=headers).json) >= 1


@pytest.mark.skipif(not backend.model_loaded, reason="xgboost native library unavailable")
def test_model_predictions_are_plausible():
    import numpy as np
    for row in ([18, 0, 20, 0, 0, 0], [45, 1, 33, 2, 0, 1], [45, 1, 33, 2, 1, 1]):
        prediction = float(backend.model.inplace_predict(np.array([row], dtype=np.float32))[0])
        assert prediction > 1000, (row, prediction)

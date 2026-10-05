import unittest

from app import create_app, db


class RiskSureSecurityTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "JWT_SECRET_KEY": "test-secret-key"
        })
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()

    def test_customer_registration_and_login(self):
        response = self.client.post("/api/auth/register", json={
            "email": "customer@example.com",
            "password": "StrongPass123!",
            "role": "customer"
        })
        self.assertEqual(response.status_code, 201)

        response = self.client.post("/api/auth/login", json={
            "email": "customer@example.com",
            "password": "StrongPass123!"
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["user"]["role"], "customer")

    def test_customer_cannot_access_admin(self):
        self.client.post("/api/auth/register", json={
            "email": "customer2@example.com",
            "password": "StrongPass123!",
            "role": "customer"
        })
        login = self.client.post("/api/auth/login", json={
            "email": "customer2@example.com",
            "password": "StrongPass123!"
        })
        token = login.get_json()["access_token"]

        response = self.client.get("/api/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
        self.assertIn(response.status_code, {401, 403})

    def test_underwriter_cannot_access_admin(self):
        self.client.post("/api/auth/register", json={
            "email": "underwriter@example.com",
            "password": "StrongPass123!",
            "role": "underwriter"
        })
        login = self.client.post("/api/auth/login", json={
            "email": "underwriter@example.com",
            "password": "StrongPass123!"
        })
        token = login.get_json()["access_token"]

        response = self.client.get("/api/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
        self.assertIn(response.status_code, {401, 403})

    def test_customer_cannot_access_other_application(self):
        self.client.post("/api/auth/register", json={
            "email": "alice@example.com",
            "password": "StrongPass123!",
            "role": "customer"
        })
        self.client.post("/api/auth/register", json={
            "email": "bob@example.com",
            "password": "StrongPass123!",
            "role": "customer"
        })

        alice_login = self.client.post("/api/auth/login", json={
            "email": "alice@example.com",
            "password": "StrongPass123!"
        })
        alice_token = alice_login.get_json()["access_token"]

        bob_login = self.client.post("/api/auth/login", json={
            "email": "bob@example.com",
            "password": "StrongPass123!"
        })
        bob_token = bob_login.get_json()["access_token"]

        with self.app.app_context():
            from models import Application
            app = Application(name="Bob App", age=35, smoker="yes", user_id=2)
            db.session.add(app)
            db.session.commit()
            app_id = app.id

        response = self.client.get(f"/api/customer/applications/{app_id}", headers={"Authorization": f"Bearer {alice_token}"})
        self.assertIn(response.status_code, {401, 403, 404})

        response = self.client.get(f"/api/customer/applications/{app_id}", headers={"Authorization": f"Bearer {bob_token}"})
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()

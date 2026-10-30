"""Auth flow end-to-end tests: register, login, /me, and role guards.

Runs against a throwaway SQLite DB in a temp dir, so nothing touches real
data. TestClient drives the app's lifespan (init_db + optional admin
bootstrap). Run from the Backend folder: python -m unittest discover -s tests -v
"""
import tempfile
import unittest
from pathlib import Path

import database

_THROWAWAY_DB = Path(tempfile.mkdtemp(prefix="civicfix-test-")) / "civicfix_test.db"
database.DATABASE_PATH = _THROWAWAY_DB  # must happen before main is imported

from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402

USER = {"name": "Test Citizen", "email": "citizen@example.com", "password": "str0ngPassw0rd"}


class AuthFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._context = TestClient(main.app)
        cls.client = cls._context.__enter__()
        cls.client.post("/api/auth/register", json=USER)

    @classmethod
    def tearDownClass(cls):
        cls._context.__exit__(None, None, None)

    def _register(self, email="other@example.com", name="Other Citizen"):
        return self.client.post(
            "/api/auth/register",
            json={"name": name, "email": email, "password": "str0ngPassw0rd"},
        )

    def test_register_returns_201_token_and_user_role(self):
        r = self._register("fresh@example.com", "Fresh Face")
        self.assertEqual(201, r.status_code)
        body = r.json()
        self.assertEqual("bearer", body["token_type"])
        self.assertTrue(body["access_token"])
        self.assertEqual("user", body["user"]["role"])
        self.assertEqual("fresh@example.com", body["user"]["email"])

    def test_duplicate_email_conflicts(self):
        self._register()
        self.assertEqual(409, self._register().status_code)

    def test_login_success_and_failure(self):
        ok = self.client.post(
            "/api/auth/login", json={"email": USER["email"], "password": USER["password"]}
        )
        self.assertEqual(200, ok.status_code)
        self.assertTrue(ok.json()["access_token"])
        bad = self.client.post(
            "/api/auth/login", json={"email": USER["email"], "password": "wrong-password"}
        )
        self.assertEqual(401, bad.status_code)

    def test_me_with_and_without_token(self):
        token = self.client.post(
            "/api/auth/login", json={"email": USER["email"], "password": USER["password"]}
        ).json()["access_token"]
        r = self.client.get("/api/auth/me", headers={"Authorization": "Bearer " + token})
        self.assertEqual(200, r.status_code)
        self.assertEqual(USER["email"], r.json()["email"])
        self.assertEqual(401, self.client.get("/api/auth/me").status_code)
        self.assertEqual(
            401,
            self.client.get(
                "/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
            ).status_code,
        )

    def test_admin_routes_reject_regular_user(self):
        body = self._register("plain@example.com", "Plain User").json()
        r = self.client.get(
            "/api/admin/stats", headers={"Authorization": "Bearer " + body["access_token"]}
        )
        self.assertEqual(403, r.status_code)


if __name__ == "__main__":
    unittest.main()

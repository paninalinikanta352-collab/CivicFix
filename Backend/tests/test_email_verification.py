"""Email verification OTP flow tests: register auto-sends, confirm marks verified.

Runs against a throwaway SQLite DB in a temp dir, in dev mode (SMTP unset,
so codes are returned in responses). Run: cd Backend && python -m unittest discover -s tests -v
"""
import tempfile
import unittest
from pathlib import Path

import database

_THROWAWAY_DB = Path(tempfile.mkdtemp(prefix="civicfix-test3-")) / "civicfix_test3.db"
database.DATABASE_PATH = _THROWAWAY_DB  # must happen before main is imported

from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402


class EmailVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._context = TestClient(main.app)
        cls.client = cls._context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._context.__exit__(None, None, None)

    def _register(self, email, name="Verify Me"):
        return self.client.post(
            "/api/auth/register",
            json={"name": name, "email": email, "password": "str0ngPassw0rd"},
        )

    def _request(self, email):
        return self.client.post("/api/auth/verify-request", json={"email": email})

    def _confirm(self, email, code):
        return self.client.post(
            "/api/auth/verify-confirm", json={"email": email, "code": code}
        )

    def test_register_auto_sends_dev_code_and_user_starts_unverified(self):
        body = self._register("auto@example.com").json()
        verification = body.get("verification") or {}
        self.assertEqual("dev", verification.get("delivery"))
        self.assertRegex(verification.get("otp", ""), r"^\d{6}$")

        token = body["access_token"]
        me = self.client.get("/api/auth/me", headers={"Authorization": "Bearer " + token}).json()
        self.assertFalse(me["verified"], "new self-registered accounts must start unverified")

    def test_confirm_with_wrong_then_right_code(self):
        email = "verify-flow@example.com"
        body = self._register(email).json()
        otp = (body.get("verification") or {})["otp"]

        wrong = self._confirm(email, "000000" if otp != "000000" else "111111")
        self.assertEqual(400, wrong.status_code)
        self.assertIn("Incorrect code", wrong.json()["detail"])

        me_before = self.client.get(
            "/api/auth/me", headers={"Authorization": "Bearer " + body["access_token"]}
        ).json()
        self.assertFalse(me_before["verified"])

        ok = self._confirm(email, otp)
        self.assertEqual(200, ok.status_code)
        me_after = self.client.get(
            "/api/auth/me", headers={"Authorization": "Bearer " + body["access_token"]}
        ).json()
        self.assertTrue(me_after["verified"], "the right code flips the flag")

    def test_confirm_marks_verified_and_request_says_so(self):
        email = "already@example.com"
        body = self._register(email).json()
        otp = (body.get("verification") or {})["otp"]
        self.assertEqual(200, self._confirm(email, otp).status_code)

        me = self.client.get(
            "/api/auth/me", headers={"Authorization": "Bearer " + body["access_token"]}
        ).json()
        self.assertTrue(me["verified"], "confirm must flip the flag")

        r = self._request(email)
        self.assertEqual(400, r.status_code, "verified accounts need no further codes")
        self.assertIn("already verified", r.json()["detail"])

        r = self._confirm(email, otp)
        self.assertEqual(400, r.status_code, "code must be single-use in the confirm flow too")

    def test_verify_request_unknown_email_404(self):
        r = self._request("ghost-verify@example.com")
        self.assertEqual(404, r.status_code)

    def test_confirm_rate_limit_after_five_wrong_attempts(self):
        email = "bruteforce@example.com"
        otp = (self._register(email).json().get("verification") or {})["otp"]
        bad = "999999" if otp != "999999" else "111111"
        for _ in range(5):
            self.assertEqual(400, self._confirm(email, bad).status_code)
        r = self._confirm(email, otp)
        self.assertEqual(400, r.status_code, "burned code must stop verifying even when correct")
        self.assertIn("Too many attempts", r.json()["detail"])


if __name__ == "__main__":
    unittest.main()

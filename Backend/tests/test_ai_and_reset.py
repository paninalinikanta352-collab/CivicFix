"""Reset-password OTP flow + AI category detection tests.

Runs against a throwaway SQLite DB in a temp dir. The OTP flow is tested in
dev mode (SMTP unset, so the code is returned in the response). AI detection
is tested both as a unit (stubbed Gemini HTTP layer) and through the real
issue-creation endpoint with a stubbed detector.

Run: cd Backend && python -m unittest discover -s tests -v
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import database

_THROWAWAY_DB = Path(tempfile.mkdtemp(prefix="civicfix-test2-")) / "civicfix_test2.db"
database.DATABASE_PATH = _THROWAWAY_DB  # must happen before main is imported

from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402
from routers import issues as issues_router  # noqa: E402

_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 48


class ResetPasswordOtpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._context = TestClient(main.app)
        cls.client = cls._context.__enter__()
        cls.client.post(
            "/api/auth/register",
            json={"name": "Resettester", "email": "resetme@example.com", "password": "oldPassw0rd12"},
        )

    @classmethod
    def tearDownClass(cls):
        cls._context.__exit__(None, None, None)

    def _forgot(self, email):
        return self.client.post("/api/auth/forgot-password", json={"email": email})

    def _reset(self, email, code, new_password):
        return self.client.post(
            "/api/auth/reset-password",
            json={"email": email, "code": code, "new_password": new_password},
        )

    def test_forgot_returns_dev_otp_without_smtp(self):
        r = self._forgot("resetme@example.com")
        self.assertEqual(202, r.status_code)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertEqual("dev", body["delivery"])
        self.assertIn("otp", body)
        self.assertRegex(body["otp"], r"^\d{6}$")

    def test_forgot_is_ratelimited(self):
        email = "cool@down.com"
        self._forgot(email)
        r = self._forgot(email)
        self.assertEqual(429, r.status_code)

    def test_forgot_never_reveals_registered_email(self):
        r = self._forgot("definitely-not-here@example.com")
        self.assertEqual(202, r.status_code)
        body = r.json()
        self.assertEqual("email", body["delivery"], "unknown emails must behave like known ones")
        self.assertNotIn("otp", body)

    def test_wrong_code_rejected_then_correct_code_resets(self):
        email = "flow@example.com"
        self.client.post(
            "/api/auth/register",
            json={"name": "Flow", "email": email, "password": "startPassw0rd"},
        )
        forgot = self.client.post("/api/auth/forgot-password", json={"email": email})
        dev_otp = forgot.json()["otp"]

        wrong = self._reset(email, "000000", "newPassw0rd99")
        self.assertEqual(400, wrong.status_code)
        self.assertIn("Incorrect code", wrong.json()["detail"])

        still_old = self.client.post("/api/auth/login", json={"email": email, "password": "startPassw0rd"})
        self.assertEqual(200, still_old.status_code, "password must stay valid until reset succeeds")

        ok = self._reset(email, dev_otp, "newPassw0rd99")
        self.assertEqual(200, ok.status_code)

        self.assertEqual(401, self.client.post("/api/auth/login", json={"email": email, "password": "startPassw0rd"}).status_code)
        self.assertEqual(200, self.client.post("/api/auth/login", json={"email": email, "password": "newPassw0rd99"}).status_code)

        stale = self._reset(email, dev_otp, "oneMorePassw0rd")
        self.assertEqual(400, stale.status_code, "OTP must be single-use")

    def test_five_wrong_attempts_burn_the_code(self):
        email = "burn@example.com"
        self.client.post(
            "/api/auth/register",
            json={"name": "Burn", "email": email, "password": "startPassw0rd"},
        )
        forgot = self.client.post("/api/auth/forgot-password", json={"email": email})
        code = forgot.json()["otp"]
        burned_digits = "999999" if code != "999999" else "000000"

        for attempt in range(5):
            r = self._reset(email, burned_digits, "ignoredPassw0rd")
            self.assertEqual(400, r.status_code)

        r = self._reset(email, code, "ignoredPassw0rd")
        self.assertEqual(400, r.status_code, "code must be gone after five failed attempts")

    def test_rejects_bad_code_shapes(self):
        email = "shapes@example.com"
        self.client.post(
            "/api/auth/register",
            json={"name": "Shapes", "email": email, "password": "startPassw0rd"},
        )
        forgot = self._forgot(email)
        otp = forgot.json()["otp"]
        self.assertEqual(422, self._reset(email, "12ab56", "ignoredPassw0rd").status_code)
        self.assertEqual(422, self._reset(email, "12345", "ignoredPassw0rd").status_code)
        # the real code survived the invalid attempts
        self.assertEqual(200, self._reset(email, otp, "shapesPassw0rd").status_code)


class FakeGeminiResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _gemini_payload(category, confidence):
    text = f'{{"category": "{category}", "confidence": {confidence}}}'
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


class AiCategorizerUnitTests(unittest.TestCase):
    def _detect(self, fake_post=None):
        import ai_categorizer

        env = {
            "CIVICFIX_GEMINI_API_KEY": "fake-key",
            "CIVICFIX_LLM_ENABLED": "true",
        }
        with patch.dict(sys.modules, {"requests": MagicMock()}):
            import requests as stub_requests  # noqa: F401  (pulled from patched sys.modules)

            if fake_post is not None:
                sys.modules["requests"].post = fake_post
            with patch.dict("os.environ", env):
                return ai_categorizer.detect_category("Broken road", "Huge potholes on park street")

    def test_detects_category_and_bounds_confidence(self):
        calls = {}

        def fake_post(url, params=None, json=None, timeout=None):
            calls["url"] = url
            calls["json"] = json
            return FakeGeminiResponse(_gemini_payload("roads", 2.5))

        result = self._detect(fake_post)
        self.assertIsNotNone(result)
        self.assertEqual("roads", result["category"])
        self.assertEqual(1.0, result["confidence"], "confidence must clamp to 1.0")
        self.assertIn("generateContent", calls["url"])
        self.assertEqual("roads", calls["json"]["generationConfig"]["responseSchema"]["properties"]["category"]["enum"][0])

    def test_garbage_response_returns_none(self):
        def fake_post(url, params=None, json=None, timeout=None):
            raise RuntimeError("network down")

        self.assertIsNone(self._detect(fake_post))

    def test_invalid_category_value_returns_none(self):
        def fake_post(url, params=None, json=None, timeout=None):
            return FakeGeminiResponse(_gemini_payload("parks_and_trees", 0.9))

        self.assertIsNone(self._detect(fake_post), "unexpected category values must never reach the DB")

    def test_disabled_or_keyless_never_calls_http(self):
        def fake_post(url, params=None, json=None, timeout=None):
            raise AssertionError("HTTP must not be called without a key")

        with patch.dict("os.environ", {"CIVICFIX_GEMINI_API_KEY": ""}):
            import ai_categorizer

            self.assertIsNone(ai_categorizer.detect_category("t", "d"))


class CreateIssueAiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        uploads_tmp = Path(tempfile.mkdtemp(prefix="civicfix-upload-"))
        cls._previous_upload_dir = issues_router.UPLOAD_DIR
        issues_router.UPLOAD_DIR = uploads_tmp
        cls._context = TestClient(main.app)
        cls.client = cls._context.__enter__()
        token = cls.client.post(
            "/api/auth/register",
            json={"name": "Reporter", "email": "reporter@example.com", "password": "str0ngPassw0rd"},
        ).json()["access_token"]
        cls.headers = {"Authorization": "Bearer " + token}

    @classmethod
    def tearDownClass(cls):
        cls._context.__exit__(None, None, None)
        issues_router.UPLOAD_DIR = cls._previous_upload_dir

    def _create(self, category="other", title="Massive garbage dump behind market", description="Trash bags piled up for a week near the market entrance"):
        return self.client.post(
            "/api/issues",
            headers=self.headers,
            data={"title": title, "description": description, "category": category},
            files={"image": ("photo.png", _PNG_BYTES, "image/png")},
        )

    def test_without_llm_key_category_stays_other(self):
        r = self._create()
        self.assertEqual(201, r.status_code)
        body = r.json()
        self.assertEqual("other", body["category"])
        self.assertEqual("default", body["category_source"])

    def test_stubbed_detector_sets_category_and_source(self):
        with patch.object(
            issues_router,
            "detect_category",
            return_value={"category": "cleanliness", "confidence": 0.92, "detail": "gemini"},
        ):
            r = self._create()
        self.assertEqual(201, r.status_code)
        body = r.json()
        self.assertEqual("cleanliness", body["category"])
        self.assertEqual("ai", body["category_source"])

    def test_explicit_category_is_never_overridden(self):
        with patch.object(
            issues_router,
            "detect_category",
            return_value={"category": "water", "confidence": 0.99, "detail": "gemini"},
        ):
            r = self._create(category="roads", title="Pothole harvesting zone", description="Deep potholes installed by the municipality")
        self.assertEqual(201, r.status_code)
        body = r.json()
        self.assertEqual("roads", body["category"], "explicit user choice must win over AI")
        self.assertEqual("user", body["category_source"])


if __name__ == "__main__":
    unittest.main()

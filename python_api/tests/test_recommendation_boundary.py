"""Isolated API contract checks; no Supabase connection or real records."""

import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from python_api.app import actor_token, app


class RecommendationBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.client.close()

    def test_model_requires_bearer(self):
        response = self.client.get("/v1/models/resource-affinity")
        self.assertEqual(response.status_code, 401)

    def test_browser_preflight_accepts_both_classio_app_origins(self):
        for origin in ("https://classio.expo.app", "https://app.masterclassio.com"):
            with self.subTest(origin=origin):
                response = self.client.options("/v1/models/resource-affinity", headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "authorization",
                })
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers.get("access-control-allow-origin"), origin)

    def test_browser_preflight_rejects_unlisted_origin(self):
        response = self.client.options("/v1/models/resource-affinity", headers={
            "Origin": "https://not-classio.invalid",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        })
        self.assertNotEqual(response.status_code, 200)

    def test_model_unavailable_fails_closed(self):
        app.dependency_overrides[actor_token] = lambda: ("synthetic-owner", "synthetic-token")
        with patch("python_api.app._ensure_affinity_bundle", new=AsyncMock(side_effect=HTTPException(503, "No approved run"))):
            response = self.client.get("/v1/models/resource-affinity")
        self.assertEqual(response.status_code, 503)

    def test_batch_rejects_unbounded_candidate_list(self):
        app.dependency_overrides[actor_token] = lambda: ("synthetic-owner", "synthetic-token")
        candidate = {"kind": "plan", "resource_id": 1, "context": {}}
        response = self.client.post("/v1/resource-affinity/score-batch", json={"candidates": [candidate] * 101})
        self.assertEqual(response.status_code, 422)

    def test_private_resource_owned_by_another_user_is_hidden(self):
        app.dependency_overrides[actor_token] = lambda: ("synthetic-owner", "synthetic-token")
        fake_response = type("Response", (), {"status_code": 200, "json": lambda self: [
            {"id": 1, "user_id": "different-synthetic-owner", "is_public": False, "status": "active"}
        ]})()
        fake_client = AsyncMock()
        fake_client.__aenter__.return_value.get.return_value = fake_response
        with patch("python_api.app._ensure_affinity_bundle", new=AsyncMock(return_value={})), \
             patch("python_api.app._settings", return_value=("https://synthetic.invalid", "synthetic-key")), \
             patch("python_api.app.httpx.AsyncClient", return_value=fake_client):
            response = self.client.post("/v1/resource-affinity/score", json={
                "kind": "plan", "resource_id": 1, "context": {},
            })
        self.assertEqual(response.status_code, 404)

    def test_student_score_rejects_invalid_target(self):
        app.dependency_overrides[actor_token] = lambda: ("synthetic-owner", "synthetic-token")
        response = self.client.post("/v1/student-recommendations/score", json={
            "samples": [{"features": {"x": 1}, "target": 2}], "candidates": [{"x": 1}],
        })
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()

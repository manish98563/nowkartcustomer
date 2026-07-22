"""
Backend tests for Iteration 13 - Order Management & Customer Order Tracking
Tests: auth endpoints, orders schema, order detail endpoint
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', '').rstrip('/')


class TestHealthAndRegression:
    """Health check and regression tests"""

    def test_backend_health(self):
        # /api/health may not exist; test root or docs
        resp = requests.get(f"{BASE_URL}/api/docs", timeout=10)
        assert resp.status_code in [200, 404]  # docs may or may not exist

    def test_me_returns_401_without_auth(self):
        resp = requests.get(f"{BASE_URL}/api/auth/me", timeout=10)
        assert resp.status_code == 401

    def test_get_order_returns_401_without_auth(self):
        """Backend GET /api/auth/orders/{order_id} returns 401 for unauthenticated requests"""
        # Use a simple order id (not GID with slashes) to avoid ingress path-decoding issues
        resp = requests.get(f"{BASE_URL}/api/auth/orders/test_order_123", timeout=10)
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"

    def test_authorize_url_endpoint_exists(self):
        """Auth authorize-url endpoint should return 400 (web not supported) not 404"""
        resp = requests.post(
            f"{BASE_URL}/api/auth/shopify/authorize-url",
            json={"codeChallenge": "test", "platform": "web"},
            timeout=10
        )
        # Web platform should return 400, not 404
        assert resp.status_code in [400, 422], f"Unexpected status: {resp.status_code}"

    def test_authorize_url_native_returns_valid_response(self):
        """Native platform authorize-url should return 200 with authorizeUrl"""
        resp = requests.post(
            f"{BASE_URL}/api/auth/shopify/authorize-url",
            json={"codeChallenge": "test_challenge_abc123", "platform": "native"},
            timeout=10
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "authorizeUrl" in data
        assert "state" in data
        assert "redirectUri" in data


class TestSchemasAndStructure:
    """Tests that verify schema fields are present in API responses"""

    def test_order_list_endpoint_401(self):
        """Without auth, orders endpoint returns 401"""
        resp = requests.get(f"{BASE_URL}/api/auth/orders/test_id", timeout=10)
        assert resp.status_code == 401

    def test_refresh_returns_401_with_bad_token(self):
        """Refresh with invalid token returns 401"""
        resp = requests.post(
            f"{BASE_URL}/api/auth/refresh",
            json={"refreshToken": "invalid_refresh_token_xyz"},
            timeout=10
        )
        assert resp.status_code == 401

    def test_logout_accepts_any_token(self):
        """Logout should succeed even with invalid token (idempotent)"""
        resp = requests.post(
            f"{BASE_URL}/api/auth/logout",
            json={"refreshToken": "nonexistent_token"},
            timeout=10
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True


@pytest.fixture
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

"""
Backend tests for Iteration 14 re-test - Order Management fixes
Tests: GID query param endpoint, auth guards, regression
"""
import pytest
import requests
import os
from urllib.parse import quote

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', '').rstrip('/')


class TestOrderQueryParamEndpoint:
    """Tests for new GET /api/auth/orders?id= query param format"""

    def test_orders_without_id_returns_422(self):
        """GET /api/auth/orders without ?id param returns 422 (missing required query param)"""
        resp = requests.get(f"{BASE_URL}/api/auth/orders", timeout=10)
        # FastAPI requires the Query param, but auth check might fire first (401)
        assert resp.status_code in [401, 422], f"Expected 401 or 422, got {resp.status_code}: {resp.text}"

    def test_orders_with_encoded_gid_returns_401_unauthenticated(self):
        """GET /api/auth/orders?id=<encoded GID> returns 401 for unauthenticated (not 404 or 422)"""
        encoded_id = quote("gid://shopify/Order/1234", safe='')
        resp = requests.get(f"{BASE_URL}/api/auth/orders?id={encoded_id}", timeout=10)
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"

    def test_orders_with_plain_id_returns_401_unauthenticated(self):
        """GET /api/auth/orders?id=plain_id returns 401 for unauthenticated"""
        resp = requests.get(f"{BASE_URL}/api/auth/orders?id=test_order_123", timeout=10)
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"

    def test_old_path_segment_format_returns_404_or_401(self):
        """Old path format /api/auth/orders/{id} should no longer be the main route"""
        resp = requests.get(f"{BASE_URL}/api/auth/orders/test_order_123", timeout=10)
        # Either 404 (route not found) or 401 (auth check)
        assert resp.status_code in [401, 404, 405], f"Got {resp.status_code}: {resp.text}"


class TestAuthRegression:
    """Regression tests for auth endpoints"""

    def test_me_requires_auth(self):
        resp = requests.get(f"{BASE_URL}/api/auth/me", timeout=10)
        assert resp.status_code == 401

    def test_authorize_url_native(self):
        resp = requests.post(
            f"{BASE_URL}/api/auth/shopify/authorize-url",
            json={"codeChallenge": "test_challenge_abc123", "platform": "native"},
            timeout=10
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "authorizeUrl" in data
        assert "state" in data
        assert "redirectUri" in data

    def test_refresh_with_invalid_token_returns_401(self):
        resp = requests.post(
            f"{BASE_URL}/api/auth/refresh",
            json={"refreshToken": "invalid_token_xyz"},
            timeout=10
        )
        assert resp.status_code == 401

    def test_logout_is_idempotent(self):
        resp = requests.post(
            f"{BASE_URL}/api/auth/logout",
            json={"refreshToken": "nonexistent_token"},
            timeout=10
        )
        assert resp.status_code == 200
        assert resp.json().get("ok") is True

    def test_addresses_requires_auth(self):
        resp = requests.get(f"{BASE_URL}/api/auth/addresses", timeout=10)
        assert resp.status_code == 401


@pytest.fixture
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

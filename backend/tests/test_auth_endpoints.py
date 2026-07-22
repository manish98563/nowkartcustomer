"""
Iteration 4: Shopify Customer Account API auth endpoints (backend-mediated OAuth2 + PKCE).
Covers: authorize-url (native + web-rejection), refresh, logout, /me & /addresses guest-401 checks.
No real Shopify email verification is available in this environment, so token-exchange completion
and address CRUD (which require an authenticated user) cannot be fully exercised here.
"""
import os

import pytest
import requests

BASE_URL = os.environ.get("EXPO_BACKEND_URL").rstrip("/")


@pytest.fixture
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestAuthorizeUrl:
    def test_native_platform_returns_authorize_url(self, api_client):
        resp = api_client.post(
            f"{BASE_URL}/api/auth/shopify/authorize-url",
            json={"codeChallenge": "TEST_challenge_" + "a" * 43, "platform": "native"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "authorizeUrl" in data and data["authorizeUrl"].startswith("https://")
        assert "state" in data and len(data["state"]) > 0
        assert "redirectUri" in data

    def test_web_platform_rejected_with_400(self, api_client):
        resp = api_client.post(
            f"{BASE_URL}/api/auth/shopify/authorize-url",
            json={"codeChallenge": "TEST_challenge_" + "b" * 43, "platform": "web", "origin": "http://localhost:3000"},
        )
        assert resp.status_code == 400, resp.text

    def test_missing_code_challenge_returns_422(self, api_client):
        resp = api_client.post(f"{BASE_URL}/api/auth/shopify/authorize-url", json={"platform": "native"})
        assert resp.status_code == 422


class TestProtectedEndpointsGuestAccess:
    """Guests (no Authorization header) must get 401, never real data."""

    def test_me_requires_auth(self, api_client):
        resp = api_client.get(f"{BASE_URL}/api/auth/me")
        assert resp.status_code == 401

    def test_addresses_get_requires_auth(self, api_client):
        resp = api_client.get(f"{BASE_URL}/api/auth/addresses")
        assert resp.status_code == 401

    def test_addresses_post_requires_auth(self, api_client):
        resp = api_client.post(
            f"{BASE_URL}/api/auth/addresses",
            json={"address1": "TEST_1 Main St", "city": "London", "territoryCode": "GB"},
        )
        assert resp.status_code == 401

    def test_me_with_garbage_token_returns_401(self, api_client):
        resp = api_client.get(
            f"{BASE_URL}/api/auth/me", headers={"Authorization": "Bearer garbage.invalid.token"}
        )
        assert resp.status_code == 401


class TestRefreshAndLogout:
    def test_refresh_with_invalid_token_returns_error(self, api_client):
        resp = api_client.post(f"{BASE_URL}/api/auth/refresh", json={"refreshToken": "TEST_nonexistent_token"})
        assert resp.status_code in (400, 401), resp.text

    def test_logout_with_invalid_token_is_idempotent_ok(self, api_client):
        # Logout should be best-effort/idempotent even for unknown tokens (no data leak, no 500)
        resp = api_client.post(f"{BASE_URL}/api/auth/logout", json={"refreshToken": "TEST_nonexistent_token"})
        assert resp.status_code in (200, 204, 400, 401), resp.text
        assert resp.status_code != 500

    def test_refresh_missing_field_returns_422(self, api_client):
        resp = api_client.post(f"{BASE_URL}/api/auth/refresh", json={})
        assert resp.status_code == 422


class TestExistingShopifyCatalogRegression:
    """Sanity check existing (previously verified) catalog endpoints still work post auth changes."""

    def test_home_endpoint(self, api_client):
        resp = api_client.get(f"{BASE_URL}/api/shopify/home")
        assert resp.status_code == 200
        assert "sections" in resp.json() or isinstance(resp.json(), dict)

    def test_categories_endpoint(self, api_client):
        resp = api_client.get(f"{BASE_URL}/api/shopify/categories")
        assert resp.status_code == 200

    def test_cart_create_still_works_guest(self, api_client):
        resp = api_client.post(f"{BASE_URL}/api/shopify/cart", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data or "cart" in data

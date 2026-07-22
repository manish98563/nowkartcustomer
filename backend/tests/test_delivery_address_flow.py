"""Delivery Address regression tests - Iteration 12
Tests: prepare_checkout accepts delivery address fields, schema validation
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://repo-clone-verify.preview.emergentagent.com")


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def cart_id(session):
    """Create a cart with a product for testing."""
    resp = session.get(f"{BASE_URL}/api/shopify/home")
    assert resp.status_code == 200
    data = resp.json()
    variant_id = None
    for rail in data.get("rails", []):
        for product in rail.get("products", []):
            for v in product.get("variants", []):
                if v.get("availableForSale"):
                    variant_id = v.get("id")
                    break
            if variant_id:
                break
        if variant_id:
            break
    assert variant_id, "Could not find a valid variant"
    resp = session.post(f"{BASE_URL}/api/shopify/cart", json={"variantId": variant_id, "quantity": 1})
    assert resp.status_code == 200
    return resp.json()["id"]


class TestPrepareCheckoutWithDeliveryAddress:
    """POST /api/shopify/checkout/prepare with optional delivery address fields."""

    def test_prepare_checkout_without_address(self, session, cart_id):
        """Base case: prepare without delivery address still works."""
        resp = session.post(f"{BASE_URL}/api/shopify/checkout/prepare", json={"cartId": cart_id})
        assert resp.status_code == 200
        data = resp.json()
        assert "checkoutUrl" in data
        assert "isValid" in data
        assert "cart" in data

    def test_prepare_checkout_with_delivery_address(self, session, cart_id):
        """New feature: delivery address fields are accepted and don't cause 422."""
        payload = {
            "cartId": cart_id,
            "deliveryFirstName": "Test",
            "deliveryLastName": "User",
            "deliveryAddress1": "123 Test Street",
            "deliveryCity": "London",
            "deliveryTerritoryCode": "GB",
            "deliveryZip": "SW1A 1AA",
        }
        resp = session.post(f"{BASE_URL}/api/shopify/checkout/prepare", json=payload)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "checkoutUrl" in data
        assert "isValid" in data

    def test_prepare_checkout_partial_address(self, session, cart_id):
        """Only city + country provided — should still be accepted (all fields optional)."""
        payload = {
            "cartId": cart_id,
            "deliveryCity": "Manchester",
            "deliveryTerritoryCode": "GB",
        }
        resp = session.post(f"{BASE_URL}/api/shopify/checkout/prepare", json=payload)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_prepare_checkout_with_address2(self, session, cart_id):
        """Address2 and phone are also accepted."""
        payload = {
            "cartId": cart_id,
            "deliveryAddress1": "10 Downing Street",
            "deliveryAddress2": "Flat 2",
            "deliveryCity": "London",
            "deliveryTerritoryCode": "GB",
            "deliveryZip": "SW1A 2AA",
            "deliveryPhone": "+447700900000",
        }
        resp = session.post(f"{BASE_URL}/api/shopify/checkout/prepare", json=payload)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_prepare_checkout_invalid_cart_returns_404(self, session):
        """Invalid cartId with delivery address returns 404 (not 422 or 500)."""
        payload = {
            "cartId": "gid://shopify/Cart/INVALID_CART_ID",
            "deliveryAddress1": "123 Test St",
            "deliveryCity": "London",
            "deliveryTerritoryCode": "GB",
        }
        resp = session.post(f"{BASE_URL}/api/shopify/checkout/prepare", json=payload)
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"

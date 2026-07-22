"""Checkout flow backend tests - Iteration 11
Tests: cart totalTax field, cart note update, checkout prepare endpoint
"""
import pytest
import requests
import os

BASE_URL = "https://repo-clone-verify.preview.emergentagent.com"

@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s

@pytest.fixture(scope="module")
def cart_id(session):
    """Create a cart with a product for testing."""
    # First get a valid variant ID from the home page
    resp = session.get(f"{BASE_URL}/api/shopify/home")
    assert resp.status_code == 200, f"Home failed: {resp.text}"
    data = resp.json()
    rails = data.get("rails", [])
    variant_id = None
    for rail in rails:
        products = rail.get("products", [])
        for product in products:
            variants = product.get("variants", [])
            for v in variants:
                if v.get("availableForSale"):
                    variant_id = v.get("id")
                    break
            if variant_id:
                break
        if variant_id:
            break

    assert variant_id, "Could not find a valid variant to add to cart"
    
    # Create cart
    resp = session.post(f"{BASE_URL}/api/shopify/cart", json={"variantId": variant_id, "quantity": 1})
    assert resp.status_code == 200, f"Cart creation failed: {resp.text}"
    cart = resp.json()
    return cart["id"]


class TestCartGetWithTotalTax:
    """Test GET /api/shopify/cart returns totalTax field"""

    def test_get_cart_returns_total_tax_field(self, session, cart_id):
        resp = session.get(f"{BASE_URL}/api/shopify/cart", params={"cart_id": cart_id})
        assert resp.status_code == 200, f"GET cart failed: {resp.text}"
        data = resp.json()
        assert "totalTax" in data, "totalTax field missing from CartOut response"
        assert isinstance(data["totalTax"], (int, float)), f"totalTax should be numeric, got {type(data['totalTax'])}"
        print(f"PASS: totalTax = {data['totalTax']}")

    def test_get_cart_has_checkout_url(self, session, cart_id):
        resp = session.get(f"{BASE_URL}/api/shopify/cart", params={"cart_id": cart_id})
        assert resp.status_code == 200
        data = resp.json()
        assert "checkoutUrl" in data
        assert data["checkoutUrl"].startswith("https://"), f"checkoutUrl looks invalid: {data['checkoutUrl']}"
        print(f"PASS: checkoutUrl = {data['checkoutUrl'][:60]}...")

    def test_get_cart_structure(self, session, cart_id):
        resp = session.get(f"{BASE_URL}/api/shopify/cart", params={"cart_id": cart_id})
        assert resp.status_code == 200
        data = resp.json()
        required_fields = ["id", "checkoutUrl", "totalQuantity", "subtotal", "total", "totalTax", "currencyCode", "lines"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        print("PASS: All CartOut fields present")


class TestCartNoteUpdate:
    """Test PUT /api/shopify/cart/note returns {ok: true}"""

    def test_update_note_returns_ok(self, session, cart_id):
        resp = session.put(f"{BASE_URL}/api/shopify/cart/note", json={
            "cartId": cart_id,
            "note": "TEST_Leave at door"
        })
        assert resp.status_code == 200, f"Note update failed: {resp.text}"
        data = resp.json()
        assert data.get("ok") == True, f"Expected {{ok: true}}, got: {data}"
        print("PASS: cart note update returns {ok: true}")

    def test_update_empty_note(self, session, cart_id):
        resp = session.put(f"{BASE_URL}/api/shopify/cart/note", json={
            "cartId": cart_id,
            "note": ""
        })
        # Empty note should still succeed (API accepts it)
        assert resp.status_code == 200, f"Empty note update failed: {resp.text}"
        print(f"PASS: empty note returns status {resp.status_code}")


class TestCheckoutPrepare:
    """Test POST /api/shopify/checkout/prepare returns valid checkoutUrl"""

    def test_prepare_checkout_returns_checkout_url(self, session, cart_id):
        resp = session.post(f"{BASE_URL}/api/shopify/checkout/prepare", json={"cartId": cart_id})
        assert resp.status_code == 200, f"Checkout prepare failed: {resp.text}"
        data = resp.json()
        assert "checkoutUrl" in data, "checkoutUrl missing from prepare response"
        assert data["checkoutUrl"].startswith("https://"), f"checkoutUrl invalid: {data['checkoutUrl']}"
        print(f"PASS: checkoutUrl present = {data['checkoutUrl'][:60]}...")

    def test_prepare_checkout_has_is_valid(self, session, cart_id):
        resp = session.post(f"{BASE_URL}/api/shopify/checkout/prepare", json={"cartId": cart_id})
        assert resp.status_code == 200
        data = resp.json()
        assert "isValid" in data, "isValid field missing"
        assert isinstance(data["isValid"], bool), "isValid should be boolean"
        print(f"PASS: isValid = {data['isValid']}")

    def test_prepare_checkout_has_cart(self, session, cart_id):
        resp = session.post(f"{BASE_URL}/api/shopify/checkout/prepare", json={"cartId": cart_id})
        assert resp.status_code == 200
        data = resp.json()
        assert "cart" in data, "cart missing from prepare response"
        assert "issues" in data, "issues missing from prepare response"
        cart = data["cart"]
        assert "totalTax" in cart, "totalTax missing from nested cart in prepare response"
        print("PASS: prepare checkout structure correct")

    def test_prepare_invalid_cart_returns_404(self, session):
        resp = session.post(f"{BASE_URL}/api/shopify/checkout/prepare", json={"cartId": "gid://shopify/Cart/invalid123"})
        assert resp.status_code == 404, f"Expected 404 for invalid cart, got {resp.status_code}"
        print("PASS: invalid cart returns 404")

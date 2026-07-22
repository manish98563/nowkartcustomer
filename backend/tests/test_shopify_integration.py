"""
Backend regression tests for Shopify Storefront API integration (Iteration 3).
Covers: home, categories, collection products, product detail, search, and
full cart lifecycle (create -> get -> add -> update -> remove), plus security
checks (no token leakage in responses) and error handling (404s, bad input).
"""
import os
import re
import subprocess

import pytest
import requests

BASE_URL = os.environ.get('EXPO_BACKEND_URL').rstrip('/')
API = f"{BASE_URL}/api"

TOKEN = "REMOVED_SECRET"


@pytest.fixture(scope="module")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def known_collection_handle(api_client):
    resp = api_client.get(f"{API}/shopify/categories")
    assert resp.status_code == 200
    groups = resp.json()
    assert len(groups) > 0
    return groups[0]["categories"][0]["handle"]


@pytest.fixture(scope="module")
def known_product(api_client, known_collection_handle):
    resp = api_client.get(f"{API}/shopify/collections/{known_collection_handle}/products?first=1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["products"]) > 0
    return data["products"][0]


class TestHome:
    def test_home_sections_200(self, api_client):
        resp = api_client.get(f"{API}/shopify/home")
        assert resp.status_code == 200
        data = resp.json()
        assert "categoryGroups" in data
        assert "rails" in data
        assert isinstance(data["categoryGroups"], list)
        assert isinstance(data["rails"], list)
        assert len(data["categoryGroups"]) > 0, "Expected at least one live category group"
        assert len(data["rails"]) > 0, "Expected at least one live product rail"

    def test_home_rail_products_have_valid_fields(self, api_client):
        resp = api_client.get(f"{API}/shopify/home")
        data = resp.json()
        rail = data["rails"][0]
        assert "title" in rail
        product = rail["products"][0]
        assert product["price"] >= 0
        assert product["currencyCode"] == "GBP"
        assert "handle" in product and product["handle"]


class TestCategories:
    def test_categories_200_structure(self, api_client):
        resp = api_client.get(f"{API}/shopify/categories")
        assert resp.status_code == 200
        groups = resp.json()
        assert isinstance(groups, list)
        assert len(groups) > 0
        for g in groups:
            assert "groupTitle" in g
            assert isinstance(g["categories"], list)
            assert len(g["categories"]) > 0


class TestCollectionProducts:
    def test_collection_products_valid_handle(self, api_client, known_collection_handle):
        resp = api_client.get(f"{API}/shopify/collections/{known_collection_handle}/products?first=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["collection"]["handle"] == known_collection_handle
        assert isinstance(data["products"], list)

    def test_collection_products_invalid_handle_404(self, api_client):
        resp = api_client.get(f"{API}/shopify/collections/this-handle-does-not-exist-zzz/products")
        assert resp.status_code == 404

    def test_collection_products_first_param_limit(self, api_client, known_collection_handle):
        resp = api_client.get(f"{API}/shopify/collections/{known_collection_handle}/products?first=51")
        assert resp.status_code == 422  # exceeds le=50


class TestProductDetail:
    def test_product_by_handle_valid(self, api_client, known_product):
        handle = known_product["handle"]
        resp = api_client.get(f"{API}/shopify/products/{handle}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["handle"] == handle
        assert data["price"] >= 0
        assert isinstance(data["variants"], list)
        assert len(data["variants"]) > 0
        variant = data["variants"][0]
        assert "availableForSale" in variant
        assert "id" in variant

    def test_product_by_handle_invalid_404(self, api_client):
        resp = api_client.get(f"{API}/shopify/products/nonexistent-product-handle-zzz-123")
        assert resp.status_code == 404


class TestSearch:
    def test_search_returns_results(self, api_client, known_product):
        # search using a token from the known product title
        term = known_product["title"].split()[0]
        resp = api_client.get(f"{API}/shopify/search", params={"q": term})
        assert resp.status_code == 200
        results = resp.json()
        assert isinstance(results, list)

    def test_search_no_results(self, api_client):
        resp = api_client.get(f"{API}/shopify/search", params={"q": "zzzznonexistentproductxyz123"})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_search_special_characters_no_crash(self, api_client):
        for q in ["!@#$%^&*()", "日本語", "a'; DROP TABLE--", "   ", "%%%"]:
            resp = api_client.get(f"{API}/shopify/search", params={"q": q})
            assert resp.status_code in (200, 422), f"Unexpected status for query {q!r}: {resp.status_code}"

    def test_search_missing_query_422(self, api_client):
        resp = api_client.get(f"{API}/shopify/search")
        assert resp.status_code == 422


class TestCartLifecycle:
    def test_full_cart_lifecycle(self, api_client, known_product):
        variant_id = known_product["variants"][0]["id"]
        variant_price = known_product["variants"][0]["price"]

        # CREATE
        create_resp = api_client.post(f"{API}/shopify/cart", json={"variantId": variant_id, "quantity": 1})
        assert create_resp.status_code == 200
        cart = create_resp.json()
        cart_id = cart["id"]
        assert cart["totalQuantity"] == 1
        assert len(cart["lines"]) == 1
        line_id = cart["lines"][0]["id"]
        assert abs(cart["subtotal"] - variant_price) < 0.01

        # GET (verify persistence)
        get_resp = api_client.get(f"{API}/shopify/cart", params={"cart_id": cart_id})
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == cart_id
        assert get_resp.json()["totalQuantity"] == 1

        # ADD SAME VARIANT AGAIN -> should merge, not duplicate
        add_resp = api_client.post(
            f"{API}/shopify/cart/lines", json={"cartId": cart_id, "variantId": variant_id, "quantity": 1}
        )
        assert add_resp.status_code == 200
        merged_cart = add_resp.json()
        assert len(merged_cart["lines"]) == 1, "Adding same variant twice should merge into one line"
        assert merged_cart["totalQuantity"] == 2
        merged_line_id = merged_cart["lines"][0]["id"]

        # UPDATE quantity
        update_resp = api_client.put(
            f"{API}/shopify/cart/lines", json={"cartId": cart_id, "lineId": merged_line_id, "quantity": 5}
        )
        assert update_resp.status_code == 200
        updated_cart = update_resp.json()
        assert updated_cart["totalQuantity"] == 5
        assert abs(updated_cart["lines"][0]["lineTotal"] - variant_price * 5) < 0.01

        # REMOVE line -> empty cart
        remove_resp = api_client.delete(
            f"{API}/shopify/cart/lines", json={"cartId": cart_id, "lineId": merged_line_id}
        )
        assert remove_resp.status_code == 200
        emptied_cart = remove_resp.json()
        assert emptied_cart["totalQuantity"] == 0
        assert len(emptied_cart["lines"]) == 0

    def test_get_cart_invalid_id_404_or_error(self, api_client):
        resp = api_client.get(f"{API}/shopify/cart", params={"cart_id": "gid://shopify/Cart/doesnotexist"})
        assert resp.status_code in (404, 502, 400)

    def test_create_cart_without_variant(self, api_client):
        resp = api_client.post(f"{API}/shopify/cart", json={})
        assert resp.status_code == 200
        cart = resp.json()
        assert cart["totalQuantity"] == 0


class TestSecurity:
    def test_token_not_in_any_response_body(self, api_client, known_collection_handle, known_product):
        endpoints = [
            f"{API}/shopify/home",
            f"{API}/shopify/categories",
            f"{API}/shopify/collections/{known_collection_handle}/products",
            f"{API}/shopify/products/{known_product['handle']}",
            f"{API}/shopify/search?q=milk",
        ]
        for url in endpoints:
            resp = api_client.get(url)
            assert TOKEN not in resp.text, f"Token leaked in response from {url}"

    def test_token_not_in_backend_logs(self):
        result = subprocess.run(
            ["grep", "-r", TOKEN, "/var/log/supervisor/"],
            capture_output=True, text=True
        )
        assert result.stdout == "", f"Token found in backend logs: {result.stdout[:500]}"

    def test_no_shopify_domain_in_frontend_source(self):
        result = subprocess.run(
            ["grep", "-rl", "shpat_", "/app/frontend/", "--include=*.ts", "--include=*.tsx", "--include=*.js"],
            capture_output=True, text=True
        )
        assert result.stdout == "", f"Shopify token pattern found in frontend source: {result.stdout}"

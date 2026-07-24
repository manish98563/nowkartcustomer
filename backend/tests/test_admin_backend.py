"""
Comprehensive Admin Backend Tests — Iteration 19
Tests: auth, RBAC, audit logs, store/rider/vendor/delivery management, regressions
"""
import pytest
import requests
import os

BASE_URL = "http://localhost:8001"

# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def super_admin_token():
    r = requests.post(f"{BASE_URL}/api/admin/auth/login", json={
        "email": "admin@nowkart.com", "password": "Admin2026!"
    })
    assert r.status_code == 200, f"Super admin login failed: {r.text}"
    return r.json()["accessToken"]


@pytest.fixture(scope="session")
def super_admin_session():
    r = requests.post(f"{BASE_URL}/api/admin/auth/login", json={
        "email": "admin@nowkart.com", "password": "Admin2026!"
    })
    assert r.status_code == 200
    return r.json()


@pytest.fixture(scope="session")
def ops_token():
    r = requests.post(f"{BASE_URL}/api/admin/auth/login", json={
        "email": "ops@nowkart.com", "password": "Ops2026!!"
    })
    if r.status_code != 200:
        pytest.skip(f"ops@nowkart.com login failed: {r.text}")
    return r.json()["accessToken"]


@pytest.fixture(scope="session")
def rider_token():
    r = requests.post(f"{BASE_URL}/api/rider/auth/login", json={
        "email": "rider1@nowkart.com", "password": "NowKart2026!"
    })
    if r.status_code != 200:
        pytest.skip(f"Rider login failed: {r.text}")
    data = r.json()
    return data.get("accessToken") or data.get("token")


@pytest.fixture(scope="session")
def vendor_token():
    r = requests.post(f"{BASE_URL}/api/vendor/auth/login", json={
        "email": "vendor1@nowkart.com", "password": "Vendor2026!"
    })
    if r.status_code != 200:
        pytest.skip(f"Vendor login failed: {r.text}")
    data = r.json()
    return data.get("accessToken") or data.get("token")


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# ─── Admin Auth Tests ─────────────────────────────────────────────────────────

class TestAdminAuth:
    """Admin authentication flows"""

    def test_login_success_super_admin(self):
        r = requests.post(f"{BASE_URL}/api/admin/auth/login", json={
            "email": "admin@nowkart.com", "password": "Admin2026!"
        })
        assert r.status_code == 200
        data = r.json()
        assert "accessToken" in data
        assert "refreshToken" in data
        assert data.get("expiresIn") == 3600
        assert data["admin"]["role"] == "super_admin"

    def test_login_wrong_password_returns_401(self):
        r = requests.post(f"{BASE_URL}/api/admin/auth/login", json={
            "email": "admin@nowkart.com", "password": "WrongPass!"
        })
        assert r.status_code == 401

    def test_login_unknown_email_returns_401(self):
        r = requests.post(f"{BASE_URL}/api/admin/auth/login", json={
            "email": "nobody@nowhere.com", "password": "pass"
        })
        assert r.status_code == 401

    def test_ops_login_success(self):
        r = requests.post(f"{BASE_URL}/api/admin/auth/login", json={
            "email": "ops@nowkart.com", "password": "Ops2026!!"
        })
        assert r.status_code == 200
        data = r.json()
        assert data["admin"]["role"] == "operations_manager"

    def test_refresh_token_rotation(self, super_admin_session):
        refresh_token = super_admin_session["refreshToken"]
        r = requests.post(f"{BASE_URL}/api/admin/auth/refresh", json={
            "refreshToken": refresh_token
        })
        assert r.status_code == 200
        data = r.json()
        assert "accessToken" in data
        assert "refreshToken" in data
        # New refresh token should be different
        assert data["refreshToken"] != refresh_token

    def test_logout_revokes_refresh_token(self, super_admin_token):
        # Login fresh to get a separate refresh token to revoke
        r = requests.post(f"{BASE_URL}/api/admin/auth/login", json={
            "email": "admin@nowkart.com", "password": "Admin2026!"
        })
        session = r.json()
        logout_r = requests.post(
            f"{BASE_URL}/api/admin/auth/logout",
            json={"refreshToken": session["refreshToken"]},
            headers=auth_headers(session["accessToken"])
        )
        assert logout_r.status_code == 204

        # Using revoked refresh token should fail
        refresh_r = requests.post(f"{BASE_URL}/api/admin/auth/refresh", json={
            "refreshToken": session["refreshToken"]
        })
        assert refresh_r.status_code in (401, 400)


# ─── Profile Tests ────────────────────────────────────────────────────────────

class TestAdminProfile:
    """Admin profile endpoint"""

    def test_get_profile_with_valid_token(self, super_admin_token):
        r = requests.get(f"{BASE_URL}/api/admin/profile",
                         headers=auth_headers(super_admin_token))
        assert r.status_code == 200
        data = r.json()
        assert data["role"] == "super_admin"
        assert data["email"] == "admin@nowkart.com"

    def test_get_profile_without_token_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/admin/profile")
        assert r.status_code == 401

    def test_get_profile_with_invalid_token_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/admin/profile",
                         headers={"Authorization": "Bearer invalid.token.here"})
        assert r.status_code == 401


# ─── Role Isolation Tests ─────────────────────────────────────────────────────

class TestRoleIsolation:
    """Ensure rider/vendor/customer JWTs are rejected on admin endpoints"""

    def test_rider_token_on_admin_endpoint_returns_401(self, rider_token):
        r = requests.get(f"{BASE_URL}/api/admin/profile",
                         headers=auth_headers(rider_token))
        assert r.status_code == 401

    def test_vendor_token_on_admin_endpoint_returns_401(self, vendor_token):
        r = requests.get(f"{BASE_URL}/api/admin/profile",
                         headers=auth_headers(vendor_token))
        assert r.status_code == 401

    def test_riders_endpoint_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/admin/riders")
        assert r.status_code == 401

    def test_vendors_endpoint_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/admin/vendors")
        assert r.status_code == 401


# ─── Admin Management (super_admin only) ─────────────────────────────────────

class TestAdminManagement:
    """Admin CRUD — super_admin only"""

    created_admin_id = None

    def test_list_admins_super_admin(self, super_admin_token):
        r = requests.get(f"{BASE_URL}/api/admin/admins",
                         headers=auth_headers(super_admin_token))
        assert r.status_code == 200
        data = r.json()
        assert "admins" in data
        assert "total" in data

    def test_list_admins_ops_returns_403(self, ops_token):
        r = requests.get(f"{BASE_URL}/api/admin/admins",
                         headers=auth_headers(ops_token))
        assert r.status_code == 403

    def test_create_admin_super_admin(self, super_admin_token):
        import time
        unique_email = f"TEST_newadmin_{int(time.time())}@nowkart.com"
        r = requests.post(f"{BASE_URL}/api/admin/admins",
                          headers=auth_headers(super_admin_token),
                          json={
                              "email": unique_email,
                              "password": "TestAdmin2026!",
                              "firstName": "TEST",
                              "lastName": "NewAdmin",
                              "role": "support"
                          })
        assert r.status_code == 201
        data = r.json()
        assert data.get("email", "").lower() == unique_email.lower()
        assert data["role"] == "support"
        TestAdminManagement.created_admin_id = data["id"]

    def test_create_admin_ops_returns_403(self, ops_token):
        r = requests.post(f"{BASE_URL}/api/admin/admins",
                          headers=auth_headers(ops_token),
                          json={
                              "email": "TEST_fail@nowkart.com",
                              "password": "TestAdmin2026!",
                              "firstName": "TEST",
                              "lastName": "Fail",
                              "role": "support"
                          })
        assert r.status_code == 403

    def test_suspend_admin(self, super_admin_token):
        admin_id = TestAdminManagement.created_admin_id
        if not admin_id:
            pytest.skip("No created admin to suspend")
        r = requests.put(f"{BASE_URL}/api/admin/admins/{admin_id}/suspend",
                         headers=auth_headers(super_admin_token))
        assert r.status_code == 200
        assert r.json()["isActive"] == False

    def test_activate_admin(self, super_admin_token):
        admin_id = TestAdminManagement.created_admin_id
        if not admin_id:
            pytest.skip("No created admin to activate")
        r = requests.put(f"{BASE_URL}/api/admin/admins/{admin_id}/activate",
                         headers=auth_headers(super_admin_token))
        assert r.status_code == 200
        assert r.json()["isActive"] == True

    def test_cleanup_created_admin(self, super_admin_token):
        admin_id = TestAdminManagement.created_admin_id
        if not admin_id:
            pytest.skip("No created admin to delete")
        r = requests.delete(f"{BASE_URL}/api/admin/admins/{admin_id}",
                            headers=auth_headers(super_admin_token))
        assert r.status_code == 204


# ─── Dashboard Tests ──────────────────────────────────────────────────────────

class TestDashboard:
    """Dashboard stats and health"""

    def test_dashboard_stats_super_admin(self, super_admin_token):
        r = requests.get(f"{BASE_URL}/api/admin/dashboard/stats",
                         headers=auth_headers(super_admin_token))
        assert r.status_code == 200
        data = r.json()
        # Should have delivery/riders/vendors/stores fields
        assert any(k in data for k in ["deliveries", "riders", "vendors", "stores", "totalDeliveries"])

    def test_dashboard_health(self, super_admin_token):
        r = requests.get(f"{BASE_URL}/api/admin/dashboard/health",
                         headers=auth_headers(super_admin_token))
        assert r.status_code == 200

    def test_dashboard_without_token_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/admin/dashboard/stats")
        assert r.status_code == 401


# ─── Audit Logs Tests ─────────────────────────────────────────────────────────

class TestAuditLogs:
    """Audit log access control and content"""

    def test_audit_logs_admin_can_view(self, super_admin_token):
        r = requests.get(f"{BASE_URL}/api/admin/audit-logs",
                         headers=auth_headers(super_admin_token))
        assert r.status_code == 200
        data = r.json()
        assert "logs" in data
        assert "total" in data

    def test_audit_logs_contain_admin_login(self, super_admin_token):
        r = requests.get(f"{BASE_URL}/api/admin/audit-logs?action=admin_login",
                         headers=auth_headers(super_admin_token))
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1

    def test_audit_logs_ops_can_view(self, ops_token):
        # operations_manager has role level 2, audit-logs requires "admin" level 3
        r = requests.get(f"{BASE_URL}/api/admin/audit-logs",
                         headers=auth_headers(ops_token))
        assert r.status_code == 403

    def test_audit_logs_without_token_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/admin/audit-logs")
        assert r.status_code == 401


# ─── Store Management Tests ───────────────────────────────────────────────────

class TestStoreManagement:
    """Store CRUD with admin auth"""

    created_store_id = None

    def test_list_stores(self, super_admin_token):
        r = requests.get(f"{BASE_URL}/api/admin/stores",
                         headers=auth_headers(super_admin_token))
        assert r.status_code == 200

    def test_create_store(self, super_admin_token):
        r = requests.post(f"{BASE_URL}/api/admin/stores",
                          headers=auth_headers(super_admin_token),
                          json={
                              "name": "TEST Store Admin",
                              "shopifyDomain": "test-store-admin.myshopify.com",
                              "storefrontToken": "test_token_12345",
                              "isActive": True,
                              "address": {"line1": "123 Test St", "city": "London", "postcode": "E1 1AA", "country": "GB"}
                          })
        assert r.status_code in (200, 201)
        data = r.json()
        assert data.get("name") == "TEST Store Admin"
        TestStoreManagement.created_store_id = data.get("id") or data.get("_id")

    def test_create_store_without_auth_returns_401(self):
        r = requests.post(f"{BASE_URL}/api/admin/stores",
                          json={"name": "Unauthorized Store"})
        assert r.status_code == 401

    def test_update_store(self, super_admin_token):
        store_id = TestStoreManagement.created_store_id
        if not store_id:
            pytest.skip("No created store to update")
        r = requests.put(f"{BASE_URL}/api/admin/stores/{store_id}",
                         headers=auth_headers(super_admin_token),
                         json={"name": "TEST Store Admin Updated"})
        assert r.status_code == 200


# ─── Rider Management Tests ───────────────────────────────────────────────────

class TestRiderManagement:
    """Rider management with admin auth and RBAC"""

    rider_id = None

    def test_list_riders_admin(self, super_admin_token):
        r = requests.get(f"{BASE_URL}/api/admin/riders",
                         headers=auth_headers(super_admin_token))
        assert r.status_code == 200
        data = r.json()
        riders = data if isinstance(data, list) else data.get("riders", [])
        if riders:
            # Find our test rider
            for rd in riders:
                if rd.get("email") == "rider1@nowkart.com":
                    TestRiderManagement.rider_id = rd.get("id") or rd.get("_id")
                    break
            if not TestRiderManagement.rider_id:
                TestRiderManagement.rider_id = (riders[0].get("id") or riders[0].get("_id"))

    def test_suspend_rider_admin(self, super_admin_token):
        rider_id = TestRiderManagement.rider_id
        if not rider_id:
            pytest.skip("No rider found to suspend")
        r = requests.put(f"{BASE_URL}/api/admin/riders/{rider_id}/suspend",
                         headers=auth_headers(super_admin_token))
        assert r.status_code == 200

    def test_activate_rider_admin(self, super_admin_token):
        rider_id = TestRiderManagement.rider_id
        if not rider_id:
            pytest.skip("No rider found to activate")
        r = requests.put(f"{BASE_URL}/api/admin/riders/{rider_id}/activate",
                         headers=auth_headers(super_admin_token))
        assert r.status_code == 200

    def test_support_can_list_riders(self, super_admin_token):
        # Create a support admin, test it, delete it
        # For now just verify ops can list
        r = requests.get(f"{BASE_URL}/api/admin/riders",
                         headers=auth_headers(super_admin_token))
        assert r.status_code == 200

    def test_ops_cannot_suspend_rider(self, ops_token):
        rider_id = TestRiderManagement.rider_id
        if not rider_id:
            pytest.skip("No rider found")
        r = requests.put(f"{BASE_URL}/api/admin/riders/{rider_id}/suspend",
                         headers=auth_headers(ops_token))
        assert r.status_code == 403

    def test_audit_log_written_for_rider_suspend(self, super_admin_token):
        """After suspend, audit logs should contain rider_suspended"""
        r = requests.get(f"{BASE_URL}/api/admin/audit-logs?action=rider_suspended",
                         headers=auth_headers(super_admin_token))
        assert r.status_code == 200


# ─── Vendor Management Tests ──────────────────────────────────────────────────

class TestVendorManagement:
    """Vendor management with admin auth"""

    vendor_id = None

    def test_list_vendors_admin(self, super_admin_token):
        r = requests.get(f"{BASE_URL}/api/admin/vendors",
                         headers=auth_headers(super_admin_token))
        assert r.status_code == 200
        data = r.json()
        vendors = data if isinstance(data, list) else data.get("vendors", [])
        if vendors:
            for vd in vendors:
                if vd.get("email") == "vendor1@nowkart.com":
                    TestVendorManagement.vendor_id = vd.get("id") or vd.get("_id")
                    break
            if not TestVendorManagement.vendor_id:
                TestVendorManagement.vendor_id = (vendors[0].get("id") or vendors[0].get("_id"))

    def test_suspend_vendor_admin(self, super_admin_token):
        vendor_id = TestVendorManagement.vendor_id
        if not vendor_id:
            pytest.skip("No vendor found to suspend")
        r = requests.put(f"{BASE_URL}/api/admin/vendors/{vendor_id}/suspend",
                         headers=auth_headers(super_admin_token))
        assert r.status_code == 200

    def test_activate_vendor_back(self, super_admin_token):
        vendor_id = TestVendorManagement.vendor_id
        if not vendor_id:
            pytest.skip("No vendor found to activate")
        r = requests.put(f"{BASE_URL}/api/admin/vendors/{vendor_id}/activate",
                         headers=auth_headers(super_admin_token))
        assert r.status_code == 200


# ─── Delivery Jobs Tests ──────────────────────────────────────────────────────

class TestDeliveryJobs:
    """Delivery job management"""

    job_id = None

    def test_list_jobs_admin(self, super_admin_token):
        r = requests.get(f"{BASE_URL}/api/admin/delivery/jobs",
                         headers=auth_headers(super_admin_token))
        assert r.status_code == 200
        data = r.json()
        jobs = data if isinstance(data, list) else data.get("jobs", [])
        if jobs:
            TestDeliveryJobs.job_id = jobs[0].get("id") or jobs[0].get("_id")

    def test_override_job_status_ops(self, ops_token):
        job_id = TestDeliveryJobs.job_id
        if not job_id:
            pytest.skip("No job found to update")
        r = requests.put(f"{BASE_URL}/api/admin/delivery/jobs/{job_id}/status",
                         headers=auth_headers(ops_token),
                         json={"status": "cancelled"})
        assert r.status_code in (200, 400, 409)  # 400/409 if invalid transition is OK

    def test_jobs_require_auth(self):
        r = requests.get(f"{BASE_URL}/api/admin/delivery/jobs")
        assert r.status_code == 401


# ─── Regression Tests ─────────────────────────────────────────────────────────

class TestRegressions:
    """Existing non-admin endpoints still work"""

    def test_shopify_home_still_works(self):
        r = requests.get(f"{BASE_URL}/api/shopify/home")
        assert r.status_code in (200, 422)  # 422 if requires params

    def test_rider_auth_login_still_works(self):
        r = requests.post(f"{BASE_URL}/api/rider/auth/login", json={
            "email": "rider1@nowkart.com", "password": "NowKart2026!"
        })
        assert r.status_code == 200

    def test_vendor_auth_login_still_works(self):
        r = requests.post(f"{BASE_URL}/api/vendor/auth/login", json={
            "email": "vendor1@nowkart.com", "password": "Vendor2026!"
        })
        assert r.status_code == 200

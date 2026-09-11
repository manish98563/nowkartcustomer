"""
Focused tests for PUT /api/admin/riders/{riderId}/set-password

Covers:
  1.  200 success — password updated, RiderAdminOut returned (no hash in body)
  2.  404 on non-existent riderId
  3.  401 unauthenticated (no Bearer token)
  4.  403 insufficient role (support cannot reset passwords)
  5.  Rider can log in with the new password after reset
  6.  Unrelated rider fields are unchanged after reset
  7.  Weak password (< 8 chars) rejected with 400
  8.  Audit log entry created for rider_password_reset action

Run with:
    LOCAL_BACKEND_URL=http://localhost:8099 pytest tests/test_rider_set_password.py -v
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get(
    "LOCAL_BACKEND_URL",
    os.environ.get("EXPO_PUBLIC_BACKEND_URL", "http://localhost:8099"),
).rstrip("/")

API = f"{BASE_URL}/api"

ADMIN_EMAIL    = "admin@nowkart.com"
ADMIN_PASSWORD = "Admin2026!"

# Support-level admin — created once, used for RBAC tests
_SUPPORT_EMAIL    = f"support_setpw_{uuid.uuid4().hex[:6]}@nowkart.com"
_SUPPORT_PASSWORD = "SupportPW2026!!"

# Unique rider so parallel runs don't collide
_RUN_ID        = str(uuid.uuid4())[:8]
RIDER_EMAIL    = f"setpw_rider_{_RUN_ID}@example.com"
RIDER_PHONE    = "+44700900100"
RIDER_INITIAL_PASSWORD = "InitialPass1!"
RIDER_NEW_PASSWORD     = "NewSecurePass99!"

BOGUS_RIDER_ID = "000000000000000000000001"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _admin_token() -> str:
    r = requests.post(
        f"{API}/admin/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    return r.json()["accessToken"]


def _support_token(admin_tok: str) -> str:
    """Create a support-level admin and return its token."""
    requests.post(
        f"{API}/admin/admins",
        json={
            "email":    _SUPPORT_EMAIL,
            "password": _SUPPORT_PASSWORD,
            "firstName": "Support",
            "lastName":  "SetPwTest",
            "role":      "support",
        },
        headers=_headers(admin_tok),
        timeout=15,
    )
    r = requests.post(
        f"{API}/admin/auth/login",
        json={"email": _SUPPORT_EMAIL, "password": _SUPPORT_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"Support login failed: {r.text}"
    return r.json()["accessToken"]


def _create_rider(admin_tok: str) -> dict:
    r = requests.post(
        f"{API}/admin/riders",
        json={
            "email":       RIDER_EMAIL,
            "phone":       RIDER_PHONE,
            "password":    RIDER_INITIAL_PASSWORD,
            "firstName":   "SetPw",
            "lastName":    "TestRider",
            "vehicleType": "bicycle",
        },
        headers=_headers(admin_tok),
        timeout=15,
    )
    assert r.status_code == 201, f"Rider create failed: {r.text}"
    return r.json()


def _delete_rider(admin_tok: str, rider_id: str) -> None:
    """Soft-delete the test rider in teardown."""
    requests.delete(
        f"{API}/admin/riders/{rider_id}",
        headers=_headers(admin_tok),
        timeout=15,
    )


# ─── Module-scoped shared state ───────────────────────────────────────────────

_state: dict = {
    "admin_token":   None,
    "support_token": None,
    "rider_id":      None,
}


@pytest.fixture(scope="module", autouse=True)
def setup_and_teardown():
    """Create test rider before all tests; soft-delete it after."""
    tok = _admin_token()
    _state["admin_token"]   = tok
    _state["support_token"] = _support_token(tok)

    rider = _create_rider(tok)
    _state["rider_id"] = rider["id"]

    yield

    _delete_rider(tok, _state["rider_id"])


# ═══════════════════════════════════════════════════════════════════════════════
# Test 1 — 200 success: password updated, RiderAdminOut returned
# ═══════════════════════════════════════════════════════════════════════════════

class TestSetPasswordSuccess:

    def test_200_returns_rider_admin_out(self):
        r = requests.put(
            f"{API}/admin/riders/{_state['rider_id']}/set-password",
            json={"password": RIDER_NEW_PASSWORD},
            headers=_headers(_state["admin_token"]),
            timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["id"] == _state["rider_id"]
        assert body["email"] == RIDER_EMAIL

    def test_response_never_contains_password_or_hash(self):
        r = requests.put(
            f"{API}/admin/riders/{_state['rider_id']}/set-password",
            json={"password": RIDER_NEW_PASSWORD},
            headers=_headers(_state["admin_token"]),
            timeout=15,
        )
        body_str = r.text
        assert "passwordHash" not in body_str, "passwordHash must never appear in response"
        assert RIDER_NEW_PASSWORD not in body_str, "Plaintext password must never appear in response"
        assert RIDER_INITIAL_PASSWORD not in body_str


# ═══════════════════════════════════════════════════════════════════════════════
# Test 2 — 404: non-existent riderId
# ═══════════════════════════════════════════════════════════════════════════════

class TestSetPasswordNotFound:

    def test_404_missing_rider(self):
        r = requests.put(
            f"{API}/admin/riders/{BOGUS_RIDER_ID}/set-password",
            json={"password": "SomePassword99!"},
            headers=_headers(_state["admin_token"]),
            timeout=15,
        )
        assert r.status_code == 404, r.text


# ═══════════════════════════════════════════════════════════════════════════════
# Test 3 — 401: unauthenticated request
# ═══════════════════════════════════════════════════════════════════════════════

class TestSetPasswordUnauthorized:

    def test_401_no_token(self):
        r = requests.put(
            f"{API}/admin/riders/{_state['rider_id']}/set-password",
            json={"password": "SomePassword99!"},
            timeout=15,
        )
        assert r.status_code == 401, r.text

    def test_401_garbage_token(self):
        r = requests.put(
            f"{API}/admin/riders/{_state['rider_id']}/set-password",
            json={"password": "SomePassword99!"},
            headers={"Authorization": "Bearer not_a_real_token"},
            timeout=15,
        )
        assert r.status_code == 401, r.text


# ═══════════════════════════════════════════════════════════════════════════════
# Test 4 — 403: insufficient role (support cannot reset passwords)
# ═══════════════════════════════════════════════════════════════════════════════

class TestSetPasswordForbidden:

    def test_403_support_role_rejected(self):
        r = requests.put(
            f"{API}/admin/riders/{_state['rider_id']}/set-password",
            json={"password": "SomePassword99!"},
            headers=_headers(_state["support_token"]),
            timeout=15,
        )
        assert r.status_code == 403, r.text


# ═══════════════════════════════════════════════════════════════════════════════
# Test 5 — Rider can log in with the new password after reset
# ═══════════════════════════════════════════════════════════════════════════════

class TestRiderLoginAfterReset:

    def test_rider_cannot_login_with_old_password(self):
        """Old password should no longer work after reset."""
        r = requests.post(
            f"{API}/rider/auth/login",
            json={"email": RIDER_EMAIL, "password": RIDER_INITIAL_PASSWORD},
            timeout=15,
        )
        # The new password was set in TestSetPasswordSuccess — old one is invalid now
        assert r.status_code == 401, (
            f"Expected 401 with old password, got {r.status_code}: {r.text}"
        )

    def test_rider_can_login_with_new_password(self):
        r = requests.post(
            f"{API}/rider/auth/login",
            json={"email": RIDER_EMAIL, "password": RIDER_NEW_PASSWORD},
            timeout=15,
        )
        assert r.status_code == 200, f"Rider login with new password failed: {r.text}"
        session = r.json()
        assert "accessToken" in session
        assert "refreshToken" in session
        assert session["rider"]["email"] == RIDER_EMAIL


# ═══════════════════════════════════════════════════════════════════════════════
# Test 6 — Unrelated rider fields are unchanged after password reset
# ═══════════════════════════════════════════════════════════════════════════════

class TestUnrelatedFieldsUnchanged:

    def test_unrelated_fields_preserved(self):
        r = requests.get(
            f"{API}/admin/riders/{_state['rider_id']}",
            headers=_headers(_state["admin_token"]),
            timeout=15,
        )
        assert r.status_code == 200
        rider = r.json()
        assert rider["email"]       == RIDER_EMAIL
        assert rider["phone"]       == RIDER_PHONE
        assert rider["firstName"]   == "SetPw"
        assert rider["lastName"]    == "TestRider"
        assert rider["vehicleType"] == "bicycle"
        assert rider["isActive"]    is True
        assert rider["isDeleted"]   is False


# ═══════════════════════════════════════════════════════════════════════════════
# Test 7 — Weak password rejected (< 8 characters)
# ═══════════════════════════════════════════════════════════════════════════════

class TestWeakPasswordRejected:

    def test_400_password_too_short(self):
        r = requests.put(
            f"{API}/admin/riders/{_state['rider_id']}/set-password",
            json={"password": "short"},
            headers=_headers(_state["admin_token"]),
            timeout=15,
        )
        assert r.status_code == 400, r.text


# ═══════════════════════════════════════════════════════════════════════════════
# Test 8 — Audit log records rider_password_reset (no password in details)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuditLogNoPassword:

    def test_audit_log_entry_created(self):
        """rider_password_reset action exists in audit logs for this rider."""
        r = requests.get(
            f"{API}/admin/audit-logs",
            params={"action": "rider_password_reset", "resourceType": "rider"},
            headers=_headers(_state["admin_token"]),
            timeout=15,
        )
        assert r.status_code == 200, r.text
        logs = r.json().get("logs", [])
        matching = [
            log for log in logs
            if log.get("resourceId") == _state["rider_id"]
        ]
        assert len(matching) > 0, "Expected at least one rider_password_reset audit log entry"

    def test_audit_log_details_contain_no_password(self):
        """Audit log details must never contain the password or hash."""
        r = requests.get(
            f"{API}/admin/audit-logs",
            params={"action": "rider_password_reset", "resourceType": "rider"},
            headers=_headers(_state["admin_token"]),
            timeout=15,
        )
        assert r.status_code == 200
        body_str = r.text
        assert RIDER_NEW_PASSWORD not in body_str, "Plaintext password must not appear in audit log"
        assert RIDER_INITIAL_PASSWORD not in body_str
        # hash prefix check — bcrypt hashes always start with '$2b$'
        assert "$2b$" not in body_str, "bcrypt hash must not appear in audit log response"

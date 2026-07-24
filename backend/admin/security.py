"""
Admin security primitives — password hashing, admin JWT, refresh token helpers.

IMPORTANT: Admin tokens carry the SPECIFIC admin role in the JWT (not a generic "admin").
  e.g., role="super_admin" | role="admin" | role="operations_manager" | role="support"

This is different from rider/vendor which have a single fixed role per actor type.
get_current_admin_required() accepts ANY token whose role is in ADMIN_ROLES.
RBAC enforcement (require_min_role) is done at the dependency level, not here.

Access token:  1 hour  (shorter than rider/vendor — admin sessions are more sensitive)
Refresh token: 8 hours (work shift — admin doesn't stay logged in for 30 days)
"""
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt

from .schemas import ADMIN_ROLES, ROLE_HIERARCHY

_JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]
_JWT_ALGORITHM  = os.environ.get("JWT_ALGORITHM", "HS256")

ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
    os.environ.get("ADMIN_JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60")
)
ADMIN_REFRESH_TOKEN_EXPIRE_HOURS: int = int(
    os.environ.get("ADMIN_REFRESH_TOKEN_EXPIRE_HOURS", "8")
)

_ctx = None

def _get_ctx():
    global _ctx
    if _ctx is None:
        from passlib.context import CryptContext
        _ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return _ctx


def hash_password(password: str) -> str:
    return _get_ctx().hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _get_ctx().verify(plain, hashed)


def create_admin_access_token(admin_id: str, role: str) -> str:
    """
    Create a signed JWT for an admin.
    The role claim holds the SPECIFIC admin role (e.g., "super_admin"),
    NOT a generic "admin" — this is different from rider/vendor.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub":  admin_id,
        "role": role,    # e.g. "super_admin", "admin", "operations_manager", "support"
        "type": "access",
        "iat":  now,
        "exp":  now + timedelta(minutes=ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, _JWT_SECRET_KEY, algorithm=_JWT_ALGORITHM)


def decode_admin_access_token(token: str) -> Optional[dict[str, Any]]:
    """
    Decode and validate an admin access token.
    Returns None if invalid, expired, or the role is not an admin role.
    Customer, rider, and vendor tokens are rejected because their role claims
    are not in ADMIN_ROLES.
    """
    try:
        payload = jwt.decode(token, _JWT_SECRET_KEY, algorithms=[_JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "access":
        return None
    if payload.get("role") not in ADMIN_ROLES:
        return None
    return payload


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def has_min_role(admin_role: str, required_role: str) -> bool:
    """True if admin_role meets or exceeds required_role in the hierarchy."""
    return ROLE_HIERARCHY.get(admin_role, 0) >= ROLE_HIERARCHY.get(required_role, 999)

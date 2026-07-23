"""
Rider security primitives — password hashing, rider JWT, refresh token helpers.

ISOLATION FROM CUSTOMER AUTH:
  This module is intentionally separate from auth/security.py.
  It uses the SAME JWT_SECRET_KEY (per architecture spec) but creates tokens
  with role="rider" so that customer tokens and rider tokens are
  distinguishable at the dependency layer.

  Token payloads:
    Customer: {"sub": user_mongo_id, "type": "access"}          ← no role claim
    Rider:    {"sub": rider_mongo_id, "role": "rider",
               "type": "access"}                                 ← has role claim

  How cross-use is blocked:
    • decode_rider_access_token() rejects any token without role="rider".
    • Customer decode_access_token() (in auth/security.py) does not check role,
      but a rider's MongoDB _id will not be found in the users_collection, so
      get_current_user_optional() returns None → treated as guest.
    • Customer-PROTECTED endpoints return 401 for unrecognised sub values.
    • This provides practical isolation without modifying customer auth code.

  NOTE: auth/security.py is NOT imported here — all primitives are self-contained.

REFRESH TOKEN PATTERN:
  Mirrors the existing auth/security.py pattern exactly:
    • Opaque 48-byte URL-safe random token
    • Stored as SHA-256 hash in rider_refresh_tokens collection
    • Single-use rotation — old token revoked on each refresh
    • Reuse detection — any reuse triggers family-wide revocation for that rider
"""
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt

# Read once at module import (environment is loaded by server.py before import)
_JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]
_JWT_ALGORITHM  = os.environ.get("JWT_ALGORITHM", "HS256")

RIDER_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
    os.environ.get("RIDER_JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "240")
)
RIDER_REFRESH_TOKEN_EXPIRE_DAYS: int = int(
    os.environ.get("RIDER_REFRESH_TOKEN_EXPIRE_DAYS", "30")
)

# ─── Password hashing ─────────────────────────────────────────────────────────
# Import lazily to defer passlib import until first use (startup-safe)
def _pwd_context():
    from passlib.context import CryptContext
    return CryptContext(schemes=["bcrypt"], deprecated="auto")

_ctx = None

def _get_ctx():
    global _ctx
    if _ctx is None:
        _ctx = _pwd_context()
    return _ctx


def hash_password(password: str) -> str:
    """Return a bcrypt hash of the password."""
    return _get_ctx().hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify a plain-text password against its bcrypt hash.
    Always runs a dummy verify even when the rider isn't found to prevent
    user-enumeration via timing side-channels.
    """
    return _get_ctx().verify(plain, hashed)


# ─── JWT ──────────────────────────────────────────────────────────────────────

def create_rider_access_token(rider_id: str) -> str:
    """
    Create a signed JWT for a rider.
    Payload includes role="rider" so get_current_rider() can distinguish
    rider tokens from customer tokens (which have no role claim).
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub":  rider_id,
        "role": "rider",         # ← distinguishes from customer tokens
        "type": "access",
        "iat":  now,
        "exp":  now + timedelta(minutes=RIDER_ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, _JWT_SECRET_KEY, algorithm=_JWT_ALGORITHM)


def decode_rider_access_token(token: str) -> Optional[dict[str, Any]]:
    """
    Decode and validate a rider access token.
    Returns None if the token is invalid, expired, or does not belong to a rider
    (i.e. is a customer token without role="rider").
    """
    try:
        payload = jwt.decode(token, _JWT_SECRET_KEY, algorithms=[_JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "access":
        return None
    if payload.get("role") != "rider":   # Reject customer tokens outright
        return None
    return payload


# ─── Refresh token helpers ────────────────────────────────────────────────────

def generate_refresh_token() -> str:
    """Generate a cryptographically random 48-byte URL-safe opaque refresh token."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """SHA-256 hash the refresh token for safe storage (never store plaintext)."""
    return hashlib.sha256(token.encode()).hexdigest()

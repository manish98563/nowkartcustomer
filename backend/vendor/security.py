"""
Vendor security primitives — password hashing, vendor JWT, refresh token helpers.

Identical pattern to rider/security.py with role="vendor".
Access token expiry: VENDOR_JWT_ACCESS_TOKEN_EXPIRE_MINUTES (default 480 = 8h shift).
Same JWT_SECRET_KEY as all other actors — role claim enforces isolation.
"""
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt

_JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]
_JWT_ALGORITHM  = os.environ.get("JWT_ALGORITHM", "HS256")

VENDOR_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
    os.environ.get("VENDOR_JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "480")
)
VENDOR_REFRESH_TOKEN_EXPIRE_DAYS: int = int(
    os.environ.get("VENDOR_REFRESH_TOKEN_EXPIRE_DAYS", "30")
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


def create_vendor_access_token(vendor_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub":  vendor_id,
        "role": "vendor",    # ← distinguishes from customer and rider tokens
        "type": "access",
        "iat":  now,
        "exp":  now + timedelta(minutes=VENDOR_ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, _JWT_SECRET_KEY, algorithm=_JWT_ALGORITHM)


def decode_vendor_access_token(token: str) -> Optional[dict[str, Any]]:
    """Returns payload if valid vendor token, None otherwise."""
    try:
        payload = jwt.decode(token, _JWT_SECRET_KEY, algorithms=[_JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "access":
        return None
    if payload.get("role") != "vendor":   # Reject customer and rider tokens
        return None
    return payload


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

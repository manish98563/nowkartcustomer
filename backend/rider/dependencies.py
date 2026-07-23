"""
Rider FastAPI dependency injection — authentication guards.

get_current_rider_required — use on any endpoint only riders should reach.
get_current_rider_optional — for endpoints that accept both riders and guests
                             (currently unused, provided for completeness).

SECURITY ARCHITECTURE:
  Same dependency pattern as auth/dependencies.py for customers.
  Both read the Authorization: Bearer header and decode the JWT.
  The distinction is enforced inside decode_rider_access_token() which
  rejects tokens without role="rider" — so a customer token on a rider
  endpoint returns 401.

  Additionally, suspended/soft-deleted riders (isActive=False or isDeleted=True)
  get HTTP 403 even with a valid token, preventing stale sessions from working
  after an admin suspension.
"""
from typing import Optional

from fastapi import Depends, Header, HTTPException

from . import security
from .service import get_rider_by_id


async def get_current_rider_optional(
    authorization: Optional[str] = Header(default=None),
) -> Optional[dict]:
    """
    Returns the authenticated rider document, or None for unauthenticated requests.
    Never raises — allows endpoints to handle guests gracefully if needed.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    payload = security.decode_rider_access_token(token)
    if not payload:
        return None
    return await get_rider_by_id(payload["sub"])


async def get_current_rider_required(
    rider: Optional[dict] = Depends(get_current_rider_optional),
) -> dict:
    """
    Returns the authenticated, active rider document.
    Raises 401 if the token is missing/invalid/expired.
    Raises 403 if the rider's account is suspended or soft-deleted.
    """
    if not rider:
        raise HTTPException(status_code=401, detail="Rider authentication required.")
    if rider.get("isDeleted", False):
        raise HTTPException(status_code=403, detail="This rider account has been removed.")
    if not rider.get("isActive", True):
        raise HTTPException(status_code=403, detail="This rider account is suspended.")
    return rider

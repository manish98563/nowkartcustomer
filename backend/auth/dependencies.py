from typing import Optional

from fastapi import Depends, Header, HTTPException

from . import security
from .service import get_user_by_id


async def get_current_user_optional(authorization: Optional[str] = Header(default=None)) -> Optional[dict]:
    """Returns the authenticated user dict, or None for guests. Never raises —
    used on endpoints that must work for both guests and logged-in customers
    (e.g. cart creation, so a guest's cart still works)."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    payload = security.decode_access_token(token)
    if not payload:
        return None
    return await get_user_by_id(payload["sub"])


async def get_current_user_required(user: Optional[dict] = Depends(get_current_user_optional)) -> dict:
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user

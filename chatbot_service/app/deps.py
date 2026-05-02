from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.core.auth import verify_token


def get_current_user(authorization: str = Header(...)) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must start with 'Bearer '",
        )
    token = authorization.removeprefix("Bearer ").strip()
    payload = verify_token(token)
    payload["_token"] = token
    return payload

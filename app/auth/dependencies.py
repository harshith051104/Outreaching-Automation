"""
FastAPI security dependencies for authentication.

Provides `get_current_user` which extracts and validates a JWT from the
Authorization header, returning the current user's data.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.jwt_handler import decode_token
from app.services.auth_service import get_user_by_id

bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """
    Extract the current authenticated user from the JWT token.

    Dependency to be used in FastAPI route handlers.

    Raises:
        HTTPException 401: If token is missing, invalid, or user not found.
    """
    try:
        payload = decode_token(credentials.credentials)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user = await get_user_by_id(user_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        HTTPBearer(auto_error=False)
    ),
) -> dict | None:
    """
    Extract the current user if a valid token is provided; return None otherwise.

    Useful for endpoints that behave differently for authenticated vs anonymous users.
    """
    if not credentials:
        return None

    try:
        payload = decode_token(credentials.credentials)
        user_id = payload.get("sub")
        if user_id:
            return await get_user_by_id(user_id)
    except Exception:
        pass

    return None


def require_role(*allowed_roles: str):
    """
    Dependency factory that enforces role-based access control.

    Usage::

        @router.get("/admin-only")
        async def admin_endpoint(user = Depends(require_role("admin"))):
            ...

        @router.get("/manager-or-admin")
        async def manager_endpoint(user = Depends(require_role("manager", "admin"))):
            ...
    """
    async def _check(current_user: dict = Depends(get_current_user)) -> dict:
        user_role = current_user.get("role", "member")
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Requires one of: {', '.join(allowed_roles)}. "
                       f"Your role: {user_role}.",
            )
        return current_user
    return _check


# Convenience shorthand dependencies
get_manager_user = require_role("manager", "admin")
get_admin_user = require_role("admin")
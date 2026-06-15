"""
Authentication API routes.

Provides register, login, and current-user endpoints.
"""

from fastapi import APIRouter, Depends, status

from app.auth.dependencies import get_current_user
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.auth_service import register_user, login_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(data: RegisterRequest):
    """
    Create a new user account.

    Returns the created user (without password hash).
    """
    return await register_user(data)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and get access token",
)
async def login(data: LoginRequest):
    """
    Authenticate with email and password.

    Returns a JWT access token on success.
    """
    result = await login_user(data)
    return TokenResponse(
        access_token=result["access_token"],
        token_type="bearer",
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
)
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    Return the currently authenticated user's profile.

    Requires a valid JWT in the Authorization header.
    """
    return UserResponse(**current_user)
"""
Authentication API routes.

Provides register, login, current-user, and user-listing endpoints.
"""

from fastapi import APIRouter, Depends, status

from app.auth.dependencies import get_current_user
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse, ForgotPasswordRequest, ResetPasswordRequest
from app.services.auth_service import register_user, login_user, request_password_reset, reset_user_password

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


@router.get(
    "/users",
    response_model=list,
    summary="List all registered users",
)
async def list_users(current_user: dict = Depends(get_current_user)):
    """
    Return all registered users (id, name, email, role, display_name).

    Used by Task Hub Assign-To dropdown and notification targeting.
    """
    from app.config.mongodb_config import get_database
    db = await get_database()
    cursor = db.users.find(
        {},
        {
            "_id": 0,
            "id": 1,
            "name": 1,
            "display_name": 1,
            "email": 1,
            "role": 1,
            "avatar_url": 1,
        },
    ).sort("name", 1)
    users = await cursor.to_list(length=200)
    return users


@router.post(
    "/forgot-password",
    summary="Request a password reset code",
)
async def forgot_password(data: ForgotPasswordRequest):
    """
    Generate a 6-digit verification code and save it.
    """
    return await request_password_reset(data)


@router.post(
    "/reset-password",
    summary="Reset password using verification code",
)
async def reset_password(data: ResetPasswordRequest):
    """
    Verify reset code and update user password.
    """
    return await reset_user_password(data)
"""
Authentication service layer.

Handles user registration, login, and user lookups.
All database operations are async via Motor.
"""

from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.config.mongodb_config import get_database
from app.schemas.auth import RegisterRequest, LoginRequest
from app.auth.password import hash_password, verify_password
from app.auth.jwt_handler import create_access_token
from app.utils.id_generator import generate_id


async def register_user(data: RegisterRequest) -> dict:
    """
    Register a new user.

    Checks for duplicate email, hashes password, inserts into DB,
    and returns the created user dict (without password).
    """
    db = await get_database()

    existing_user = await db.users.find_one({"email": data.email.lower()})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    now = datetime.now(timezone.utc)
    # Determine role: first registered user becomes admin; subsequent are members
    total_users = await db.users.count_documents({})
    role = "admin" if total_users == 0 else "member"

    display_name = getattr(data, "display_name", "") or data.name.strip()

    user_doc = {
        "id": generate_id(),
        "email": data.email.lower().strip(),
        "name": data.name.strip(),
        "display_name": display_name,
        "password_hash": hash_password(data.password),
        "is_active": True,
        "role": role,
        "created_at": now,
        "updated_at": now,
    }

    await db.users.insert_one(user_doc)

    return {
        "id": user_doc["id"],
        "email": user_doc["email"],
        "name": user_doc["name"],
        "display_name": user_doc["display_name"],
        "role": user_doc["role"],
        "is_active": user_doc["is_active"],
        "created_at": user_doc["created_at"],
    }


async def login_user(data: LoginRequest) -> dict:
    """
    Authenticate a user and return a JWT token response.

    Validates credentials and generates an access token.
    """
    db = await get_database()

    user = await db.users.find_one({"email": data.email.lower()})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not verify_password(data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )

    token = create_access_token(
        data={"sub": user["id"], "email": user["email"], "name": user["name"]}
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "display_name": user.get("display_name", user["name"]),
            "role": user.get("role", "member"),
        },
    }


async def get_user_by_id(user_id: str) -> dict:
    """Fetch a single user by their ID. Returns None if not found."""
    db = await get_database()
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    user.pop("_id", None)
    user.pop("password_hash", None)
    return user


async def get_user_by_email(email: str) -> dict:
    """Fetch a single user by email. Returns None if not found."""
    db = await get_database()
    user = await db.users.find_one({"email": email.lower()})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    user.pop("_id", None)
    user.pop("password_hash", None)
    return user
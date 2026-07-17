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


async def request_password_reset(data) -> dict:
    """Generate a password reset code for a user."""
    import random
    from datetime import datetime, timedelta, timezone
    import logging

    db = await get_database()
    email_clean = data.email.lower().strip()

    user = await db.users.find_one({"email": email_clean})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No user registered with this email address.",
        )

    code = f"{random.randint(100000, 999999)}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

    await db.password_resets.update_one(
        {"email": email_clean},
        {
            "$set": {
                "code": code,
                "expires_at": expires_at
            }
        },
        upsert=True
    )

    logger = logging.getLogger("app.services.auth_service")
    logger.info(f"PASSWORD RESET REQUEST for {email_clean}. Code: {code}")
    print(f"\n🔑 [AUTH SERVICE] PASSWORD RESET REQUEST for {email_clean}.\n   Code: {code}\n")

    return {"message": "Reset code generated successfully.", "code": code}


async def reset_user_password(data) -> dict:
    """Verify reset code and update user's password."""
    from datetime import datetime, timezone
    from app.auth.password import hash_password

    db = await get_database()
    email_clean = data.email.lower().strip()

    reset_entry = await db.password_resets.find_one({"email": email_clean})
    if not reset_entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No password reset request found for this email.",
        )

    now = datetime.now(timezone.utc)
    expires_at = reset_entry["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if now > expires_at:
        await db.password_resets.delete_one({"email": email_clean})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset code has expired. Please request a new one.",
        )

    if reset_entry["code"] != data.code.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset code.",
        )

    user = await db.users.find_one({"email": email_clean})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    await db.users.update_one(
        {"id": user["id"]},
        {
            "$set": {
                "password_hash": hash_password(data.new_password),
                "updated_at": now
            }
        }
    )

    await db.password_resets.delete_one({"email": email_clean})

    return {"message": "Password reset successful."}
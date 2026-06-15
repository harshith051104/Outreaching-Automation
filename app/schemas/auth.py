"""
Pydantic schemas for authentication endpoints (register, login, token).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """POST /api/auth/register request body."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(..., min_length=1, max_length=200)


class LoginRequest(BaseModel):
    """POST /api/auth/login request body."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Returned after successful login / register."""
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Public-facing representation of a user."""
    id: str
    email: str
    name: str
    is_active: bool
    created_at: datetime
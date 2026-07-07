"""
================================================
  Auth Schemas — login, user management
================================================
"""

from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    email: str
    role: str

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ── User Management Schemas ──

class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    role: str = "admin"  # default to admin


class UserListOut(BaseModel):
    id: int
    email: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}

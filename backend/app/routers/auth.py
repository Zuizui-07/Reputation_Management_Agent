"""
================================================
  Auth Router — POST /api/auth/login
================================================
"""

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import AsyncSessionLocal
from app.models.user import User
from app.auth import verify_password, create_access_token
from app.schemas.auth import LoginRequest, LoginResponse, UserOut
from app.services.log_activity import log_activity

router = APIRouter()

# Rate limiter — 5 login attempts per minute per IP
limiter = Limiter(key_func=get_remote_address)


@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest):
    """
    Authenticate admin user with email + password.
    Returns JWT access token on success.
    Rate limited to 5 attempts per minute per IP.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.email == body.email)
        )
        user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(data={"sub": user.email, "role": user.role})

    # Log the login
    await log_activity(user.email, "login", f"Logged in as {user.role}")

    return LoginResponse(
        access_token=token,
        user=UserOut(email=user.email, role=user.role),
    )

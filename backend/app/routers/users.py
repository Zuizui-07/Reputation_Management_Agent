"""
================================================
  Users Router — User management (superadmin only)
================================================
"""

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import select
from typing import List

from app.database import AsyncSessionLocal
from app.models.user import User
from app.auth import hash_password, require_superadmin
from app.schemas.auth import CreateUserRequest, UserListOut
from app.services.log_activity import log_activity

router = APIRouter()


@router.get("/", response_model=List[UserListOut])
async def list_users(admin: dict = Depends(require_superadmin)):
    """List all users. Superadmin only."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).order_by(User.created_at.desc())
        )
        users = result.scalars().all()
    return users


@router.post("/", response_model=UserListOut, status_code=status.HTTP_201_CREATED)
async def create_user(body: CreateUserRequest, admin: dict = Depends(require_superadmin)):
    """Create a new user. Superadmin only."""
    # Validate role
    if body.role not in ("superadmin", "admin"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be 'superadmin' or 'admin'",
        )

    # Check for duplicate email
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.email == body.email)
        )
        if result.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists",
            )

        new_user = User(
            email=body.email,
            password_hash=hash_password(body.password),
            role=body.role,
        )
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)

    await log_activity(admin["email"], "create_user", f"Created user {body.email} with role {body.role}")

    return new_user


@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
async def delete_user(user_id: int, admin: dict = Depends(require_superadmin)):
    """Delete a user by ID. Superadmin only. Cannot delete yourself."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # Prevent deleting yourself
        if user.email == admin["email"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot delete your own account",
            )

        await session.delete(user)
        await session.commit()

    await log_activity(admin["email"], "delete_user", f"Deleted user {user.email}")

    return {"status": "deleted", "email": user.email}

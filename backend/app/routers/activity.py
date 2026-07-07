"""
================================================
  Activity Router — View activity logs (superadmin only)
================================================
"""

import math
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.models.activity_log import ActivityLog
from app.auth import require_superadmin
from pydantic import BaseModel


# ── Schemas ──
class ActivityLogOut(BaseModel):
    id: int
    user_email: str
    action: str
    details: Optional[str] = None
    performed_at: datetime

    model_config = {"from_attributes": True}


class ActivityLogResponse(BaseModel):
    logs: List[ActivityLogOut]
    total: int
    page: int
    pages: int


router = APIRouter()


@router.get("/", response_model=ActivityLogResponse)
async def get_activity_logs(
    user: Optional[str] = Query(None, description="Filter by user email"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_superadmin),
):
    """
    Get paginated activity logs. Superadmin only.
    Filterable by user email and action type.
    """
    # Build base query
    query = select(ActivityLog)
    count_query = select(func.count(ActivityLog.id))

    if user:
        query = query.where(ActivityLog.user_email == user)
        count_query = count_query.where(ActivityLog.user_email == user)

    if action:
        query = query.where(ActivityLog.action == action)
        count_query = count_query.where(ActivityLog.action == action)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    offset = (page - 1) * limit
    query = query.order_by(desc(ActivityLog.performed_at)).offset(offset).limit(limit)

    result = await db.execute(query)
    logs = result.scalars().all()

    return ActivityLogResponse(
        logs=logs,
        total=total,
        page=page,
        pages=max(1, math.ceil(total / limit)),
    )


@router.get("/actions", response_model=List[str])
async def get_distinct_actions(
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_superadmin),
):
    """Get distinct action types for the filter dropdown."""
    result = await db.execute(
        select(ActivityLog.action).distinct().order_by(ActivityLog.action)
    )
    return [row[0] for row in result.all()]


@router.get("/users", response_model=List[str])
async def get_distinct_users(
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_superadmin),
):
    """Get distinct user emails for the filter dropdown."""
    result = await db.execute(
        select(ActivityLog.user_email).distinct().order_by(ActivityLog.user_email)
    )
    return [row[0] for row in result.all()]

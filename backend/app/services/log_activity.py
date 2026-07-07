"""
================================================
  Activity Logging Service — helper to log user actions
================================================
"""

import logging
from app.database import AsyncSessionLocal
from app.models.activity_log import ActivityLog

logger = logging.getLogger(__name__)


async def log_activity(user_email: str, action: str, details: str | None = None):
    """
    Log a user activity to the activity_logs table.
    This is fire-and-forget — errors are logged but don't break the caller.
    """
    try:
        async with AsyncSessionLocal() as session:
            entry = ActivityLog(
                user_email=user_email,
                action=action,
                details=details,
            )
            session.add(entry)
            await session.commit()
    except Exception as e:
        logger.error(f"Failed to log activity: {e}")

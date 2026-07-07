"""
================================================
  ActivityLog Model — System-wide audit trail
================================================
"""

import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database import Base


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_email = Column(String(255), nullable=False, index=True)
    action = Column(String(100), nullable=False, index=True)
    details = Column(Text, nullable=True)
    performed_at = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<ActivityLog id={self.id} user={self.user_email} action={self.action}>"

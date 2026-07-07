"""
================================================
  Action Model — Audit trail for every event
================================================
"""

import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


# ── Action type enum values ──
ACTION_TYPE_VALUES = (
    "received",
    "classified",
    "draft_generated",
    "auto_sent",
    "escalated",
    "approved",
    "rejected",
    "edited_and_approved",
)


class Action(Base):
    __tablename__ = "actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(
        Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_type = Column(
        SAEnum(*ACTION_TYPE_VALUES, name="action_type_enum"),
        nullable=False,
    )
    actor = Column(String(100), nullable=True)           # 'agent' or admin email
    final_reply = Column(Text, nullable=True)            # actual reply text that was sent
    performed_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

    # ── Relationship ──
    message = relationship("Message", back_populates="actions")

    def __repr__(self) -> str:
        return f"<Action id={self.id} type={self.action_type} actor={self.actor}>"

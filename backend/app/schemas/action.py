"""
================================================
  Action Schemas — audit log response
================================================
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ActionOut(BaseModel):
    id: int
    message_id: int
    action_type: str
    actor: Optional[str] = None
    final_reply: Optional[str] = None
    performed_at: datetime

    model_config = {"from_attributes": True}

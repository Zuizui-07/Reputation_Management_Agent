"""
================================================
  Message Schemas — request and response models
================================================
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class MessageOut(BaseModel):
    """Single pending message for admin review."""
    id: int
    platform: str
    sender_name: Optional[str] = None
    sender_id: str
    content: str
    intent: str
    confidence: float
    received_at: datetime
    drafted_reply: str

    model_config = {"from_attributes": True}


class AutoSentMessageOut(BaseModel):
    """Single auto-sent message for the log view."""
    id: int
    platform: str
    sender_name: Optional[str] = None
    sender_id: str
    content: str
    intent: str
    confidence: float
    sent_reply: str
    sent_at: datetime

    model_config = {"from_attributes": True}


class AutoSentListResponse(BaseModel):
    """Paginated list of auto-sent messages."""
    messages: List[AutoSentMessageOut]
    total: int
    page: int
    limit: int
    total_pages: int


class ApproveRequest(BaseModel):
    """Body for approve endpoint."""
    edited_reply: Optional[str] = None


class RejectRequest(BaseModel):
    """Body for reject endpoint."""
    reason: Optional[str] = None


class ApproveResponse(BaseModel):
    success: bool = True
    sent_at: datetime


class RejectResponse(BaseModel):
    success: bool = True


class RegenerateResponse(BaseModel):
    drafted_reply: str

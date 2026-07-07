"""
================================================
  Message Models — Message, Classification, DraftedReply
================================================
"""

import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime,
    Enum as SAEnum, ForeignKey,
)
from sqlalchemy.orm import relationship
from app.database import Base


# ── Intent enum values ──
INTENT_VALUES = (
    "potential_lead",
    "customer_support",
    "general_inquiry",
    "sensitive_complaint",
    "partnership_inquiry",
    "spam",
)


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(
        SAEnum("facebook", "instagram","google_reviews","reddit", name="platform_enum"),
        nullable=False,
    )
    platform_msg_id = Column(String(255), unique=True, nullable=False, index=True)
    sender_id = Column(String(255), nullable=False)
    sender_name = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    thread_id = Column(String(255), nullable=True)
    received_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

    # ── Relationships ──
    classification = relationship(
        "Classification", back_populates="message", uselist=False, lazy="selectin"
    )
    drafted_reply = relationship(
        "DraftedReply", back_populates="message", uselist=False, lazy="selectin"
    )
    actions = relationship(
        "Action", back_populates="message", lazy="selectin",
        order_by="Action.performed_at.desc()"
    )

    def __repr__(self) -> str:
        return f"<Message id={self.id} platform={self.platform} sender={self.sender_name}>"


class Classification(Base):
    __tablename__ = "classifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(
        Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    intent = Column(
        SAEnum(*INTENT_VALUES, name="intent_enum"),
        nullable=False,
    )
    confidence = Column(Float, nullable=False)
    raw_llm_response = Column(Text, nullable=True)
    classified_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

    # ── Relationship ──
    message = relationship("Message", back_populates="classification")

    def __repr__(self) -> str:
        return f"<Classification id={self.id} intent={self.intent} confidence={self.confidence}>"


class DraftedReply(Base):
    __tablename__ = "drafted_replies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(
        Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content = Column(Text, nullable=False)
    generated_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)
    model_used = Column(String(100), nullable=True)

    # ── Relationship ──
    message = relationship("Message", back_populates="drafted_reply")

    def __repr__(self) -> str:
        return f"<DraftedReply id={self.id} message_id={self.message_id}>"

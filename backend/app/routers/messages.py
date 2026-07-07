"""
================================================
  Messages Router — all message endpoints
  All routes require JWT authentication.
================================================
"""

import math
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.auth import get_current_user
from app.models.message import Message, Classification, DraftedReply
from app.models.action import Action
from app.schemas.message import (
    MessageOut, AutoSentMessageOut, AutoSentListResponse,
    ApproveRequest, ApproveResponse,
    RejectRequest, RejectResponse,
    RegenerateResponse,
)
from app.services import groq_agent
from app.services import facebook as fb_service
from app.services import instagram as ig_service
from app.services.log_activity import log_activity
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


# ──────────────────────────────────────────────
#  GET /pending — escalated messages for admin
# ──────────────────────────────────────────────
@router.get("/pending", response_model=list[MessageOut])
async def get_pending_messages(
    platform: str | None = Query(None, description="Filter by platform"),
    intent: str | None = Query(None, description="Filter by intent"),
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
):
    """
    Get messages that were escalated and are pending admin review.
    These are messages where the latest action is 'escalated'
    (not yet approved or rejected).
    """
    # ── Build query with eager loading ──
    query = (
        select(Message)
        .options(
            selectinload(Message.classification),
            selectinload(Message.drafted_reply),
            selectinload(Message.actions),
        )
    )

    # ── Platform filter ──
    if platform:
        query = query.where(Message.platform == platform)

    # ── Intent filter — join classification ──
    if intent:
        query = query.join(Classification).where(Classification.intent == intent)

    # ── Only fetch messages whose latest action is 'escalated' ──
    # Get IDs of messages already actioned (approved/rejected/sent)
    actioned_ids_subquery = (
        select(Action.message_id)
        .where(Action.action_type.in_(
            ["approved", "rejected", "edited_and_approved", "auto_sent"]
        ))
    )

    # Get IDs of escalated messages that haven't been actioned yet
    escalated_ids_subquery = (
        select(Action.message_id)
        .where(Action.action_type == "escalated")
        .where(Action.message_id.not_in(actioned_ids_subquery))
    )

    query = query.where(Message.id.in_(escalated_ids_subquery))

    # ── Execute (single execution) ──
    result = await db.execute(query)
    messages = result.scalars().unique().all()

    # ── Build response ──
    pending = []
    for msg in messages:
        pending.append(MessageOut(
            id=msg.id,
            platform=msg.platform,
            sender_name=msg.sender_name,
            sender_id=msg.sender_id,
            content=msg.content,
            intent=msg.classification.intent if msg.classification else "unknown",
            confidence=msg.classification.confidence if msg.classification else 0.0,
            received_at=msg.received_at,
            drafted_reply=msg.drafted_reply.content if msg.drafted_reply else "",
        ))

    # Sort by most recent first
    pending.sort(key=lambda m: m.received_at, reverse=True)
    return pending


# ──────────────────────────────────────────────
#  GET /auto-sent — auto-sent messages log
# ──────────────────────────────────────────────
@router.get("/auto-sent", response_model=AutoSentListResponse)
async def get_auto_sent_messages(
    platform: str | None = Query(None, description="Filter by platform"),
    intent: str | None = Query(None, description="Filter by intent"),
    search: str | None = Query(None, description="Search in message content"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
):
    """
    Get messages that were auto-sent by the agent.
    Paginated, filterable, and searchable.
    """
    # ── Build conditions ──
    conditions = [Action.action_type == "auto_sent"]

    if platform:
        conditions.append(Message.platform == platform)
    if intent:
        conditions.append(Classification.intent == intent)
    if search:
        conditions.append(Message.content.ilike(f"%{search}%"))

    # ── Build query ──
    query = select(Message).join(Action).where(and_(*conditions)).options(
        selectinload(Message.classification),
        selectinload(Message.drafted_reply),
        selectinload(Message.actions),
    )

    # Join Classification table if filtering by intent
    if intent:
        query = query.join(Classification, Message.id == Classification.message_id)

    # ── Count total ──
    count_query = (
        select(func.count(func.distinct(Message.id)))
        .select_from(Message)
        .join(Action)
        .where(and_(*conditions))
    )
    if intent:
        count_query = count_query.join(Classification, Message.id == Classification.message_id)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # ── Paginate ──
    offset = (page - 1) * limit
    query = query.order_by(Message.received_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    messages = result.scalars().unique().all()

    # ── Build response ──
    auto_sent_list = []
    for msg in messages:
        auto_action = next(
            (a for a in msg.actions if a.action_type == "auto_sent"), None
        )
        auto_sent_list.append(AutoSentMessageOut(
            id=msg.id,
            platform=msg.platform,
            sender_name=msg.sender_name,
            sender_id=msg.sender_id,
            content=msg.content,
            intent=msg.classification.intent if msg.classification else "unknown",
            confidence=msg.classification.confidence if msg.classification else 0.0,
            sent_reply=auto_action.final_reply if auto_action else "",
            sent_at=auto_action.performed_at if auto_action else msg.created_at,
        ))

    return AutoSentListResponse(
        messages=auto_sent_list,
        total=total,
        page=page,
        limit=limit,
        total_pages=math.ceil(total / limit) if total > 0 else 1,
    )


# ──────────────────────────────────────────────
#  POST /trigger-poll — debug endpoint (auth required)
# ──────────────────────────────────────────────
@router.post("/trigger-poll")
async def trigger_poll(
    background_tasks: BackgroundTasks,
    _user: str = Depends(get_current_user),
):
    """Manually trigger a polling cycle. Requires authentication."""
    from app.services.message_processor import run_polling_cycle
    background_tasks.add_task(run_polling_cycle)
    return {"status": "polling started"}


# ──────────────────────────────────────────────
#  POST /{id}/approve — approve & send reply
# ──────────────────────────────────────────────
@router.post("/{message_id}/approve", response_model=ApproveResponse)
async def approve_message(
    message_id: int,
    body: ApproveRequest,
    db: AsyncSession = Depends(get_db),
    user_email: str = Depends(get_current_user),
):
    """
    Approve a pending message and send the reply (original or edited).
    """
    msg = await db.get(Message, message_id, options=[
        selectinload(Message.actions),
        selectinload(Message.drafted_reply),
    ])

    if msg is None:
        raise HTTPException(status_code=404, detail="Message not found")

    # Check if already actioned
    latest = max(msg.actions, key=lambda a: a.performed_at) if msg.actions else None
    if latest and latest.action_type in ("approved", "rejected", "edited_and_approved", "auto_sent"):
        raise HTTPException(status_code=400, detail="Message already processed")

    # Determine reply text
    reply_text = body.edited_reply or (msg.drafted_reply.content if msg.drafted_reply else "")
    if not reply_text:
        raise HTTPException(status_code=400, detail="No reply text available")

    if not msg.sender_id:
        raise HTTPException(status_code=400, detail="Missing recipient ID")

    # Extra protection for Instagram
    if msg.platform == "instagram" and not msg.sender_id.isdigit():
        logger.error(f"Invalid Instagram sender_id: {msg.sender_id}")
        raise HTTPException(status_code=400, detail="Invalid Instagram recipient ID")
    # Send the reply via the appropriate platform
    send_fn = fb_service.send_message if msg.platform == "facebook" else ig_service.send_message
    try:
        success = await send_fn(msg.sender_id, reply_text)
        if not success:
            logger.error(
                f"Send failed. platform={msg.platform} sender_id={msg.sender_id} message_id{msg.id}" 
            )
            raise HTTPException(status_code=502, detail="Failed to send reply via platform API")

    except ValueError as e:
        logger.warning(
            f"Platform rejected message. sender_id={msg.sender_id} reason={str(e)}"
        )
        raise HTTPException(status_code=400, detail=str(e))
    # Determine action type
    action_type = "edited_and_approved" if body.edited_reply else "approved"

    # Log the action
    action = Action(
        message_id=msg.id,
        action_type=action_type,
        actor=user_email,
        final_reply=reply_text,
    )
    db.add(action)
    await db.commit()

    await log_activity(user_email, "approve_message", f"Approved message #{msg.id} from {msg.sender_name} ({msg.platform})")

    return ApproveResponse(sent_at=action.performed_at)


# ──────────────────────────────────────────────
#  POST /{id}/reject — reject without sending
# ──────────────────────────────────────────────
@router.post("/{message_id}/reject", response_model=RejectResponse)
async def reject_message(
    message_id: int,
    body: RejectRequest,
    db: AsyncSession = Depends(get_db),
    user_email: str = Depends(get_current_user),
):
    """
    Reject a pending message without sending any reply.
    """
    msg = await db.get(Message, message_id, options=[
        selectinload(Message.actions),
    ])

    if msg is None:
        raise HTTPException(status_code=404, detail="Message not found")

    # Check if already actioned
    latest = max(msg.actions, key=lambda a: a.performed_at) if msg.actions else None
    if latest and latest.action_type in ("approved", "rejected", "edited_and_approved", "auto_sent"):
        raise HTTPException(status_code=400, detail="Message already processed")

    action = Action(
        message_id=msg.id,
        action_type="rejected",
        actor=user_email,
        final_reply=body.reason,
    )
    db.add(action)
    await db.commit()

    await log_activity(user_email, "reject_message", f"Rejected message #{msg.id} from {msg.sender_name} ({msg.platform})")

    return RejectResponse()


# ──────────────────────────────────────────────
#  POST /{id}/regenerate — re-draft via Groq
# ──────────────────────────────────────────────
@router.post("/{message_id}/regenerate", response_model=RegenerateResponse)
async def regenerate_reply(
    message_id: int,
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
):
    """
    Re-generate the drafted reply for a pending message using Groq.
    """
    msg = await db.get(Message, message_id, options=[
        selectinload(Message.classification),
        selectinload(Message.drafted_reply),
    ])

    if msg is None:
        raise HTTPException(status_code=404, detail="Message not found")

    intent = msg.classification.intent if msg.classification else "general_inquiry"

    # Call Groq for a new draft
    try:
        new_reply = await groq_agent.draft_reply(
            content=msg.content,
            intent=intent,
            sender_name=msg.sender_name,
        )
    except Exception as e:
        logger.error(f"Regenerate failed for msg {message_id}: {e}")
        raise HTTPException(status_code=502, detail="Failed to generate new reply")

    # Update existing draft or create new one
    if msg.drafted_reply:
        msg.drafted_reply.content = new_reply
        msg.drafted_reply.generated_at = datetime.now(timezone.utc)
        msg.drafted_reply.model_used = settings.GROQ_MODEL
    else:
        db.add(DraftedReply(
            message_id=msg.id,
            content=new_reply,
            model_used=settings.GROQ_MODEL,
        ))

    await db.commit()

    await log_activity(_user, "regenerate_draft", f"Regenerated draft for message #{msg.id}")

    return RegenerateResponse(drafted_reply=new_reply)

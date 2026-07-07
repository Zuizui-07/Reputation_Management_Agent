"""
================================================
  Message Processor — orchestrates the full
  fetch → dedup → classify → draft → send/escalate pipeline
================================================
"""

import logging
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal
from app.models.message import Message, Classification, DraftedReply
from app.models.action import Action
from app.services import groq_agent
from app.services import facebook as fb_service
from app.services import instagram as ig_service
from app.services import google_reviews as google_service
from app.services import reddit as reddit_service
from app.config import settings

logger = logging.getLogger(__name__)

# Intents that should ALWAYS be escalated, regardless of confidence
ALWAYS_ESCALATE_INTENTS = {"sensitive_complaint", "partnership_inquiry"}


async def run_polling_cycle():
    """
    Main orchestrator — called by the scheduler every N minutes.

    Flow:
      1. Fetch messages from FB + IG + Google Reviews + Reddit
      2. Dedup against existing DB records
      3. For each new message: classify → draft reply → auto-send or escalate
      4. Log every action in the audit trail
    """
    logger.info("═══ Starting polling cycle ═══")

    # ── Step 1: Fetch raw messages from both platforms ──
    fb_messages = await fb_service.fetch_new_conversations()
    ig_messages = await ig_service.fetch_new_conversations()
    google_messages = await google_service.fetch_new_conversations()
    reddit_messages = await reddit_service.fetch_new_conversations()
    all_raw = fb_messages + ig_messages + google_messages + reddit_messages

    if not all_raw:
        logger.info("No new messages from any platform")
        return

    logger.info(f"Fetched {len(fb_messages)} FB + {len(ig_messages)} IG + {len(google_messages)} Google + {len(reddit_messages)} Reddit raw messages")
    # ── Step 2–4: process each message ──
    processed = 0
    errors = 0

    async with AsyncSessionLocal() as session:
        for raw in all_raw:
            try:
                await _process_single_message(session, raw)
                processed += 1
            except Exception as e:
                errors += 1
                logger.error(
                    f"Error processing message {raw.get('platform_msg_id')}: {e}",
                    exc_info=True,
                )

    logger.info(
        f"═══ Polling cycle complete: {processed} processed, {errors} errors ═══"
    )


async def _process_single_message(session: AsyncSession, raw: dict):
    """Process a single raw message through the full pipeline."""

    # ── Dedup check ──
    existing = await session.execute(
        select(Message).where(Message.platform_msg_id == raw["platform_msg_id"])
    )
    if existing.scalar_one_or_none() is not None:
        return  # Already in DB, skip silently

    # ── Save message to DB ──
    message = Message(
        platform=raw["platform"],
        platform_msg_id=raw["platform_msg_id"],
        sender_id=raw["sender_id"],
        sender_name=raw.get("sender_name"),
        content=raw["content"],
        thread_id=raw.get("thread_id"),
        received_at=raw["received_at"],
    )
    session.add(message)
    await session.flush()  # get message.id

    # Log: received
    session.add(Action(
        message_id=message.id,
        action_type="received",
        actor="agent",
    ))

    # ── Classify via Groq ──
    try:
        classification_result = await groq_agent.classify_message(raw["content"])
    except Exception as e:
        logger.error(f"Classification failed for msg {message.id}, escalating: {e}")
        # Don't rollback — keep the message in DB and escalate for manual review
        session.add(Action(
            message_id=message.id,
            action_type="escalated",
            actor="agent",
        ))
        await session.commit()
        return

    intent = classification_result["intent"]
    confidence = classification_result["confidence"]

    classification = Classification(
        message_id=message.id,
        intent=intent,
        confidence=confidence,
        raw_llm_response=str(classification_result),
    )
    session.add(classification)

    # Log: classified
    session.add(Action(
        message_id=message.id,
        action_type="classified",
        actor="agent",
    ))

    # ── Spam filter ──
    if intent == "spam":
        logger.info(f"Message {message.id} classified as spam, escalating for admin review")
        session.add(Action(
            message_id=message.id,
            action_type="escalated",
            actor="agent",
        ))
        await session.commit()
        return

    # ── Draft reply via Groq (with RAG context) ──
    rag_context = None
    try:
        from app.services.knowledge.retriever import retrieve_context
        rag_context = await retrieve_context(raw["content"])
        if rag_context:
            logger.info(f"RAG context retrieved for message {message.id}")
    except Exception as e:
        logger.warning(f"RAG retrieval failed for msg {message.id}, proceeding without context: {e}")

    try:
        reply_text = await groq_agent.draft_reply(
            content=raw["content"],
            intent=intent,
            sender_name=raw.get("sender_name"),
            rag_context=rag_context,
        )
    except Exception as e:
        logger.error(f"Draft failed for msg {message.id}, escalating: {e}")
        # Still escalate so admin can handle
        session.add(Action(
            message_id=message.id,
            action_type="escalated",
            actor="agent",
        ))
        await session.commit()
        return

    drafted = DraftedReply(
        message_id=message.id,
        content=reply_text,
        model_used=settings.GROQ_MODEL,
    )
    session.add(drafted)

    # Log: draft generated
    session.add(Action(
        message_id=message.id,
        action_type="draft_generated",
        actor="agent",
    ))

    # ── Decide: auto-send or escalate ──
    should_escalate = (
        intent in ALWAYS_ESCALATE_INTENTS
        or confidence < settings.AUTO_SEND_CONFIDENCE_THRESHOLD
    )

    if should_escalate:
        # Escalate to dashboard inbox for admin review
        session.add(Action(
            message_id=message.id,
            action_type="escalated",
            actor="agent",
        ))
        logger.info(
            f"Message {message.id} escalated (intent={intent}, confidence={confidence})"
        )
        await session.commit()
        return

    # ── Auto-send the reply ──
        # Fixed ✅
    if raw["platform"] == "facebook":
        success = await fb_service.send_message(raw["sender_id"], reply_text)
    elif raw["platform"] == "instagram":
        success = await ig_service.send_message(raw["sender_id"], reply_text)
    elif raw["platform"] == "google_reviews":
        # For google reviews, thread_id holds the full review path
        success = await google_service.send_message(raw["thread_id"], reply_text)
    elif raw["platform"] == "reddit":
        success = await reddit_service.send_message(raw["thread_id"], reply_text)
    else:
        logger.error(f"Unknown platform: {raw['platform']}")
        success = False

    if success:
        session.add(Action(
            message_id=message.id,
            action_type="auto_sent",
            actor="agent",
            final_reply=reply_text,
        ))
        logger.info(f"Message {message.id} auto-sent successfully")
    else:
        # Send failed → escalate to dashboard
        session.add(Action(
            message_id=message.id,
            action_type="escalated",
            actor="agent",
        ))
        logger.warning(f"Message {message.id} send failed, escalated to dashboard")

    await session.commit()

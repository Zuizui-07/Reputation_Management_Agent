"""
================================================
  Facebook Service — poll DMs and send replies
================================================
"""

import httpx
import logging
from datetime import datetime
from app.config import settings

logger = logging.getLogger(__name__)

GRAPH_URL = "https://graph.facebook.com/v18.0"
TIMEOUT = 30.0


async def fetch_new_conversations() -> list[dict]:
    """
    Fetches recent conversations from Facebook Page inbox.
    Returns list of normalized message dicts ready for DB insertion.
    """
    messages = []

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # Step 1: Get list of conversations
            resp = await client.get(
                f"{GRAPH_URL}/{settings.FB_PAGE_ID}/conversations",
                params={
                    "fields": "id,updated_time,participants",
                    "access_token": settings.FB_PAGE_ACCESS_TOKEN,
                    "limit": 25,
                },
            )
            resp.raise_for_status()
            conv_data = resp.json()
            conversations = conv_data.get("data", [])
            logger.info(f"[FB DEBUG] Conversations API returned {len(conversations)} conversations")
            logger.info(f"[FB DEBUG] Raw response keys: {list(conv_data.keys())}")

            for conv in conversations:
                try:
                    conv_id = conv.get("id", "unknown")
                    participants = conv.get("participants", {}).get("data", [])
                    participant_names = [p.get("name", "?") for p in participants]
                    logger.info(f"[FB DEBUG] Conv {conv_id} — participants: {participant_names}")

                    # Step 2: Get messages in each conversation
                    msg_resp = await client.get(
                        f"{GRAPH_URL}/{conv_id}/messages",
                        params={
                            "fields": "id,message,from,created_time",
                            "access_token": settings.FB_PAGE_ACCESS_TOKEN,
                            "limit": 5,
                        },
                    )
                    msg_resp.raise_for_status()
                    msg_data = msg_resp.json().get("data", [])
                    logger.info(f"[FB DEBUG] Conv {conv_id} has {len(msg_data)} messages")

                    for msg in msg_data:
                        from_id = msg.get("from", {}).get("id", "unknown")
                        from_name = msg.get("from", {}).get("name", "unknown")
                        content = msg.get("message", "")
                        logger.info(
                            f"[FB DEBUG]   msg_id={msg.get('id')} from={from_name}({from_id}) "
                            f"page_id={settings.FB_PAGE_ID} "
                            f"is_page={from_id == settings.FB_PAGE_ID} "
                            f"content_preview='{content[:50] if content else '(empty)'}'"
                        )

                        # Skip messages sent BY the page (only process inbound)
                        if from_id == settings.FB_PAGE_ID:
                            logger.info(f"[FB DEBUG]   → Skipped (sent by page)")
                            continue

                        # Skip messages without content
                        if not content:
                            logger.info(f"[FB DEBUG]   → Skipped (no content)")
                            continue

                        logger.info(f"[FB DEBUG]   → ✅ KEEPING this message!")
                        messages.append({
                            "platform": "facebook",
                            "platform_msg_id": msg["id"],
                            "sender_id": from_id,
                            "sender_name": from_name,
                            "content": content,
                            "thread_id": conv_id,
                            "received_at": datetime.fromisoformat(
                                msg["created_time"].replace("Z", "+00:00")
                            ),
                        })
                except Exception as e:
                    logger.warning(f"Error fetching messages for FB conversation {conv.get('id')}: {e}")
                    continue

    except httpx.HTTPStatusError as e:
        logger.error(f"Facebook API HTTP error: {e.response.status_code} — {e.response.text}")
    except httpx.RequestError as e:
        logger.error(f"Facebook API connection error: {e}")
    except Exception as e:
        logger.error(f"Facebook polling unexpected error: {e}")

    return messages


async def send_message(recipient_id: str, text: str) -> bool:
    """
    Send a reply DM to a Facebook user via the Send API.
    Returns True on success, False on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{GRAPH_URL}/me/messages",
                params={"access_token": settings.FB_PAGE_ACCESS_TOKEN},
                json={
                    "recipient": {"id": recipient_id},
                    "message": {"text": text},
                },
            )
            if resp.status_code == 200:
                logger.info(f"FB message sent to {recipient_id}")
                return True
            else:
                logger.error(f"FB send failed ({resp.status_code}): {resp.text}")
                return False
    except Exception as e:
        logger.error(f"FB send_message error: {e}")
        return False

"""
================================================
  Instagram Service — poll DMs and send replies
================================================
"""

import httpx
import logging
from datetime import datetime, timezone
from app.config import settings

logger = logging.getLogger(__name__)

GRAPH_URL = "https://graph.facebook.com/v18.0"
TIMEOUT = 30.0


async def fetch_new_conversations() -> list[dict]:
    """
    Fetches recent DMs from Instagram Business inbox via Graph API.
    Returns list of normalized message dicts ready for DB insertion.
    """
    messages = []

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # Instagram DMs use the Conversations API via the Facebook Page ID
            # with platform=instagram filter
            resp = await client.get(
                f"{GRAPH_URL}/{settings.FB_PAGE_ID}/conversations",
                params={
                    "platform": "instagram",
                    "fields": "id,updated_time,participants{id,username},messages{id,message,from,created_time}",
                    "access_token": settings.IG_PAGE_ACCESS_TOKEN,
                    "limit": 25,
                },
            )
            resp.raise_for_status()
            conversations = resp.json().get("data", [])

            for conv in conversations:
                conv_id = conv["id"]

                conv_details_resp = await client.get(
                    f"{GRAPH_URL}/{conv_id}",
                    params={
                        "fields": "participants{id,username}",
                        "access_token": settings.IG_PAGE_ACCESS_TOKEN,
                    },
                ) 

                conv_details_resp.raise_for_status()
                conv_details = conv_details_resp.json()

                participants = conv_details.get("participants", {}).get("data", [])
                logger.info(f"Conv {conv_id} participants → {participants}")
                try:
                    for msg in conv.get("messages", {}).get("data", []):
                        # Skip messages sent by our page/IG account
                        sender_id = msg.get("from", {}).get("id", "")
                        if sender_id == settings.IG_USER_ID:
                            continue

                        # Skip messages without content
                        if not msg.get("message"):
                            continue
                        logger.info(f"Raw IG created_time → {msg.get('created_time')}")

                        parsed_time = datetime.strptime(
                            msg["created_time"],
                            "%Y-%m-%dT%H:%M:%S%z"
                        ).astimezone(timezone.utc)
                        logger.info(f"Parsed IG time (UTC) → {parsed_time}")


                        igsid = None
                        for p in participants:
                            if p["id"] == settings.IG_USER_ID:
                                continue
                            if p["id"] == settings.FB_PAGE_ID:
                                continue
                            igsid = p["id"]
                            break

                        if not igsid:
                            logger.warning(
                                f"No valid IGSID found. conv={conv.get('id')} participants={participants} from={msg.get('from')}"
                            )
                            continue
                        parsed_time = datetime.strptime(
                            msg["created_time"],
                            "%Y-%m-%dT%H:%M:%S%z"
                        ).astimezone(timezone.utc)

                        logger.info(f"Parsed IG time (UTC) → {parsed_time}")
                        messages.append({
                            "platform": "instagram",
                            "platform_msg_id": msg["id"],
                            "sender_id": igsid,
                            "sender_name": (
                                msg["from"].get("name")
                                or msg["from"].get("username")
                            ),
                            "content": msg["message"],
                            "thread_id": conv["id"],
                            "received_at": parsed_time,
                        })
                except Exception as e:
                    logger.warning(f"Error processing IG conversation {conv.get('id')}: {e}")
                    continue

    except httpx.HTTPStatusError as e:
        logger.error(f"Instagram API HTTP error: {e.response.status_code} — {e.response.text}")
    except httpx.RequestError as e:
        logger.error(f"Instagram API connection error: {e}")
    except Exception as e:
        logger.error(f"Instagram polling unexpected error: {e}")

    return messages


async def send_message(recipient_id: str, text: str) -> bool:
    """
    Send a reply DM to an Instagram user via the Graph API.
    Returns True on success, False on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            logger.info(f"Sending IG DM → recipient_id={recipient_id}")
            resp = await client.post(
                f"{GRAPH_URL}/{settings.FB_PAGE_ID}/messages",
                params={"access_token": settings.IG_PAGE_ACCESS_TOKEN},
                json={
                    "recipient": {"id": recipient_id},
                    "message": {"text": text},
                    "messaging_type":"RESPONSE",
                },
            )
            # TO:
            if resp.status_code == 200:
                logger.info(f"IG message sent to {recipient_id}")
                return True
            else:
                error_data = resp.json().get("error", {})
                logger.error(f"Full IG error response → {resp.json()}")
                error_subcode = error_data.get("error_subcode")
                
                if error_subcode == 2534022:
                    logger.warning(f"IG message window expired for {recipient_id} — user must message first")
                    raise ValueError("Instagram 24-hour messaging window has expired. The user needs to send a new message before you can reply.")
                
                logger.error(f"IG send failed ({resp.status_code}): {resp.text}")
                return False
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"IG send_message error: {e}")
        return False

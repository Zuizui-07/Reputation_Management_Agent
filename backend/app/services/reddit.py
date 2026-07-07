"""
================================================
  Reddit Service — poll mentions/comments and send replies
  Uses PRAW (Python Reddit API Wrapper)
================================================
"""

import logging
import time
from datetime import datetime, timezone
from app.config import settings

logger = logging.getLogger(__name__)

REDDIT_POLL_INTERVAL = 900  # 15 minutes in seconds
_last_reddit_poll: float = 0
_reddit_instance = None


# ──────────────────────────────────────────────
#  Reddit Client
# ──────────────────────────────────────────────

def _get_reddit_client():
    """
    Returns a PRAW Reddit instance.
    Creates it once and reuses it (singleton pattern).
    """
    global _reddit_instance

    if _reddit_instance is not None:
        return _reddit_instance

    if not settings.REDDIT_CLIENT_ID or not settings.REDDIT_CLIENT_SECRET:
        logger.error("[REDDIT] Reddit credentials not configured in .env")
        return None

    try:
        import praw
        _reddit_instance = praw.Reddit(
            client_id=settings.REDDIT_CLIENT_ID,
            client_secret=settings.REDDIT_CLIENT_SECRET,
            username=settings.REDDIT_USERNAME,
            password=settings.REDDIT_PASSWORD,
            user_agent=f"reputation-agent-dev/1.0 by {settings.REDDIT_USERNAME}",
        )
        logger.info("[REDDIT] Reddit client initialized successfully")
        return _reddit_instance
    except Exception as e:
        logger.error(f"[REDDIT] Failed to initialize Reddit client: {e}")
        return None


# ──────────────────────────────────────────────
#  Fetch Mentions & DMs
# ──────────────────────────────────────────────

async def fetch_new_conversations() -> list[dict]:
    """
    Fetches Reddit mentions and DMs that need a reply.
    Returns list of normalized message dicts ready for DB insertion.
    """
    messages = []

    # Rate limiting — don't poll more than once every 15 minutes
    global _last_reddit_poll
    if time.time() - _last_reddit_poll < REDDIT_POLL_INTERVAL:
        return []
    _last_reddit_poll = time.time()

    if not settings.REDDIT_CLIENT_ID:
        logger.warning("[REDDIT] Reddit not configured — skipping")
        return []

    try:
        reddit = _get_reddit_client()
        if not reddit:
            return []

        # ── Fetch inbox mentions ──
        # This gets all mentions of your Reddit username
        logger.info("[REDDIT] Fetching inbox mentions...")

        for mention in reddit.inbox.mentions(limit=25):
            # Skip if already replied
            mention.refresh()
            already_replied = any(
                reply.author and reply.author.name == settings.REDDIT_USERNAME
                for reply in mention.replies
            )

            if already_replied:
                logger.info(f"[REDDIT DEBUG] Mention {mention.id} — already replied, skipping")
                continue

            # Build full content with context
            full_content = f"[Reddit Mention in r/{mention.subreddit}] {mention.body}"

            logger.info(f"[REDDIT DEBUG] Mention {mention.id} from u/{mention.author} → keeping ✅")

            messages.append({
                "platform": "reddit",
                "platform_msg_id": mention.id,
                "sender_id": str(mention.author),
                "sender_name": str(mention.author),
                "content": full_content,
                "thread_id": mention.id,        # used for sending reply
                "received_at": datetime.fromtimestamp(
                    mention.created_utc, tz=timezone.utc
                ),
            })

        # ── Fetch DMs ──
        logger.info("[REDDIT] Fetching DMs...")

        for message in reddit.inbox.messages(limit=25):
            # Skip sent messages
            if message.author and message.author.name == settings.REDDIT_USERNAME:
                continue

            # Skip already replied messages
            if message.replies:
                logger.info(f"[REDDIT DEBUG] DM {message.id} — already replied, skipping")
                continue

            full_content = f"[Reddit DM] {message.body}"

            logger.info(f"[REDDIT DEBUG] DM {message.id} from u/{message.author} → keeping ✅")

            messages.append({
                "platform": "reddit",
                "platform_msg_id": f"dm_{message.id}",
                "sender_id": str(message.author),
                "sender_name": str(message.author),
                "content": full_content,
                "thread_id": message.id,        # used for sending reply
                "received_at": datetime.fromtimestamp(
                    message.created_utc, tz=timezone.utc
                ),
            })

        logger.info(f"[REDDIT] Fetched {len(messages)} new items total")

    except Exception as e:
        logger.error(f"[REDDIT] Unexpected error: {e}", exc_info=True)

    return messages


# ──────────────────────────────────────────────
#  Send Reply
# ──────────────────────────────────────────────

async def send_message(thread_id: str, text: str) -> bool:
    """
    Reply to a Reddit mention or DM.
    thread_id is the Reddit comment/message ID stored in thread_id field.
    Returns True on success, False on failure.
    """
    try:
        reddit = _get_reddit_client()
        if not reddit:
            logger.error("[REDDIT] Cannot send reply — no Reddit client")
            return False

        # Check if it's a DM or a comment mention
        if thread_id.startswith("dm_"):
            # It's a DM — reply to the message
            actual_id = thread_id.replace("dm_", "")
            message = reddit.inbox.message(actual_id)
            message.reply(text)
            logger.info(f"[REDDIT] DM reply sent to message {actual_id}")
        else:
            # It's a mention/comment — reply to the comment
            comment = reddit.comment(id=thread_id)
            comment.reply(text)
            logger.info(f"[REDDIT] Comment reply sent to {thread_id}")

        return True

    except Exception as e:
        logger.error(f"[REDDIT] send_message error: {e}")
        return False
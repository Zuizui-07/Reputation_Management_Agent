"""
================================================
  Google Reviews Service — poll reviews and send replies
  Uses Google Business Profile API with OAuth 2.0
================================================
"""
import time
import httpx
import logging
import json
import os
from datetime import datetime, timezone
from app.config import settings

logger = logging.getLogger(__name__)

GBP_ACCOUNT_URL = "https://mybusinessaccountmanagement.googleapis.com/v1"
REVIEWS_URL = "https://mybusiness.googleapis.com/v4"
TOKEN_URL = "https://oauth2.googleapis.com/token"
TIMEOUT = 30.0
TOKEN_CACHE_FILE = "./data/google_token_cache.json"
_last_google_poll: float = 0
GOOGLE_POLL_INTERVAL = 900  # 15 minutes in seconds


# ──────────────────────────────────────────────
#  Token Management
# ──────────────────────────────────────────────

#check the saved token file for a valid token before making API calls. This avoids unnecessary token refreshes and reduces latency.
def _load_cached_token() -> dict | None:
    try:
        if os.path.exists(TOKEN_CACHE_FILE):
            with open(TOKEN_CACHE_FILE, "r") as f:
                token_data = json.load(f)
                # Check if the token is still valid
                if "token_expiry" in token_data and time.time() < token_data["token_expiry"]:
                    return token_data
    except Exception:
        pass
    return None


# Fixed ✅ — saves token WITH expiry time
def _save_cached_token(token_data: dict):
    try:
        os.makedirs(os.path.dirname(TOKEN_CACHE_FILE), exist_ok=True)

        # Calculate expiry timestamp
        # expires_in = 3600 (1 hour) — given by Google
        # we subtract 300 seconds (5 min buffer) to be safe
        expires_in = token_data.get("expires_in", 3600)
        token_data["token_expiry"] = time.time() + expires_in - 300

        with open(TOKEN_CACHE_FILE, "w") as f:
            json.dump(token_data, f)
        logger.info("[GOOGLE] Token cached with expiry timestamp")
    except Exception as e:
        logger.warning(f"Could not cache token: {e}")

#Calls Google's API saying "here's my refresh token, give me a fresh access token." Saves it and returns it.
async def _refresh_access_token() -> str | None:
    refresh_token = settings.GOOGLE_REFRESH_TOKEN
    if not refresh_token:
        logger.error("[GOOGLE] No refresh token configured — run OAuth setup first")
        return None

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(TOKEN_URL, data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            })
            resp.raise_for_status()
            token_data = resp.json()
            _save_cached_token(token_data)
            logger.info("[GOOGLE] Access token refreshed successfully")
            return token_data.get("access_token")
    except Exception as e:
        logger.error(f"[GOOGLE] Failed to refresh token: {e}")
        return None

async def _get_access_token() -> str | None:
    cached = _load_cached_token()
    if cached and cached.get("access_token"):
        logger.debug("[GOOGLE] Using cached access token")
        return cached["access_token"]
    # No valid cache — get fresh token
    logger.info("[GOOGLE] No valid cached token — refreshing")
    return await _refresh_access_token()

# ──────────────────────────────────────────────
#  Fetch Reviews
# ──────────────────────────────────────────────

async def fetch_new_conversations() -> list[dict]:
    """
    Fetches recent Google reviews that have no reply yet.
    Returns list of normalized message dicts ready for DB insertion.
    """
    messages = []

    global _last_google_poll
    if time.time() - _last_google_poll < GOOGLE_POLL_INTERVAL:
        return []
    _last_google_poll = time.time()
    try:
        token = await _get_access_token()
        if not token:
            logger.error("[GOOGLE] Cannot fetch reviews — no valid token")
            return messages

        # Fixed ✅ — just read from config
        account_name = settings.GOOGLE_ACCOUNT_NAME
        location_name = settings.GOOGLE_LOCATION_NAME

        if not account_name or not location_name:
            logger.error("[GOOGLE] GOOGLE_ACCOUNT_NAME or GOOGLE_LOCATION_NAME not set in .env")
            return messages

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                f"{REVIEWS_URL}/{location_name}/reviews",
                headers={"Authorization": f"Bearer {token}"},
                params={"pageSize": 20},
            )
            resp.raise_for_status()
            reviews = resp.json().get("reviews", [])
            logger.info(f"[GOOGLE DEBUG] Fetched {len(reviews)} reviews")

            for review in reviews:
                review_id = review.get("reviewId", "")
                reviewer = review.get("reviewer", {})
                reviewer_name = reviewer.get("displayName", "Anonymous")
                comment = review.get("comment", "")
                star_rating = review.get("starRating", "STAR_RATING_UNSPECIFIED")
                create_time = review.get("createTime", "")
                reply = review.get("reviewReply")

                logger.info(
                    f"[GOOGLE DEBUG] Review {review_id} from {reviewer_name} "
                    f"rating={star_rating} has_reply={reply is not None} "
                    f"preview='{comment[:50] if comment else '(no comment)'}'"
                )

                # Skip reviews that already have a reply
                if reply is not None:
                    logger.info(f"[GOOGLE DEBUG]   → Skipped (already replied)")
                    continue

                # Skip reviews without comments
                if not comment:
                    logger.info(f"[GOOGLE DEBUG]   → Skipped (no comment)")
                    continue

                star_map = {
                    "ONE": "⭐ (1/5)",
                    "TWO": "⭐⭐ (2/5)",
                    "THREE": "⭐⭐⭐ (3/5)",
                    "FOUR": "⭐⭐⭐⭐ (4/5)",
                    "FIVE": "⭐⭐⭐⭐⭐ (5/5)",
                }
                stars = star_map.get(star_rating, star_rating)
                full_content = f"[Google Review {stars}] {comment}"

                logger.info(f"[GOOGLE DEBUG]   → ✅ KEEPING this review!")
                # Fixed ✅
                full_review_name = f"{location_name}/reviews/{review_id}"
                # full path like "accounts/123/locations/456/reviews/ABC123"
                # this is what send_message() needs to reply correctly

                messages.append({
                    "platform": "google_reviews",
                    "platform_msg_id": review_id,         # short ID — used for dedup check
                    "sender_id": reviewer_name,
                    "sender_name": reviewer_name,
                    "content": full_content,
                    "thread_id": full_review_name,         # full path — used for sending reply
                    "received_at": datetime.fromisoformat(
                        create_time.replace("Z", "+00:00")
                    ) if create_time else datetime.now(timezone.utc),
                })

    except httpx.HTTPStatusError as e:
        logger.error(f"[GOOGLE] HTTP error: {e.response.status_code} — {e.response.text}")
    except httpx.RequestError as e:
        logger.error(f"[GOOGLE] Connection error: {e}")
    except Exception as e:
        logger.error(f"[GOOGLE] Unexpected error: {e}", exc_info=True)

    return messages


# ──────────────────────────────────────────────
#  Send Reply
# ──────────────────────────────────────────────

async def send_message(review_name: str, text: str) -> bool:
    """
    Reply to a Google Review.
    review_name is the full path e.g. 'accounts/123/locations/456/reviews/789'
    Returns True on success, False on failure.
    """
    try:
        token = await _get_access_token()
        if not token:
            logger.error("[GOOGLE] Cannot send reply — no valid token")
            return False

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.put(
                f"{REVIEWS_URL}/{review_name}/reply",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={"comment": text},
            )
            if resp.status_code in (200, 201):
                logger.info(f"[GOOGLE] Reply sent to review {review_name}")
                return True
            else:
                logger.error(f"[GOOGLE] Reply failed ({resp.status_code}): {resp.text}")
                return False

    except Exception as e:
        logger.error(f"[GOOGLE] send_message error: {e}")
        return False
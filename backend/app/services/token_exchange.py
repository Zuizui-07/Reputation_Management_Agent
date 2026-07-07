"""
================================================
  Token Exchange — Convert short-lived tokens
  to never-expiring Page Access Tokens
================================================

Flow:
  1. Short-lived user token (1 hour)  →  Long-lived user token (60 days)
  2. Long-lived user token            →  Never-expiring Page Access Token

The page token obtained from a long-lived user token does NOT expire.
"""

import logging
import httpx
from pathlib import Path
from app.config import settings

logger = logging.getLogger(__name__)

GRAPH_URL = "https://graph.facebook.com/v18.0"
ENV_PATH = Path(__file__).resolve().parent.parent.parent.parent / ".env"


async def exchange_for_long_lived_token(short_lived_token: str) -> dict:
    """
    Exchange a short-lived user token for a long-lived user token (60 days),
    then get a never-expiring Page Access Token from it.
    Returns {user_token, page_token, expires_in, page_name}.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        # Step 1: Exchange for long-lived user token
        logger.info("Step 1: Exchanging short-lived token for long-lived user token...")
        r1 = await client.get(f"{GRAPH_URL}/oauth/access_token", params={
            "grant_type": "fb_exchange_token",
            "client_id": settings.APP_ID,
            "client_secret": settings.APP_SECRET,
            "fb_exchange_token": short_lived_token,
        })

        if r1.status_code != 200:
            error = r1.json().get("error", {})
            raise ValueError(f"Token exchange failed: {error.get('message', r1.text)}")

        data1 = r1.json()
        long_lived_user_token = data1["access_token"]
        expires_in = data1.get("expires_in", 5184000)  # ~60 days
        logger.info(f"Got long-lived user token (expires in {expires_in // 86400} days)")

        # Step 2: Get page access token (never expires when from long-lived user token)
        logger.info(f"Step 2: Getting page token for page {settings.FB_PAGE_ID}...")
        r2 = await client.get(f"{GRAPH_URL}/{settings.FB_PAGE_ID}", params={
            "fields": "access_token,name",
            "access_token": long_lived_user_token,
        })

        if r2.status_code != 200:
            error = r2.json().get("error", {})
            raise ValueError(f"Page token request failed: {error.get('message', r2.text)}")

        data2 = r2.json()
        page_token = data2["access_token"]
        page_name = data2.get("name", "Unknown")
        logger.info(f"Got never-expiring page token for '{page_name}'")

        # Step 3: Verify the page token works
        r3 = await client.get(f"{GRAPH_URL}/debug_token", params={
            "input_token": page_token,
            "access_token": f"{settings.APP_ID}|{settings.APP_SECRET}",
        })

        token_info = {}
        if r3.status_code == 200:
            debug_data = r3.json().get("data", {})
            token_info = {
                "is_valid": debug_data.get("is_valid", False),
                "expires_at": debug_data.get("expires_at", 0),  # 0 = never expires
                "scopes": debug_data.get("scopes", []),
            }
            if token_info["expires_at"] == 0:
                logger.info("✅ Token NEVER expires!")
            else:
                logger.info(f"Token expires at: {token_info['expires_at']}")

        return {
            "long_lived_user_token": long_lived_user_token,
            "page_token": page_token,
            "page_name": page_name,
            "expires_in_days": expires_in // 86400,
            "token_info": token_info,
        }


def update_env_token(new_token: str):
    """
    Update FB_PAGE_ACCESS_TOKEN and IG_PAGE_ACCESS_TOKEN in the .env file
    with the new never-expiring page token.
    """
    if not ENV_PATH.exists():
        raise FileNotFoundError(f".env file not found at {ENV_PATH}")

    content = ENV_PATH.read_text()

    # Replace both tokens
    lines = content.splitlines()
    updated_lines = []
    for line in lines:
        if line.startswith("FB_PAGE_ACCESS_TOKEN="):
            updated_lines.append(f"FB_PAGE_ACCESS_TOKEN={new_token}")
        elif line.startswith("IG_PAGE_ACCESS_TOKEN="):
            updated_lines.append(f"IG_PAGE_ACCESS_TOKEN={new_token}")
        else:
            updated_lines.append(line)

    ENV_PATH.write_text("\n".join(updated_lines) + "\n")
    logger.info(f"Updated .env with new token")

    # Also update runtime settings
    settings.FB_PAGE_ACCESS_TOKEN = new_token
    settings.IG_PAGE_ACCESS_TOKEN = new_token
    logger.info("Runtime settings updated — no restart needed")

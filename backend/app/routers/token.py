"""
================================================
  Token Router — Token management endpoints
================================================
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from app.auth import require_superadmin
from app.services.token_exchange import exchange_for_long_lived_token, update_env_token
from app.services.log_activity import log_activity


router = APIRouter()


class TokenExchangeRequest(BaseModel):
    short_lived_token: str


class TokenExchangeResponse(BaseModel):
    success: bool
    page_name: str
    never_expires: bool
    message: str
    scopes: list = []


@router.post("/exchange", response_model=TokenExchangeResponse)
async def exchange_token(
    body: TokenExchangeRequest,
    admin: dict = Depends(require_superadmin),
):
    """
    Exchange a short-lived user token for a never-expiring Page Access Token.
    Updates .env and runtime settings automatically. Superadmin only.

    Steps:
    1. Go to Graph API Explorer (developers.facebook.com/tools/explorer)
    2. Select your app, request user_token with permissions
    3. Copy the short-lived token
    4. Paste it here — this endpoint will exchange it for a permanent page token
    """
    try:
        result = await exchange_for_long_lived_token(body.short_lived_token)

        # Update .env and runtime settings
        update_env_token(result["page_token"])

        never_expires = result["token_info"].get("expires_at", 0) == 0
        scopes = result["token_info"].get("scopes", [])

        await log_activity(
            admin["email"],
            "token_exchange",
            f"Exchanged token for page '{result['page_name']}' — {'never expires' if never_expires else 'long-lived'}",
        )

        page_name = result["page_name"]
        expire_msg = "Never expires!" if never_expires else f"Expires in {result['expires_in_days']} days."

        return TokenExchangeResponse(
            success=True,
            page_name=page_name,
            never_expires=never_expires,
            message=f"Token updated for '{page_name}'. {expire_msg}",
            scopes=scopes,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Token exchange failed: {str(e)}")

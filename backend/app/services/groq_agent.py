"""
================================================
  Groq Agent Service — classify and draft replies
================================================
"""

import httpx
import json
import logging
from app.config import settings

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
TIMEOUT = 30.0


# ── Classification System Prompt ──
CLASSIFY_SYSTEM_PROMPT = """
You are a message classification agent for Auxilo Finserve, an education loan NBFC in India.
Auxilo provides education loans for studying in India and abroad (collateral and non-collateral).

Classify the incoming social media DM into EXACTLY one of these intents:
- potential_lead: Person interested in applying for or learning about education loans
- customer_support: Existing customer with a query, complaint, or follow-up on their loan
- general_inquiry: General questions about Auxilo, eligibility, process, not yet a lead
- sensitive_complaint: Angry customer, legal threat, RBI complaint mention, PR risk
- partnership_inquiry: B2B, institutional, or partnership interest
- spam: Irrelevant, promotional, bot-like, or garbage message

Also provide a confidence score between 0.0 and 1.0.

Respond ONLY with valid JSON in this exact format:
{
  "intent": "<intent_label>",
  "confidence": <float between 0.0 and 1.0>,
  "reason": "<one sentence explanation>"
}
""".strip()


# ── Draft Reply System Prompt ──
DRAFT_SYSTEM_PROMPT = """
You are a professional social media manager for Auxilo Finserve, an education loan NBFC in India.
Auxilo provides collateral and non-collateral education loans for India and abroad studies.
Website: auxilo.com | Interest rates start from 10.5% p.a.

{rag_context}

Draft a warm, helpful, professional reply to the following DM.
The intent of this message is: {intent}

Rules:
- Be warm but professional. Use the sender's first name if available.
- Keep replies concise (max 4-5 sentences for simple queries, slightly longer for complex ones)
- For potential_lead: acknowledge their interest, give brief info, invite them to apply or request a callback
- For customer_support: empathize, ask for their loan account number or registered mobile to assist further
- For general_inquiry: answer helpfully and point them to auxilo.com or suggest a callback
- For sensitive_complaint: be empathetic, apologize, assure them a senior will follow up within 24 hours
- For partnership_inquiry: express interest, ask them to email partnerships@auxilo.com
- If company knowledge is provided above, use it to give specific and accurate information
- Do NOT include hashtags, emojis (unless natural), or marketing language
- Do NOT promise specific interest rates or loan amounts unless confirmed in the company knowledge
- Do NOT make up information not found in the company knowledge
- End with a clear next step for the user

Reply in plain text only. No JSON, no formatting, no subject lines.
""".strip()


# ── Valid intents for validation ──
VALID_INTENTS = {
    "potential_lead",
    "customer_support",
    "general_inquiry",
    "sensitive_complaint",
    "partnership_inquiry",
    "spam",
}


async def classify_message(content: str) -> dict:
    """
    Classify a message using Groq LLM.
    Returns dict: { intent: str, confidence: float, reason: str }
    Raises on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": CLASSIFY_SYSTEM_PROMPT},
                        {"role": "user", "content": f"Message: {content}"},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 200,
                },
            )
            response.raise_for_status()

        result = response.json()
        text = result["choices"][0]["message"]["content"].strip()

        # Parse JSON — handle potential markdown code blocks
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove opening fence line (```json or ```)
            if lines[0].strip().startswith("```"):
                lines = lines[1:]
            # Remove closing fence line (```)
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        parsed = json.loads(text)

        # Validate the response structure
        intent = parsed.get("intent", "general_inquiry")
        confidence = parsed.get("confidence", 0.5)

        # Ensure intent is valid
        if intent not in VALID_INTENTS:
            logger.warning(f"Invalid intent '{intent}' from Groq, defaulting to general_inquiry")
            intent = "general_inquiry"

        # Clamp confidence
        confidence = max(0.0, min(1.0, float(confidence)))

        return {
            "intent": intent,
            "confidence": confidence,
            "reason": parsed.get("reason", ""),
        }

    except json.JSONDecodeError as e:
        logger.error(f"Groq classification JSON parse error: {e}")
        raise ValueError(f"Failed to parse Groq classification response: {e}")
    except httpx.HTTPStatusError as e:
        logger.error(f"Groq API error ({e.response.status_code}): {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"Groq classification error: {e}")
        raise


async def draft_reply(
    content: str,
    intent: str,
    sender_name: str = None,
    rag_context: str = None,
) -> str:
    """
    Draft a reply using Groq LLM, optionally augmented with RAG context.
    Returns plain text reply string.
    Raises on failure.
    """
    user_prompt = f"Sender name: {sender_name or 'Unknown'}\nMessage: {content}"

    # Inject RAG context into system prompt
    from app.services.knowledge.retriever import format_rag_context_for_prompt
    rag_section = format_rag_context_for_prompt(rag_context) if rag_context else ""
    system_prompt = DRAFT_SYSTEM_PROMPT.replace("{intent}", intent).replace("{rag_context}", rag_section)

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 400,
                },
            )
            response.raise_for_status()

        result = response.json()
        reply = result["choices"][0]["message"]["content"].strip()

        if not reply:
            raise ValueError("Groq returned empty reply")

        logger.info(f"Draft reply generated (RAG context: {'yes' if rag_context else 'no'})")
        return reply

    except httpx.HTTPStatusError as e:
        logger.error(f"Groq draft API error ({e.response.status_code}): {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"Groq draft reply error: {e}")
        raise

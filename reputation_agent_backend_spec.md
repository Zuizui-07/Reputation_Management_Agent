# Reputation Management Agent — Backend Specification
> Use this document as a complete prompt to build the backend directly.

---

## Project Overview

Build a **FastAPI backend** for Auxilo Finserve's Reputation Management Agent. The system polls Facebook and Instagram for new DMs every 15 minutes, classifies each message using Groq LLM, drafts a reply, then either auto-sends it (high confidence) or holds it in a MySQL database for superadmin approval via the dashboard.

---

## Tech Stack

| Component | Choice |
|---|---|
| Framework | FastAPI (Python 3.11+) |
| Task Scheduling | APScheduler (AsyncIOScheduler) |
| Database ORM | SQLAlchemy 2.0 (async) |
| Database | MySQL 8.0+ |
| LLM | Groq API (`llama-3.3-70b-versatile`) |
| Social Media | Meta Graph API (Facebook + Instagram) |
| Auth | JWT (python-jose + passlib) |
| HTTP Client | httpx (async) |
| Env Config | python-dotenv |
| Migrations | Alembic |
| Password Hash | bcrypt |

---

## Project Folder Structure

```
backend/
├── main.py                  ← FastAPI app entry point, scheduler startup
├── .env                     ← Environment variables (never commit)
├── .env.example             ← Template with all keys (commit this)
├── requirements.txt
├── alembic.ini
├── alembic/
│   └── versions/            ← Migration files
├── app/
│   ├── __init__.py
│   ├── config.py            ← Load and validate all env vars
│   ├── database.py          ← SQLAlchemy async engine + session
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── message.py       ← Message, Classification, DraftedReply models
│   │   ├── action.py        ← Action audit log model
│   │   └── user.py          ← Admin user model
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── message.py       ← Pydantic request/response schemas
│   │   ├── auth.py          ← Login request/response schemas
│   │   └── action.py        ← Action schemas
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py          ← POST /api/auth/login
│   │   └── messages.py      ← All message endpoints
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── facebook.py      ← Poll FB DMs + send FB reply
│   │   ├── instagram.py     ← Poll IG DMs + send IG reply
│   │   ├── groq_agent.py    ← Classify + draft reply via Groq
│   │   └── message_processor.py ← Orchestrates poll → classify → save/send
│   │
│   ├── scheduler.py         ← APScheduler setup + polling job
│   └── auth.py              ← JWT creation + verification dependency
```

---

## Environment Variables (`.env`)

```env
# ── App ──
APP_ENV=development
SECRET_KEY=your_random_64_char_secret_key_here
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# ── Database ──
DATABASE_URL=mysql+aiomysql://root:password@localhost:3306/reputation_agent_db

# ── Meta / Facebook ──
FB_APP_ID=your_facebook_app_id
FB_APP_SECRET=your_facebook_app_secret
FB_PAGE_ID=your_page_id
FB_PAGE_ACCESS_TOKEN=your_page_access_token

# ── Meta / Instagram ──
IG_USER_ID=your_instagram_user_id
IG_PAGE_ACCESS_TOKEN=your_instagram_page_access_token

# ── Groq ──
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=llama-3.3-70b-versatile

# ── Agent Config ──
AUTO_SEND_CONFIDENCE_THRESHOLD=0.85
POLLING_INTERVAL_MINUTES=15

# ── Admin User (created on first run) ──
ADMIN_EMAIL=superadmin@auxilo.com
ADMIN_PASSWORD=changeme123
```

---

## Database Schema (MySQL)

### Table: `users`
```sql
CREATE TABLE users (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  email         VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role          ENUM('superadmin') DEFAULT 'superadmin',
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Table: `messages`
```sql
CREATE TABLE messages (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  platform        ENUM('facebook', 'instagram') NOT NULL,
  platform_msg_id VARCHAR(255) UNIQUE NOT NULL,   -- Meta's message ID (dedup key)
  sender_id       VARCHAR(255) NOT NULL,           -- Platform-scoped user ID
  sender_name     VARCHAR(255),
  content         TEXT NOT NULL,
  thread_id       VARCHAR(255),
  received_at     DATETIME NOT NULL,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Table: `classifications`
```sql
CREATE TABLE classifications (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  message_id      INT NOT NULL REFERENCES messages(id),
  intent          ENUM('potential_lead','customer_support','general_inquiry',
                       'sensitive_complaint','partnership_inquiry','spam') NOT NULL,
  confidence      FLOAT NOT NULL,                  -- 0.0 to 1.0
  raw_llm_response TEXT,                           -- Full Groq response for debugging
  classified_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Table: `drafted_replies`
```sql
CREATE TABLE drafted_replies (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  message_id      INT NOT NULL REFERENCES messages(id),
  content         TEXT NOT NULL,
  generated_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  model_used      VARCHAR(100)                     -- e.g. llama-3.3-70b-versatile
);
```

### Table: `actions`
```sql
CREATE TABLE actions (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  message_id      INT NOT NULL REFERENCES messages(id),
  action_type     ENUM('received','classified','draft_generated',
                       'auto_sent','escalated','approved','rejected',
                       'edited_and_approved') NOT NULL,
  actor           VARCHAR(100),                    -- 'agent' or admin email
  final_reply     TEXT,                            -- actual reply text that was sent
  performed_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

> **Deduplication rule**: Before inserting any message, check if `platform_msg_id` already exists in the `messages` table. If it does, skip it. This prevents duplicate processing across polling cycles.

---

## SQLAlchemy Models (`app/models/`)

### `message.py`
```python
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.database import Base
import datetime

class Message(Base):
    __tablename__ = "messages"
    id              = Column(Integer, primary_key=True, index=True)
    platform        = Column(SAEnum('facebook','instagram'), nullable=False)
    platform_msg_id = Column(String(255), unique=True, nullable=False)
    sender_id       = Column(String(255), nullable=False)
    sender_name     = Column(String(255))
    content         = Column(Text, nullable=False)
    thread_id       = Column(String(255))
    received_at     = Column(DateTime, nullable=False)
    created_at      = Column(DateTime, default=datetime.datetime.utcnow)

    classification  = relationship("Classification", back_populates="message", uselist=False)
    drafted_reply   = relationship("DraftedReply", back_populates="message", uselist=False)
    actions         = relationship("Action", back_populates="message")


class Classification(Base):
    __tablename__ = "classifications"
    id              = Column(Integer, primary_key=True)
    message_id      = Column(Integer, ForeignKey("messages.id"), nullable=False)
    intent          = Column(SAEnum('potential_lead','customer_support','general_inquiry',
                                    'sensitive_complaint','partnership_inquiry','spam'))
    confidence      = Column(Float, nullable=False)
    raw_llm_response = Column(Text)
    classified_at   = Column(DateTime, default=datetime.datetime.utcnow)

    message         = relationship("Message", back_populates="classification")


class DraftedReply(Base):
    __tablename__ = "drafted_replies"
    id              = Column(Integer, primary_key=True)
    message_id      = Column(Integer, ForeignKey("messages.id"), nullable=False)
    content         = Column(Text, nullable=False)
    generated_at    = Column(DateTime, default=datetime.datetime.utcnow)
    model_used      = Column(String(100))

    message         = relationship("Message", back_populates="drafted_reply")
```

---

## Pydantic Schemas (`app/schemas/message.py`)

```python
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class MessageOut(BaseModel):
    id:            int
    platform:      str
    sender_name:   Optional[str]
    sender_id:     str
    content:       str
    intent:        str
    confidence:    float
    received_at:   datetime
    drafted_reply: str

    class Config:
        from_attributes = True


class AutoSentMessageOut(BaseModel):
    id:           int
    platform:     str
    sender_name:  Optional[str]
    content:      str
    intent:       str
    confidence:   float
    sent_reply:   str
    sent_at:      datetime

    class Config:
        from_attributes = True


class ApproveRequest(BaseModel):
    edited_reply: Optional[str] = None   # if admin edited the reply before approving


class RejectRequest(BaseModel):
    reason: Optional[str] = None
```

---

## Groq Agent Service (`app/services/groq_agent.py`)

This is the brain of the system. Two functions: classify and draft.

### Classification Prompt
```python
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
"""
```

### Draft Reply Prompt
```python
DRAFT_SYSTEM_PROMPT = """
You are a professional social media manager for Auxilo Finserve, an education loan NBFC in India.
Auxilo provides collateral and non-collateral education loans for India and abroad studies.
Website: auxilo.com | Interest rates start from 10.5% p.a.

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
- Do NOT include hashtags, emojis (unless natural), or marketing language
- Do NOT promise specific interest rates or loan amounts
- End with a clear next step for the user

Reply in plain text only. No JSON, no formatting, no subject lines.
"""
```

### Implementation
```python
import httpx
import json
from app.config import settings

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

async def classify_message(content: str) -> dict:
    """Returns { intent, confidence, reason }"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": settings.GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": CLASSIFY_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Message: {content}"}
                ],
                "temperature": 0.1,       # Low temp for consistent classification
                "max_tokens": 200
            },
            timeout=30.0
        )
    result = response.json()
    text = result["choices"][0]["message"]["content"]
    return json.loads(text)   # Parse JSON response


async def draft_reply(content: str, intent: str, sender_name: str = None) -> str:
    """Returns plain text drafted reply string"""
    user_prompt = f"Sender name: {sender_name or 'Unknown'}\nMessage: {content}"
    system = DRAFT_SYSTEM_PROMPT.replace("{intent}", intent)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": settings.GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.7,       # Higher temp for natural-sounding replies
                "max_tokens": 400
            },
            timeout=30.0
        )
    result = response.json()
    return result["choices"][0]["message"]["content"].strip()
```

---

## Facebook Polling Service (`app/services/facebook.py`)

```python
import httpx
from datetime import datetime
from app.config import settings

GRAPH_URL = "https://graph.facebook.com/v18.0"

async def fetch_new_conversations() -> list[dict]:
    """
    Fetches recent conversations from Facebook Page inbox.
    Returns list of normalized message dicts.
    """
    async with httpx.AsyncClient() as client:
        # Step 1: Get list of conversations
        resp = await client.get(
            f"{GRAPH_URL}/{settings.FB_PAGE_ID}/conversations",
            params={
                "fields": "id,updated_time,participants",
                "access_token": settings.FB_PAGE_ACCESS_TOKEN,
                "limit": 25
            }
        )
        conversations = resp.json().get("data", [])

        messages = []
        for conv in conversations:
            # Step 2: Get messages in each conversation
            msg_resp = await client.get(
                f"{GRAPH_URL}/{conv['id']}/messages",
                params={
                    "fields": "id,message,from,created_time",
                    "access_token": settings.FB_PAGE_ACCESS_TOKEN,
                    "limit": 5
                }
            )
            for msg in msg_resp.json().get("data", []):
                # Skip messages sent BY the page (only process inbound)
                if msg["from"]["id"] == settings.FB_PAGE_ID:
                    continue
                messages.append({
                    "platform": "facebook",
                    "platform_msg_id": msg["id"],
                    "sender_id": msg["from"]["id"],
                    "sender_name": msg["from"].get("name"),
                    "content": msg["message"],
                    "thread_id": conv["id"],
                    "received_at": datetime.fromisoformat(
                        msg["created_time"].replace("Z", "+00:00")
                    )
                })
    return messages


async def send_message(recipient_id: str, text: str) -> bool:
    """Send a reply DM to a Facebook user. Returns True on success."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GRAPH_URL}/me/messages",
            params={"access_token": settings.FB_PAGE_ACCESS_TOKEN},
            json={
                "recipient": {"id": recipient_id},
                "message": {"text": text}
            }
        )
    return resp.status_code == 200
```

---

## Instagram Polling Service (`app/services/instagram.py`)

```python
import httpx
from datetime import datetime
from app.config import settings

GRAPH_URL = "https://graph.facebook.com/v18.0"

async def fetch_new_conversations() -> list[dict]:
    """
    Fetches recent DMs from Instagram Business inbox.
    Returns list of normalized message dicts.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GRAPH_URL}/{settings.IG_USER_ID}/conversations",
            params={
                "platform": "instagram",
                "fields": "id,updated_time,participants,messages{id,message,from,created_time}",
                "access_token": settings.IG_PAGE_ACCESS_TOKEN,
                "limit": 25
            }
        )
        conversations = resp.json().get("data", [])

        messages = []
        for conv in conversations:
            for msg in conv.get("messages", {}).get("data", []):
                if msg["from"]["id"] == settings.IG_USER_ID:
                    continue
                messages.append({
                    "platform": "instagram",
                    "platform_msg_id": msg["id"],
                    "sender_id": msg["from"]["id"],
                    "sender_name": msg["from"].get("name") or msg["from"].get("username"),
                    "content": msg["message"],
                    "thread_id": conv["id"],
                    "received_at": datetime.fromisoformat(
                        msg["created_time"].replace("Z", "+00:00")
                    )
                })
    return messages


async def send_message(recipient_id: str, text: str) -> bool:
    """Send a reply DM to an Instagram user. Returns True on success."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GRAPH_URL}/{settings.IG_USER_ID}/messages",
            params={"access_token": settings.IG_PAGE_ACCESS_TOKEN},
            json={
                "recipient": {"id": recipient_id},
                "message": {"text": text}
            }
        )
    return resp.status_code == 200
```

---

## Message Processor (`app/services/message_processor.py`)

This is the orchestrator — called by the scheduler every polling cycle.

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.message import Message, Classification, DraftedReply
from app.models.action import Action
from app.services import facebook, instagram, groq_agent
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Intents that should NEVER be auto-sent regardless of confidence
ALWAYS_ESCALATE_INTENTS = {"sensitive_complaint", "partnership_inquiry"}

# Intents that should be silently ignored (no reply drafted)
IGNORE_INTENTS = {"spam"}


async def run_polling_cycle(db: AsyncSession):
    """
    Full polling cycle:
    1. Fetch new messages from FB + IG
    2. Deduplicate against DB
    3. Classify each message
    4. Draft reply
    5. Auto-send if confidence >= threshold, else save for approval
    """
    logger.info("Starting polling cycle...")

    # Fetch from both platforms
    fb_messages  = await facebook.fetch_new_conversations()
    ig_messages  = await instagram.fetch_new_conversations()
    all_messages = fb_messages + ig_messages

    logger.info(f"Fetched {len(all_messages)} messages (FB: {len(fb_messages)}, IG: {len(ig_messages)})")

    for msg_data in all_messages:
        await process_single_message(db, msg_data)

    logger.info("Polling cycle complete.")


async def process_single_message(db: AsyncSession, msg_data: dict):
    # ── Step 1: Deduplication ──
    existing = await db.execute(
        select(Message).where(Message.platform_msg_id == msg_data["platform_msg_id"])
    )
    if existing.scalar_one_or_none():
        return   # Already processed, skip

    # ── Step 2: Save message ──
    message = Message(**msg_data)
    db.add(message)
    await db.flush()   # Get message.id without full commit

    await _log_action(db, message.id, "received", actor="agent")

    # ── Step 3: Classify ──
    try:
        classification_result = await groq_agent.classify_message(message.content)
    except Exception as e:
        logger.error(f"Classification failed for msg {message.platform_msg_id}: {e}")
        await db.rollback()
        return

    classification = Classification(
        message_id=message.id,
        intent=classification_result["intent"],
        confidence=classification_result["confidence"],
        raw_llm_response=str(classification_result)
    )
    db.add(classification)
    await _log_action(db, message.id, "classified", actor="agent")

    # ── Step 4: Skip spam ──
    if classification_result["intent"] in IGNORE_INTENTS:
        await db.commit()
        logger.info(f"Ignored spam message {message.platform_msg_id}")
        return

    # ── Step 5: Draft reply ──
    try:
        reply_text = await groq_agent.draft_reply(
            content=message.content,
            intent=classification_result["intent"],
            sender_name=message.sender_name
        )
    except Exception as e:
        logger.error(f"Draft generation failed for msg {message.platform_msg_id}: {e}")
        await db.rollback()
        return

    drafted = DraftedReply(
        message_id=message.id,
        content=reply_text,
        model_used=settings.GROQ_MODEL
    )
    db.add(drafted)
    await _log_action(db, message.id, "draft_generated", actor="agent")

    # ── Step 6: Auto-send or escalate ──
    confidence   = classification_result["confidence"]
    intent       = classification_result["intent"]
    should_escalate = (
        intent in ALWAYS_ESCALATE_INTENTS or
        confidence < settings.AUTO_SEND_CONFIDENCE_THRESHOLD
    )

    if should_escalate:
        await _log_action(db, message.id, "escalated", actor="agent")
        logger.info(f"Escalated message {message.platform_msg_id} (intent={intent}, confidence={confidence:.2f})")
    else:
        # Auto-send
        platform_service = facebook if message.platform == "facebook" else instagram
        success = await platform_service.send_message(message.sender_id, reply_text)

        if success:
            await _log_action(db, message.id, "auto_sent", actor="agent", final_reply=reply_text)
            logger.info(f"Auto-sent reply for {message.platform_msg_id}")
        else:
            # If send fails, escalate instead
            await _log_action(db, message.id, "escalated", actor="agent")
            logger.warning(f"Auto-send failed, escalated {message.platform_msg_id}")

    await db.commit()


async def _log_action(db, message_id, action_type, actor, final_reply=None):
    action = Action(
        message_id=message_id,
        action_type=action_type,
        actor=actor,
        final_reply=final_reply
    )
    db.add(action)
```

---

## Scheduler (`app/scheduler.py`)

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import AsyncSessionLocal
from app.services.message_processor import run_polling_cycle
from app.config import settings
import logging

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def polling_job():
    async with AsyncSessionLocal() as db:
        try:
            await run_polling_cycle(db)
        except Exception as e:
            logger.error(f"Polling job error: {e}")


def start_scheduler():
    scheduler.add_job(
        polling_job,
        trigger="interval",
        minutes=settings.POLLING_INTERVAL_MINUTES,
        id="dm_polling",
        replace_existing=True
    )
    scheduler.start()
    logger.info(f"Scheduler started — polling every {settings.POLLING_INTERVAL_MINUTES} mins")
```

---

## API Routers

### Auth Router (`app/routers/auth.py`)

```
POST /api/auth/login
  Body:    { email: string, password: string }
  Returns: { access_token: string, token_type: "bearer", user: { email, role } }
  Errors:  401 if invalid credentials
```

Implementation: verify email + bcrypt password against `users` table, return signed JWT.

---

### Messages Router (`app/routers/messages.py`)

All routes require `Authorization: Bearer <token>` header.

```
GET /api/messages/pending
  Returns: List[MessageOut]
  Logic:   SELECT messages that have a drafted_reply but whose latest action
           is 'escalated' (not yet approved/rejected/auto_sent)
  Query params: platform (optional), intent (optional)

GET /api/messages/auto-sent
  Returns: List[AutoSentMessageOut]
  Logic:   SELECT messages whose latest action is 'auto_sent'
  Query params: platform, intent, date_from, date_to, search (content LIKE)
  Pagination: ?page=1&limit=20

POST /api/messages/{id}/approve
  Body:    ApproveRequest { edited_reply?: string }
  Logic:
    1. Load message + drafted_reply
    2. Use edited_reply if provided, else drafted_reply.content
    3. Call platform send_message(sender_id, reply_text)
    4. Log action as 'approved' or 'edited_and_approved'
  Returns: { success: true, sent_at: datetime }
  Errors:  404 if not found, 400 if already actioned

POST /api/messages/{id}/reject
  Body:    RejectRequest { reason?: string }
  Logic:   Log action as 'rejected' with reason in actor field
  Returns: { success: true }

POST /api/messages/{id}/regenerate
  Logic:
    1. Load message + classification
    2. Call groq_agent.draft_reply() again
    3. Update drafted_replies record with new content
  Returns: { drafted_reply: string }
```

---

## Auth System (`app/auth.py`)

```python
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({**data, "exp": expire}, settings.SECRET_KEY, algorithm="HS256")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=["HS256"])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
        return email
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
```

---

## Main Entry Point (`main.py`)

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, messages
from app.scheduler import start_scheduler
from app.database import engine, Base
from app.models import message, action, user   # import all models for Alembic
import logging

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Reputation Manager API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,     prefix="/api/auth",     tags=["Auth"])
app.include_router(messages.router, prefix="/api/messages", tags=["Messages"])


@app.on_event("startup")
async def startup():
    # Create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Seed superadmin on first run
    await seed_admin()
    # Start polling scheduler
    start_scheduler()


@app.get("/health")
async def health():
    return {"status": "ok"}
```

---

## Requirements (`requirements.txt`)

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
sqlalchemy[asyncio]==2.0.30
aiomysql==0.2.0
alembic==1.13.1
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
httpx==0.27.0
python-dotenv==1.0.1
apscheduler==3.10.4
pydantic-settings==2.2.1
```

---

## Decision Logic Summary

```
New DM arrives
      │
      ▼
Already in DB? ──YES──► Skip (dedup)
      │
      NO
      │
      ▼
Save to messages table
      │
      ▼
Groq: Classify intent + confidence
      │
      ▼
Intent = spam? ──YES──► Log + ignore (no reply)
      │
      NO
      │
      ▼
Draft reply via Groq
      │
      ▼
Intent in [sensitive_complaint, partnership_inquiry]?
OR confidence < 0.85?
      │
     YES ──► Save to DB as 'escalated' ──► Appears in Dashboard Inbox
      │
      NO
      │
      ▼
Call Meta API to send reply
      │
      ▼
Success? ──NO──► Escalate to dashboard
      │
     YES
      │
      ▼
Log as 'auto_sent' ──► Appears in Auto-sent Log
```

---

## Error Handling Rules

| Scenario | Behavior |
|---|---|
| Groq API timeout/error | Log error, skip message, retry next polling cycle |
| Meta send API failure | Escalate to dashboard instead of auto-send |
| DB connection error | Log + alert, scheduler retries next cycle |
| Duplicate message_id | Silently skip (deduplication) |
| Invalid JWT on API | Return 401, frontend redirects to login |
| Message already actioned | Return 400 "Message already processed" |

---

## Prompt to Use for Development

Copy and paste this entire document with this instruction:

> "Build this FastAPI backend exactly as specified in this document. Create all files in the folder structure defined. Use async SQLAlchemy with MySQL via aiomysql. Implement all routes, services, models, and the APScheduler polling job exactly as described. The Groq API is used for classification and reply drafting with the exact prompts provided. Include proper error handling, logging, and JWT auth on all message routes. Make it production-quality and fully functional."

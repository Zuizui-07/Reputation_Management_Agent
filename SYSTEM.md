# Reputation Management Agent — System Documentation

> **Auxilo Finserve** — AI-powered social media reputation management platform that automatically monitors, classifies, and responds to Facebook & Instagram DMs using Groq LLM.

---

## Table of Contents

- [System Overview](#system-overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Environment Variables](#environment-variables)
- [Database Schema](#database-schema)
- [Backend — API Reference](#backend--api-reference)
- [Backend — Core Services](#backend--core-services)
- [Frontend — Pages & Components](#frontend--pages--components)
- [Message Processing Pipeline](#message-processing-pipeline)
- [Authentication & Security](#authentication--security)
- [Scheduler & Polling](#scheduler--polling)
- [How to Run](#how-to-run)
- [Admin Credentials](#admin-credentials)

---

## System Overview

The Reputation Management Agent is an end-to-end platform that:

1. **Polls** Facebook and Instagram Page inboxes for new DMs every 15 minutes
2. **Classifies** each message intent using Groq LLM (LLaMA 3.3 70B)
3. **Retrieves** relevant company knowledge via RAG (Retrieval-Augmented Generation) from uploaded PDFs and website content
4. **Drafts** an AI-generated reply tailored to the intent, augmented with real company knowledge
5. **Auto-sends** replies when confidence ≥ 85% and intent is non-sensitive
6. **Escalates** messages to a human admin dashboard when confidence is low or intent is sensitive/partnership
7. **Filters** spam messages automatically (no reply, no escalation)
8. **Logs** every action in a full audit trail
9. **Learns** from company documents — superadmin can upload PDFs and website URLs to train the agent

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                       FRONTEND (Vanilla HTML/CSS/JS)                     │
│  ┌──────────┐ ┌──────────────┐ ┌───────────────┐ ┌──────────────────┐   │
│  │ Login    │ │ Inbox        │ │ Auto-Sent Log │ │ Knowledge Base   │   │
│  │ Page     │ │ (Pending     │ │ (History &    │ │ (Upload PDFs,    │   │
│  │          │ │  Approvals)  │ │  Search)      │ │  Scan URLs)      │   │
│  └──────────┘ └──────────────┘ └───────────────┘ └──────────────────┘   │
│         │            │                │                  │               │
│         └──────────── JWT Auth Token ─┴──────────────────┘               │
└─────────────────────────┬────────────────────────────────────────────────┘
                          │ HTTP (localhost:8000)
┌─────────────────────────┴────────────────────────────────────────────────┐
│                      BACKEND (FastAPI + Uvicorn)                         │
│  ┌──────────────┐  ┌────────────┐  ┌─────────────┐  ┌───────────────┐   │
│  │ Auth Router  │  │ Messages   │  │ Knowledge   │  │ APScheduler   │   │
│  │ /api/auth/*  │  │ Router     │  │ Router      │  │ (15-min poll) │   │
│  └──────────────┘  │ /api/msg/* │  │ /api/know/* │  └──────┬────────┘   │
│                    └────────────┘  └──────┬──────┘         │            │
│  ┌───────────────────────────────────────┴┴────────────────┴──────┐     │
│  │                  Message Processor (Orchestrator)               │     │
│  │  ┌─────────┐ ┌───────────┐ ┌────────────────┐ ┌────────────┐  │     │
│  │  │ FB      │ │ IG        │ │ Groq Agent     │ │ RAG        │  │     │
│  │  │ Service │ │ Service   │ │ (Classify+     │ │ Retriever  │  │     │
│  │  │         │ │           │ │  Draft+RAG)    │ │ (ChromaDB) │  │     │
│  │  └────┬────┘ └─────┬─────┘ └────────┬───────┘ └──────┬─────┘  │     │
│  └───────┼────────────┼────────────────┼────────────────┼─────────┘     │
└──────────┼────────────┼────────────────┼────────────────┼────────────────┘
           │            │                │                │
    ┌──────┴──────┐ ┌───┴──────┐  ┌──────┴───────┐  ┌────┴──────────┐
    │ Meta Graph  │ │ Meta     │  │ Groq API     │  │ ChromaDB      │
    │ API (FB)    │ │ Graph    │  │ (LLaMA 3.3   │  │ (Vector Store │
    │             │ │ API (IG) │  │  70B)        │  │  + Embeddings)│
    └─────────────┘ └──────────┘  └──────────────┘  └───────────────┘

              ┌──────────────────────┐
              │   AWS RDS MySQL      │
              │ reputation_agent_db  │
              │                      │
              │ • users              │
              │ • messages           │
              │ • classifications    │
              │ • drafted_replies    │
              │ • actions            │
              │ • activity_logs      │
              │ • knowledge_documents│
              │ • knowledge_chunks   │
              └──────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | HTML5, CSS3, Vanilla JS | Dashboard UI |
| **Backend** | Python 3.12, FastAPI | REST API server |
| **Server** | Uvicorn (ASGI) | Async HTTP server |
| **Database** | MySQL 8 (AWS RDS) | Persistent storage |
| **ORM** | SQLAlchemy 2.0 (async) + aiomysql | Async database access |
| **Vector DB** | ChromaDB (persistent) | Embedding storage & semantic search |
| **Embeddings** | sentence-transformers (all-MiniLM-L6-v2) | Text → 384-dim vector embeddings |
| **LLM** | Groq API (LLaMA 3.3 70B Versatile) | Message classification & RAG-augmented reply drafting |
| **Social APIs** | Meta Graph API v18.0 | Facebook & Instagram DM polling + sending |
| **Auth** | JWT (python-jose) + bcrypt (passlib) | Admin authentication |
| **Scheduler** | APScheduler | Periodic polling job |
| **HTTP Client** | httpx | Async API calls to Meta & Groq |
| **PDF Parsing** | PyPDF2 | Extract text from uploaded PDFs |
| **Web Scraping** | BeautifulSoup4 + lxml | Recursive full-site website crawling |
| **Config** | pydantic-settings + python-dotenv | Environment variable management |

---

## Project Structure

```
Reputation_Management_Agent/
│
├── .env                                    # All secrets & configuration
├── .gitignore
├── SYSTEM.md                               # ← This file
├── TECHNICAL_DOCUMENTATION.md              # Detailed technical documentation
├── reputation_agent_backend_spec.md        # Backend specification document
├── reputation_dashboard_frontend_spec.md   # Frontend specification document
│
├── frontend/                               # Static frontend (no build step)
│   ├── index.html                          # Auth redirect (entry point)
│   ├── login.html                          # Login page
│   ├── inbox.html                          # Pending messages dashboard
│   ├── autosent.html                       # Auto-sent message log
│   ├── users.html                          # User management (superadmin)
│   ├── activity.html                       # Activity logs (superadmin)
│   ├── knowledge.html                      # 🧠 Knowledge Base management (superadmin)
│   ├── css/
│   │   ├── variables.css                   # Design tokens (colors, fonts, spacing)
│   │   ├── base.css                        # Global styles, resets, utilities
│   │   ├── login.css                       # Login page styles
│   │   ├── sidebar.css                     # Sidebar navigation styles
│   │   ├── inbox.css                       # Inbox page styles
│   │   ├── autosent.css                    # Auto-sent log styles
│   │   ├── users.css                       # User management styles
│   │   ├── activity.css                    # Activity logs styles
│   │   └── knowledge.css                   # Knowledge Base styles
│   └── js/
│       ├── api.js                          # API layer — all fetch() wrappers
│       ├── auth.js                         # Login, logout, token management
│       ├── inbox.js                        # Inbox page logic
│       ├── autosent.js                     # Auto-sent page logic
│       ├── users.js                        # User management logic
│       ├── activity.js                     # Activity logs logic
│       └── knowledge.js                    # Knowledge Base logic (upload, search, CRUD)
│
├── backend/                                # Python FastAPI backend
│   ├── main.py                             # App entry point, lifespan, CORS
│   ├── requirements.txt                    # Python dependencies
│   ├── schema.sql                          # Raw SQL CREATE TABLE statements
│   ├── venv/                               # Virtual environment (not committed)
│   ├── data/                               # Runtime data (not committed)
│   │   ├── uploads/                        # Uploaded PDF files
│   │   └── chromadb/                       # ChromaDB vector store persistence
│   └── app/
│       ├── __init__.py
│       ├── config.py                       # Pydantic settings (env loader)
│       ├── database.py                     # Async SQLAlchemy engine & session
│       ├── auth.py                         # JWT creation, verification, hashing
│       ├── scheduler.py                    # APScheduler setup (15-min polling)
│       ├── models/
│       │   ├── __init__.py                 # Model imports
│       │   ├── user.py                     # User model (admin auth)
│       │   ├── message.py                  # Message, Classification, DraftedReply
│       │   ├── action.py                   # Action audit log model
│       │   ├── activity_log.py             # System-wide activity log
│       │   └── knowledge_document.py       # 🧠 KnowledgeDocument + KnowledgeChunk
│       ├── schemas/
│       │   ├── __init__.py                 # Schema imports
│       │   ├── auth.py                     # LoginRequest, LoginResponse, UserOut
│       │   ├── message.py                  # MessageOut, AutoSentMessageOut, etc.
│       │   ├── action.py                   # ActionOut
│       │   └── knowledge.py                # 🧠 URLUploadRequest, DocumentOut, etc.
│       ├── services/
│       │   ├── __init__.py
│       │   ├── facebook.py                 # FB Graph API: poll DMs + send replies
│       │   ├── instagram.py                # IG Graph API: poll DMs + send replies
│       │   ├── groq_agent.py               # Groq LLM: classify + RAG-augmented draft
│       │   ├── message_processor.py        # Orchestrator: full processing pipeline
│       │   ├── log_activity.py             # Activity logging helper
│       │   ├── token_exchange.py           # Token exchange (short → permanent)
│       │   └── knowledge/                  # 🧠 RAG Pipeline
│       │       ├── __init__.py
│       │       ├── pdf_parser.py           # Extract text from PDFs
│       │       ├── url_scraper.py          # Recursive full-site web crawler
│       │       ├── chunker.py              # Text splitting with overlap
│       │       ├── embedder.py             # sentence-transformers embeddings
│       │       ├── vector_store.py         # ChromaDB add/delete/query
│       │       ├── retriever.py            # RAG context retrieval for LLM
│       │       └── processor.py            # Full ingestion pipeline orchestrator
│       └── routers/
│           ├── __init__.py
│           ├── auth.py                     # POST /api/auth/login
│           ├── messages.py                 # Message endpoints (6 routes)
│           ├── users.py                    # User CRUD (superadmin only)
│           ├── activity.py                 # Activity logs (superadmin only)
│           ├── token.py                    # Token exchange (superadmin only)
│           └── knowledge.py                # 🧠 Knowledge Base CRUD + search
```

---

## Environment Variables

All configuration is loaded from `.env` in the project root:

| Variable | Description | Example |
|----------|-------------|---------|
| `APP_ENV` | Environment mode | `development` |
| `SECRET_KEY` | JWT signing secret | Random 64-char string |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT token lifetime | `1440` (24 hours) |
| `APP_ID` | Meta App ID | `1625210535338747` |
| `APP_SECRET` | Meta App Secret | `78ef2e...` |
| `FB_PAGE_ID` | Facebook Page ID | `969597406242160` |
| `FB_PAGE_ACCESS_TOKEN` | Facebook Page access token | `EAAXG...` |
| `IG_USER_ID` | Instagram user/page ID | `tushar_kadam_21_` |
| `IG_PAGE_ACCESS_TOKEN` | Instagram page access token | *(needs real token)* |
| `WEBHOOK_VERIFY_TOKEN` | Webhook verification string | Any random string |
| `GROQ_API_KEY` | Groq API key | `gsk_4zjr...` |
| `GROQ_MODEL` | Groq model name | `llama-3.3-70b-versatile` |
| `DATABASE_URL` | MySQL connection string | `mysql+mysqlconnector://...` |
| `DB_HOST` | Database host | `tis-mysql-instance.cf4...` |
| `DB_USER` | Database username | `auxilo425` |
| `DB_PASSWORD` | Database password | *(redacted)* |
| `DB_NAME` | Database name | `reputation_agent_db` |
| `AUTO_SEND_CONFIDENCE_THRESHOLD` | Min confidence for auto-send | `0.85` (85%) |
| `POLLING_INTERVAL_MINUTES` | Polling frequency | `15` |
| `CHROMA_PERSIST_DIR` | ChromaDB storage path | `./data/chromadb` |
| `EMBEDDING_MODEL` | sentence-transformers model | `all-MiniLM-L6-v2` |
| `RAG_CHUNK_SIZE` | Max characters per text chunk | `2000` |
| `RAG_CHUNK_OVERLAP` | Overlap between chunks | `200` |
| `RAG_TOP_K` | Number of chunks to retrieve | `5` |
| `UPLOAD_DIR` | PDF upload storage path | `./data/uploads` |
| `RAG_MAX_CRAWL_DEPTH` | Max URL crawl depth | `3` |
| `RAG_MAX_CRAWL_PAGES` | Max pages to crawl per URL | `50` |
| `ADMIN_EMAIL` | Default admin email (seeded on startup) | `superadmin@auxilo.com` |
| `ADMIN_PASSWORD` | Default admin password | `changeme123` |

---

## Database Schema

The system uses **8 tables** in `reputation_agent_db` on AWS RDS MySQL (5 core + 1 activity log + 2 knowledge base):

### Entity Relationship

```
┌───────────┐     ┌──────────────────┐     ┌─────────────────┐
│   users   │     │    messages       │────▶│ classifications  │
│           │     │                  │     │                 │
│ id (PK)   │     │ id (PK)          │     │ id (PK)         │
│ email     │     │ platform         │     │ message_id (FK) │
│ pass_hash │     │ platform_msg_id  │     │ intent          │
│ role      │     │ sender_id        │     │ confidence      │
│ created_at│     │ sender_name      │     │ raw_llm_response│
└───────────┘     │ content          │     │ classified_at   │
                  │ thread_id        │     └─────────────────┘
                  │ received_at      │
                  │ created_at       │     ┌─────────────────┐
                  │                  │────▶│ drafted_replies  │
                  │                  │     │                 │
                  │                  │     │ id (PK)         │
                  │                  │     │ message_id (FK) │
                  │                  │     │ content         │
                  │                  │     │ generated_at    │
                  │                  │     │ model_used      │
                  │                  │     └─────────────────┘
                  │                  │
                  │                  │     ┌─────────────────┐
                  │                  │────▶│    actions       │
                  └──────────────────┘     │                 │
                                          │ id (PK)         │
                                          │ message_id (FK) │
                                          │ action_type     │
                                          │ actor           │
                                          │ final_reply     │
                                          │ performed_at    │
                                          └─────────────────┘
```

### Table Details

#### `users`
| Column | Type | Notes |
|--------|------|-------|
| `id` | INT AUTO_INCREMENT | Primary key |
| `email` | VARCHAR(255) | Unique, indexed |
| `password_hash` | VARCHAR(255) | bcrypt hash |
| `role` | ENUM('superadmin', 'admin', 'viewer') | Access level |
| `created_at` | DATETIME | Auto-set |

#### `messages`
| Column | Type | Notes |
|--------|------|-------|
| `id` | INT AUTO_INCREMENT | Primary key |
| `platform` | ENUM('facebook', 'instagram') | Source platform |
| `platform_msg_id` | VARCHAR(255) | Unique, for deduplication |
| `sender_id` | VARCHAR(255) | Platform user ID |
| `sender_name` | VARCHAR(255) | Display name |
| `content` | TEXT | Message body |
| `thread_id` | VARCHAR(255) | Conversation thread ID |
| `received_at` | DATETIME | When the DM was sent |
| `created_at` | DATETIME | When stored in DB |

#### `classifications`
| Column | Type | Notes |
|--------|------|-------|
| `id` | INT AUTO_INCREMENT | Primary key |
| `message_id` | INT (FK → messages) | CASCADE delete |
| `intent` | ENUM (6 types) | See intents below |
| `confidence` | FLOAT | 0.0 — 1.0 |
| `raw_llm_response` | TEXT | Full Groq response |
| `classified_at` | DATETIME | When classified |

**Intent Types:**
- `potential_lead` — Sales opportunity
- `customer_support` — Help request
- `general_inquiry` — General question
- `sensitive_complaint` — Complaint requiring care
- `partnership_inquiry` — Business partnership
- `spam` — Junk / irrelevant

#### `drafted_replies`
| Column | Type | Notes |
|--------|------|-------|
| `id` | INT AUTO_INCREMENT | Primary key |
| `message_id` | INT (FK → messages) | CASCADE delete |
| `content` | TEXT | AI-drafted reply text |
| `generated_at` | DATETIME | When drafted |
| `model_used` | VARCHAR(100) | e.g., `llama-3.3-70b-versatile` |

#### `actions`
| Column | Type | Notes |
|--------|------|-------|
| `id` | INT AUTO_INCREMENT | Primary key |
| `message_id` | INT (FK → messages) | CASCADE delete |
| `action_type` | ENUM (8 types) | See action types below |
| `actor` | VARCHAR(100) | `system` or admin email |
| `final_reply` | TEXT | Reply text that was sent |
| `performed_at` | DATETIME | When action was taken |

**Action Types:**
- `received` — Message ingested from platform
- `classified` — Groq intent classification completed
- `draft_generated` — AI reply drafted
- `auto_sent` — Reply sent automatically (high confidence)
- `escalated` — Sent to admin dashboard for review
- `approved` — Admin approved and sent the draft
- `rejected` — Admin rejected the message
- `edited_and_approved` — Admin edited the reply and sent it

#### `knowledge_documents`
| Column | Type | Notes |
|--------|------|-------|
| `id` | INT AUTO_INCREMENT | Primary key |
| `doc_type` | ENUM('pdf', 'url') | Source type |
| `filename` | VARCHAR(500) | Original filename or root URL |
| `file_path` | VARCHAR(1000) | Server storage path (PDFs only) |
| `status` | ENUM('pending','processing','ready','failed') | Processing status |
| `total_chunks` | INT | Number of text chunks extracted |
| `total_pages_crawled` | INT | For URLs: pages scraped |
| `uploaded_by` | INT (FK → users) | Who uploaded |
| `uploaded_at` | DATETIME | Upload timestamp |
| `processed_at` | DATETIME | When processing completed |
| `error_message` | TEXT | Error details if failed |

#### `knowledge_chunks`
| Column | Type | Notes |
|--------|------|-------|
| `id` | INT AUTO_INCREMENT | Primary key |
| `document_id` | INT (FK → knowledge_documents) | CASCADE delete |
| `chunk_index` | INT | Order within document |
| `content` | TEXT | The text chunk |
| `metadata_json` | JSON | Page number, URL, section, etc. |
| `created_at` | DATETIME | When created |

---

## Backend — API Reference

Base URL: `http://localhost:8000`

### Health Check

| Method | Path | Auth | Response |
|--------|------|------|----------|
| `GET` | `/health` | ❌ | `{"status": "ok", "version": "1.0.0"}` |

### Authentication

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/auth/login` | ❌ | Login with email/password, returns JWT |

**Request Body:**
```json
{
  "email": "superadmin@auxilo.com",
  "password": "changeme123"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "user": {
    "email": "superadmin@auxilo.com",
    "role": "superadmin"
  }
}
```

### Messages

All message endpoints require `Authorization: Bearer <token>` header.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/messages/pending` | List escalated messages awaiting approval |
| `GET` | `/api/messages/auto-sent` | Paginated log of auto-sent messages |
| `POST` | `/api/messages/{id}/approve` | Approve and send reply |
| `POST` | `/api/messages/{id}/reject` | Reject message with reason |
| `POST` | `/api/messages/{id}/regenerate` | Re-draft reply using Groq |

#### GET `/api/messages/pending`

**Query Parameters (optional):**
- `platform` — Filter by `facebook` or `instagram`
- `intent` — Filter by intent type

**Response:** Array of message objects with classification, drafted reply, and action history.

#### GET `/api/messages/auto-sent`

**Query Parameters:**
- `page` — Page number (default: 1)
- `limit` — Items per page (default: 20)
- `platform` — Filter by platform
- `intent` — Filter by intent
- `search` — Search in message content

**Response:**
```json
{
  "messages": [...],
  "total": 42,
  "page": 1,
  "limit": 20,
  "total_pages": 3
}
```

#### POST `/api/messages/{id}/approve`

**Request Body:**
```json
{
  "edited_reply": "Optional custom reply text"
}
```

**Response (200):**
```json
{
  "sent_at": "2026-02-19T23:15:00"
}
```

#### POST `/api/messages/{id}/reject`

**Request Body:**
```json
{
  "reason": "Off-topic / Not relevant"
}
```

#### POST `/api/messages/{id}/regenerate`

**Response (200)** (reply is now RAG-augmented if knowledge base has relevant content):
```json
{
  "drafted_reply": "New AI-generated reply text...",
  "model_used": "llama-3.3-70b-versatile"
}
```

---

## Backend — Core Services

### 1. Facebook Service (`app/services/facebook.py`)

- **`fetch_new_conversations()`** — Polls `GET /{page_id}/conversations` from Meta Graph API v18.0. For each conversation, fetches the last 5 messages. Filters out messages sent BY the page (outbound). Returns normalized message dicts.
- **`send_message(recipient_id, text)`** — Sends a reply via `POST /me/messages` (Facebook Send API).

### 2. Instagram Service (`app/services/instagram.py`)

- **`fetch_new_conversations()`** — Same structure as Facebook but uses `platform=instagram` parameter. Requires a valid Instagram Page Access Token.
- **`send_message(recipient_id, text)`** — Sends reply via Instagram messaging.

### 3. Groq Agent Service (`app/services/groq_agent.py`)

- **`classify_message(content)`** — Sends message to Groq with a system prompt that instructs it to classify intent into one of 6 categories and provide a confidence score (0.0–1.0). Returns JSON `{"intent": "...", "confidence": 0.XX}`.
- **`draft_reply(content, intent, sender_name, rag_context)`** — Generates a professional reply based on the classified intent, **augmented with RAG context** from the knowledge base when available. Uses intent-specific tone (e.g., warm for leads, empathetic for complaints).

**LLM Features:**
- JSON parsing resilience (handles markdown code fences)
- Intent validation (defaults to `general_inquiry` if invalid)
- Confidence clamping (0.0–1.0)
- `temperature: 0.1` for classification, `0.7` for reply drafting
- **RAG Context Injection** — When relevant company knowledge is found, it's injected into the system prompt so the LLM references real company data

### 4. Message Processor (`app/services/message_processor.py`)

The central orchestrator that runs the full pipeline:

```
fetch_messages() → deduplicate() → classify() → filter_spam() → retrieve_rag_context() → draft_reply() → decide() → act()
```

- Per-message error isolation (one failure doesn't stop the pipeline)
- Logs every step as an `Action` record
- **RAG retrieval** runs before drafting (graceful fallback if vector store is empty or retrieval fails)

### 5. Knowledge Base Services (`app/services/knowledge/`)

The RAG (Retrieval-Augmented Generation) pipeline:

| Service | Purpose |
|---------|--------|
| `pdf_parser.py` | Extract text from PDFs page-by-page (PyPDF2) |
| `url_scraper.py` | Recursive full-site BFS crawler (same-domain, configurable depth/pages) |
| `chunker.py` | Recursive character splitting with overlap (2000 char chunks, 200 overlap) |
| `embedder.py` | Generate 384-dim embeddings via sentence-transformers (lazy-loaded) |
| `vector_store.py` | ChromaDB persistent collection (add, delete, cosine query) |
| `retriever.py` | Embed query → search ChromaDB → format context for LLM prompt |
| `processor.py` | Full pipeline orchestrator: parse → chunk → embed → index |

**Pipeline Flow:**
```
Upload PDF / Submit URL
  → Parse text (PDF) or Crawl site (URL)
    → Chunk text (500-token overlapping segments)
      → Generate embeddings (all-MiniLM-L6-v2)
        → Store in ChromaDB + Save chunks to MySQL
```

---

## Message Processing Pipeline

```
                    ┌──────────────────────┐
                    │  Scheduler Trigger    │
                    │  (every 15 min)       │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  Fetch from FB + IG   │
                    │  via Graph API        │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  Deduplicate          │
                    │  (by platform_msg_id) │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  Classify via Groq    │
                    │  → intent + confid.   │
                    └──────────┬───────────┘
                               │
                 ┌─────────────┼─────────────┐
                 │             │             │
          ┌──────▼──────┐     │      ┌──────▼──────┐
          │   SPAM      │     │      │  Non-Spam   │
          │  → Skip     │     │      │  → Draft    │
          │  (no reply) │     │      │    Reply    │
          └─────────────┘     │      └──────┬──────┘
                              │             │
                              │    ┌────────▼────────┐
                              │    │  Decision Logic  │
                              │    └────────┬────────┘
                              │             │
                    ┌─────────┴──────┐ ┌────┴──────────┐
                    │ AUTO-SEND      │ │ ESCALATE      │
                    │ confidence ≥85%│ │ confidence <85%│
                    │ AND intent is  │ │ OR intent is   │
                    │ NOT sensitive  │ │ sensitive/     │
                    │ NOT partnership│ │ partnership    │
                    └────────────────┘ └───────────────┘
                           │                   │
                    ┌──────▼──────┐     ┌──────▼──────┐
                    │ Send via    │     │ Show in     │
                    │ Meta API    │     │ Admin Inbox │
                    │ Log action  │     │ for review  │
                    └─────────────┘     └─────────────┘
```

### Decision Matrix

| Intent | Confidence ≥ 85% | Confidence < 85% |
|--------|:-----------------:|:-----------------:|
| Potential Lead | ✅ Auto-send | 🔔 Escalate |
| Customer Support | ✅ Auto-send | 🔔 Escalate |
| General Inquiry | ✅ Auto-send | 🔔 Escalate |
| Sensitive Complaint | 🔔 **Always Escalate** | 🔔 **Always Escalate** |
| Partnership Inquiry | 🔔 **Always Escalate** | 🔔 **Always Escalate** |
| Spam | 🚫 Skip (no reply) | 🚫 Skip (no reply) |

---

## Frontend — Pages & Components

### Design System
- **Theme:** Dark mode with green (#00F5A0) accents
- **Fonts:** Syne (headings), DM Sans (body), DM Mono (code)
- **Style:** Glassmorphism, smooth animations, responsive

### Pages

| Page | File | Description |
|------|------|-------------|
| **Entry** | `index.html` | Auth check → redirect to login or inbox |
| **Login** | `login.html` | Email/password authentication |
| **Inbox** | `inbox.html` | Two-panel layout: message list + detail panel |
| **Auto-Sent Log** | `autosent.html` | Searchable, paginated history of auto-sent messages |
| **Users** | `users.html` | User management (superadmin only) |
| **Activity** | `activity.html` | Activity logs (superadmin only) |
| **Knowledge Base** | `knowledge.html` | 🧠 Upload PDFs, scan websites, search knowledge, manage docs |

### Inbox Features
- Filter by platform (Facebook/Instagram) and intent
- Click a message to see full details in the right panel
- View original message, AI classification (intent + confidence %), and drafted reply
- **Approve** — Send the reply (or edit it first)
- **Reject** — Reject with a reason
- **Regenerate** — Ask Groq to re-draft the reply
- **Edit Reply** — Modify the AI draft before approving
- Responsive: sidebar collapses on mobile

### Auto-Sent Log Features
- Search across message content
- Filter by platform and intent
- Paginated with page controls
- View sent reply text for each message

### JavaScript Modules

| Module | Purpose |
|--------|---------|
| `api.js` | All `fetch()` wrappers, auth headers, progress bar, toast notifications |
| `auth.js` | Token management (get/set/clear), login form handler, logout, auth guards |
| `inbox.js` | Message list rendering, detail panel, approve/reject/regenerate actions |
| `autosent.js` | Auto-sent log rendering, search, pagination, filters |
| `users.js` | User management CRUD |
| `activity.js` | Activity logs rendering with filters |
| `knowledge.js` | 🧠 PDF drag-and-drop upload, URL crawl submission, semantic search testing, document CRUD |

---

## Authentication & Security

### JWT Token Flow

```
Login → POST /api/auth/login → JWT (24h expiry) → Stored in localStorage
                                                         │
Every API call → Authorization: Bearer <token> ──────────┘
                                                         │
Backend → Decode JWT → Verify signature + expiry → Extract user email
                                                         │
401 Unauthorized → Frontend clears token → Redirect to login
```

### Password Security
- Passwords hashed with **bcrypt** (12 rounds) via `passlib`
- Plain-text passwords never stored or logged

### CORS
- Configured to allow all origins in development mode (`allow_origins=["*"]`)
- Should be restricted in production to specific domains

---

## Scheduler & Polling

- **Library:** APScheduler (`AsyncIOScheduler`)
- **Job:** `Social Media Polling`
- **Trigger:** Interval — every `POLLING_INTERVAL_MINUTES` (default: 15 min)
- **Misfire Grace:** 60 seconds
- **Lifecycle:** Starts on app startup, shuts down on app shutdown

The scheduler calls `run_polling_cycle()` in `message_processor.py`, which:
1. Fetches messages from Facebook and Instagram
2. Processes each through the full pipeline
3. Logs all actions to the database

---

## How to Run

### Prerequisites
- Python 3.12+
- MySQL 8 database (local or AWS RDS)
- Valid Meta Graph API Page Access Token
- Groq API key

### Backend

```bash
# Navigate to backend
cd backend

# Create virtual environment (first time only)
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies (first time only)
pip install -r requirements.txt

# Start the server
uvicorn main:app --reload --port 8000
```

On startup, the server will:
1. Create all 8 database tables (if they don't exist)
2. Create `data/uploads/` and `data/chromadb/` directories
3. Seed the superadmin user (if not already present)
4. Start the APScheduler for polling

### Frontend

Open `frontend/login.html` via **VS Code Live Server** (right-click → Open with Live Server) or any HTTP server on port 5500:

```bash
# Or use Python's built-in server
cd frontend
python3 -m http.server 5500
```

Then visit: `http://127.0.0.1:5500/frontend/login.html`

---

## Admin Credentials

| Field | Value |
|-------|-------|
| **Email** | `superadmin@auxilo.com` |
| **Password** | `changeme123` |

> ⚠️ **Change these in production** by updating `ADMIN_EMAIL` and `ADMIN_PASSWORD` in `.env` before the first server start.

---

## Key Configuration

| Setting | Default | Effect |
|---------|---------|--------|
| `AUTO_SEND_CONFIDENCE_THRESHOLD` | `0.85` | Messages with confidence ≥ this are auto-sent |
| `POLLING_INTERVAL_MINUTES` | `15` | How often FB/IG inboxes are polled |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | JWT token lifetime (24 hours) |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq LLM model used for classification & drafting |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | sentence-transformers model for embeddings |
| `RAG_CHUNK_SIZE` | `2000` | Max characters per text chunk (~500 tokens) |
| `RAG_TOP_K` | `5` | Number of relevant chunks retrieved per query |
| `RAG_MAX_CRAWL_DEPTH` | `3` | How deep the URL crawler follows links |
| `RAG_MAX_CRAWL_PAGES` | `50` | Max pages scraped per website |

---

*Built for Auxilo Finserve — Reputation Management Agent v2.0.0 (with RAG Knowledge Base)*

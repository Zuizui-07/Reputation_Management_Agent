"""
================================================
  Main Entry Point — Reputation Manager API
================================================
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
import logging

from app.config import settings
from app.database import engine, Base, AsyncSessionLocal
from app.models import User, Message, Classification, DraftedReply, Action  # noqa: F401
from app.models import KnowledgeDocument, KnowledgeChunk  # noqa: F401
from app.auth import hash_password, verify_password
from app.scheduler import start_scheduler

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
#  Lifespan (startup + shutdown)
# ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # ── STARTUP ──
    logger.info("╔═══════════════════════════════════════╗")
    logger.info("║  Reputation Manager API — Starting    ║")
    logger.info("╚═══════════════════════════════════════╝")

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created / verified")

    # Create upload and data directories
    from pathlib import Path
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)
    logger.info("Data directories created / verified")

    # Seed superadmin
    await seed_admin()

    # Start scheduler
    start_scheduler()

    yield

    # ── SHUTDOWN ──
    logger.info("Shutting down...")
    await engine.dispose()


# ──────────────────────────────────────────────
#  FastAPI App
# ──────────────────────────────────────────────
app = FastAPI(
    title="Reputation Manager API",
    description="Backend for Auxilo Finserve social media reputation management agent",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",  # Allow all origins for deployment flexibility
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8080",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──
from app.routers import auth, messages, users, activity, token, knowledge  # noqa: E402

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(messages.router, prefix="/api/messages", tags=["Messages"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(activity.router, prefix="/api/activity", tags=["Activity"])
app.include_router(token.router, prefix="/api/token", tags=["Token Management"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["Knowledge Base"])

# ── Rate Limiter (for auth.login) ──
app.state.limiter = auth.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ──────────────────────────────────────────────
#  Health Check
# ──────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "version": "1.0.0"}


# ──────────────────────────────────────────────
#  Admin Seed
# ──────────────────────────────────────────────
async def seed_admin():
    """Create the superadmin user on first run, or update password if changed."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.email == settings.ADMIN_EMAIL)
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            admin = User(
                email=settings.ADMIN_EMAIL,
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                role="superadmin",
            )
            session.add(admin)
            await session.commit()
            logger.info(f"Superadmin seeded: {settings.ADMIN_EMAIL}")
        else:
            # Update password if it changed in .env
            if not verify_password(settings.ADMIN_PASSWORD, existing.password_hash):
                existing.password_hash = hash_password(settings.ADMIN_PASSWORD)
                await session.commit()
                logger.info(f"Superadmin password updated: {settings.ADMIN_EMAIL}")
            else:
                logger.info(f"Superadmin already exists: {settings.ADMIN_EMAIL}")

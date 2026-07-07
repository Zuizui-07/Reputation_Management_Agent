"""
================================================
  Configuration — loads and validates all env vars
================================================
"""

from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional


class Settings(BaseSettings):
    """All application settings loaded from .env file."""

    # ── App ──
    APP_ENV: str = "development"
    SECRET_KEY: str = "your_random_64_char_secret_key_here"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # ── Database ──
    DATABASE_URL: str = "mysql+aiomysql://root:@localhost:3306/reputation_agent_db"
    DB_HOST: Optional[str] = None
    DB_USER: Optional[str] = None
    DB_PASSWORD: Optional[str] = None
    DB_NAME: Optional[str] = None

    # ── Meta App ──
    APP_ID: Optional[str] = None
    APP_SECRET: Optional[str] = None

    # ── Facebook ──
    FB_PAGE_ID: str = ""
    FB_PAGE_ACCESS_TOKEN: str = ""

    # ── Google Reviews ──
    GOOGLE_CLIENT_ID: str = "602462506954-89pbr9bqtd1pbfq3ahjasig7pr9mpeh3.apps.googleusercontent.com"
    GOOGLE_CLIENT_SECRET: str = "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"
    GOOGLE_REFRESH_TOKEN: str = "1//04JPccQFMgY4ZCgYIARAAGAQSNwF-L9IrDF022_togiHgdejQTjY8ehRJIGaTBwa-VQTU76lieOqbMHsrZJNrny627ujCY6AYf7g"
    GOOGLE_ACCOUNT_NAME: str = "accounts/104846196755011630283"      
    GOOGLE_LOCATION_NAME: str = "locations/9397695944111266726"  

    # ── Reddit ──
    REDDIT_CLIENT_ID: str = ""
    REDDIT_CLIENT_SECRET: str = ""
    REDDIT_USERNAME: str = "Hungry_Contact_4168"
    REDDIT_PASSWORD: str = "Tasmiya@1234"
    REDDIT_SUBREDDIT: str = ""

    # ── Instagram ──
    IG_USER_ID: str = ""
    IG_PAGE_ACCESS_TOKEN: str = ""

    # ── Webhook ──
    WEBHOOK_VERIFY_TOKEN: Optional[str] = None

    # ── Groq ──
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # ── Agent Config ──
    AUTO_SEND_CONFIDENCE_THRESHOLD: float = 0.85
    POLLING_INTERVAL_MINUTES: int = 15

    # ── RAG / Knowledge Base ──
    CHROMA_PERSIST_DIR: str = "./data/chromadb"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    RAG_CHUNK_SIZE: int = 2000
    RAG_CHUNK_OVERLAP: int = 200
    RAG_TOP_K: int = 5
    UPLOAD_DIR: str = "./data/uploads"
    RAG_MAX_CRAWL_DEPTH: int = 3
    RAG_MAX_CRAWL_PAGES: int = 50

    # ── Admin Seed ──
    ADMIN_EMAIL: str = "superadmin@auxilo.com"
    ADMIN_PASSWORD: str = "changeme123"

    @property
    def async_database_url(self) -> str:
        """Convert any sync MySQL URL to async aiomysql URL."""
        url = self.DATABASE_URL
        # Replace sync drivers with async driver
        for sync_driver in ("mysql+mysqlconnector://", "mysql://", "mysql+pymysql://"):
            if url.startswith(sync_driver):
                url = url.replace(sync_driver, "mysql+aiomysql://", 1)
                break
        return url

    @property
    def sync_database_url(self) -> str:
        """Return a synchronous URL for Alembic migrations."""
        url = self.DATABASE_URL
        if "aiomysql" in url:
            url = url.replace("mysql+aiomysql://", "mysql+mysqlconnector://", 1)
        return url

    model_config = {
        "env_file": str(Path(__file__).resolve().parent.parent.parent / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()

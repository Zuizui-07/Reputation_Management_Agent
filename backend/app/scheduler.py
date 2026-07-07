"""
================================================
  Scheduler — APScheduler polling job
================================================
"""

import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import settings

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def polling_job():
    """
    Wrapper that runs the message processor polling cycle.
    Imported here to avoid circular imports.
    """
    from app.services.message_processor import run_polling_cycle
    try:
        await run_polling_cycle()
    except Exception as e:
        logger.error(f"Polling job error: {e}", exc_info=True)


def start_scheduler():
    """
    Start the APScheduler with the polling job.
    Called from FastAPI startup event.
    """
    scheduler.add_job(
        polling_job,
        trigger="interval",
        minutes=settings.POLLING_INTERVAL_MINUTES,
        id="polling_job",
        name="Social Media Polling",
        replace_existing=True,
        misfire_grace_time=60,
    )
    scheduler.start()
    logger.info(
        f"Scheduler started — polling every {settings.POLLING_INTERVAL_MINUTES} minutes"
    )

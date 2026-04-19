"""
T-BE-18: APScheduler integration.

Starts a background interval job every 60 seconds to process pending
notify_log entries (upcoming reminders, cancelled notifications).

Respects RUN_SCHEDULER env var — set to false in non-scheduler replicas.
"""
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def start() -> None:
    global _scheduler
    if not settings.run_scheduler:
        logger.info("RUN_SCHEDULER=false — scheduler not started")
        return

    from app.db import SessionLocal
    from app.services.notify_service import process_pending_logs

    def _job() -> None:
        db = SessionLocal()
        try:
            count = process_pending_logs(db)
            if count:
                logger.debug("Scheduler: processed %d notify_log entries", count)
        except Exception:
            logger.exception("Scheduler job error")
        finally:
            db.close()

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(_job, "interval", seconds=60, id="notify_pending", replace_existing=True)
    _scheduler.start()
    logger.info("APScheduler started (notify job every 60s)")


def stop() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")

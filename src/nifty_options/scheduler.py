"""Optional weekday CSV import scheduler for the single-process app container."""

import logging
import time as time_module
from datetime import datetime, timedelta
from datetime import time as datetime_time
from threading import Thread
from zoneinfo import ZoneInfo

from nifty_options.config import Settings, get_settings
from nifty_options.pipeline import run_pipeline

logger = logging.getLogger(__name__)
INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")


def _next_weekday_run(now: datetime, run_time: datetime_time) -> datetime:
    candidate = now.date()
    while True:
        target = datetime.combine(candidate, run_time, tzinfo=INDIA_TIMEZONE)
        if candidate.weekday() < 5 and target > now:
            return target
        candidate += timedelta(days=1)


def _run_import(settings: Settings) -> None:
    options_path = settings.options_csv_path
    if not options_path.is_file():
        logger.warning("Scheduled import skipped because options CSV is missing: %s", options_path)
        return
    prices_path = settings.prices_csv_path if settings.prices_csv_path.is_file() else None
    try:
        run_pipeline(options_path, prices_path, settings.database_path)
    except Exception:
        logger.exception("Scheduled CSV import failed")


def _scheduler_loop(settings: Settings) -> None:
    while True:
        now = datetime.now(INDIA_TIMEZONE)
        next_run = _next_weekday_run(now, settings.scheduler_time)
        delay = max((next_run - now).total_seconds(), 1.0)
        logger.info("Next scheduled CSV import at %s India time", next_run.isoformat())
        time_module.sleep(delay)
        _run_import(settings)


def start_daily_scheduler() -> Thread | None:
    """Start one daemon scheduler thread when explicitly enabled in configuration."""
    settings = get_settings()
    if not settings.scheduler_enabled:
        return None
    thread = Thread(
        target=_scheduler_loop,
        args=(settings,),
        name="banknifty-daily-import",
        daemon=True,
    )
    thread.start()
    logger.info("Daily CSV import scheduler enabled for %s India time", settings.scheduler_time)
    return thread

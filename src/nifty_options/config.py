"""Minimal environment-backed local configuration."""

import math
import os
from dataclasses import dataclass
from datetime import time
from pathlib import Path

from dotenv import load_dotenv


def _project_root() -> Path:
    current_directory = Path.cwd().resolve()
    if (current_directory / "pyproject.toml").is_file():
        return current_directory
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    return current_directory


PROJECT_ROOT = _project_root()
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    database_path: Path
    log_level: str
    alert_webhook_url: str | None
    max_csv_bytes: int
    http_timeout_seconds: float
    http_max_attempts: int
    http_min_interval_seconds: float
    http_max_response_bytes: int
    scheduler_enabled: bool
    scheduler_time: time
    options_csv_path: Path
    prices_csv_path: Path


def _int_setting(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _float_setting(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = os.getenv(name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def get_settings() -> Settings:
    """Return settings, resolving relative paths from the repository root."""
    configured_value = os.getenv("DATABASE_PATH", "data/nifty_options.duckdb").strip()
    if not configured_value or "\0" in configured_value:
        raise ValueError("DATABASE_PATH must be a non-empty path")
    configured_path = Path(configured_value)
    database_path = (
        configured_path if configured_path.is_absolute() else PROJECT_ROOT / configured_path
    )
    log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ValueError("LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")
    alert_webhook_url = os.getenv("ALERT_WEBHOOK_URL", "").strip() or None

    scheduler_value = os.getenv("SCHEDULER_ENABLED", "false").strip().casefold()
    if scheduler_value not in {"true", "false"}:
        raise ValueError("SCHEDULER_ENABLED must be true or false")
    try:
        scheduler_time = time.fromisoformat(os.getenv("SCHEDULER_TIME", "18:15").strip())
    except ValueError as exc:
        raise ValueError("SCHEDULER_TIME must be a local 24-hour time such as 18:15") from exc

    def configured_file(name: str, default: str) -> Path:
        path = Path(os.getenv(name, default).strip()).expanduser()
        return path if path.is_absolute() else PROJECT_ROOT / path

    return Settings(
        database_path=database_path,
        log_level=log_level,
        alert_webhook_url=alert_webhook_url,
        max_csv_bytes=_int_setting("MAX_CSV_BYTES", 100 * 1024 * 1024, 1, 1024 * 1024 * 1024),
        http_timeout_seconds=_float_setting("HTTP_TIMEOUT_SECONDS", 15.0, 0.1, 300.0),
        http_max_attempts=_int_setting("HTTP_MAX_ATTEMPTS", 4, 1, 10),
        http_min_interval_seconds=_float_setting("HTTP_MIN_INTERVAL_SECONDS", 1.0, 0.0, 3600.0),
        http_max_response_bytes=_int_setting(
            "HTTP_MAX_RESPONSE_BYTES", 25 * 1024 * 1024, 1, 512 * 1024 * 1024
        ),
        scheduler_enabled=scheduler_value == "true",
        scheduler_time=scheduler_time,
        options_csv_path=configured_file("OPTIONS_CSV", "data/raw/options.csv"),
        prices_csv_path=configured_file("PRICES_CSV", "data/raw/prices.csv"),
    )

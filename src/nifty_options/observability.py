"""Structured logging and lightweight input quality summaries."""

import json
import logging
from datetime import UTC, datetime
from typing import Any
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import pandas as pd


class JsonFormatter(logging.Formatter):
    """Render log records as one JSON object per line for container log collectors."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        standard_fields = logging.makeLogRecord({}).__dict__
        for key, value in record.__dict__.items():
            if key not in standard_fields and key not in {
                "message",
                "asctime",
            }:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: str) -> None:
    """Configure the root logger once; output is suitable for stdout collection."""
    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(JsonFormatter())
        root.addHandler(stream_handler)
    else:
        for handler in root.handlers:
            handler.setFormatter(JsonFormatter())


def price_quality(prices: pd.DataFrame) -> dict[str, Any]:
    """Summarize expected coverage of a validated daily price input."""
    dates = prices["trade_date"]
    return {
        "rows": len(prices),
        "symbols": sorted(prices["symbol"].unique().tolist()),
        "date_start": dates.min().isoformat(),
        "date_end": dates.max().isoformat(),
        "duplicate_keys": int(prices.duplicated(["symbol", "trade_date"]).sum()),
    }


def options_quality(options: pd.DataFrame) -> dict[str, Any]:
    """Summarize snapshot, expiry, side, and open-interest coverage."""
    snapshot_times = options["snapshot_at"]
    side_counts = options["option_type"].value_counts().to_dict()
    return {
        "rows": len(options),
        "underlyings": sorted(options["underlying"].unique().tolist()),
        "snapshot_start": snapshot_times.min().isoformat(),
        "snapshot_end": snapshot_times.max().isoformat(),
        "expiries": sorted(value.isoformat() for value in options["expiry"].unique()),
        "option_type_rows": {str(key): int(value) for key, value in side_counts.items()},
        "call_open_interest": float(
            options.loc[options["option_type"].eq("CE"), "open_interest"].sum()
        ),
        "put_open_interest": float(
            options.loc[options["option_type"].eq("PE"), "open_interest"].sum()
        ),
    }


def quality_warnings(options: pd.DataFrame, prices: pd.DataFrame) -> list[str]:
    """Return non-fatal coverage warnings; schema and row validity are enforced elsewhere."""
    warnings: list[str] = []
    if set(options["option_type"].unique()) != {"CE", "PE"}:
        warnings.append("options snapshot does not contain both CE and PE rows")
    if prices.empty:
        warnings.append("price input is absent; price indicators were not updated")
    return warnings


def alert_pipeline_failure(webhook_url: str, run_id: str, error_type: str) -> None:
    """Send a minimal failure notification to an explicitly configured HTTPS webhook."""
    parsed = urlsplit(webhook_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("ALERT_WEBHOOK_URL must be HTTPS and cannot contain URL credentials")
    body = json.dumps(
        {"text": f"BankNifty analytics pipeline failed (run {run_id}, {error_type})."}
    ).encode("utf-8")
    request = Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            if not 200 <= response.status < 300:
                raise OSError(f"Alert endpoint returned HTTP {response.status}")
    except (TimeoutError, URLError, OSError) as error:
        raise RuntimeError("Pipeline failure alert could not be delivered") from error

"""Validation for canonical daily OHLCV input."""

import pandas as pd

from nifty_options.validation.common import (
    DataValidationError,
    normalize_columns,
    numeric_column,
    require_columns,
)

REQUIRED = {"trade_date", "symbol", "open", "high", "low", "close", "volume"}


def validate_prices(frame: pd.DataFrame) -> pd.DataFrame:
    frame = normalize_columns(frame)
    if "date" in frame and "trade_date" not in frame:
        frame = frame.rename(columns={"date": "trade_date"})
    require_columns(frame, REQUIRED, "Price CSV")
    if frame.empty:
        raise DataValidationError("Price CSV has no data rows")
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.date
    if frame["trade_date"].isna().any():
        raise DataValidationError("Price CSV contains invalid trade_date values")
    frame["symbol"] = frame["symbol"].astype("string").str.strip().str.upper()
    if frame["symbol"].isna().any() or frame["symbol"].eq("").any():
        raise DataValidationError("Price CSV contains blank symbols")
    for column in ("open", "high", "low", "close", "volume"):
        numeric_column(frame, column, required=True)
    if (frame[["open", "high", "low", "close"]] <= 0).any().any():
        raise DataValidationError("OHLC prices must be positive")
    if (frame["volume"] < 0).any():
        raise DataValidationError("Volume cannot be negative")
    if (frame["high"] < frame[["open", "low", "close"]].max(axis=1)).any():
        raise DataValidationError("High must be greater than or equal to open, low, and close")
    if (frame["low"] > frame[["open", "high", "close"]].min(axis=1)).any():
        raise DataValidationError("Low must be less than or equal to open, high, and close")
    if frame.duplicated(["symbol", "trade_date"]).any():
        raise DataValidationError("Price CSV has duplicate symbol/trade_date rows")
    return frame[["trade_date", "symbol", "open", "high", "low", "close", "volume"]]

"""Validation for long-form options-chain snapshots."""

import pandas as pd

from nifty_options.validation.common import (
    DataValidationError,
    normalize_columns,
    numeric_column,
    require_columns,
)

REQUIRED = {
    "snapshot_at",
    "underlying",
    "expiry",
    "strike",
    "option_type",
    "open_interest",
    "iv",
    "underlying_price",
}
OPTION_TYPE_MAP = {"CE": "CE", "CALL": "CE", "PE": "PE", "PUT": "PE"}


def validate_option_chain(frame: pd.DataFrame) -> pd.DataFrame:
    frame = normalize_columns(frame)
    aliases = {
        "snapshot_date": "snapshot_at",
        "underlying_symbol": "underlying",
        "oi": "open_interest",
        "change_in_oi": "change_in_oi",
        "vol": "volume",
        "last": "last_price",
    }
    frame = frame.rename(
        columns={
            key: value for key, value in aliases.items() if key in frame and value not in frame
        }
    )
    require_columns(frame, REQUIRED, "Options CSV")
    if frame.empty:
        raise DataValidationError("Options CSV has no data rows")
    frame["snapshot_at"] = pd.to_datetime(frame["snapshot_at"], errors="coerce")
    frame["expiry"] = pd.to_datetime(frame["expiry"], errors="coerce").dt.date
    if frame["snapshot_at"].isna().any() or frame["expiry"].isna().any():
        raise DataValidationError("Options CSV contains an invalid snapshot_at or expiry")
    frame["underlying"] = frame["underlying"].astype("string").str.strip().str.upper()
    if frame["underlying"].isna().any() or frame["underlying"].eq("").any():
        raise DataValidationError("Options CSV contains a blank underlying")
    frame["option_type"] = (
        frame["option_type"].astype("string").str.strip().str.upper().map(OPTION_TYPE_MAP)
    )
    if frame["option_type"].isna().any():
        raise DataValidationError("option_type must be CE/CALL or PE/PUT")
    for column in ("strike", "open_interest", "iv", "underlying_price"):
        numeric_column(frame, column, required=True)
    for column in ("change_in_oi", "volume", "bid", "ask", "last_price", "underlying_price"):
        numeric_column(frame, column)
    if (
        (frame["strike"] <= 0).any()
        or (frame["open_interest"] < 0).any()
        or (frame["iv"] < 0).any()
    ):
        raise DataValidationError(
            "Strike must be positive; open_interest and iv cannot be negative"
        )
    if (frame["iv"] > 1000).any():
        raise DataValidationError(
            "IV values must be at most 1000 in the units supplied by the source"
        )
    if (frame["volume"] < 0).any() or (frame[["bid", "ask", "last_price"]] < 0).any().any():
        raise DataValidationError("Volume and option prices cannot be negative")
    key = ["snapshot_at", "underlying", "expiry", "strike", "option_type"]
    if frame.duplicated(key).any():
        raise DataValidationError(
            "Options CSV has duplicate snapshot/underlying/expiry/strike/type rows"
        )
    columns = [
        *key,
        "open_interest",
        "change_in_oi",
        "volume",
        "iv",
        "bid",
        "ask",
        "last_price",
        "underlying_price",
    ]
    return (
        frame[columns]
        .sort_values(["snapshot_at", "expiry", "strike", "option_type"])
        .reset_index(drop=True)
    )

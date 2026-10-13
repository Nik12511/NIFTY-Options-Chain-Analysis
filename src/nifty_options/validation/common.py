"""Shared CSV column and numeric validation helpers."""

import math

import pandas as pd


class DataValidationError(ValueError):
    """Raised when an input file does not meet the canonical data contract."""


def normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame.columns = [
        str(column).strip().casefold().replace(" ", "_").replace("-", "_")
        for column in frame.columns
    ]
    if frame.columns.duplicated().any():
        duplicates = sorted(set(frame.columns[frame.columns.duplicated()].tolist()))
        raise DataValidationError(f"Duplicate columns after normalization: {duplicates}")
    return frame


def require_columns(frame: pd.DataFrame, columns: set[str], source: str) -> None:
    missing = sorted(columns - set(frame.columns))
    if missing:
        raise DataValidationError(f"{source} is missing required columns: {', '.join(missing)}")


def numeric_column(frame: pd.DataFrame, name: str, *, required: bool = False) -> None:
    if name not in frame.columns:
        if required:
            raise DataValidationError(f"Missing required numeric column: {name}")
        frame[name] = 0.0
        return
    original = frame[name]
    converted = pd.to_numeric(original, errors="coerce")
    invalid = converted.isna() & original.notna() & original.astype(str).str.strip().ne("")
    if invalid.any():
        rows = (invalid[invalid].index[:5] + 2).tolist()
        raise DataValidationError(f"Column '{name}' has non-numeric values near CSV rows {rows}")
    non_finite = converted.map(lambda value: pd.notna(value) and not math.isfinite(value))
    if non_finite.any():
        raise DataValidationError(f"Column '{name}' contains an infinite value")
    if required and converted.isna().any():
        raise DataValidationError(f"Required column '{name}' contains blank values")
    frame[name] = converted.fillna(0.0) if not required else converted

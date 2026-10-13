"""Read standardized CSV source files."""

from pathlib import Path

import pandas as pd

from nifty_options.validation.options import validate_option_chain
from nifty_options.validation.prices import validate_prices


def _checked_csv(path: str | Path) -> Path:
    file_path = Path(path).expanduser()
    if file_path.suffix.casefold() != ".csv":
        raise ValueError("Input file must have a .csv extension")
    if not file_path.is_file():
        raise FileNotFoundError(f"CSV file does not exist or is not a regular file: {file_path}")
    from nifty_options.config import get_settings

    size = file_path.stat().st_size
    maximum = get_settings().max_csv_bytes
    if size > maximum:
        raise ValueError(f"CSV file is {size} bytes; configured maximum is {maximum} bytes")
    return file_path


def read_prices_csv(path: str | Path) -> pd.DataFrame:
    return validate_prices(pd.read_csv(_checked_csv(path)))


def read_options_csv(path: str | Path) -> pd.DataFrame:
    return validate_option_chain(pd.read_csv(_checked_csv(path)))

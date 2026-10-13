"""Shared synthetic fixtures for the project test suite."""

from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def options_csv() -> Path:
    return Path(__file__).parent / "fixtures" / "options_chain.csv"


@pytest.fixture
def prices_csv(tmp_path: Path) -> Path:
    dates = pd.bdate_range("2025-10-20", periods=55)
    closes = [10000.0 + index for index in range(len(dates))]
    frame = pd.DataFrame(
        {
            "trade_date": dates.date,
            "symbol": "BANKNIFTY",
            "open": [close - 0.5 for close in closes],
            "high": [close + 1 for close in closes],
            "low": [close - 1 for close in closes],
            "close": closes,
            "volume": 1000,
        }
    )
    path = tmp_path / "prices.csv"
    frame.to_csv(path, index=False)
    return path

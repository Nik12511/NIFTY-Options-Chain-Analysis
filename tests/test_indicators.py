"""Unit coverage for daily price indicators."""

import pandas as pd
import pytest

from nifty_options.indicators.prices import calculate_price_indicators


def test_calculates_sma20_sma50_and_rsi14_after_warmup() -> None:
    closes = [10000.0 + index for index in range(55)]
    prices = pd.DataFrame(
        {
            "trade_date": pd.bdate_range("2025-01-01", periods=len(closes)).date,
            "symbol": "BANKNIFTY",
            "close": closes,
        }
    )

    result = calculate_price_indicators(prices)
    latest = result.iloc[-1]

    assert latest["sma_20"] == pytest.approx(10044.5)
    assert latest["sma_50"] == pytest.approx(10029.5)
    assert latest["rsi_14"] == pytest.approx(100.0)
    assert pd.isna(result.iloc[18]["sma_20"])

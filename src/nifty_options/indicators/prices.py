"""Simple, explicitly parameterized daily price indicators."""

import pandas as pd


def calculate_price_indicators(prices: pd.DataFrame) -> pd.DataFrame:
    """Calculate SMA(20), SMA(50), and Wilder RSI(14) for each symbol."""
    result: list[pd.DataFrame] = []
    for symbol, group in prices.sort_values("trade_date").groupby("symbol", sort=False):
        close = group["close"].astype(float)
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
        relative_strength = avg_gain / avg_loss.where(avg_loss.ne(0))
        rsi = 100 - (100 / (1 + relative_strength))
        rsi = rsi.mask(avg_loss.eq(0) & avg_gain.gt(0), 100).mask(
            avg_loss.eq(0) & avg_gain.eq(0), 50
        )
        result.append(
            pd.DataFrame(
                {
                    "trade_date": group["trade_date"].values,
                    "symbol": symbol,
                    "sma_20": close.rolling(20, min_periods=20).mean().values,
                    "sma_50": close.rolling(50, min_periods=50).mean().values,
                    "rsi_14": rsi.values,
                }
            )
        )
    return (
        pd.concat(result, ignore_index=True)
        if result
        else pd.DataFrame(columns=["trade_date", "symbol", "sma_20", "sma_50", "rsi_14"])
    )

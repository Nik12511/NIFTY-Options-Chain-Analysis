"""PCR, max-pain, IV-smile, and strike-level open-interest calculations."""

import pandas as pd


def put_call_ratio(chain: pd.DataFrame) -> float | None:
    calls = chain.loc[chain["option_type"].eq("CE"), "open_interest"].sum()
    puts = chain.loc[chain["option_type"].eq("PE"), "open_interest"].sum()
    return float(puts / calls) if calls else None


def max_pain_strike(chain: pd.DataFrame) -> float | None:
    """Return strike minimizing aggregate expiry intrinsic payout weighted by OI."""
    if chain.empty:
        return None
    strikes = pd.Index(sorted(chain["strike"].unique()), dtype="float64")
    grouped = chain.pivot_table(
        index="strike",
        columns="option_type",
        values="open_interest",
        aggfunc="sum",
        fill_value=0,
    ).reindex(strikes, fill_value=0)
    calls = grouped.get("CE", pd.Series(0.0, index=strikes)).astype(float)
    puts = grouped.get("PE", pd.Series(0.0, index=strikes)).astype(float)

    call_oi_below = calls.cumsum().shift(1, fill_value=0)
    call_strike_oi_below = (
        (calls * strikes.to_series(index=strikes)).cumsum().shift(1, fill_value=0)
    )
    put_oi_above = puts.iloc[::-1].cumsum().iloc[::-1] - puts
    put_strike_oi_above = (puts * strikes.to_series(index=strikes)).iloc[::-1].cumsum().iloc[
        ::-1
    ] - puts * strikes.to_series(index=strikes)
    payouts = (
        strikes.to_series(index=strikes) * call_oi_below
        - call_strike_oi_below
        + put_strike_oi_above
        - strikes.to_series(index=strikes) * put_oi_above
    )
    return float(payouts.idxmin())


def iv_smile(chain: pd.DataFrame) -> pd.DataFrame:
    return chain[["strike", "option_type", "iv"]].sort_values(["option_type", "strike"])


def oi_distribution(chain: pd.DataFrame) -> pd.DataFrame:
    return (
        chain.pivot_table(
            index="strike",
            columns="option_type",
            values="open_interest",
            aggfunc="sum",
            fill_value=0,
        )
        .reindex(columns=["CE", "PE"], fill_value=0)
        .rename(columns={"CE": "call_oi", "PE": "put_oi"})
        .reset_index()
        .sort_values("strike")
    )


def summarize_snapshot(chain: pd.DataFrame) -> pd.DataFrame:
    rows = []
    group_keys = ["snapshot_at", "underlying", "expiry"]
    for (snapshot_at, underlying, expiry), snapshot in chain.groupby(group_keys, sort=True):
        prices = snapshot["underlying_price"].dropna()
        rows.append(
            {
                "snapshot_at": snapshot_at,
                "underlying": underlying,
                "expiry": expiry,
                "pcr": put_call_ratio(snapshot),
                "max_pain": max_pain_strike(snapshot),
                "underlying_price": float(prices.median()) if not prices.empty else None,
            }
        )
    return pd.DataFrame(rows)

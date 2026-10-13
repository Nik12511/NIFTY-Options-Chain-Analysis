"""Dashboard for stored price indicators and options-chain analytics."""

import os
from pathlib import Path
from threading import Thread

import pandas as pd
import streamlit as st

from nifty_options.analytics.options import iv_smile, oi_distribution
from nifty_options.config import get_settings
from nifty_options.observability import configure_logging
from nifty_options.scheduler import start_daily_scheduler

st.set_page_config(page_title="BankNifty Options Analytics", page_icon="📈", layout="wide")
settings = get_settings()
configure_logging(settings.log_level)


@st.cache_resource
def initialize_scheduler() -> Thread | None:
    return start_daily_scheduler()


initialize_scheduler()
st.title("BankNifty Options Analytics")
if os.getenv("DEMO_DATA", "").strip().casefold() == "true":
    st.warning(
        "SYNTHETIC DEMO DATA — This bundled dataset is illustrative, not live market data. "
        "Do not use it for trading or investment decisions."
    )
database_path = settings.database_path


def database_version(path: str) -> tuple[int, int, int, int]:
    """Use database and WAL metadata to invalidate cached reads after imports."""
    stat = Path(path).stat()
    wal_path = Path(f"{path}.wal")
    wal_stat = wal_path.stat() if wal_path.exists() else None
    return (
        stat.st_mtime_ns,
        stat.st_size,
        wal_stat.st_mtime_ns if wal_stat else 0,
        wal_stat.st_size if wal_stat else 0,
    )


@st.cache_data(ttl=300, max_entries=32)
def load_metadata(
    path: str, version: tuple[int, int, int, int]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    import duckdb

    connection = duckdb.connect(path)
    try:
        analytics = connection.execute(
            "SELECT * FROM option_analytics ORDER BY underlying, expiry, snapshot_at"
        ).df()
        symbols = connection.execute("SELECT DISTINCT symbol FROM prices ORDER BY symbol").df()
    finally:
        connection.close()
    return analytics, symbols


@st.cache_data(ttl=300, max_entries=32)
def load_snapshot(
    path: str,
    version: tuple[int, int, int, int],
    underlying: str,
    expiry: str,
    snapshot_at: str,
) -> pd.DataFrame:
    import duckdb

    connection = duckdb.connect(path)
    try:
        return connection.execute(
            """SELECT strike, option_type, iv, open_interest
               FROM option_chain
               WHERE underlying = ? AND expiry = ? AND snapshot_at = ?
               ORDER BY strike, option_type""",
            [underlying, pd.Timestamp(expiry).date(), pd.Timestamp(snapshot_at).to_pydatetime()],
        ).df()
    finally:
        connection.close()


@st.cache_data(ttl=300, max_entries=32)
def load_latest_price(path: str, version: tuple[int, int, int, int], symbol: str) -> pd.DataFrame:
    import duckdb

    connection = duckdb.connect(path)
    try:
        return connection.execute(
            """SELECT p.symbol, p.trade_date, p.close, i.name, i.value
               FROM prices p
               LEFT JOIN indicators i USING (symbol, trade_date)
               WHERE p.symbol = ?
                 AND p.trade_date = (SELECT MAX(trade_date) FROM prices WHERE symbol = ?)
               ORDER BY i.name""",
            [symbol, symbol],
        ).df()
    finally:
        connection.close()


if not Path(database_path).exists():
    st.info(
        "No database yet. Import an options CSV with "
        "`python -m nifty_options.pipeline --options-csv <file.csv>`."
    )
    st.stop()

version = database_version(str(database_path))
analytics, symbols = load_metadata(str(database_path), version)
if analytics.empty:
    st.info(
        "The database has no options snapshots yet. Import a valid options-chain CSV "
        "to populate the dashboard."
    )
    st.stop()

underlying_values = sorted(analytics["underlying"].dropna().unique())
underlying = st.selectbox(
    "Underlying",
    underlying_values,
    index=underlying_values.index("BANKNIFTY") if "BANKNIFTY" in underlying_values else 0,
)
subset = analytics.loc[analytics["underlying"].eq(underlying)].copy()
expiries = sorted(subset["expiry"].dropna().unique())
expiry = st.selectbox("Expiry", expiries, index=0)
series = subset.loc[subset["expiry"].eq(expiry)].sort_values("snapshot_at")
snapshots = sorted(series["snapshot_at"].unique())
snapshot_at = st.selectbox("Snapshot", snapshots, index=len(snapshots) - 1)
snapshot = load_snapshot(
    str(database_path), version, underlying, str(expiry), pd.Timestamp(snapshot_at).isoformat()
)

selected_metrics = series.loc[series["snapshot_at"].eq(snapshot_at)].iloc[-1]
m1, m2, m3 = st.columns(3)
m1.metric(
    "Put / Call OI ratio",
    "—" if pd.isna(selected_metrics["pcr"]) else f"{selected_metrics['pcr']:.3f}",
)
m2.metric(
    "Max pain strike",
    "—" if pd.isna(selected_metrics["max_pain"]) else f"{selected_metrics['max_pain']:,.2f}",
)
m3.metric(
    "Underlying price",
    "—"
    if pd.isna(selected_metrics["underlying_price"])
    else f"{selected_metrics['underlying_price']:,.2f}",
)

left, right = st.columns(2)
with left:
    st.subheader("PCR history")
    pcr_history = series.set_index("snapshot_at")[["pcr"]]
    st.line_chart(pcr_history, y="pcr", height=280)
with right:
    st.subheader("Max pain history")
    pain_history = series.set_index("snapshot_at")[["max_pain"]]
    st.line_chart(pain_history, y="max_pain", height=280)

left, right = st.columns(2)
with left:
    st.subheader("Implied volatility by strike")
    smile = (
        iv_smile(snapshot)
        .pivot_table(index="strike", columns="option_type", values="iv", aggfunc="mean")
        .sort_index()
    )
    st.line_chart(smile, height=300)
    st.caption("IV values use the units provided in the source CSV (commonly percent).")
with right:
    st.subheader("Open interest by strike")
    distribution = oi_distribution(snapshot).set_index("strike")
    st.bar_chart(distribution, height=300)

if not symbols.empty:
    st.subheader("Latest price indicators")
    available_symbols = sorted(symbols["symbol"].dropna().unique())
    symbol = st.selectbox("Price symbol", available_symbols)
    latest = load_latest_price(str(database_path), version, symbol)
    latest_values = latest.pivot_table(
        index="trade_date", columns="name", values="value", aggfunc="last"
    )
    row = latest_values.iloc[-1] if not latest_values.empty else pd.Series(dtype=float)
    close = float(latest["close"].iloc[-1])
    metrics = st.columns(4)
    metrics[0].metric("Close", f"{close:,.2f}")
    for slot, key, label in zip(
        metrics[1:], ("sma_20", "sma_50", "rsi_14"), ("SMA 20", "SMA 50", "RSI 14"), strict=True
    ):
        value = row.get(key)
        slot.metric(label, "—" if pd.isna(value) or value is None else f"{value:,.2f}")

st.caption(f"Data store: {database_path}")

"""DuckDB schema and idempotent batch writes."""

from pathlib import Path

import duckdb
import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    symbol VARCHAR NOT NULL,
    trade_date DATE NOT NULL,
    open DOUBLE NOT NULL,
    high DOUBLE NOT NULL,
    low DOUBLE NOT NULL,
    close DOUBLE NOT NULL,
    volume DOUBLE NOT NULL,
    PRIMARY KEY (symbol, trade_date)
);
CREATE TABLE IF NOT EXISTS indicators (
    symbol VARCHAR NOT NULL,
    trade_date DATE NOT NULL,
    name VARCHAR NOT NULL,
    value DOUBLE,
    parameters VARCHAR NOT NULL,
    PRIMARY KEY (symbol, trade_date, name)
);
CREATE TABLE IF NOT EXISTS option_chain (
    snapshot_at TIMESTAMP NOT NULL,
    underlying VARCHAR NOT NULL,
    expiry DATE NOT NULL,
    strike DOUBLE NOT NULL,
    option_type VARCHAR NOT NULL,
    open_interest DOUBLE NOT NULL,
    change_in_oi DOUBLE NOT NULL,
    volume DOUBLE NOT NULL,
    iv DOUBLE NOT NULL,
    bid DOUBLE NOT NULL,
    ask DOUBLE NOT NULL,
    last_price DOUBLE NOT NULL,
    underlying_price DOUBLE NOT NULL,
    PRIMARY KEY (snapshot_at, underlying, expiry, strike, option_type)
);
CREATE TABLE IF NOT EXISTS option_analytics (
    snapshot_at TIMESTAMP NOT NULL,
    underlying VARCHAR NOT NULL,
    expiry DATE NOT NULL,
    pcr DOUBLE,
    max_pain DOUBLE,
    underlying_price DOUBLE,
    PRIMARY KEY (snapshot_at, underlying, expiry)
);
"""

TABLE_COLUMNS = {
    "prices": {"symbol", "trade_date", "open", "high", "low", "close", "volume"},
    "indicators": {"symbol", "trade_date", "name", "value", "parameters"},
    "option_chain": {
        "snapshot_at",
        "underlying",
        "expiry",
        "strike",
        "option_type",
        "open_interest",
        "change_in_oi",
        "volume",
        "iv",
        "bid",
        "ask",
        "last_price",
        "underlying_price",
    },
    "option_analytics": {
        "snapshot_at",
        "underlying",
        "expiry",
        "pcr",
        "max_pain",
        "underlying_price",
    },
}


def connect(database_path: str | Path) -> duckdb.DuckDBPyConnection:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(path))
    connection.execute(SCHEMA)
    return connection


def replace_rows(
    connection: duckdb.DuckDBPyConnection, table: str, frame: pd.DataFrame, columns: list[str]
) -> None:
    if frame.empty:
        return
    if table not in TABLE_COLUMNS or not set(columns) <= TABLE_COLUMNS[table]:
        raise ValueError("Unsupported table or column in database batch write")
    relation_name = "_batch_" + table
    connection.register(relation_name, frame[columns])
    selected = ", ".join(columns)
    try:
        connection.execute(
            f"INSERT OR REPLACE INTO {table} ({selected}) SELECT {selected} FROM {relation_name}"
        )
    finally:
        connection.unregister(relation_name)


def store_prices(connection: duckdb.DuckDBPyConnection, prices: pd.DataFrame) -> None:
    replace_rows(
        connection,
        "prices",
        prices,
        ["symbol", "trade_date", "open", "high", "low", "close", "volume"],
    )


def store_indicators(connection: duckdb.DuckDBPyConnection, indicators: pd.DataFrame) -> None:
    if indicators.empty:
        return
    long = indicators.melt(
        id_vars=["symbol", "trade_date"], var_name="name", value_name="value"
    ).dropna(subset=["value"])
    params = {"sma_20": "window=20", "sma_50": "window=50", "rsi_14": "window=14;method=Wilder"}
    long["parameters"] = long["name"].map(params)
    replace_rows(
        connection, "indicators", long, ["symbol", "trade_date", "name", "value", "parameters"]
    )


def store_option_chain(connection: duckdb.DuckDBPyConnection, chain: pd.DataFrame) -> None:
    columns = [
        "snapshot_at",
        "underlying",
        "expiry",
        "strike",
        "option_type",
        "open_interest",
        "change_in_oi",
        "volume",
        "iv",
        "bid",
        "ask",
        "last_price",
        "underlying_price",
    ]
    replace_rows(connection, "option_chain", chain, columns)


def store_option_analytics(connection: duckdb.DuckDBPyConnection, analytics: pd.DataFrame) -> None:
    columns = ["snapshot_at", "underlying", "expiry", "pcr", "max_pain", "underlying_price"]
    replace_rows(connection, "option_analytics", analytics, columns)

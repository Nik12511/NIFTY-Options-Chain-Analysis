"""Run an idempotent import and calculation pass from standardized CSV files."""

import argparse
import logging
from pathlib import Path
from time import monotonic
from uuid import uuid4

import pandas as pd

from nifty_options.analytics.options import summarize_snapshot
from nifty_options.config import get_settings
from nifty_options.indicators.prices import calculate_price_indicators
from nifty_options.ingestion.csv_files import read_options_csv, read_prices_csv
from nifty_options.observability import (
    alert_pipeline_failure,
    configure_logging,
    options_quality,
    price_quality,
    quality_warnings,
)
from nifty_options.storage.database import (
    connect,
    store_indicators,
    store_option_analytics,
    store_option_chain,
    store_prices,
)

logger = logging.getLogger("nifty_options.pipeline")


def run_pipeline(
    options_csv: str | Path,
    prices_csv: str | Path | None = None,
    database_path: str | Path | None = None,
) -> None:
    settings = get_settings()
    db_path = Path(database_path) if database_path else settings.database_path
    configure_logging(settings.log_level)
    run_id = uuid4().hex
    started = monotonic()
    connection = None
    transaction_open = False
    try:
        logger.info(
            "Pipeline run started",
            extra={"event": "pipeline_started", "run_id": run_id, "database": str(db_path)},
        )
        options = read_options_csv(options_csv)
        prices = read_prices_csv(prices_csv) if prices_csv else pd.DataFrame()
        option_metrics = options_quality(options)
        price_metrics = price_quality(prices) if not prices.empty else {"rows": 0}
        logger.info(
            "Input quality summary",
            extra={
                "event": "input_quality",
                "run_id": run_id,
                "options": option_metrics,
                "prices": price_metrics,
            },
        )
        warnings = quality_warnings(options, prices)
        for warning in warnings:
            logger.warning(
                warning,
                extra={"event": "data_quality_warning", "run_id": run_id},
            )
        connection = connect(db_path)
        connection.execute("BEGIN TRANSACTION")
        transaction_open = True
        store_option_chain(connection, options)
        store_option_analytics(connection, summarize_snapshot(options))
        if not prices.empty:
            store_prices(connection, prices)
            changed_symbols = sorted(prices["symbol"].unique().tolist())
            placeholders = ", ".join("?" for _ in changed_symbols)
            history = connection.execute(
                "SELECT symbol, trade_date, close FROM prices "
                f"WHERE symbol IN ({placeholders}) ORDER BY symbol, trade_date",
                changed_symbols,
            ).df()
            recalculated = calculate_price_indicators(history)
            earliest_changed = (
                prices.assign(trade_date=pd.to_datetime(prices["trade_date"]))
                .groupby("symbol")["trade_date"]
                .min()
            )
            recalculated["earliest_changed"] = recalculated["symbol"].map(earliest_changed)
            recalculated = recalculated.loc[
                recalculated["trade_date"] >= recalculated["earliest_changed"]
            ].drop(columns="earliest_changed")
            store_indicators(connection, recalculated)
        connection.execute("COMMIT")
        transaction_open = False
        logger.info(
            "Pipeline run completed",
            extra={
                "event": "pipeline_completed",
                "run_id": run_id,
                "options_rows": len(options),
                "price_rows": len(prices),
                "duration_seconds": round(monotonic() - started, 3),
                "quality_warning_count": len(warnings),
            },
        )
    except Exception as error:
        if connection is not None and transaction_open:
            connection.execute("ROLLBACK")
        logger.exception(
            "Pipeline run failed",
            extra={
                "event": "pipeline_failed",
                "run_id": run_id,
                "duration_seconds": round(monotonic() - started, 3),
                "error_type": type(error).__name__,
            },
        )
        if settings.alert_webhook_url:
            try:
                alert_pipeline_failure(settings.alert_webhook_url, run_id, type(error).__name__)
                logger.info(
                    "Pipeline failure alert delivered",
                    extra={"event": "pipeline_alert_delivered", "run_id": run_id},
                )
            except Exception:
                logger.exception(
                    "Pipeline failure alert could not be delivered",
                    extra={"event": "pipeline_alert_failed", "run_id": run_id},
                )
        raise
    finally:
        if connection is not None:
            connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import BankNifty prices and an options-chain CSV into DuckDB"
    )
    parser.add_argument("--options-csv", required=True, help="Long-form options-chain CSV")
    parser.add_argument("--prices-csv", help="Optional daily OHLCV CSV")
    parser.add_argument("--database", help="DuckDB file (defaults to DATABASE_PATH)")
    args = parser.parse_args()
    run_pipeline(args.options_csv, args.prices_csv, args.database)


if __name__ == "__main__":
    main()

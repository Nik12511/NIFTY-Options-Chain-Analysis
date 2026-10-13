"""Integration coverage for CSV ingestion, DuckDB persistence, and calculations."""

import duckdb
import pytest

from nifty_options.pipeline import run_pipeline


def test_pipeline_persists_idempotently_and_computes_outputs(
    options_csv, prices_csv, tmp_path
) -> None:
    database = tmp_path / "analytics.duckdb"

    run_pipeline(options_csv, prices_csv, database)
    run_pipeline(options_csv, prices_csv, database)

    connection = duckdb.connect(str(database), read_only=True)
    try:
        assert connection.execute("SELECT count(*) FROM option_chain").fetchone()[0] == 6
        assert connection.execute("SELECT count(*) FROM option_analytics").fetchone()[0] == 1
        pcr, max_pain = connection.execute("SELECT pcr, max_pain FROM option_analytics").fetchone()
        assert pcr == pytest.approx(0.75)
        assert max_pain == pytest.approx(110.0)
        assert connection.execute("SELECT count(*) FROM prices").fetchone()[0] == 55
        assert connection.execute("SELECT count(*) FROM indicators").fetchone()[0] > 0
        sma_20 = connection.execute("""
            SELECT value FROM indicators
            WHERE symbol = 'BANKNIFTY' AND name = 'sma_20'
            ORDER BY trade_date DESC LIMIT 1
        """).fetchone()[0]
        assert sma_20 == pytest.approx(10044.5)
    finally:
        connection.close()

# Resume-safe project bullets

These bullets describe implemented features and do not claim unmeasured performance or business impact. Adjust tense and detail to match the work you personally completed.

- Built a Python data pipeline that validates daily OHLCV and options-chain CSVs, computes price indicators and options analytics, and writes results transactionally to DuckDB.
- Developed a Streamlit dashboard for PCR and max-pain history, implied-volatility smiles, open interest by strike, and latest price indicators.
- Containerized the dashboard with Docker Compose and added an opt-in scheduled CSV import, structured JSON logging, input-quality warnings, and configurable HTTPS failure alerts.
- Added Ruff and Mypy checks, pytest coverage, dependency locks, and a GitHub Actions workflow for quality checks and image builds.

## Adding measured results later

No throughput, latency, data-volume, uptime, or accuracy measurements are currently claimed. To add a number, save the benchmark method and results, including hardware/runtime, fixture or dataset size, repetitions, and baseline. Example template (fill only with measured results):

> Reduced [named operation] from [baseline] to [result] on [dataset size] using [repeatable method] on [environment].

Do not use synthetic fixture counts as live-market coverage or a production-scale result. Do not revive historical backtest figures unless the backtest is re-run and verified against the refactored project.

# Code review checklist

- [ ] Data contracts and accepted CSV aliases are explicit; malformed and duplicate rows fail with useful errors.
- [ ] Indicator and options math matches the documented definition and has focused tests, including zero and boundary cases.
- [ ] Re-importing the same trading date or snapshot is deterministic and does not create duplicate rows.
- [ ] Database writes remain parameterized or use registered data frames; external text is never interpolated into SQL identifiers.
- [ ] Secrets stay in ignored local configuration or the deployment secret store; logs omit credentials and sensitive query values.
- [ ] Network calls have timeouts, bounded retries, rate limiting, response-size limits, and clear non-retryable failures.
- [ ] New public functions have type annotations; Ruff and Mypy pass.
- [ ] Dashboard queries handle an empty or partial database and cache data with a bounded lifetime.
- [ ] Documentation and example data reflect real implemented behavior; performance or resume claims have measured evidence.

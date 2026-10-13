"""Unit coverage for options-chain metrics."""

import pandas as pd
import pytest

from nifty_options.analytics.options import max_pain_strike, put_call_ratio


@pytest.fixture
def chain() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "strike": [100, 110, 120, 100, 110, 120],
            "option_type": ["CE", "CE", "CE", "PE", "PE", "PE"],
            "open_interest": [10, 20, 10, 5, 20, 5],
        }
    )


def test_put_call_ratio_uses_put_oi_divided_by_call_oi(chain: pd.DataFrame) -> None:
    assert put_call_ratio(chain) == pytest.approx(0.75)


def test_put_call_ratio_is_undefined_when_call_oi_is_zero() -> None:
    chain = pd.DataFrame({"option_type": ["PE"], "open_interest": [10]})
    assert put_call_ratio(chain) is None


def test_max_pain_minimizes_oi_weighted_intrinsic_payout(chain: pd.DataFrame) -> None:
    assert max_pain_strike(chain) == 110

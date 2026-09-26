import numpy as np
import pandas as pd
import pytest

from mijang.indicators import (
    beta_alpha,
    cagr,
    compute_indicators,
    daily_returns,
    max_drawdown,
    total_return,
    win_rate,
)


def series(values, start="2020-01-01"):
    idx = pd.bdate_range(start, periods=len(values))
    return pd.Series(values, index=idx, dtype=float)


def test_total_return():
    assert total_return(series([100, 110, 150])) == pytest.approx(0.5)


def test_cagr_two_years_doubling():
    idx = pd.to_datetime(["2020-01-01", "2022-01-01"])
    p = pd.Series([100.0, 200.0], index=idx)
    assert cagr(p) == pytest.approx(2 ** (365.25 / 731) - 1)


def test_max_drawdown():
    assert max_drawdown(series([100, 120, 60, 90, 130])) == pytest.approx(-0.5)


def test_win_rate():
    r = daily_returns(series([100, 101, 100, 102, 103]))
    assert win_rate(r) == pytest.approx(0.75)


def test_beta_of_leveraged_series_is_two():
    rng = np.random.default_rng(0)
    b = pd.Series(rng.normal(0, 0.01, 500), index=pd.bdate_range("2020-01-01", periods=500))
    beta, alpha = beta_alpha(2 * b, b)
    assert beta == pytest.approx(2.0)
    assert alpha == pytest.approx(0.0, abs=1e-12)


def test_compute_indicators_has_ten_keys():
    rng = np.random.default_rng(1)
    p = series(100 * np.cumprod(1 + rng.normal(0.0005, 0.01, 300)))
    bench = series(100 * np.cumprod(1 + rng.normal(0.0004, 0.008, 300)))
    result = compute_indicators(p, bench, risk_free=0.04)
    assert len(result) == 10
    assert all(np.isfinite(v) for v in result.values())

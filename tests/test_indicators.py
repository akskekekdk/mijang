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


def test_rank_skips_short_history_and_sorts():
    from mijang.top20 import load_universe, rank

    idx = pd.bdate_range("2021-01-01", "2026-01-01")
    n = len(idx)
    prices = pd.DataFrame(
        {
            "SLOW": np.linspace(100, 150, n),
            "FAST": np.linspace(100, 400, n),
            "NEW": [np.nan] * (n // 2) + list(np.linspace(10, 100, n - n // 2)),
        },
        index=idx,
    )
    result = rank(prices, top=20)
    assert list(result["ticker"]) == ["FAST", "SLOW"]
    assert result.loc[1, "return_5y"] == pytest.approx(3.0)
    assert load_universe()["NVDA"] == "엔비디아"


def test_model_learns_planted_signal_without_lookahead():
    """모멘텀이 강한 종목이 계속 오르도록 만든 가짜 시장에서 학습·예측이 동작하는지."""
    from mijang import model as m

    rng = np.random.default_rng(3)
    idx = pd.bdate_range("2015-01-01", "2021-12-31")
    drifts = np.linspace(-0.0005, 0.0015, 30)
    rets = rng.normal(drifts, 0.01, size=(len(idx), 30))
    prices = pd.DataFrame(100 * np.cumprod(1 + rets, axis=0), index=idx,
                          columns=[f"T{i}" for i in range(30)])
    bench = pd.Series(100 * np.cumprod(1 + rng.normal(0.0004, 0.008, len(idx))), index=idx)

    result = m.predict(prices, bench, {"T29": "최고"}, top=5)
    assert len(result["stocks"]) == 5
    assert result["backtest"]["top_avg_excess_3m"] > result["backtest"]["universe_avg_excess_3m"]
    # 추세가 강한 절반(T15~T29)에서만 뽑혀야 한다
    assert {s["ticker"] for s in result["stocks"]} <= {f"T{i}" for i in range(15, 30)}
    # 최근 데이터(정답 미확정)는 학습에 쓰이지 않았는지
    data = m.build_dataset(prices, bench)
    last = data[data["date"] == data["date"].max()]
    assert last["fwd_excess"].isna().all()

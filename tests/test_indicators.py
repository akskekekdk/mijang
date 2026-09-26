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
    assert result["accuracy"]["avg_excess_3m"] > result["accuracy"]["universe_avg_excess_3m"]
    assert sum(r["chosen"] for r in result["methods"]) == 1
    assert len(result["methods"]) == len(m.METHODS) + len(m.MIXES)
    assert all(len(r["components"]) >= 3 for r in result["methods"] if r["kind"] == "혼합")
    # 근거: 모든 후보에 지표표·기여도·유사사례가 있고, 추천 종목에는 이유 문장이 있다
    d = result["details"][result["stocks"][0]["ticker"]]
    assert set(d["values"]) == set(m.FEATURES) and d["contrib"]["cagr"] is None
    assert d["similar"]["n"] == m.SIMILAR_K and len(d["similar"]["examples"]) == 3
    assert d["recommended"] and d["rank"] == 1
    assert len(result["details"]) == 30
    assert [f["key"] for f in result["features"]] == m.FEATURES
    # 하루치 추천은 잡음이 있으므로: 평균적으로 강한 종목이고, 5개 중 4개 이상은 강한 절반(T15~T29)
    picked = [int(s["ticker"][1:]) for s in result["stocks"]]
    assert np.mean(picked) > 17
    assert sum(i >= 15 for i in picked) >= 4
    # 최근 데이터(정답 미확정)는 학습에 쓰이지 않았는지
    data = m.build_dataset(prices, bench)
    last = data[data["date"] == data["date"].max()]
    assert last["fwd_excess"].isna().all()


def test_technical_indicators_on_known_series():
    from mijang.model import WINDOW, technical

    idx = pd.bdate_range("2020-01-01", periods=WINDOW + 1)
    rising = pd.Series(np.linspace(100, 200, WINDOW + 1), index=idx)
    t = technical(rising, pd.Series(1000.0, index=idx))
    assert t["rsi14"] == 100.0  # 매일 오르면 RSI 100
    assert t["from_high"] == 0.0
    assert t["from_low"] == pytest.approx(1.0)
    assert t["ma200_gap"] > 0 and t["macd_hist"] >= 0
    assert t["volume_trend"] == pytest.approx(0.0)


def test_contributions_follow_rule_weights():
    """규칙 방법에선 쓰인 지표만 기여도가 있고, 방향이 맞아야 한다."""
    from mijang import model as m

    rng = np.random.default_rng(0)
    today = pd.DataFrame(rng.random((50, len(m.FEATURES))), columns=m.FEATURES)
    predictor = m._rule({"mom_12_1": 1})(today)
    c = m.contributions(predictor, today)
    best = today["mom_12_1"].idxmax()
    assert c.loc[best, "mom_12_1"] > 0
    assert (c.drop(columns="mom_12_1").abs() < 1e-9).all().all()


def test_mix_predictor_averages_component_ranks():
    """혼합 예측은 구성 방법 순위의 평균이라, 두 규칙이 1등으로 꼽은 종목이 1등이어야 한다."""
    from mijang import model as m

    rng = np.random.default_rng(1)
    today = pd.DataFrame(rng.random((40, len(m.FEATURES))), columns=m.FEATURES)
    today.loc[7, ["mom_12_1", "sharpe"]] = 1.0
    chosen = {"key": "mix", "components": ["momentum", "sharpe"]}
    predictor = m.build_predictor(chosen, today.assign(fwd_excess=0.0, date=0), today)
    scores = predictor(today)
    assert scores.argmax() == 7 and scores.max() == pytest.approx(1.0)

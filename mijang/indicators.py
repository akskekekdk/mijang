"""미국 주식 수익률 평가를 위한 10가지 핵심 지표.

모든 함수는 일간 종가(pandas.Series, DatetimeIndex)를 입력으로 받는다.
연환산은 미국 시장 연간 거래일 252일 기준.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252

INDICATOR_LABELS = {
    "total_return": "1. 누적 수익률 (Total Return)",
    "cagr": "2. 연평균 복리 수익률 (CAGR)",
    "volatility": "3. 연환산 변동성 (Volatility)",
    "sharpe": "4. 샤프 지수 (Sharpe Ratio)",
    "sortino": "5. 소르티노 지수 (Sortino Ratio)",
    "mdd": "6. 최대 낙폭 (MDD)",
    "calmar": "7. 칼마 지수 (Calmar Ratio)",
    "beta": "8. 베타 (Beta, vs 벤치마크)",
    "alpha": "9. 젠센 알파 (Jensen's Alpha, 연환산)",
    "win_rate": "10. 일간 승률 (Win Rate)",
}

PERCENT_KEYS = {"total_return", "cagr", "volatility", "mdd", "alpha", "win_rate"}


def daily_returns(prices: pd.Series) -> pd.Series:
    return prices.pct_change().dropna()


def total_return(prices: pd.Series) -> float:
    """기간 전체 수익률: 마지막가 / 첫가 - 1."""
    return float(prices.iloc[-1] / prices.iloc[0] - 1)


def cagr(prices: pd.Series) -> float:
    """연평균 복리 수익률. 실제 달력 일수(365.25일=1년) 기준."""
    years = (prices.index[-1] - prices.index[0]).days / 365.25
    if years <= 0:
        return float("nan")
    return float((prices.iloc[-1] / prices.iloc[0]) ** (1 / years) - 1)


def volatility(returns: pd.Series) -> float:
    """일간 수익률 표준편차 × √252."""
    return float(returns.std() * np.sqrt(TRADING_DAYS))


def sharpe(returns: pd.Series, risk_free: float = 0.0) -> float:
    """(연환산 초과수익) / 연환산 변동성."""
    excess = returns - risk_free / TRADING_DAYS
    std = excess.std()
    if std == 0:
        return float("nan")
    return float(excess.mean() / std * np.sqrt(TRADING_DAYS))


def sortino(returns: pd.Series, risk_free: float = 0.0) -> float:
    """샤프와 같지만 하락 변동성(downside deviation)만 위험으로 본다."""
    excess = returns - risk_free / TRADING_DAYS
    downside = np.sqrt((np.minimum(excess, 0) ** 2).mean())
    if downside == 0:
        return float("nan")
    return float(excess.mean() / downside * np.sqrt(TRADING_DAYS))


def max_drawdown(prices: pd.Series) -> float:
    """고점 대비 최대 하락률 (음수)."""
    drawdown = prices / prices.cummax() - 1
    return float(drawdown.min())


def calmar(prices: pd.Series) -> float:
    """CAGR / |MDD|."""
    mdd = max_drawdown(prices)
    if mdd == 0:
        return float("nan")
    return float(cagr(prices) / abs(mdd))


def beta_alpha(
    returns: pd.Series, bench_returns: pd.Series, risk_free: float = 0.0
) -> tuple[float, float]:
    """벤치마크 대비 베타와 연환산 젠센 알파."""
    rf = risk_free / TRADING_DAYS
    joined = pd.concat([returns, bench_returns], axis=1, join="inner").dropna()
    if len(joined) < 2:
        return float("nan"), float("nan")
    r, b = joined.iloc[:, 0] - rf, joined.iloc[:, 1] - rf
    var = b.var()
    if var == 0:
        return float("nan"), float("nan")
    beta = r.cov(b) / var
    alpha = (r.mean() - beta * b.mean()) * TRADING_DAYS
    return float(beta), float(alpha)


def win_rate(returns: pd.Series) -> float:
    """수익이 난 거래일의 비율."""
    if len(returns) == 0:
        return float("nan")
    return float((returns > 0).mean())


def compute_indicators(
    prices: pd.Series,
    benchmark: pd.Series | None = None,
    risk_free: float = 0.0,
) -> dict[str, float]:
    """10가지 지표를 한 번에 계산한다.

    risk_free: 연 무위험 수익률 (예: 미국 3개월 국채 0.04).
    """
    prices = prices.dropna()
    rets = daily_returns(prices)
    if benchmark is not None:
        beta, alpha = beta_alpha(rets, daily_returns(benchmark.dropna()), risk_free)
    else:
        beta, alpha = float("nan"), float("nan")
    return {
        "total_return": total_return(prices),
        "cagr": cagr(prices),
        "volatility": volatility(rets),
        "sharpe": sharpe(rets, risk_free),
        "sortino": sortino(rets, risk_free),
        "mdd": max_drawdown(prices),
        "calmar": calmar(prices),
        "beta": beta,
        "alpha": alpha,
        "win_rate": win_rate(rets),
    }

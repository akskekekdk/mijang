"""과거 지표 → 미래 수익률 학습으로 유망 종목 예측: python -m mijang.model

1. 매월 말, 종목마다 직전 1년 가격으로 10대 지표 + 모멘텀 지표를 계산한다.
2. 정답: 그 뒤 3개월(63거래일) 동안 S&P 500(SPY)보다 많이 올랐는가 (1/0).
3. 그래디언트 부스팅 분류기로 "지표 → SPY를 이길 확률"을 학습한다.
4. 연도별 워크포워드 백테스트(과거로만 학습 → 다음 해 예측)로 실제 성능을 잰다.
5. 전체 데이터로 다시 학습해 오늘 지표로 확률을 예측하고 상위 20개를 고른다.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

from .indicators import compute_indicators
from .top20 import load_universe

WINDOW = 252  # 지표 계산 구간: 1년
HORIZON = 63  # 예측 구간: 3개월
BENCHMARK = "SPY"
OUTPUT = Path(__file__).resolve().parent.parent / "data" / "predictions.json"

INDICATOR_KEYS = [
    "total_return", "cagr", "volatility", "sharpe", "sortino",
    "mdd", "calmar", "beta", "alpha", "win_rate",
]
FEATURES = INDICATOR_KEYS + ["mom_1m", "mom_3m", "from_high"]


def features_at(prices: pd.DataFrame, bench: pd.Series, i: int) -> pd.DataFrame:
    """i번째 거래일 기준, 직전 WINDOW일로 계산한 종목별 지표."""
    window = prices.iloc[i - WINDOW : i + 1]
    bench_w = bench.iloc[i - WINDOW : i + 1]
    rows = {}
    for ticker in prices.columns:
        p = window[ticker]
        if p.isna().any():
            continue  # 1년치 데이터가 온전하지 않으면 제외
        row = compute_indicators(p, bench_w)
        row["mom_1m"] = p.iloc[-1] / p.iloc[-22] - 1
        row["mom_3m"] = p.iloc[-1] / p.iloc[-64] - 1
        row["from_high"] = p.iloc[-1] / p.max() - 1
        rows[ticker] = row
    return pd.DataFrame.from_dict(rows, orient="index")[FEATURES] if rows else pd.DataFrame(columns=FEATURES)


def rebalance_days(index: pd.DatetimeIndex) -> list[int]:
    """각 달의 마지막 거래일 위치 + 가장 최근 거래일."""
    s = pd.Series(np.arange(len(index)), index=index)
    days = s.groupby([index.year, index.month]).max().tolist()
    if days[-1] != len(index) - 1:
        days.append(len(index) - 1)
    return [d for d in days if d >= WINDOW]


def build_dataset(prices: pd.DataFrame, bench: pd.Series) -> pd.DataFrame:
    """(날짜, 종목)별 지표와 정답. 미래 3개월이 아직 안 지난 행은 정답이 NaN."""
    frames = []
    for i in rebalance_days(prices.index):
        feats = features_at(prices, bench, i)
        if feats.empty:
            continue
        if i + HORIZON < len(prices):
            fwd = prices.iloc[i + HORIZON] / prices.iloc[i] - 1
            fwd_bench = bench.iloc[i + HORIZON] / bench.iloc[i] - 1
            feats["fwd_excess"] = (fwd - fwd_bench).reindex(feats.index)
        else:
            feats["fwd_excess"] = np.nan
        feats["date"] = prices.index[i]
        frames.append(feats.rename_axis("ticker").reset_index())
    return pd.concat(frames, ignore_index=True)


def cross_sectional_rank(df: pd.DataFrame) -> pd.DataFrame:
    """같은 날짜 안에서 지표를 0~1 순위로 바꾼다. 시장 전체가 좋던 해/나쁘던 해의 차이를 없앤다."""
    out = df.copy()
    out[FEATURES] = df.groupby("date")[FEATURES].rank(pct=True)
    return out


def make_model() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        # 주가 신호는 잡음이 커서 얕은 트리 + 큰 잎으로 과적합을 막는다.
        max_iter=100, learning_rate=0.03, max_depth=2,
        min_samples_leaf=300, l2_regularization=1.0, random_state=0,
    )


def walk_forward(data: pd.DataFrame, top: int = 20, min_train_years: int = 3) -> dict:
    """연도별로 과거 데이터로만 학습하고 다음 해를 예측해 성과를 모은다."""
    labeled = data.dropna(subset=["fwd_excess"])
    years = sorted(labeled["date"].dt.year.unique())
    first_year = years[0] + min_train_years
    picks, all_rows = [], []
    for year in [y for y in years if y >= first_year]:
        start = pd.Timestamp(year=year, month=1, day=1)
        # 정답 기간(3개월)이 테스트 시작 전에 끝난 행만 학습에 사용 (미래 정보 누출 방지)
        train = labeled[labeled["date"] < start - pd.DateOffset(months=3)]
        test = labeled[labeled["date"].dt.year == year].copy()
        if len(train) < 500 or test.empty:
            continue
        model = make_model().fit(train[FEATURES], train["fwd_excess"] > 0)
        test["prob"] = model.predict_proba(test[FEATURES])[:, 1]
        all_rows.append(test)
        picks.append(test.sort_values("prob", ascending=False).groupby("date").head(top))

    oos = pd.concat(all_rows)
    chosen = pd.concat(picks)
    by_date_top = chosen.groupby("date")["fwd_excess"].mean()
    by_date_all = oos.groupby("date")["fwd_excess"].mean()
    return {
        "period": f"{oos['date'].min():%Y-%m} ~ {oos['date'].max():%Y-%m}",
        "rebalances": int(by_date_top.size),
        "auc": float(roc_auc_score(oos["fwd_excess"] > 0, oos["prob"])),
        "top_avg_excess_3m": float(by_date_top.mean()),
        "universe_avg_excess_3m": float(by_date_all.mean()),
        "top_hit_rate": float((chosen["fwd_excess"] > 0).mean()),
        "universe_hit_rate": float((oos["fwd_excess"] > 0).mean()),
        "months_top_beat_universe": float((by_date_top > by_date_all).mean()),
    }


def predict(prices: pd.DataFrame, bench: pd.Series, names: dict[str, str], top: int = 20) -> dict:
    data = cross_sectional_rank(build_dataset(prices, bench))
    backtest = walk_forward(data, top)

    labeled = data.dropna(subset=["fwd_excess"])
    model = make_model().fit(labeled[FEATURES], labeled["fwd_excess"] > 0)
    latest = data[data["date"] == data["date"].max()].copy()
    latest["prob"] = model.predict_proba(latest[FEATURES])[:, 1]
    latest = latest.sort_values("prob", ascending=False).head(top)

    raw = features_at(prices, bench, len(prices) - 1)  # 순위가 아닌 실제 지표값 (앱 표시용)
    stocks = [
        {
            "ticker": r.ticker,
            "name": names.get(r.ticker, r.ticker),
            "prob": round(float(r.prob), 4),
            "indicators": {k: round(float(raw.loc[r.ticker, k]), 4) for k in FEATURES},
        }
        for r in latest.itertuples()
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of": f"{prices.index[-1]:%Y-%m-%d}",
        "horizon_days": HORIZON,
        "target": "향후 3개월 수익률이 SPY보다 높을 확률",
        "features": FEATURES,
        "train_rows": int(len(labeled)),
        "backtest": backtest,
        "stocks": stocks,
    }


def load_prices(tickers: list[str], period: str) -> pd.DataFrame:
    import yfinance as yf

    data = yf.download(tickers, period=period, auto_adjust=True, progress=False)
    return data["Close"].dropna(how="all")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="지표 기반 3개월 후 SPY 초과 확률 예측")
    parser.add_argument("--period", default="10y", help="학습에 쓸 과거 기간")
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)

    names = load_universe()
    prices = load_prices(list(names) + [BENCHMARK], args.period)
    bench = prices.pop(BENCHMARK)
    result = predict(prices, bench, names, args.top)

    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    bt = result["backtest"]
    print(f"학습 데이터 {result['train_rows']:,}행 | 백테스트 {bt['period']} ({bt['rebalances']}회)")
    print(f"AUC {bt['auc']:.3f} | 상위{args.top} 3개월 초과수익 평균 {bt['top_avg_excess_3m']:+.2%} "
          f"(전체 {bt['universe_avg_excess_3m']:+.2%}) | SPY 이긴 비율 {bt['top_hit_rate']:.1%} "
          f"(전체 {bt['universe_hit_rate']:.1%}) | 전체보다 나은 달 {bt['months_top_beat_universe']:.1%}")
    print(f"\n{result['as_of']} 기준 예측 TOP {args.top}")
    for i, s in enumerate(result["stocks"], 1):
        print(f"{i:>2}. {s['name']}({s['ticker']})  SPY 이길 확률 {s['prob']:.1%}")


if __name__ == "__main__":
    main()

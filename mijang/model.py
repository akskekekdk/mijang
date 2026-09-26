"""여러 지표 × 여러 예측 방법을 과거 데이터로 겨뤄서 가장 잘 맞힌 방법으로 매수추천: python -m mijang.model

1. 매월 말, 종목마다 직전 1년 가격·거래량으로 지표 23개를 계산한다
   (10대 수익률 지표 + 모멘텀·추세·과열·거래량 기술지표).
2. 정답: 그 뒤 3개월(63거래일) 동안 S&P 500(SPY)보다 많이 올랐는가 (1/0).
3. 예측 방법 6가지(단순 규칙 2 + 머신러닝 3 + 앙상블)를 연도별 워크포워드로 검증한다
   (항상 과거로만 학습 → 다음 해 예측).
4. "선정 기간"의 추천 적중률(추천 종목 중 SPY를 이긴 비율)이 가장 높은 방법을 고르고,
   고를 때 쓰지 않은 최근 "검증 기간" 성적을 따로 보고한다.
5. 고른 방법을 전체 데이터로 다시 학습해 오늘 지표로 매수추천 20개를 뽑는다.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from .indicators import compute_indicators
from .top20 import load_universe

WINDOW = 252  # 지표 계산 구간: 1년
HORIZON = 63  # 예측 구간: 3개월
HOLDOUT_YEARS = 2  # 방법 선정에 쓰지 않고 성적 확인에만 쓰는 최근 연수
BENCHMARK = "SPY"
OUTPUT = Path(__file__).resolve().parent.parent / "data" / "predictions.json"

INDICATOR_KEYS = [
    "total_return", "cagr", "volatility", "sharpe", "sortino",
    "mdd", "calmar", "beta", "alpha", "win_rate",
]
TECHNICAL_KEYS = [
    "mom_1m", "mom_3m", "mom_6m", "mom_12_1",  # 모멘텀 (12_1: 최근 1개월 뺀 1년)
    "from_high", "from_low",  # 52주 고점/저점 대비
    "ma50_gap", "ma200_gap",  # 이동평균 대비 괴리
    "rsi14", "macd_hist", "bb_pctb",  # 과열/침체
    "vol_1m", "volume_trend",  # 최근 변동성, 거래량 추세
]
FEATURES = INDICATOR_KEYS + TECHNICAL_KEYS


# ---------------------------------------------------------------- 지표 계산

def _ema(x: np.ndarray, span: int) -> np.ndarray:
    alpha = 2 / (span + 1)
    out = np.empty_like(x)
    out[0] = x[0]
    for k in range(1, len(x)):
        out[k] = alpha * x[k] + (1 - alpha) * out[k - 1]
    return out


def technical(p: pd.Series, v: pd.Series | None) -> dict[str, float]:
    """가격 p(길이 WINDOW+1), 거래량 v로 기술지표 계산."""
    a = p.to_numpy(dtype=float)
    last = a[-1]
    diff = np.diff(a[-15:])
    gain, loss = diff.clip(min=0).mean(), (-diff).clip(min=0).mean()
    macd = _ema(a, 12) - _ema(a, 26)
    ma20, sd20 = a[-20:].mean(), a[-20:].std()
    rets = np.diff(a[-22:]) / a[-22:-1]
    out = {
        "mom_1m": last / a[-22] - 1,
        "mom_3m": last / a[-64] - 1,
        "mom_6m": last / a[-127] - 1,
        "mom_12_1": a[-22] / a[0] - 1,
        "from_high": last / a.max() - 1,
        "from_low": last / a.min() - 1,
        "ma50_gap": last / a[-50:].mean() - 1,
        "ma200_gap": last / a[-200:].mean() - 1,
        "rsi14": 100.0 if loss == 0 else 100 - 100 / (1 + gain / loss),
        "macd_hist": (macd[-1] - _ema(macd, 9)[-1]) / last,
        "bb_pctb": 0.5 if sd20 == 0 else (last - (ma20 - 2 * sd20)) / (4 * sd20),
        "vol_1m": rets.std() * np.sqrt(252),
        "volume_trend": np.nan,
    }
    if v is not None:
        vv = v.to_numpy(dtype=float)
        base = np.nanmean(vv[-120:])
        if base > 0:
            out["volume_trend"] = np.nanmean(vv[-20:]) / base - 1
    return out


def features_at(prices: pd.DataFrame, volumes: pd.DataFrame | None, bench: pd.Series, i: int) -> pd.DataFrame:
    """i번째 거래일 기준, 직전 WINDOW일로 계산한 종목별 지표."""
    window = prices.iloc[i - WINDOW : i + 1]
    vol_w = volumes.iloc[i - WINDOW : i + 1] if volumes is not None else None
    bench_w = bench.iloc[i - WINDOW : i + 1]
    rows = {}
    for ticker in prices.columns:
        p = window[ticker]
        if p.isna().any():
            continue  # 1년치 데이터가 온전하지 않으면 제외
        row = compute_indicators(p, bench_w)
        v = vol_w[ticker] if vol_w is not None and ticker in vol_w else None
        row.update(technical(p, v))
        rows[ticker] = row
    return pd.DataFrame.from_dict(rows, orient="index")[FEATURES] if rows else pd.DataFrame(columns=FEATURES)


def rebalance_days(index: pd.DatetimeIndex) -> list[int]:
    """각 달의 마지막 거래일 위치 + 가장 최근 거래일."""
    s = pd.Series(np.arange(len(index)), index=index)
    days = s.groupby([index.year, index.month]).max().tolist()
    if days[-1] != len(index) - 1:
        days.append(len(index) - 1)
    return [d for d in days if d >= WINDOW]


def build_dataset(prices: pd.DataFrame, bench: pd.Series, volumes: pd.DataFrame | None = None) -> pd.DataFrame:
    """(날짜, 종목)별 지표와 정답. 미래 3개월이 아직 안 지난 행은 정답이 NaN."""
    frames = []
    for i in rebalance_days(prices.index):
        feats = features_at(prices, volumes, bench, i)
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
    """같은 날짜 안에서 지표를 0~1 순위로 바꾼다. 시장 전체가 좋던 해/나쁘던 해의 차이를 없앤다.
    값이 없는 지표(예: 거래량 없음)는 중간값 0.5로 채운다."""
    out = df.copy()
    out[FEATURES] = df.groupby("date")[FEATURES].rank(pct=True).fillna(0.5)
    return out


# ---------------------------------------------------------------- 예측 방법

@dataclass
class Method:
    key: str
    label: str
    description: str
    # (학습 데이터, 예측할 데이터) → 점수 (높을수록 유망)
    score: Callable[[pd.DataFrame, pd.DataFrame], np.ndarray]


def _rule(feature: str) -> Callable[[pd.DataFrame, pd.DataFrame], np.ndarray]:
    return lambda train, test: test[feature].to_numpy()


def _fit_predict(make) -> Callable[[pd.DataFrame, pd.DataFrame], np.ndarray]:
    def score(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
        model = make().fit(train[FEATURES], train["fwd_excess"] > 0)
        return model.predict_proba(test[FEATURES])[:, 1]
    return score


def _logistic():
    return LogisticRegression(C=0.1, max_iter=1000)


def _gbm():
    # 주가 신호는 잡음이 커서 얕은 트리 + 큰 잎으로 과적합을 막는다.
    return HistGradientBoostingClassifier(
        max_iter=100, learning_rate=0.03, max_depth=2,
        min_samples_leaf=300, l2_regularization=1.0, random_state=0,
    )


def _forest():
    return RandomForestClassifier(
        n_estimators=300, max_depth=4, min_samples_leaf=100,
        max_features=0.5, n_jobs=-1, random_state=0,
    )


def _ensemble(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    """세 모델의 점수를 날짜별 순위로 바꿔 평균한다."""
    ranks = []
    for make in (_logistic, _gbm, _forest):
        s = pd.Series(_fit_predict(make)(train, test), index=test.index)
        ranks.append(s.groupby(test["date"]).rank(pct=True))
    return pd.concat(ranks, axis=1).mean(axis=1).to_numpy()


METHODS = [
    Method("momentum", "모멘텀 규칙", "최근 1개월을 뺀 1년 수익률이 높은 순", _rule("mom_12_1")),
    Method("sharpe", "샤프 규칙", "1년 샤프 지수(위험 대비 수익)가 높은 순", _rule("sharpe")),
    Method("logistic", "로지스틱 회귀", "지표 23개의 가중합으로 SPY 초과 확률 추정", _fit_predict(_logistic)),
    Method("gbm", "그래디언트 부스팅", "얕은 결정트리 100개를 차례로 보정", _fit_predict(_gbm)),
    Method("forest", "랜덤 포레스트", "결정트리 300개의 투표", _fit_predict(_forest)),
    Method("ensemble", "앙상블", "로지스틱·부스팅·포레스트 점수 평균", _ensemble),
]


# ---------------------------------------------------------------- 검증

def walk_forward_scores(data: pd.DataFrame, method: Method, min_train_years: int = 3) -> pd.DataFrame:
    """연도별로 과거 데이터로만 학습하고 그해를 예측한 점수 (정답 있는 행만)."""
    labeled = data.dropna(subset=["fwd_excess"])
    years = sorted(labeled["date"].dt.year.unique())
    out = []
    for year in [y for y in years if y >= years[0] + min_train_years]:
        start = pd.Timestamp(year=year, month=1, day=1)
        # 정답 기간(3개월)이 테스트 시작 전에 끝난 행만 학습에 사용 (미래 정보 누출 방지)
        train = labeled[labeled["date"] < start - pd.DateOffset(months=3)]
        test = labeled[labeled["date"].dt.year == year].copy()
        if len(train) < 500 or test.empty:
            continue
        test["score"] = method.score(train, test)
        out.append(test)
    return pd.concat(out)


def evaluate(scored: pd.DataFrame, top: int) -> dict:
    """추천(날짜별 점수 상위 top개) 성적."""
    picks = scored.sort_values("score", ascending=False).groupby("date").head(top)
    by_date_top = picks.groupby("date")["fwd_excess"].mean()
    by_date_all = scored.groupby("date")["fwd_excess"].mean()
    return {
        "period": f"{scored['date'].min():%Y-%m} ~ {scored['date'].max():%Y-%m}",
        "rebalances": int(by_date_top.size),
        "hit_rate": float((picks["fwd_excess"] > 0).mean()),
        "universe_hit_rate": float((scored["fwd_excess"] > 0).mean()),
        "avg_excess_3m": float(by_date_top.mean()),
        "universe_avg_excess_3m": float(by_date_all.mean()),
        "months_beat_universe": float((by_date_top > by_date_all).mean()),
        "auc": float(roc_auc_score(scored["fwd_excess"] > 0, scored["score"])),
    }


def compare_methods(data: pd.DataFrame, top: int) -> tuple[Method, list[dict]]:
    """방법별 성적을 선정 기간/검증 기간으로 나눠 매기고, 선정 기간 적중률 1위를 고른다."""
    results = []
    for method in METHODS:
        scored = walk_forward_scores(data, method)
        cutoff = pd.Timestamp(year=scored["date"].dt.year.max() - HOLDOUT_YEARS + 1, month=1, day=1)
        results.append({
            "key": method.key,
            "label": method.label,
            "description": method.description,
            "selection": evaluate(scored[scored["date"] < cutoff], top),
            "holdout": evaluate(scored[scored["date"] >= cutoff], top),
            "overall": evaluate(scored, top),
        })
    best = max(results, key=lambda r: (r["selection"]["hit_rate"], r["selection"]["avg_excess_3m"]))
    for r in results:
        r["chosen"] = r is best
    return next(m for m in METHODS if m.key == best["key"]), results


def predict(prices: pd.DataFrame, bench: pd.Series, names: dict[str, str],
            top: int = 20, volumes: pd.DataFrame | None = None) -> dict:
    data = cross_sectional_rank(build_dataset(prices, bench, volumes))
    method, results = compare_methods(data, top)

    labeled = data.dropna(subset=["fwd_excess"])
    latest = data[data["date"] == data["date"].max()].copy()
    latest["score"] = method.score(labeled, latest)
    latest["score_pct"] = latest["score"].rank(pct=True)
    latest = latest.sort_values("score", ascending=False).head(top)

    raw = features_at(prices, volumes, bench, len(prices) - 1)  # 순위가 아닌 실제 지표값
    chosen = next(r for r in results if r["chosen"])
    stocks = [
        {
            "ticker": r.ticker,
            "name": names.get(r.ticker, r.ticker),
            "score": round(float(r.score_pct), 4),  # 오늘 후보 중 순위 (1 = 최고)
            "indicators": {k: None if pd.isna(raw.loc[r.ticker, k]) else round(float(raw.loc[r.ticker, k]), 4)
                           for k in FEATURES},
        }
        for r in latest.itertuples()
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of": f"{prices.index[-1]:%Y-%m-%d}",
        "horizon_days": HORIZON,
        "target": "향후 3개월 수익률이 SPY보다 높을지",
        "features": FEATURES,
        "train_rows": int(len(labeled)),
        "method": {"key": method.key, "label": method.label, "description": method.description},
        "accuracy": chosen["overall"],
        "holdout": chosen["holdout"],
        "methods": results,
        "stocks": stocks,
    }


# ---------------------------------------------------------------- 실행

def load_prices(tickers: list[str], period: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    import yfinance as yf

    data = yf.download(tickers, period=period, auto_adjust=True, progress=False)
    close = data["Close"].dropna(how="all")
    return close, data["Volume"].reindex(close.index)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="여러 방법 비교 후 3개월 매수추천")
    parser.add_argument("--period", default="10y", help="학습에 쓸 과거 기간")
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)

    names = load_universe()
    prices, volumes = load_prices(list(names) + [BENCHMARK], args.period)
    bench = prices.pop(BENCHMARK)
    volumes = volumes.drop(columns=[BENCHMARK], errors="ignore")
    result = predict(prices, bench, names, args.top, volumes)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"학습 데이터 {result['train_rows']:,}행 | 지표 {len(FEATURES)}개 | 추천 {args.top}개 기준\n")
    print(f"{'방법':<12}{'선정기간 적중률':>14}{'초과수익':>10}{'검증기간 적중률':>16}{'초과수익':>10}{'AUC':>8}")
    for r in result["methods"]:
        s, h = r["selection"], r["holdout"]
        mark = " ◀ 선택" if r["chosen"] else ""
        print(f"{r['label']:<12}{s['hit_rate']:>13.1%}{s['avg_excess_3m']:>+10.2%}"
              f"{h['hit_rate']:>15.1%}{h['avg_excess_3m']:>+10.2%}{r['overall']['auc']:>8.3f}{mark}")
    base = result["methods"][0]["overall"]
    print(f"(참고: 아무거나 골랐을 때 적중률 {base['universe_hit_rate']:.1%}, "
          f"평균 초과수익 {base['universe_avg_excess_3m']:+.2%})")
    print(f"\n{result['as_of']} 기준 매수추천 ({result['method']['label']})")
    for i, s in enumerate(result["stocks"], 1):
        print(f"{i:>2}. {s['name']}({s['ticker']})  점수 {s['score'] * 100:.0f}")


if __name__ == "__main__":
    main()

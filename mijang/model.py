"""여러 지표 × 여러 예측 방법을 과거 데이터로 겨뤄서 가장 잘 맞힌 방법으로 매수추천: python -m mijang.model

1. 매월 말, 종목마다 지표 31개를 계산한다: 직전 1년 가격·거래량으로 10대 수익률 지표 + 기술지표 13개,
   SEC 공시로 재무지표 8개(PER·PBR·PSR·ROE·영업이익률·매출/EPS 성장률·부채비율, 그 시점까지 공시된 값만).
2. 정답: 그 뒤 3개월(63거래일) 동안 S&P 500(SPY)보다 많이 올랐는가.
3. 예측 방법 20가지(팩터 규칙 12 + 머신러닝 7 + 앙상블)와, 이들을 섞은 혼합 4가지를
   연도별 워크포워드로 검증한다 (항상 과거로만 학습 → 다음 해 예측).
4. "선정 기간"의 추천 적중률(추천 종목 중 SPY를 이긴 비율)이 가장 높은 방법을 고르고,
   고를 때 쓰지 않은 최근 "검증 기간" 성적을 따로 보고한다.
5. 고른 방법으로 오늘 후보 전체에 점수를 매겨 매수추천 20개를 뽑고, 종목마다 근거를 남긴다:
   지표값·순위표, 지표별 점수 기여도, 과거에 지표가 비슷했던 사례의 실제 결과.
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
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import roc_auc_score
from sklearn.neighbors import KNeighborsClassifier, NearestNeighbors
from sklearn.neural_network import MLPClassifier

from .fundamentals import FUND_KEYS, Company, load_companies
from .indicators import compute_indicators
from .top20 import load_universe

WINDOW = 252  # 지표 계산 구간: 1년
HORIZON = 63  # 예측 구간: 3개월
HOLDOUT_YEARS = 2  # 방법 선정에 쓰지 않고 성적 확인에만 쓰는 최근 연수
SIMILAR_K = 50  # 근거로 보여줄 "비슷한 과거 사례" 수
BENCHMARK = "SPY"
OUTPUT = Path(__file__).resolve().parent.parent / "data" / "predictions.json"

# (키, 이름, 설명, 표시형식) — 앱도 이 이름·설명을 그대로 쓴다.
FEATURE_INFO = [
    ("total_return", "1년 수익률", "최근 1년 주가 상승률", "pct"),
    ("cagr", "연평균 수익률", "1년 수익률을 연 복리로 환산", "pct"),
    ("volatility", "연 변동성", "일간 수익률 표준편차 × √252", "pct"),
    ("sharpe", "샤프 지수", "변동성 1단위당 수익", "num"),
    ("sortino", "소르티노 지수", "하락 변동성 1단위당 수익", "num"),
    ("mdd", "최대 낙폭", "1년 중 고점 대비 가장 크게 빠진 폭", "pct"),
    ("calmar", "칼마 지수", "연평균 수익률 ÷ |최대 낙폭|", "num"),
    ("beta", "베타", "S&P 500이 1% 움직일 때 움직이는 정도", "num"),
    ("alpha", "젠센 알파", "시장 움직임으로 설명 안 되는 연 초과수익", "pct"),
    ("win_rate", "일간 승률", "1년 중 오른 날 비율", "pct"),
    ("mom_1m", "1개월 수익률", "최근 21거래일 상승률", "pct"),
    ("mom_3m", "3개월 수익률", "최근 63거래일 상승률", "pct"),
    ("mom_6m", "6개월 수익률", "최근 126거래일 상승률", "pct"),
    ("mom_12_1", "12-1 모멘텀", "최근 1개월을 뺀 1년 상승률", "pct"),
    ("from_high", "52주 고점 대비", "1년 최고가에서 얼마나 내려와 있나", "pct"),
    ("from_low", "52주 저점 대비", "1년 최저가에서 얼마나 올라와 있나", "pct"),
    ("ma50_gap", "50일선 괴리", "현재가 ÷ 50일 이동평균 − 1", "pct"),
    ("ma200_gap", "200일선 괴리", "현재가 ÷ 200일 이동평균 − 1", "pct"),
    ("rsi14", "RSI(14)", "70 이상 과열, 30 이하 침체", "num"),
    ("macd_hist", "MACD 히스토그램", "단기 추세 가속도 (가격 대비)", "pct"),
    ("bb_pctb", "볼린저 %B", "20일 밴드 안 위치 (1 위쪽 끝, 0 아래쪽 끝)", "num"),
    ("vol_1m", "1개월 변동성", "최근 21거래일 변동성 (연환산)", "pct"),
    ("volume_trend", "거래량 추세", "20일 평균 거래량 ÷ 120일 평균 − 1", "pct"),
    # 재무 지표 (SEC 공시, 그 시점까지 공시된 최근 4분기 기준)
    ("per", "PER", "주가 ÷ 주당순이익 (적자면 없음)", "num"),
    ("pbr", "PBR", "주가 ÷ 주당순자산", "num"),
    ("psr", "PSR", "주가 ÷ 주당매출", "num"),
    ("roe", "ROE", "순이익 ÷ 자기자본", "pct"),
    ("op_margin", "영업이익률", "영업이익 ÷ 매출", "pct"),
    ("rev_growth", "매출 성장률", "최근 4분기 매출 ÷ 1년 전 4분기 매출 − 1", "pct"),
    ("eps_growth", "EPS 성장률", "최근 4분기 EPS의 1년 전 대비 변화", "pct"),
    ("debt_ratio", "부채비율", "부채 ÷ 자기자본", "num"),
]
FEATURES = [k for k, *_ in FEATURE_INFO]
# 1년 구간에선 CAGR == 1년 수익률이라 똑같은 지표가 두 번 들어가면 선형 모델 가중치가 서로 상쇄된다.
# 표에는 보여주되 모델 입력에서는 뺀다.
MODEL_FEATURES = [k for k in FEATURES if k != "cagr"]
LABELS = {k: label for k, label, *_ in FEATURE_INFO}
FORMATS = {k: fmt for k, _, _, fmt in FEATURE_INFO}


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
    df = pd.DataFrame.from_dict(rows, orient="index") if rows else pd.DataFrame()
    return df.reindex(columns=FEATURES).astype(float)  # 재무지표 칸은 build_dataset 에서 채운다


def rebalance_days(index: pd.DatetimeIndex) -> list[int]:
    """각 달의 마지막 거래일 위치 + 가장 최근 거래일."""
    s = pd.Series(np.arange(len(index)), index=index)
    days = s.groupby([index.year, index.month]).max().tolist()
    if days[-1] != len(index) - 1:
        days.append(len(index) - 1)
    return [d for d in days if d >= WINDOW]


def build_dataset(prices: pd.DataFrame, bench: pd.Series, volumes: pd.DataFrame | None = None,
                  companies: dict[str, Company] | None = None, raw_prices: pd.DataFrame | None = None) -> pd.DataFrame:
    """(날짜, 종목)별 지표 원래값과 정답. 미래 3개월이 아직 안 지난 행은 정답이 NaN.
    companies 가 있으면 재무지표도 넣는다 (raw_prices: 배당 조정 안 한 종가, PER 등 계산용)."""
    frames = []
    val_prices = raw_prices if raw_prices is not None else prices
    for i in rebalance_days(prices.index):
        feats = features_at(prices, volumes, bench, i)
        if feats.empty:
            continue
        date = prices.index[i]
        for ticker in feats.index:
            comp = (companies or {}).get(ticker)
            price = val_prices[ticker].iloc[i] if ticker in val_prices else np.nan
            if comp is not None and not np.isnan(price):
                for k, v in comp.at(date, price).items():
                    feats.loc[ticker, k] = v
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

Predictor = Callable[[pd.DataFrame], np.ndarray]  # 순위화된 지표 → 점수 (높을수록 유망)


@dataclass
class Method:
    key: str
    label: str
    kind: str  # "규칙" / "머신러닝" / "앙상블"
    description: str
    fit: Callable[[pd.DataFrame], Predictor]  # 학습 데이터 → 예측 함수


def _rule(weights: dict[str, float]) -> Callable[[pd.DataFrame], Predictor]:
    """지표 순위의 가중합. 음수 가중치는 '낮을수록 좋다'."""
    def fit(train: pd.DataFrame) -> Predictor:
        return lambda df: sum(w * df[k].to_numpy() for k, w in weights.items())
    return fit


def _classifier(make) -> Callable[[pd.DataFrame], Predictor]:
    def fit(train: pd.DataFrame) -> Predictor:
        model = make().fit(train[MODEL_FEATURES].to_numpy(), (train["fwd_excess"] > 0).to_numpy())
        return lambda df: model.predict_proba(df[MODEL_FEATURES].to_numpy())[:, 1]
    return fit


def _ridge_rank(train: pd.DataFrame) -> Predictor:
    """정답을 '같은 달 안에서 몇 등이었나'(0~1)로 두고 선형 회귀."""
    target = train.groupby("date")["fwd_excess"].rank(pct=True)
    model = Ridge(alpha=10.0).fit(train[MODEL_FEATURES].to_numpy(), target.to_numpy())
    return lambda df: model.predict(df[MODEL_FEATURES].to_numpy())


def _logistic():
    return LogisticRegression(C=0.1, max_iter=1000)


def _gbm():
    # 주가 신호는 잡음이 커서 얕은 트리 + 큰 잎으로 과적합을 막는다.
    return HistGradientBoostingClassifier(max_iter=100, learning_rate=0.03, max_depth=2,
                                          min_samples_leaf=300, l2_regularization=1.0, random_state=0)


def _forest():
    return RandomForestClassifier(n_estimators=200, max_depth=4, min_samples_leaf=100,
                                  max_features=0.5, n_jobs=-1, random_state=0)


def _extra():
    return ExtraTreesClassifier(n_estimators=200, max_depth=5, min_samples_leaf=100,
                                max_features=0.5, n_jobs=-1, random_state=0)


def _knn():
    return KNeighborsClassifier(n_neighbors=200)


def _mlp():
    return MLPClassifier(hidden_layer_sizes=(32, 16), alpha=0.01, learning_rate_init=0.001,
                         early_stopping=True, max_iter=300, random_state=0)


def _ensemble(train: pd.DataFrame) -> Predictor:
    """로지스틱·부스팅·포레스트·k-최근접 확률 평균."""
    preds = [_classifier(make)(train) for make in (_logistic, _gbm, _forest, _knn)]
    return lambda df: np.mean([p(df) for p in preds], axis=0)


METHODS = [
    Method("momentum", "모멘텀", "규칙", "최근 1개월을 뺀 1년 수익률 높은 순", _rule({"mom_12_1": 1})),
    Method("sharpe", "샤프 우수", "규칙", "1년 샤프 지수(위험 대비 수익) 높은 순", _rule({"sharpe": 1})),
    Method("low_vol", "저변동성", "규칙", "1년 변동성 낮은 순 (저변동성 이상현상)", _rule({"volatility": -1})),
    Method("reversal", "단기 반전", "규칙", "최근 1개월 많이 떨어진 순 (되돌림 기대)", _rule({"mom_1m": -1})),
    Method("trend", "추세 추종", "규칙", "50일·200일 이동평균 위로 많이 올라간 순", _rule({"ma50_gap": 1, "ma200_gap": 1})),
    Method("near_high", "신고가 근접", "규칙", "52주 고점에 가까운 순", _rule({"from_high": 1})),
    Method("multi", "멀티팩터", "규칙", "모멘텀 + 샤프 + 저변동성 순위 평균",
           _rule({"mom_12_1": 1, "sharpe": 1, "volatility": -1})),
    Method("value", "가치", "규칙", "PER·PBR·PSR 낮은 순 (저평가)", _rule({"per": -1, "pbr": -1, "psr": -1})),
    Method("quality", "퀄리티", "규칙", "ROE·영업이익률 높고 부채비율 낮은 순",
           _rule({"roe": 1, "op_margin": 1, "debt_ratio": -1})),
    Method("growth", "성장", "규칙", "매출·EPS 성장률 높은 순", _rule({"rev_growth": 1, "eps_growth": 1})),
    Method("value_mom", "가치+모멘텀", "규칙", "싸면서(PER·PBR 낮고) 오르는 중(12-1 모멘텀)",
           _rule({"per": -1, "pbr": -1, "mom_12_1": 2})),
    Method("garp", "성장+가치(GARP)", "규칙", "성장률 높은데 PER 낮은 순", _rule({"eps_growth": 1, "rev_growth": 1, "per": -2})),
    Method("logistic", "로지스틱 회귀", "머신러닝", "지표 30개의 가중합으로 SPY 초과 확률", _classifier(_logistic)),
    Method("ridge", "릿지 순위회귀", "머신러닝", "3개월 뒤 순위(몇 등)를 직접 예측하는 선형 회귀", _ridge_rank),
    Method("knn", "유사사례(k-NN)", "머신러닝", "과거에 지표가 가장 비슷했던 200건의 결과 비율", _classifier(_knn)),
    Method("gbm", "그래디언트 부스팅", "머신러닝", "얕은 결정트리 100개를 차례로 보정", _classifier(_gbm)),
    Method("forest", "랜덤 포레스트", "머신러닝", "결정트리 200개의 투표", _classifier(_forest)),
    Method("extra", "엑스트라 트리", "머신러닝", "무작위로 자른 결정트리 200개의 투표", _classifier(_extra)),
    Method("mlp", "신경망", "머신러닝", "은닉층 2개(32·16)짜리 작은 신경망", _classifier(_mlp)),
    Method("ensemble", "앙상블", "앙상블", "로지스틱·부스팅·포레스트·k-NN 확률 평균", _ensemble),
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
        test["score"] = method.fit(train)(test)
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


# 여러 방법 섞기: 구성 방법들의 점수를 날짜별 순위(0~1)로 바꿔 평균한다.
# (이름, 설명, 구성 방법 고르는 함수: 단일 방법 성적표 → 키 목록)
MIXES = [
    ("mix_all", "전체 혼합", lambda singles: [r["key"] for r in singles]),
    ("mix_ml", "머신러닝 혼합", lambda singles: [r["key"] for r in singles if r["kind"] == "머신러닝"]),
    ("mix_top3", "상위3 혼합", lambda singles: [r["key"] for r in _by_selection(singles)[:3]]),
    ("mix_top5", "상위5 혼합", lambda singles: [r["key"] for r in _by_selection(singles)[:5]]),
]


def _by_selection(results: list[dict]) -> list[dict]:
    return sorted(results, key=lambda r: (r["selection"]["hit_rate"], r["selection"]["avg_excess_3m"]), reverse=True)


def _grade(key: str, label: str, kind: str, description: str, scored: pd.DataFrame, top: int, **extra) -> dict:
    cutoff = pd.Timestamp(year=scored["date"].dt.year.max() - HOLDOUT_YEARS + 1, month=1, day=1)
    return {
        "key": key, "label": label, "kind": kind, "description": description, **extra,
        "selection": evaluate(scored[scored["date"] < cutoff], top),
        "holdout": evaluate(scored[scored["date"] >= cutoff], top),
        "overall": evaluate(scored, top),
    }


def compare_methods(data: pd.DataFrame, top: int) -> tuple[dict, list[dict]]:
    """단일 방법과 혼합 방법의 성적을 선정 기간/검증 기간으로 나눠 매기고, 선정 기간 적중률 1위를 고른다.
    혼합의 구성(상위 3·5개)도 선정 기간 성적으로만 정하므로 검증 기간은 끝까지 깨끗하게 남는다."""
    scored = {m.key: walk_forward_scores(data, m) for m in METHODS}
    results = [_grade(m.key, m.label, m.kind, m.description, scored[m.key], top) for m in METHODS]
    singles = list(results)
    labels = {m.key: m.label for m in METHODS}
    for key, label, pick in MIXES:
        parts = pick(singles)
        base = scored[parts[0]]
        mixed = base.drop(columns="score").copy()
        mixed["score"] = pd.concat(
            [scored[k]["score"].groupby(scored[k]["date"]).rank(pct=True) for k in parts], axis=1
        ).mean(axis=1)
        desc = "·".join(labels[k] for k in parts) + " 순위 평균"
        results.append(_grade(key, label, "혼합", desc, mixed, top, components=parts))
    best = _by_selection(results)[0]
    for r in results:
        r["chosen"] = r is best
    return best, results


def build_predictor(chosen: dict, labeled: pd.DataFrame, today: pd.DataFrame) -> Predictor:
    """고른 방법을 전체 데이터로 학습. 혼합이면 구성 방법마다 오늘 후보 중 순위(고정 기준)를 평균한다."""
    methods = {m.key: m for m in METHODS}
    if "components" not in chosen:
        return methods[chosen["key"]].fit(labeled)
    preds = [methods[k].fit(labeled) for k in chosen["components"]]
    refs = [np.sort(p(today)) for p in preds]
    return lambda df: np.mean(
        [np.searchsorted(ref, p(df), side="right") / len(ref) for p, ref in zip(preds, refs)], axis=0
    )


def feature_report(labeled: pd.DataFrame) -> list[dict]:
    """지표별 과거 성적: 그 지표가 상위 20% / 하위 20%였던 종목의 3개월 뒤 결과."""
    rows = []
    win = labeled["fwd_excess"] > 0
    for key, label, desc, fmt in FEATURE_INFO:
        r = labeled[key]
        hi, lo = r > 0.8, r <= 0.2
        ic = labeled.groupby("date").apply(lambda g: g[key].corr(g["fwd_excess"], method="spearman"))
        hi_ex, lo_ex = labeled.loc[hi, "fwd_excess"].mean(), labeled.loc[lo, "fwd_excess"].mean()
        rows.append({
            "key": key, "label": label, "description": desc, "format": fmt,
            "top_hit_rate": float(win[hi].mean()), "top_avg_excess": float(hi_ex),
            "bottom_hit_rate": float(win[lo].mean()), "bottom_avg_excess": float(lo_ex),
            "ic": float(ic.mean()),
            "better": "높을수록" if hi_ex > lo_ex else "낮을수록",
        })
    return rows


# ---------------------------------------------------------------- 근거

def contributions(predictor: Predictor, today: pd.DataFrame) -> pd.DataFrame:
    """지표 하나를 '보통'(순위 0.5)으로 바꿨을 때 오늘 후보 중 순위(%)가 얼마나 내려가는지 = 그 지표의 기여도(%p)."""
    base_scores = predictor(today)
    ref = np.sort(base_scores)

    def pct(scores: np.ndarray) -> np.ndarray:
        return np.searchsorted(ref, scores, side="right") / len(ref)

    base = pct(base_scores)
    out = {}
    for key in MODEL_FEATURES:
        neutral = today.copy()
        neutral[key] = 0.5
        out[key] = (base - pct(predictor(neutral))) * 100
    return pd.DataFrame(out, index=today.index)


def similar_cases(labeled: pd.DataFrame, today: pd.DataFrame, names: dict[str, str]) -> list[dict]:
    """오늘 종목마다 과거에 지표(순위)가 가장 비슷했던 SIMILAR_K건과 그 3개월 뒤 결과."""
    nn = NearestNeighbors(n_neighbors=SIMILAR_K).fit(labeled[MODEL_FEATURES].to_numpy())
    _, idx = nn.kneighbors(today[MODEL_FEATURES].to_numpy())
    out = []
    for row in idx:
        cases = labeled.iloc[row]
        ex = cases.head(3)
        out.append({
            "n": SIMILAR_K,
            "hit_rate": round(float((cases["fwd_excess"] > 0).mean()), 4),
            "avg_excess": round(float(cases["fwd_excess"].mean()), 4),
            "median_excess": round(float(cases["fwd_excess"].median()), 4),
            "examples": [
                {"date": f"{r.date:%Y-%m}", "ticker": r.ticker, "name": names.get(r.ticker, r.ticker),
                 "excess": round(float(r.fwd_excess), 4)}
                for r in ex.itertuples()
            ],
        })
    return out


def _fmt(key: str, v: float) -> str:
    return f"{v * 100:+.1f}%" if FORMATS[key] == "pct" else f"{v:.2f}"


def reasons(contrib: pd.Series, ranks: pd.Series, raw: pd.Series, n: int = 3) -> list[str]:
    """기여도가 큰 지표를 사람이 읽을 문장으로."""
    lines = []
    for key in contrib.abs().sort_values(ascending=False).index[:n]:
        c = contrib[key]
        if abs(c) < 0.5:
            break
        pos = f"상위 {max(1, round((1 - ranks[key]) * 100))}%" if ranks[key] >= 0.5 else f"하위 {max(1, round(ranks[key] * 100))}%"
        effect = "점수 올림" if c > 0 else "점수 깎음"
        value = "-" if pd.isna(raw[key]) else _fmt(key, raw[key])
        lines.append(f"{LABELS[key]} {value} ({pos}) → {effect} {c:+.0f}%p")
    return lines


# ---------------------------------------------------------------- 예측

def predict(prices: pd.DataFrame, bench: pd.Series, names: dict[str, str], top: int = 20,
            volumes: pd.DataFrame | None = None, companies: dict[str, Company] | None = None,
            raw_prices: pd.DataFrame | None = None) -> dict:
    raw_all = build_dataset(prices, bench, volumes, companies, raw_prices)
    data = cross_sectional_rank(raw_all)
    chosen, results = compare_methods(data, top)

    labeled = data.dropna(subset=["fwd_excess"])
    last_date = data["date"].max()
    today = data[data["date"] == last_date].set_index("ticker")
    predictor = build_predictor(chosen, labeled, today)
    raw = raw_all[raw_all["date"] == last_date].set_index("ticker")

    score = pd.Series(predictor(today), index=today.index)
    pct = score.rank(pct=True)
    order = score.sort_values(ascending=False).index
    contrib = contributions(predictor, today)
    similar = dict(zip(today.index, similar_cases(labeled, today, names)))

    details = {}
    for rank, ticker in enumerate(order, 1):
        details[ticker] = {
            "name": names.get(ticker, ticker),
            "rank": rank,
            "score": round(float(pct[ticker]), 4),
            "recommended": rank <= top,
            "values": {k: None if pd.isna(raw.loc[ticker, k]) else round(float(raw.loc[ticker, k]), 4) for k in FEATURES},
            "ranks": {k: round(float(today.loc[ticker, k]), 3) for k in FEATURES},
            "contrib": {k: round(float(contrib.loc[ticker, k]), 1) if k in contrib else None for k in FEATURES},
            "reasons": reasons(contrib.loc[ticker], today.loc[ticker], raw.loc[ticker]),
            "similar": similar[ticker],
        }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of": f"{prices.index[-1]:%Y-%m-%d}",
        "horizon_days": HORIZON,
        "target": "향후 3개월 수익률이 SPY보다 높을지",
        "train_rows": int(len(labeled)),
        "candidates": int(len(today)),
        "method": {k: chosen[k] for k in ("key", "label", "kind", "description")},
        "accuracy": chosen["overall"],
        "holdout": chosen["holdout"],
        "methods": results,
        "features": feature_report(labeled),
        "stocks": [{"ticker": t, "name": details[t]["name"], "score": details[t]["score"]} for t in order[:top]],
        "details": details,
    }


# ---------------------------------------------------------------- 실행

def load_prices(tickers: list[str], period: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(수정종가: 배당·분할 조정, 종가: 분할만 조정, 거래량, 분할 비율)"""
    import yfinance as yf

    data = yf.download(tickers, period=period, auto_adjust=False, actions=True, progress=False)
    adj = data["Adj Close"].dropna(how="all")
    return adj, data["Close"].reindex(adj.index), data["Volume"].reindex(adj.index), data["Stock Splits"].reindex(adj.index)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="여러 방법 비교 후 3개월 매수추천")
    parser.add_argument("--period", default="10y", help="학습에 쓸 과거 기간")
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)

    names = load_universe()
    prices, raw_prices, volumes, splits = load_prices(list(names) + [BENCHMARK], args.period)
    bench = prices.pop(BENCHMARK)
    companies = load_companies(list(prices.columns), splits)
    result = predict(prices, bench, names, args.top, volumes, companies, raw_prices)
    args.out.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    print(f"학습 데이터 {result['train_rows']:,}행 | 지표 {len(FEATURES)}개(모델 입력 {len(MODEL_FEATURES)}개) | 방법 {len(result['methods'])}개 | 추천 {args.top}개\n")
    print(f"{'방법':<14}{'선정 적중률':>10}{'초과수익':>10}{'검증 적중률':>12}{'초과수익':>10}{'AUC':>8}")
    for r in result["methods"]:
        s, h = r["selection"], r["holdout"]
        mark = " ◀ 선택" if r["chosen"] else ""
        print(f"{r['label']:<14}{s['hit_rate']:>10.1%}{s['avg_excess_3m']:>+10.2%}"
              f"{h['hit_rate']:>12.1%}{h['avg_excess_3m']:>+10.2%}{r['overall']['auc']:>8.3f}{mark}")
    base = result["methods"][0]["overall"]
    print(f"(참고: 아무거나 골랐을 때 적중률 {base['universe_hit_rate']:.1%}, "
          f"평균 초과수익 {base['universe_avg_excess_3m']:+.2%})\n")
    print(f"{'지표':<14}{'상위20% 적중':>12}{'초과':>8}{'하위20% 적중':>12}{'초과':>8}{'IC':>7}")
    for f in result["features"]:
        print(f"{f['label']:<14}{f['top_hit_rate']:>12.1%}{f['top_avg_excess']:>+8.2%}"
              f"{f['bottom_hit_rate']:>12.1%}{f['bottom_avg_excess']:>+8.2%}{f['ic']:>7.3f}")
    print(f"\n{result['as_of']} 기준 매수추천 ({result['method']['label']})")
    for i, s in enumerate(result["stocks"], 1):
        d = result["details"][s["ticker"]]
        sim = d["similar"]
        print(f"{i:>2}. {s['name']}({s['ticker']}) 점수 {s['score'] * 100:.0f} | 유사사례 {sim['n']}건 중 "
              f"{sim['hit_rate']:.0%} 승, 평균 {sim['avg_excess']:+.1%} | " + " / ".join(d["reasons"][:2]))


if __name__ == "__main__":
    main()

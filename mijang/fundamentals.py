"""SEC EDGAR 공시(XBRL)로 과거 시점별 재무지표(PER·PBR·ROE 등)를 계산한다.

미래 정보가 섞이지 않도록 "그 날짜까지 공시된(filed) 숫자"만 쓴다. 같은 기간 숫자가 나중에
정정 공시돼도 처음 공시된 값을 쓴다. 달러(USD)로 보고하지 않는 해외 기업(IFRS·유로 등)은 값이 비어 있다.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

# SEC는 "이름 이메일" 형식의 User-Agent를 요구한다 (https://www.sec.gov/os/accessing-edgar-data).
# 본인 연락처로 바꾸려면 환경변수 SEC_USER_AGENT 를 설정한다.
USER_AGENT = os.environ.get("SEC_USER_AGENT", "mijang-research contact@example.com")
CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache" / "edgar"
MAX_AGE_DAYS = 7

# 개념별로 시도할 XBRL 태그 (앞쪽 우선)
TAGS = {
    "eps": ["EarningsPerShareDiluted", "EarningsPerShareBasic"],
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet",
                "RevenuesNetOfInterestExpense"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "op_income": ["OperatingIncomeLoss"],
    "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "liabilities": ["Liabilities"],
    "shares": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
}
FLOWS = ["eps", "revenue", "net_income", "op_income"]  # 기간 합계 (최근 4분기 합 = TTM)
STOCKS = ["equity", "liabilities"]  # 시점 잔액

FUND_KEYS = ["per", "pbr", "psr", "roe", "op_margin", "rev_growth", "eps_growth", "debt_ratio"]


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def _cached(name: str, url: str) -> dict | None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / name
    if not path.exists() or time.time() - path.stat().st_mtime > MAX_AGE_DAYS * 86400:
        try:
            path.write_bytes(_get(url))
        except Exception:
            if not path.exists():
                return None
        time.sleep(0.12)  # SEC 초당 10회 제한
    try:
        return json.loads(path.read_bytes())
    except ValueError:
        return None


def cik_map() -> dict[str, int]:
    data = _cached("company_tickers.json", "https://www.sec.gov/files/company_tickers.json") or {}
    return {v["ticker"].upper().replace(".", "-"): int(v["cik_str"]) for v in data.values()}


# ---------------------------------------------------------------- 공시 → 시점별 값

@dataclass
class Series:
    """한 개념의 값들: (기간 끝, 공시일, 값). 흐름 항목은 분기(약 91일) 값."""
    end: list[pd.Timestamp] = field(default_factory=list)
    filed: list[pd.Timestamp] = field(default_factory=list)
    val: list[float] = field(default_factory=list)


def _facts(gaap: dict, tags: list[str], unit: str) -> list[dict]:
    """여러 태그의 사실들을 합친다 (단위가 정확히 unit 인 것만). 같은 기간은 앞쪽 태그 우선."""
    seen, out = set(), []
    for tag in tags:
        for f in gaap.get(tag, {}).get("units", {}).get(unit, []):
            key = (f.get("start"), f["end"])
            if key in seen:
                continue
            seen.add(key)
            out.append(f)
    return out


def _first_filed(facts: list[dict], min_days: int, max_days: int | None) -> dict[pd.Timestamp, tuple[pd.Timestamp, float]]:
    """기간 길이 조건에 맞는 사실을 기간 끝별로, 가장 먼저 공시된 값만 남긴다."""
    out: dict[pd.Timestamp, tuple[pd.Timestamp, float]] = {}
    for f in facts:
        end, filed = pd.Timestamp(f["end"]), pd.Timestamp(f["filed"])
        if max_days is not None:
            if "start" not in f:
                continue
            days = (end - pd.Timestamp(f["start"])).days
            if not (min_days <= days <= max_days):
                continue
        if end not in out or filed < out[end][0]:
            out[end] = (filed, float(f["val"]))
    return out


def flow_quarters(facts: list[dict]) -> Series:
    """분기 값. 10-K에만 있는 4분기는 연간 − (1~3분기)로 만든다."""
    q = _first_filed(facts, 80, 100)
    annual = _first_filed(facts, 350, 380)
    for end, (filed, total) in annual.items():
        if end in q:
            continue
        prior = [e for e in q if pd.Timedelta(days=60) < end - e < pd.Timedelta(days=300)]
        if len(prior) == 3:
            q[end] = (max(filed, *(q[e][0] for e in prior)), total - sum(q[e][1] for e in prior))
    s = Series()
    for end in sorted(q):
        s.end.append(end)
        s.filed.append(q[end][0])
        s.val.append(q[end][1])
    return s


def stock_values(facts: list[dict]) -> Series:
    v = _first_filed(facts, 0, None)
    s = Series()
    for end in sorted(v):
        s.end.append(end)
        s.filed.append(v[end][0])
        s.val.append(v[end][1])
    return s


def ttm(s: Series, t: pd.Timestamp, years_back: int = 0) -> float:
    """t 시점까지 공시된 최근 4분기 합 (years_back=1 이면 그 1년 전 4분기 합)."""
    known = [(e, v) for e, f, v in zip(s.end, s.filed, s.val) if f <= t]
    if len(known) < 4 + 4 * years_back:
        return np.nan
    known = known[len(known) - 4 - 4 * years_back : len(known) - 4 * years_back]
    span = (known[-1][0] - known[0][0]).days
    if not 250 <= span <= 300:  # 연속된 4분기가 아니면 버린다
        return np.nan
    return float(sum(v for _, v in known))


def latest(s: Series, t: pd.Timestamp) -> float:
    known = [v for f, v in zip(s.filed, s.val) if f <= t]
    return known[-1] if known else np.nan


@dataclass
class Company:
    series: dict[str, Series]

    def at(self, t: pd.Timestamp, price: float) -> dict[str, float]:
        """t 시점, 주가 price 기준 재무지표."""
        s = self.series
        eps, eps_prev = ttm(s["eps"], t), ttm(s["eps"], t, 1)
        rev, rev_prev = ttm(s["revenue"], t), ttm(s["revenue"], t, 1)
        ni, op = ttm(s["net_income"], t), ttm(s["op_income"], t)
        equity, liab, shares = latest(s["equity"], t), latest(s["liabilities"], t), latest(s["shares"], t)
        bvps = equity / shares if shares and shares > 0 else np.nan
        sps = rev / shares if shares and shares > 0 else np.nan
        return {
            "per": price / eps if eps > 0 else np.nan,  # 적자면 PER 없음
            "pbr": price / bvps if bvps > 0 else np.nan,
            "psr": price / sps if sps > 0 else np.nan,
            "roe": ni / equity if equity > 0 else np.nan,
            "op_margin": op / rev if rev > 0 else np.nan,
            "rev_growth": rev / rev_prev - 1 if rev_prev > 0 else np.nan,
            "eps_growth": (eps - eps_prev) / abs(eps_prev) if eps_prev and not np.isnan(eps_prev) else np.nan,
            "debt_ratio": liab / equity if equity > 0 else np.nan,
        }


def _split_adjust(facts: list[dict], splits: pd.Series | None, per_share: bool) -> list[dict]:
    """공시 당시 기준 주당 숫자를 현재 주식 수 기준으로 맞춘다 (주가가 분할 조정돼 있으므로).
    공시일 뒤에 있었던 분할 비율을 모두 곱해, 주당값은 나누고 주식 수는 곱한다.
    4분기 = 연간 − (1~3분기) 계산 전에 해야 분할 전후 숫자가 섞이지 않는다."""
    if splits is None or splits.empty:
        return facts
    out = []
    for f in facts:
        factor = float(splits[splits.index > pd.Timestamp(f["filed"])].prod())
        out.append({**f, "val": f["val"] / factor if per_share else f["val"] * factor})
    return out


def parse_company(facts_json: dict, splits: pd.Series | None = None) -> Company:
    """splits: 분할일 → 비율 (예: 4:1 분할이면 4.0)."""
    gaap = facts_json.get("facts", {}).get("us-gaap", {})
    series = {}
    for key, tags in TAGS.items():
        unit = {"eps": "USD/shares", "shares": "shares"}.get(key, "USD")
        facts = _facts(gaap, tags, unit)
        if key == "shares":
            series[key] = _shares(_split_adjust(facts, splits, per_share=False))
        elif key == "eps":
            series[key] = flow_quarters(_split_adjust(facts, splits, per_share=True))
        elif key in FLOWS:
            series[key] = flow_quarters(facts)
        else:
            series[key] = stock_values(facts)
    return Company(series)


def _shares(facts: list[dict]) -> Series:
    """분기 가중평균 희석주식수 (시점 잔액처럼 최신값을 쓴다)."""
    q = _first_filed(facts, 80, 100)
    s = Series()
    for end in sorted(q):
        s.end.append(end)
        s.filed.append(q[end][0])
        s.val.append(q[end][1])
    return s


def load_companies(tickers: list[str], splits: pd.DataFrame | None = None, log=print) -> dict[str, Company]:
    """splits: 날짜 × 종목 분할 비율 (분할 없는 날은 0 또는 1)."""
    ciks = cik_map()
    out = {}
    for t in tickers:
        cik = ciks.get(t.upper())
        if cik is None:
            continue
        data = _cached(f"CIK{cik:010d}.json", f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json")
        if data:
            sp = None
            if splits is not None and t in splits:
                col = splits[t]
                sp = col[(col > 0) & (col != 1)]
            out[t] = parse_company(data, sp)
    log(f"재무 데이터: {len(out)}/{len(tickers)} 종목")
    return out

"""커맨드라인: python -m mijang AAPL MSFT NVDA --period 3y"""

from __future__ import annotations

import argparse
import math

import pandas as pd

from .indicators import INDICATOR_LABELS, PERCENT_KEYS, compute_indicators


def fetch_prices(tickers: list[str], period: str) -> pd.DataFrame:
    import yfinance as yf

    data = yf.download(tickers, period=period, auto_adjust=True, progress=False)
    close = data["Close"]
    if isinstance(close, pd.Series):
        close = close.to_frame(tickers[0])
    return close


def fmt(key: str, value: float) -> str:
    if value is None or math.isnan(value):
        return "-"
    return f"{value * 100:,.2f}%" if key in PERCENT_KEYS else f"{value:,.2f}"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="미국 주식 수익률 10대 지표")
    parser.add_argument("tickers", nargs="+", help="티커 (예: AAPL MSFT NVDA)")
    parser.add_argument("--period", default="1y", help="기간: 6mo, 1y, 3y, 5y, 10y, max")
    parser.add_argument("--benchmark", default="SPY", help="베타/알파 기준 지수 (기본 SPY)")
    parser.add_argument("--rf", type=float, default=0.04, help="연 무위험 수익률 (기본 0.04)")
    args = parser.parse_args(argv)

    tickers = [t.upper() for t in args.tickers]
    bench = args.benchmark.upper()
    prices = fetch_prices(sorted(set(tickers + [bench])), args.period)

    table = {}
    for t in tickers:
        if t not in prices or prices[t].dropna().empty:
            print(f"[경고] {t} 데이터 없음")
            continue
        result = compute_indicators(prices[t], prices.get(bench), args.rf)
        table[t] = {INDICATOR_LABELS[k]: fmt(k, v) for k, v in result.items()}

    if table:
        with pd.option_context("display.max_columns", None, "display.width", 200):
            print(f"\n기간: {args.period} | 벤치마크: {bench} | 무위험수익률: {args.rf:.2%}\n")
            print(pd.DataFrame(table).to_string())


if __name__ == "__main__":
    main()

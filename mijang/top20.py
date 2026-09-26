"""최근 5년 수익률 상위 20개 미국 종목 선정: python -m mijang.top20"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .indicators import cagr, max_drawdown, total_return

UNIVERSE_FILE = Path(__file__).resolve().parent.parent / "data" / "universe.txt"


def load_universe(path: Path = UNIVERSE_FILE) -> dict[str, str]:
    """{티커: 한글이름}"""
    universe = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            ticker, _, name = line.partition(" ")
            universe[ticker.upper()] = name.strip() or ticker.upper()
    return universe


def rank(prices: pd.DataFrame, top: int = 20, years: int = 5) -> pd.DataFrame:
    """전체 기간 데이터가 있는 종목만 5년 누적 수익률 순으로 정렬한다."""
    start_limit = prices.index[-1] - pd.DateOffset(years=years) + pd.Timedelta(days=31)
    rows = []
    for ticker in prices.columns:
        p = prices[ticker].dropna()
        if len(p) < 2 or p.index[0] > start_limit:
            continue  # 상장 5년 미만
        rows.append(
            {
                "ticker": ticker,
                "return_5y": total_return(p),
                "cagr": cagr(p),
                "mdd": max_drawdown(p),
                "price": float(p.iloc[-1]),
            }
        )
    df = pd.DataFrame(rows).sort_values("return_5y", ascending=False).head(top)
    df.index = range(1, len(df) + 1)
    return df


def main(argv: list[str] | None = None) -> None:
    import yfinance as yf

    parser = argparse.ArgumentParser(description="5년 수익률 상위 미국 종목")
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args(argv)

    universe = load_universe()
    data = yf.download(list(universe), period="5y", interval="1wk", auto_adjust=True, progress=False)
    result = rank(data["Close"], top=args.top)
    result.insert(1, "name", result["ticker"].map(universe))
    fmt = result.copy()
    for col in ("return_5y", "cagr", "mdd"):
        fmt[col] = fmt[col].map(lambda v: f"{v * 100:,.1f}%")
    fmt["price"] = fmt["price"].map(lambda v: f"${v:,.2f}")
    print(fmt.to_string())


if __name__ == "__main__":
    main()

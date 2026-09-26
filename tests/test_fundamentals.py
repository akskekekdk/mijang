import numpy as np
import pandas as pd
import pytest

from mijang import fundamentals as f


def fact(start, end, val, filed):
    d = {"end": end, "val": val, "filed": filed}
    if start:
        d["start"] = start
    return d


def company(splits=None):
    """분기 EPS 1.0씩(분할 전 기준). 연간 10-K는 분할 뒤 공시돼 분할 후 기준(0.4)."""
    eps = [
        fact("2023-01-01", "2023-03-31", 1.0, "2023-04-20"),
        fact("2023-04-01", "2023-06-30", 1.0, "2023-07-20"),
        fact("2023-07-01", "2023-09-30", 1.0, "2023-10-20"),
        fact("2023-01-01", "2023-12-31", 0.4, "2024-02-20"),  # 연간, 10:1 분할(2024-01-10) 뒤 공시
    ]
    gaap = {
        "EarningsPerShareDiluted": {"units": {"USD/shares": eps}},
        "StockholdersEquity": {"units": {"USD": [fact(None, "2023-12-31", 1000.0, "2024-02-20")]}},
        "WeightedAverageNumberOfDilutedSharesOutstanding": {"units": {"shares": [
            fact("2023-10-01", "2023-12-31", 100.0, "2024-02-20")]}},
    }
    return f.parse_company({"facts": {"us-gaap": gaap}}, splits)


def test_q4_derived_after_split_adjustment():
    c = company(pd.Series({pd.Timestamp("2024-01-10"): 10.0}))
    q = c.series["eps"]
    # 1~3분기는 분할 전 공시 → /10 = 0.1, 4분기 = 0.4 − 0.3 = 0.1
    assert q.val == pytest.approx([0.1, 0.1, 0.1, 0.1])
    assert f.ttm(q, pd.Timestamp("2024-03-01")) == pytest.approx(0.4)
    assert c.at(pd.Timestamp("2024-03-01"), 8.0)["per"] == pytest.approx(20.0)


def test_no_lookahead_before_filing():
    c = company(pd.Series({pd.Timestamp("2024-01-10"): 10.0}))
    # 연간 공시(2024-02-20) 전에는 4분기가 없으니 TTM도 없다
    assert np.isnan(f.ttm(c.series["eps"], pd.Timestamp("2024-02-19")))
    assert np.isnan(c.at(pd.Timestamp("2024-02-19"), 8.0)["pbr"])
    assert c.at(pd.Timestamp("2024-02-20"), 8.0)["pbr"] == pytest.approx(8.0 / (1000.0 / 100.0))

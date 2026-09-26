# mijang — 미장(미국 주식) 수익률 10대 지표

Yahoo Finance 데이터(`yfinance`)로 미국 주식의 수익률·위험을 10가지 지표로 계산합니다.

## 10가지 지표

| # | 지표 | 의미 | 해석 |
|---|------|------|------|
| 1 | 누적 수익률 (Total Return) | 기간 전체 가격 변화 `마지막가/첫가 - 1` | 배당 재투자 반영(수정주가) |
| 2 | CAGR | 연평균 복리 수익률 | 기간이 다른 종목끼리 비교할 때 |
| 3 | 연환산 변동성 | 일간 수익률 표준편차 × √252 | 높을수록 가격 출렁임이 큼 |
| 4 | 샤프 지수 | (수익률 − 무위험수익률) / 변동성 | 1 이상 양호, 2 이상 우수 |
| 5 | 소르티노 지수 | 샤프와 같지만 **하락** 변동성만 위험으로 봄 | 상승 변동성은 벌점 없음 |
| 6 | MDD (최대 낙폭) | 고점 대비 최대 하락률 | 최악의 경우 얼마나 물렸나 |
| 7 | 칼마 지수 | CAGR / \|MDD\| | 낙폭 대비 수익 효율 |
| 8 | 베타 | 벤치마크(기본 SPY) 대비 민감도 | 1보다 크면 시장보다 크게 움직임 |
| 9 | 젠센 알파 | 베타로 설명되지 않는 연 초과수익 | 양수면 시장 대비 초과 성과 |
| 10 | 일간 승률 | 상승 마감한 거래일 비율 | 50% 이상이면 오른 날이 더 많음 |

## 설치 & 실행

```bash
pip install -r requirements.txt

python -m mijang AAPL MSFT NVDA                 # 기본: 최근 1년, SPY 기준, 무위험 4%
python -m mijang TSLA QQQ --period 5y           # 기간: 6mo, 1y, 3y, 5y, 10y, max
python -m mijang AAPL --benchmark QQQ --rf 0.045
```

코드에서 직접 사용:

```python
from mijang import compute_indicators
result = compute_indicators(prices, benchmark=spy_prices, risk_free=0.04)
```

## 테스트

```bash
pytest -q
```

GitHub에 푸시하면 `.github/workflows/test.yml`이 자동으로 테스트를 돌립니다.

## Git 푸시 세팅

처음 한 번:

```bash
git clone https://github.com/akskekekdk/mijang.git
cd mijang
git config user.name  "내 이름"
git config user.email "내 이메일"
```

작업 후 푸시:

```bash
git add .
git commit -m "변경 내용"
git push -u origin <브랜치명>   # 처음 한 번만 -u, 이후엔 git push
```

HTTPS 푸시 시 비밀번호 대신 GitHub Personal Access Token(Settings → Developer settings → Tokens)을 사용하세요.
`git config --global credential.helper store` 로 한 번 입력한 토큰을 저장할 수 있습니다.

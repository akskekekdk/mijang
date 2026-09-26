# mijang — 미장(미국 주식) 수익률 도구

<img src="android/tools/icon_preview.png" width="96" align="right" alt="미장 아이콘">

1. **안드로이드 앱 "미장"**: 최근 5년 수익률 상위 20개 미국 종목을 골라 잠금화면 알림으로 보여줍니다.
2. **Python 도구**: 종목별 수익률 10대 지표 계산, 5년 수익률 TOP 20 출력.

## 📱 안드로이드 앱 설치

휴대폰 브라우저에서 GitHub에 로그인한 뒤 아래 링크로 APK를 받아 설치하세요.

**https://github.com/akskekekdk/mijang/releases/latest/download/mijang.apk**

- 처음 설치할 때 "출처를 알 수 없는 앱 설치"를 허용해야 합니다.
- 앱을 처음 열면 알림 권한을 허용하세요. 5년 데이터를 모으느라 첫 로딩에 1분 정도 걸립니다.
- main에 푸시할 때마다 새 APK가 자동으로 빌드됩니다. 같은 링크로 받아 덮어서 설치하면 됩니다.

### 동작 방식

- **종목 선정**: `data/universe.txt`의 S&P 100 + 나스닥 100 종목 중 상장한 지 5년이 넘은 종목을
  최근 5년 누적 수익률(수정주가, 배당 재투자 반영) 순으로 정렬해 상위 20개를 고릅니다. 순위는 하루에 한 번 다시 계산합니다.
- **알림**: 1시간마다 현재가와 전일 대비 등락률을 받아서 알림 2개(1~10위, 11~20위)로 띄웁니다.
  상승은 빨강, 하락은 파랑으로 표시하고 맨 아래에 `09.26(토) 09:47 기준`처럼 조회 시각을 붙입니다.
- **잠금화면 표시**: 삼성 휴대폰은 `설정 → 잠금화면 → 알림`에서 "상세히 보기"를 켜야 내용까지 보입니다.
  배터리 최적화 때문에 갱신이 늦으면 `설정 → 애플리케이션 → 미장 → 배터리 → 제한 없음`으로 바꾸세요.

## 5년 수익률 TOP 20 (Python)

```bash
python -m mijang.top20
```

## 수익률 10대 지표 (Python)

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
git push origin main
```

HTTPS 푸시 시 비밀번호 대신 GitHub Personal Access Token(Settings → Developer settings → Tokens)을 사용하세요.
`git config --global credential.helper store` 로 한 번 입력한 토큰을 저장할 수 있습니다.

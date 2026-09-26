# mijang — 미장(미국 주식) 수익률 도구

<img src="android/tools/icon_preview.png" width="96" align="right" alt="미장 아이콘">

1. **안드로이드 앱 "미장"**: 과거 지표→수익률 패턴을 학습한 모델이 고른 유망 미국 종목 20개를 잠금화면 알림으로 보여줍니다.
2. **Python 도구**: 예측 모델(`mijang.model`), 종목별 수익률 10대 지표, 5년 수익률 TOP 20.

## 📱 안드로이드 앱 설치

휴대폰 브라우저에서 GitHub에 로그인한 뒤 아래 링크로 APK를 받아 설치하세요.

**https://github.com/akskekekdk/mijang/releases/latest/download/mijang.apk**

- 처음 설치할 때 "출처를 알 수 없는 앱 설치"를 허용해야 합니다.
- 앱을 처음 열면 알림 권한을 허용하세요.
- main에 푸시할 때마다 새 APK가 자동으로 빌드됩니다. 같은 링크로 받아 덮어서 설치하면 됩니다.

### 동작 방식

**예측 모델** (`mijang/model.py`, GitHub Actions가 매일 한국시간 07:30에 다시 학습)

1. 지난 10년 동안 매월 말, 종목마다 직전 1년 가격으로 **10대 지표**(누적수익률, CAGR, 변동성, 샤프,
   소르티노, MDD, 칼마, 베타, 알파, 승률)와 모멘텀(1개월·3개월 수익률, 52주 고점 대비)을 계산합니다.
2. 정답은 **그 뒤 3개월 동안 SPY(S&P 500)보다 더 올랐는지**입니다.
3. 그래디언트 부스팅 분류기가 "이런 지표일 때 → 시장을 이길 확률"을 학습합니다.
   지표는 같은 달 종목끼리의 순위(0~1)로 바꿔서, 상승장인지 하락장인지와 상관없이 비교되게 했습니다.
4. 오늘 지표를 넣어 확률이 높은 20개를 `data/predictions.json`에 저장하면, 앱이 이 파일을 받아 갑니다.

**성능 (워크포워드 백테스트: 과거로만 학습 → 다음 해 예측, 2020-01 ~ 2026-05)**

| | 모델 상위 20 | 전체 종목 평균 |
|---|---|---|
| 3개월 뒤 SPY 대비 초과수익 (평균) | **+5.7%** | +0.8% |
| SPY를 이긴 종목 비율 | 52.4% | 47.6% |
| 상위 20이 전체 평균보다 나았던 달 | 62.3% | – |

개별 종목 적중력(AUC 0.53)은 동전 던지기보다 약간 나은 수준입니다. 상위 20개를 묶었을 때만 차이가 납니다.
또 후보 종목이 **지금** S&P 100/나스닥 100에 들어 있는 회사들이라(생존 편향) 실제 성과는 백테스트보다 낮을 가능성이 큽니다.
**참고용이며 수익을 보장하지 않습니다.**

**앱**

- 3시간마다 예측 파일을, 1시간마다 현재가·전일 대비 등락률을 받아 알림 2개(1~10위, 11~20위)로 띄웁니다.
  상승은 빨강, 하락은 파랑이고, 맨 아래에 `09.26(토) 09:47 기준`처럼 조회 시각이 붙습니다.
- 앱 화면에는 종목별 "확률"(향후 3개월 SPY를 이길 확률, 모델 추정)과 백테스트 요약이 나옵니다.
- **잠금화면 표시**: 삼성 휴대폰은 `설정 → 잠금화면 → 알림`에서 "상세히 보기"를 켜야 내용까지 보입니다.
  배터리 최적화 때문에 갱신이 늦으면 `설정 → 애플리케이션 → 미장 → 배터리 → 제한 없음`으로 바꾸세요.

## 예측 모델 직접 실행 (Python)

```bash
python -m mijang.model            # 학습 + 백테스트 + 오늘 예측 → data/predictions.json
```

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

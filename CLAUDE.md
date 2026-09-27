# 작업 규칙

- 모든 작업은 **main 브랜치**에 커밋하고 `git push origin main` 으로 푸시한다. 별도 브랜치를 만들지 않는다.
- 커밋 메시지는 한국어로 짧게.

# 구조

- `mijang/` — Python: 10대 수익률 지표(`indicators.py`), 예측 모델(`model.py`), SEC 재무지표(`fundamentals.py`), 5년 수익률 TOP 20(`top20.py`). 테스트는 `pytest -q`.
  - 재무지표는 공시일(filed) 기준으로만 써서 미래 정보가 섞이지 않게 한다. 주당 숫자는 공시 원본 단계에서 분할 조정한다.
  - SEC 요청 User-Agent는 환경변수 `SEC_USER_AGENT`로 바꿀 수 있다. 원본은 `.cache/edgar`에 캐시(커밋 안 함).
- `data/predictions.json` — 모델 예측 결과. `predict.yml`이 매일 다시 만들어 main에 커밋하고, 앱이 raw URL로 받아 간다. 형식을 바꾸면 앱 파서(`Model.kt`)도 같이 바꾼다.
- `data/universe.txt` — 후보 종목(티커 + 한글이름). 모델 학습 대상.
- `android/` — 안드로이드 앱 "미장". `./gradlew testDebugUnitTest assembleDebug`.
  - main에 푸시하면 GitHub Actions가 APK를 빌드해 Releases의 `latest`에 올린다.
  - 같이 올리는 `version.json`(versionCode = 빌드 번호)으로 앱이 새 버전을 확인하고 앱 안에서 업데이트한다(`Updater.kt`).
  - 서명 키 `android/app/mijang.keystore`는 저장소에 둔다. 바꾸면 기존 설치본이 업데이트되지 않는다.
  - 아이콘은 `android/tools/make_icons.py`로 생성 (Noto Sans CJK KR Bold 필요).

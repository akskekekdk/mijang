# 작업 규칙

- 모든 작업은 **main 브랜치**에 커밋하고 `git push origin main` 으로 푸시한다. 별도 브랜치를 만들지 않는다.
- 커밋 메시지는 한국어로 짧게.

# 구조

- `mijang/` — Python: 10대 수익률 지표(`indicators.py`), 5년 수익률 TOP 20(`top20.py`). 테스트는 `pytest -q`.
- `data/universe.txt` — 후보 종목(티커 + 한글이름). Python과 안드로이드 앱이 같은 파일을 쓴다.
- `android/` — 안드로이드 앱 "미장". `./gradlew testDebugUnitTest assembleDebug`.
  - main에 푸시하면 GitHub Actions가 APK를 빌드해 Releases의 `latest`에 올린다.
  - 아이콘은 `android/tools/make_icons.py`로 생성 (Noto Sans CJK KR Bold 필요).

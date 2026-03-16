# AI 기반 QA 자동화 플랫폼

Claude AI API로 테스트 케이스를 자동 생성하고, Playwright로 브라우저 자동화 실행,
SQLite에 결과를 저장하고, Streamlit 대시보드로 시각화하며, Slack으로 알림을 전송하는
end-to-end QA 자동화 플랫폼입니다.

## 시스템 흐름

기능 명세 입력
→ AI 테스트 케이스 생성 (Claude API)
→ Playwright 자동화 실행
→ 결과 데이터 저장 (SQLite)
→ 품질 분석 리포트 (Streamlit 대시보드)
→ Slack 알림

## 기술 스택

| 분류 | 기술 |
|------|------|
| 언어 | Python 3.13 |
| 브라우저 자동화 | Playwright 1.58 |
| AI | Claude API (Anthropic) |
| 데이터베이스 | SQLite3 |
| 데이터 분석 | pandas |
| 대시보드 | Streamlit |
| 알림 | Slack Incoming Webhook |
| 테스트 프레임워크 | pytest |

## 프로젝트 구조
qa-automation-platform/
├── ai_generator/          # AI 테스트 케이스 생성 모듈
├── test_runner/           # Playwright 자동화 실행 모듈
├── analyzer/              # DB 저장 및 결과 분석 모듈
├── dashboard/             # Streamlit 대시보드
├── notifier/              # Slack 알림 모듈
├── tests/generated/       # 생성된 테스트 케이스 및 pytest 파일
├── data/                  # 실행 결과 데이터 (DB, 스크린샷, 로그, 리포트)
├── .env                   # 환경변수 설정
└── requirements.txt       # 패키지 목록

## 환경 설정

**1. 가상환경 생성 및 활성화**
```bash
python -m venv venv
venv\Scripts\activate  # Windows
```

**2. 패키지 설치**
```bash
pip install -r requirements.txt
```

**3. Playwright 브라우저 설치**
```bash
playwright install chromium
```

**4. .env 파일 설정**
ANTHROPIC_API_KEY=your_api_key
SLACK_WEBHOOK_URL=your_webhook_url
TARGET_BASE_URL=https://www.saucedemo.com
PYTHONIOENCODING=utf-8

## 실행 방법

**1. AI 테스트 케이스 생성**
```bash
python ai_generator/case_generator.py
```

**2. Playwright 자동화 실행 (DB 저장 + Slack 알림 포함)**
```bash
python test_runner/playwright_runner.py
```

**3. pytest로 실행**
```bash
python -m pytest tests/generated/test_login.py -v
```

**4. Streamlit 대시보드 실행**
```bash
streamlit run dashboard/app.py
```

**5. 분석 리포트 출력**
```bash
python analyzer/report_generator.py
```

## 개발 이력

| Phase | 내용 |
|-------|------|
| Phase 1 | 환경 설정 |
| Phase 2 | AI 테스트 케이스 생성 모듈 |
| Phase 3 | Playwright 자동화 실행 |
| Phase 4 | 결과 저장 및 분석 대시보드 |
| Phase 5 | Slack 알림 연동 |
| Phase 6 | 통합 테스트 및 문서화 |

# config/settings.py

import os
from dotenv import load_dotenv

# .env 파일에서 환경변수 불러오기
load_dotenv()

# ===========================
# Claude API 설정
# ===========================
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# ===========================
# Slack 설정
# ===========================
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

# ===========================
# 테스트 대상 설정
# ===========================
TARGET_BASE_URL = os.getenv("TARGET_BASE_URL", "https://www.saucedemo.com")

# ===========================
# 파일 경로 설정
# ===========================
SCREENSHOT_DIR = os.getenv("SCREENSHOT_DIR", "data/screenshots")
DB_PATH = os.getenv("DB_PATH", "data/results.db")
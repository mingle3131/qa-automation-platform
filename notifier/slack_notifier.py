import sys
import os

# 프로젝트 루트를 Python 경로에 추가
# → 어떤 위치에서 실행하든 프로젝트 내 모듈을 찾을 수 있게 함
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from dotenv import load_dotenv

# .env 파일에서 환경변수 로드
load_dotenv()

# Slack Incoming Webhook URL (.env에서 읽기)
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")


def _build_progress_bar(pass_rate: float) -> str:
    # 성공률을 10칸짜리 블록 막대로 변환
    # 예: 80.0 → "████████░░"
    filled = round(pass_rate / 10)  # 채울 칸 수 (0~10)
    empty = 10 - filled
    return "█" * filled + "░" * empty


def _build_status_text(pass_rate: float) -> str:
    # 성공률에 따라 상태 텍스트 결정
    if pass_rate == 100.0:
        return "전체 통과"
    elif pass_rate >= 80.0:
        return "일부 실패 — 점검 권장"
    else:
        return "다수 실패 — 즉시 확인 필요"


def send_slack_notification(summary: dict) -> bool:
    # Slack Incoming Webhook으로 QA 테스트 결과를 전송하는 함수
    # summary: {"total": int, "pass": int, "fail": int, "pass_rate": float}
    # 반환값: 전송 성공 True, 실패 False

    # Webhook URL이 없으면 경고 출력 후 종료
    if not SLACK_WEBHOOK_URL:
        print("[경고] SLACK_WEBHOOK_URL이 설정되지 않았습니다. .env 파일을 확인해주세요.")
        return False

    total = summary.get("total", 0)
    passed = summary.get("pass", 0)
    failed = summary.get("fail", 0)
    pass_rate = summary.get("pass_rate", 0.0)

    # 성공률 막대 및 상태 텍스트 생성
    progress_bar = _build_progress_bar(pass_rate)
    status_text = _build_status_text(pass_rate)

    # Slack 메시지 본문 구성 (mrkdwn 형식)
    message = (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "QA 자동화 테스트 결과\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"전체: {total}건\n"
        f"PASS: {passed}건\n"
        f"FAIL: {failed:2d}건\n"
        f"성공률: [{progress_bar}] {pass_rate}%\n"
        f"상태: {status_text}\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

    # Slack Block Kit 페이로드 구성 (text 타입: mrkdwn)
    payload = {
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message,
                },
            }
        ]
    }

    # Webhook URL로 POST 요청 전송
    response = requests.post(SLACK_WEBHOOK_URL, json=payload)

    # 응답 코드로 성공/실패 판단
    if response.status_code == 200:
        print("[Slack] 알림 전송 성공")
        return True
    else:
        print(f"[Slack] 알림 전송 실패 (HTTP {response.status_code}: {response.text})")
        return False


if __name__ == "__main__":
    # 더미 데이터로 Slack 알림 전송 테스트
    dummy_summary = {
        "total": 15,
        "pass": 12,
        "fail": 3,
        "pass_rate": 80.0,
    }

    print("[테스트] 더미 데이터로 Slack 알림 전송 중...")
    result = send_slack_notification(dummy_summary)
    print(f"[테스트] 전송 결과: {'성공' if result else '실패'}")

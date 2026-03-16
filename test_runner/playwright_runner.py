"""
Playwright 기반 브라우저 자동화 테스트 러너
saucedemo.com 로그인 테스트를 실행하고 결과를 스크린샷으로 저장합니다.
"""

from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright


# 스크린샷 저장 경로
SCREENSHOT_DIR = Path(__file__).parent.parent / "data" / "screenshots"

# 테스트 대상 설정
TARGET_URL = "https://www.saucedemo.com"
USERNAME = "standard_user"
PASSWORD = "secret_sauce"


def save_screenshot(page, result: str) -> Path:
    """
    현재 페이지 스크린샷을 저장합니다.

    파일명 형식: login_PASS_20250316_143022.png
    """
    # 스크린샷 저장 폴더가 없으면 생성
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    # 타임스탬프 생성 (YYYYMMDD_HHMMSS)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 파일명 조합
    filename = f"login_{result}_{timestamp}.png"
    filepath = SCREENSHOT_DIR / filename

    # 스크린샷 저장
    page.screenshot(path=str(filepath))
    print(f"[스크린샷] 저장 완료: {filepath}")

    return filepath


def run_login_test():
    """
    saucedemo.com 로그인 테스트를 실행합니다.

    판정 기준: 로그인 후 URL에 'inventory' 포함 여부
    - 포함 시 → PASS
    - 미포함 시 → FAIL
    """
    with sync_playwright() as p:
        # Chromium 브라우저 실행 (headless=False: 창이 화면에 보이게)
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        try:
            # 1. 테스트 대상 URL 접속
            print(f"[접속] {TARGET_URL}")
            page.goto(TARGET_URL)

            # 2. 아이디 입력
            print(f"[입력] 아이디: {USERNAME}")
            page.fill("#user-name", USERNAME)

            # 3. 비밀번호 입력
            print(f"[입력] 비밀번호: {'*' * len(PASSWORD)}")
            page.fill("#password", PASSWORD)

            # 4. 로그인 버튼 클릭
            print("[클릭] 로그인 버튼")
            page.click("#login-button")

            # 5. 페이지 로딩 대기 (URL 변경 감지)
            page.wait_for_load_state("networkidle")

            # 6. 현재 URL 확인 후 PASS/FAIL 판정
            current_url = page.url
            print(f"[URL] 로그인 후 현재 URL: {current_url}")

            if "inventory" in current_url:
                result = "PASS"
                print(f"[결과] {result} - 'inventory' URL 확인됨")
            else:
                result = "FAIL"
                print(f"[결과] {result} - 'inventory' URL 미확인 (현재: {current_url})")

            # 7. 결과 스크린샷 저장
            screenshot_path = save_screenshot(page, result)

        except Exception as e:
            # 예외 발생 시 FAIL 처리 후 스크린샷 저장
            result = "FAIL"
            print(f"[오류] 테스트 중 예외 발생: {e}")
            screenshot_path = save_screenshot(page, result)

        finally:
            # 브라우저 종료
            browser.close()
            print("[종료] 브라우저 닫힘")

    return result


if __name__ == "__main__":
    print("=" * 50)
    print("  saucedemo.com 로그인 테스트 시작")
    print("=" * 50)

    final_result = run_login_test()

    print("=" * 50)
    print(f"  최종 결과: {final_result}")
    print("=" * 50)

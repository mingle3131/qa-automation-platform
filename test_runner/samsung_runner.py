import sys
import os

# 프로젝트 루트를 Python 경로에 추가
# → 어떤 위치에서 실행하든 analyzer, notifier 등 모듈을 찾을 수 있게 함
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright
from analyzer.db_manager import save_result, create_tables, get_summary
from notifier.slack_notifier import send_slack_notification


# 테스트 대상 URL
SAMSUNG_URL = "https://www.samsung.com/sec/"

# 검증할 기획전 하위 메뉴 8개
MENU_ITEMS = [
    {"test_id": "TC-001", "name": "스페셜"},
    {"test_id": "TC-002", "name": "모바일"},
    {"test_id": "TC-003", "name": "TV/영상음향"},
    {"test_id": "TC-004", "name": "주방가전"},
    {"test_id": "TC-005", "name": "리빙가전"},
    {"test_id": "TC-006", "name": "PC/주변기기"},
    {"test_id": "TC-007", "name": "액세서리"},
    {"test_id": "TC-008", "name": "스마트싱스"},
]

# 스크린샷 저장 경로
SCREENSHOT_DIR = Path(__file__).parent.parent / "data" / "screenshots"


def run_samsung_menu_test() -> list:
    # samsung.com 기획전 하위 메뉴 8개 노출 여부를 검증하는 함수
    # 반환값: [{"test_id": ..., "name": ..., "result": ...}, ...] 형식의 결과 리스트

    # 실행 세션 식별용 run_id 생성 (함수 시작 시 한 번만 생성)
    run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S")

    results = []

    with sync_playwright() as p:
        # Chromium 브라우저 실행 (headless=False: 창이 화면에 보이게)
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1,
        )
        page = context.new_page()

        try:
            # 1. samsung.com 접속 후 페이지 로딩 완료 대기
            print(f"[접속] {SAMSUNG_URL}")
            page.goto(SAMSUNG_URL, timeout=60000)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(2)

            # 2. 햄버거 메뉴 버튼 클릭
            print("[클릭] 햄버거 메뉴 버튼")
            page.locator("button.nv00-gnb-v4__utility-hamburger").click()
            time.sleep(1)

            # 3. 기획전 옆 토글 버튼(>) 클릭 → 하위 메뉴 펼치기
            print("[클릭] 기획전 토글 버튼")
            page.locator("button.nv00-gnb-v4__l0-menu-toggle-btn[data-texten='promotion']").click()
            time.sleep(1)

            # 5. 하위 메뉴 탭 렌더링 대기 후 스크린샷 저장
            time.sleep(1)
            SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = SCREENSHOT_DIR / f"samsung_menu_{timestamp}.png"
            page.screenshot(path=str(screenshot_path))
            print(f"[스크린샷] 저장 완료: {screenshot_path}")

            # 6. 기획전 하위 메뉴 탭 8개 노출 여부 순회 검증
            for item in MENU_ITEMS:
                test_id = item["test_id"]
                name = item["name"]

                # 메뉴 탭 텍스트 요소가 화면에 보이는지 확인
                is_visible = page.locator(
                    "div.nv00-gnb-v4__l1-menu-container"
                ).get_by_text(name, exact=True).is_visible()

                result = "PASS" if is_visible else "FAIL"
                print(f"  [{test_id}] {name}: {result}")

                # DB에 결과 저장 (create_tables는 __main__에서 이미 호출)
                save_result(
                    test_id=test_id,
                    title=f"기획전 하위 메뉴 노출 확인 - {name}",
                    result=result,
                    screenshot_path=str(screenshot_path),
                    error_message=None if result == "PASS" else f"메뉴 탭 미노출: {name}",
                    run_id=run_id,
                )

                results.append({"test_id": test_id, "name": name, "result": result})

        except Exception as e:
            # 예외 발생 시 모든 항목을 FAIL로 기록
            print(f"[오류] 테스트 중 예외 발생: {e}")
            for item in MENU_ITEMS:
                # 이미 결과가 기록된 항목은 건너뜀
                if any(r["test_id"] == item["test_id"] for r in results):
                    continue
                save_result(
                    test_id=item["test_id"],
                    title=f"기획전 하위 메뉴 노출 확인 - {item['name']}",
                    result="FAIL",
                    screenshot_path=None,
                    error_message=str(e),
                    run_id=run_id,
                )
                results.append({"test_id": item["test_id"], "name": item["name"], "result": "FAIL"})

        finally:
            # 브라우저 종료
            browser.close()
            print("[종료] 브라우저 닫힘")

    return results


if __name__ == "__main__":
    # DB 테이블 초기화 (없으면 생성, 있으면 무시)
    create_tables()

    print("=" * 50)
    print("  samsung.com 기획전 메뉴 노출 테스트 시작")
    print("=" * 50)

    # 테스트 실행
    results = run_samsung_menu_test()

    # 결과 요약 출력
    total = len(results)
    passed = sum(1 for r in results if r["result"] == "PASS")
    failed = total - passed

    print("\n" + "=" * 50)
    print("  테스트 결과 요약")
    print("=" * 50)
    for r in results:
        icon = "✅" if r["result"] == "PASS" else "❌"
        print(f"  {icon} [{r['test_id']}] {r['name']}: {r['result']}")
    print("─" * 50)
    print(f"  총 {total}개 | 성공 {passed}개 | 실패 {failed}개")
    print("=" * 50)

    # DB 전체 통계 기반 Slack 알림 전송
    summary = get_summary()
    send_slack_notification(summary)

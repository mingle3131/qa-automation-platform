"""
Playwright 기반 브라우저 자동화 테스트 러너
saucedemo.com 로그인 테스트를 실행하고 결과를 스크린샷으로 저장합니다.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import re
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright
from analyzer.db_manager import save_result, create_tables, get_summary
from notifier.slack_notifier import send_slack_notification


# 스크린샷 저장 경로
SCREENSHOT_DIR = Path(__file__).parent.parent / "data" / "screenshots"

# 테스트 케이스 JSON 파일 저장 경로
TEST_CASES_DIR = Path(__file__).parent.parent / "tests" / "generated"

# 테스트 대상 URL
TARGET_URL = "https://www.saucedemo.com"

# 기본 로그인 정보 (test_case 없이 단독 실행 시 사용)
USERNAME = "standard_user"
PASSWORD = "secret_sauce"


def load_test_cases() -> list:
    # tests/generated/ 폴더에서 가장 최신 JSON 파일을 찾아 test_cases 리스트 반환

    # test_cases_*.json 패턴으로 파일 탐색
    json_files = sorted(TEST_CASES_DIR.glob("test_cases_*.json"))

    if not json_files:
        print("[오류] tests/generated/ 폴더에 테스트 케이스 파일이 없습니다.")
        return []

    # 파일명 오름차순 정렬 → 마지막 항목이 가장 최신 파일
    latest_file = json_files[-1]
    print(f"[로드] 테스트 케이스 파일: {latest_file}")

    # JSON 파일 읽기 (한글 깨짐 방지: utf-8 인코딩)
    with open(latest_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    test_cases = data.get("test_cases", [])
    print(f"[로드] 총 {len(test_cases)}개 테스트 케이스 로드 완료")
    return test_cases


def _parse_credentials(steps: list) -> tuple:
    # steps 리스트에서 username과 password를 정규식으로 추출
    # 예) "Username 필드에 'standard_user' 입력" → username = "standard_user"
    # 예) "Username 필드를 비워둠" → username = "" (빈 문자열)

    username = ""
    password = ""

    for step in steps:
        # Username 추출: 작은따옴표 안의 값 파싱
        match = re.search(r"Username 필드에 '(.+?)' 입력", step)
        if match:
            username = match.group(1)

        # Password 추출: 작은따옴표 안의 값 파싱
        match = re.search(r"Password 필드에 '(.+?)' 입력", step)
        if match:
            password = match.group(1)

    # 파싱 실패 시 기본값 없이 빈 문자열 그대로 반환
    # (단독 실행 시 기본값은 run_login_test() else 분기에서 처리)
    return username, password


def _check_expected_result(page, expected_result: str) -> bool:
    # expected_result 문자열을 분석하여 실제 페이지 상태와 비교, PASS 여부 반환

    current_url = page.url

    # 인벤토리 페이지 이동 여부 확인
    if "inventory" in expected_result:
        return "inventory" in current_url

    # 에러 메시지 표시 여부 확인 (data-test="error" 요소)
    if "에러 메시지" in expected_result:
        error_element = page.locator("[data-test='error']")
        return error_element.is_visible()

    # 비밀번호 마스킹 처리 여부 확인 (input type="password")
    if "마스킹" in expected_result:
        input_type = page.get_attribute("#password", "type")
        return input_type == "password"

    # X버튼으로 에러 메시지 닫기 확인
    # → 잘못된 자격증명으로 로그인하여 에러를 유발한 뒤, X버튼 클릭 후 에러가 사라졌는지 확인
    if "X버튼" in expected_result or "닫기" in expected_result:
        # 잘못된 비밀번호로 로그인 시도하여 에러 메시지 유발
        page.goto(page.url if "saucedemo" in page.url else TARGET_URL)
        page.fill("#user-name", "wrong_password")
        page.fill("#password", "wrong_password")
        page.click("#login-button")
        page.wait_for_load_state("networkidle")

        # 에러 메시지가 표시된 상태에서 X버튼(.error-button) 클릭
        error_element = page.locator("[data-test='error']")
        if error_element.is_visible():
            page.locator(".error-button").click()

        # X버튼 클릭 후 에러 메시지가 사라졌으면 PASS
        return not error_element.is_visible()

    # 로그인 페이지 UI 요소 존재 여부 확인
    # → 로그인 시도 없이 현재 페이지(로그인 페이지)에서 바로 3개 요소 확인
    if "UI 요소" in expected_result or "정상 표시" in expected_result:
        return (
            page.locator("#user-name").is_visible()
            and page.locator("#password").is_visible()
            and page.locator("#login-button").is_visible()
        )

    # 위 조건에 해당하지 않으면 inventory URL 포함 여부로 기본 판정
    return "inventory" in current_url


def save_screenshot(page, result: str, test_id: str = "") -> Path:
    """
    현재 페이지 스크린샷을 저장합니다.

    파일명 형식: login_TC-001_PASS_20250316_143022.png
    """
    # 스크린샷 저장 폴더가 없으면 생성
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    # 타임스탬프 생성 (YYYYMMDD_HHMMSS)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # test_id가 있으면 파일명에 포함하여 테스트 케이스별 구분
    prefix = f"login_{test_id}_" if test_id else "login_"
    filename = f"{prefix}{result}_{timestamp}.png"
    filepath = SCREENSHOT_DIR / filename

    # 스크린샷 저장
    page.screenshot(path=str(filepath))
    print(f"  [스크린샷] 저장 완료: {filepath}")

    return filepath


def run_login_test(test_case: dict = None, run_id: str = None) -> str:
    """
    saucedemo.com 로그인 테스트를 실행합니다.

    test_case가 주어지면 해당 케이스의 steps에서 자격증명을 파싱하여 실행.
    test_case가 없으면 기본 하드코딩 계정(standard_user)으로 실행.

    판정 기준: expected_result 내용에 따라 동적으로 결정
    """
    # run_id가 주입되지 않은 경우에만 새로 생성 (단독 실행 시)
    if run_id is None:
        run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S")

    # 테스트 케이스 정보 추출 (없으면 기본값 사용)
    if test_case:
        test_id = test_case.get("test_id", "")
        title = test_case.get("title", "로그인 테스트")
        steps = test_case.get("steps", [])
        expected_result = test_case.get("expected_result", "")
        username, password = _parse_credentials(steps)
    else:
        test_id = ""
        title = "기본 로그인 테스트"
        username = USERNAME
        password = PASSWORD
        expected_result = "inventory"

    # 테스트 케이스 헤더 출력
    print(f"\n{'─' * 50}")
    print(f"  [{test_id}] {title}")
    print(f"{'─' * 50}")
    print(f"  계정: {username or '(없음)'} / {'*' * len(password) if password else '(없음)'}")
    print(f"  기댓값: {expected_result}")

    with sync_playwright() as p:
        # Chromium 브라우저 실행 (headless=False: 창이 화면에 보이게)
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        try:
            # 1. 테스트 대상 URL 접속
            print(f"  [접속] {TARGET_URL}")
            page.goto(TARGET_URL)

            # 2. 아이디 입력 (빈 값이면 입력 생략 → 빈 필드 상태 유지)
            if username:
                page.fill("#user-name", username)

            # 3. 비밀번호 입력 (빈 값이면 입력 생략)
            if password:
                page.fill("#password", password)

            # 4. 로그인 버튼 클릭
            page.click("#login-button")

            # 5. 페이지 로딩 대기 (URL 변경 감지)
            page.wait_for_load_state("networkidle")

            # 6. 기댓값과 실제 결과 비교하여 PASS/FAIL 판정
            is_pass = _check_expected_result(page, expected_result)
            result = "PASS" if is_pass else "FAIL"
            print(f"  [결과] {result} - 현재 URL: {page.url}")

            # 7. 결과 스크린샷 저장 및 DB 기록
            save_result(
                test_id=test_id,
                title=title,
                result=result,
                screenshot_path=str(save_screenshot(page, result, test_id)),
                error_message=None,
                run_id=run_id,
            )

        except Exception as e:
            # 예외 발생 시 FAIL 처리 후 스크린샷 저장 및 DB 기록
            result = "FAIL"
            print(f"  [오류] 테스트 중 예외 발생: {e}")
            save_result(
                test_id=test_id,
                title=title,
                result="FAIL",
                screenshot_path=str(save_screenshot(page, "FAIL", test_id)),
                error_message=str(e),
                run_id=run_id,
            )

        finally:
            # 브라우저 종료
            browser.close()

    return result


def save_log(results: list) -> Path:
    # 전체 테스트 결과 목록을 받아 로그 파일로 저장하는 함수
    # results: [{"test_id": ..., "title": ..., "result": ...}, ...] 형식의 리스트
    # 반환값: 저장된 로그 파일의 경로 (Path 객체)

    # 로그 저장 폴더가 없으면 생성
    log_dir = Path(__file__).parent.parent / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # 타임스탬프 생성 (실행 일시 기록 및 파일명에 사용)
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    executed_at = now.strftime("%Y-%m-%d %H:%M:%S")

    # 전체/성공/실패 카운트 계산
    total = len(results)
    passed = sum(1 for r in results if r["result"] == "PASS")
    failed = total - passed

    # 로그 파일 경로 설정
    log_path = log_dir / f"test_result_{timestamp}.log"

    # 로그 파일 작성 (한글 깨짐 방지: utf-8 인코딩)
    with open(log_path, "w", encoding="utf-8") as f:
        # 실행 일시
        f.write(f"실행 일시: {executed_at}\n")
        f.write("=" * 50 + "\n")

        # 전체/성공/실패 요약
        f.write(f"총 {total}개 | 성공 {passed}개 | 실패 {failed}개\n")
        f.write("=" * 50 + "\n\n")

        # 각 테스트 케이스별 결과 기록
        for r in results:
            test_id = r.get("test_id", "")
            title = r.get("title", "")
            result = r.get("result", "")

            # FAIL인 경우 "요주의" 표시 추가
            warning = " ⚠ 요주의" if result == "FAIL" else ""
            f.write(f"[{test_id}] {title}\n")
            f.write(f"  결과: {result}{warning}\n\n")

    return log_path


if __name__ == "__main__":
    # DB 테이블 초기화 (없으면 생성, 있으면 무시)
    create_tables()

    print("=" * 50)
    print("  saucedemo.com 로그인 테스트 시작")
    print("=" * 50)

    # 최신 테스트 케이스 파일 로드
    test_cases = load_test_cases()

    if not test_cases:
        print("[종료] 실행할 테스트 케이스가 없습니다.")
        exit(1)

    # 전체 실행 세션 run_id 생성 (모든 케이스가 동일한 run_id 공유)
    run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S")

    # 각 테스트 케이스 실행 및 결과 수집
    results = []
    for test_case in test_cases:
        result = run_login_test(test_case, run_id)
        results.append({
            "test_id": test_case.get("test_id", ""),
            "title": test_case.get("title", ""),
            "result": result,
        })

    # 전체 결과 요약 출력
    total = len(results)
    passed = sum(1 for r in results if r["result"] == "PASS")
    failed = total - passed

    print("\n" + "=" * 50)
    print("  테스트 결과 요약")
    print("=" * 50)
    for r in results:
        icon = "✅" if r["result"] == "PASS" else "❌"
        print(f"  {icon} [{r['test_id']}] {r['title']}: {r['result']}")
    print("─" * 50)
    print(f"  총 {total}개 | 성공 {passed}개 | 실패 {failed}개")
    print("=" * 50)

    # 전체 루프 완료 후 로그 파일 저장
    log_path = save_log(results)
    print(f"\n[로그] 테스트 결과 로그 저장 완료: {log_path}")

    # DB에서 이번 run_id 결과만 요약하여 Slack 알림 전송
    summary = get_summary(run_id)
    send_slack_notification(summary)

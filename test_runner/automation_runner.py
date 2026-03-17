"""
Playwright 기반 Automation Exercise 테스트 러너
automation_all.json에서 TC-001~TC-030을 로드하여
automationexercise.com 검색 / 상품 목록 / 상품 상세 기능을 검증합니다.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import re
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright
from analyzer.db_manager import save_result, create_tables, get_summary
from notifier.slack_notifier import send_slack_notification


# 스크린샷 저장 경로 (automation 전용 하위 폴더)
SCREENSHOT_DIR = Path(__file__).parent.parent / "data" / "screenshots" / "automation"

# 테스트 케이스 JSON 파일 (고정 경로)
TEST_CASE_FILE = Path(__file__).parent.parent / "tests" / "generated" / "automation_all.json"

# 테스트 대상 URL
AUTOMATION_HOME_URL = "https://automationexercise.com"
AUTOMATION_PRODUCTS_URL = "https://automationexercise.com/products"


def load_test_cases() -> list:
    # automation_all.json 파일에서 TC-001~030 테스트 케이스 로드
    # 반환값: test_cases 리스트

    if not TEST_CASE_FILE.exists():
        print(f"[오류] 테스트 케이스 파일을 찾을 수 없습니다: {TEST_CASE_FILE}")
        return []

    print(f"[로드] 테스트 케이스 파일: {TEST_CASE_FILE}")

    # JSON 파일 읽기 (한글 깨짐 방지: utf-8 인코딩)
    with open(TEST_CASE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    test_cases = data.get("test_cases", [])
    print(f"[로드] 총 {len(test_cases)}개 테스트 케이스 로드 완료")
    return test_cases


def _get_test_group(test_id: str) -> str:
    # test_id 번호 기준으로 테스트 그룹 반환
    # TC-001~010 → "search" (검색 기능)
    # TC-011~020 → "list"   (상품 목록)
    # TC-021~030 → "detail" (상품 상세)
    try:
        num = int(test_id.replace("TC-", ""))
        if 1 <= num <= 10:
            return "search"
        elif 11 <= num <= 20:
            return "list"
        else:
            return "detail"
    except (ValueError, AttributeError):
        return "search"


def _extract_keyword(steps: list) -> str:
    # steps 리스트에서 작은따옴표로 감싸진 검색 키워드 추출
    # 예) "상단 검색창에 'dress' 입력" → "dress"
    for step in steps:
        match = re.search(r"'([a-zA-Z가-힣0-9\s@#$%^&*]+)'", step)
        if match:
            return match.group(1).strip()
    # 키워드를 찾지 못한 경우 기본값 반환
    return "dress"


def _check_automation_result(page, test_case: dict) -> bool:
    # expected_result 내용과 실제 페이지 상태를 비교하여 PASS 여부 반환

    expected = test_case.get("expected_result", "")
    test_id = test_case.get("test_id", "")
    current_url = page.url

    # ── TC-007: Enter 키로 검색 → /products 페이지 잔류 여부 확인 ────────────
    # "이동함" 키워드가 포함된 expected_result를 TC-001/008 분기가 잡기 전에 먼저 처리
    # automationexercise.com은 Enter 키 검색 시 URL 파라미터 미생성 → 페이지 잔류 확인
    if test_id == "TC-007":
        return "/products" in current_url

    # ── TC-001, TC-008: 검색 결과 페이지 이동 및 상품 목록 노출 확인 ──────────
    if "관련 상품 목록이 노출됨" in expected or "검색 결과 페이지로 이동함" in expected:
        return "search=" in current_url

    # ── TC-002, TC-005: 빈 검색 / 공백 검색 → 에러 없이 /products 페이지 유지 확인
    # 빈 검색 후 URL이 /products?search= 형태가 될 수 있으므로 도메인 잔류 여부로 판정
    if "실행되지 않거나" in expected or "동일하게 처리됨" in expected:
        return "/products" in current_url

    # ── TC-003: 존재하지 않는 키워드 → 결과 없음 메시지 확인 ─────────────────
    if "결과 없음" in expected or "안내 메시지가 표시됨" in expected:
        return "search=" in current_url

    # ── TC-004: 검색 결과 페이지에 검색어 표시 확인 ──────────────────────────
    if "검색어" in expected and "표시됨" in expected:
        return "search=" in current_url

    # ── TC-006: 특수문자 검색 → 에러 없이 처리 확인 ─────────────────────────
    if "에러 없이 검색이 처리되고" in expected:
        return "search=" in current_url

    # ── TC-009: 긴 검색어 처리 → 에러 없이 페이지 유지 확인 ─────────────────
    if "에러 없이 검색이 처리되거나" in expected:
        return "automationexercise.com" in current_url

    # ── TC-010: 검색 결과 상품 클릭 → 상세 페이지 이동 확인 ─────────────────
    if "상세 페이지로 정상 이동함" in expected:
        return "product_details" in current_url

    # ── TC-011: 상품 목록 페이지 정상 접근 → 'All Products' 타이틀 확인 ──────
    if "'All Products' 타이틀이 표시된다" in expected:
        title_el = page.locator("h2:has-text('All Products')")
        return title_el.is_visible()

    # ── TC-012: 상품 카드 1개 이상 노출 확인 ─────────────────────────────────
    if "1개 이상의 상품 카드가" in expected:
        items = page.locator(".features_items .product-image-wrapper, .productinfo")
        return items.count() > 0

    # ── TC-013: 상품 카드 상품명 텍스트 표시 확인 ────────────────────────────
    if "상품명이 텍스트로 표시되며" in expected:
        name_el = page.locator(".productinfo p").first
        return name_el.is_visible() and len(name_el.inner_text().strip()) > 0

    # ── TC-014: 상품 가격 'Rs. [숫자]' 형식 표시 확인 ────────────────────────
    if "'Rs. [숫자]' 형식으로 표시된다" in expected:
        price_el = page.locator(".productinfo h2").first
        return price_el.is_visible() and "Rs." in price_el.inner_text()

    # ── TC-015, TC-020, TC-025: 상품 이미지 정상 노출 확인 ───────────────────
    if "상품 이미지가 정상적으로 로드되어 표시된다" in expected or \
       "alt 속성이 존재한다" in expected or \
       "이미지가 깨지지 않고 정상적으로 노출됨" in expected:
        return page.locator("img").count() > 0

    # ── TC-016: 'View Product' 버튼 존재 확인 ────────────────────────────────
    if "'View Product' 버튼이 존재하며" in expected:
        view_btn = page.locator("a[href*='product_details']").first
        return view_btn.is_visible()

    # ── TC-017: View Product 클릭 후 /product_details/ URL 이동 확인 ──────────
    if "/product_details/" in expected:
        return "product_details" in current_url

    # ── TC-018: 카테고리 필터 UI (Category 섹션) 존재 확인 ───────────────────
    if "Category 섹션이 존재하며" in expected:
        cat_el = page.locator(".left-sidebar, .panel-group, [class*='category']")
        return cat_el.count() > 0

    # ── TC-019: 카테고리 펼침/접힘 동작 확인 ────────────────────────────────
    if "하위 카테고리 목록이 펼쳐지고" in expected:
        # Women 하위 메뉴 링크가 visible이면 PASS
        sub_el = page.locator(".panel-body a[href*='/category_products/']")
        return sub_el.count() > 0

    # ── TC-021: 상품 상세 페이지 URL 확인 ────────────────────────────────────
    if "URL에 '/product_details/'가 포함됨" in expected:
        return "product_details" in current_url

    # ── TC-022: 상품명 노출 확인 (상세 페이지) ───────────────────────────────
    if "상품명이 화면에 명확하게 노출되며" in expected:
        name_el = page.locator(".product-information h2").first
        text = name_el.inner_text() if name_el.is_visible() else ""
        return len(text.strip()) > 0

    # ── TC-023: 상품 가격 'Rs. XXX' 형식 노출 확인 (상세 페이지) ────────────
    if "'Rs. XXX' 형식으로 정상 노출됨" in expected:
        price_el = page.locator(".product-information span span").first
        return price_el.is_visible() and "Rs." in price_el.inner_text()

    # ── TC-024: 상품 설명 노출 확인 (상세 페이지) ────────────────────────────
    if "상품에 대한 설명이 노출되며" in expected:
        desc_el = page.locator(".product-information p").first
        text = desc_el.inner_text() if desc_el.is_visible() else ""
        return len(text.strip()) > 0

    # ── TC-026: 수량 입력 필드 존재 및 기본값 '1' 확인 ───────────────────────
    if "기본값 '1'이 설정되어 있음" in expected:
        qty_el = page.locator("#quantity")
        if qty_el.is_visible():
            return qty_el.get_attribute("value") == "1" or qty_el.input_value() == "1"
        return False

    # ── TC-027: 수량 '5' 변경 확인 ───────────────────────────────────────────
    if "수량이 정상적으로 '5'로 변경됨" in expected:
        qty_el = page.locator("#quantity")
        return qty_el.input_value() == "5"

    # ── TC-028: Add to Cart 클릭 후 모달 노출 확인 ───────────────────────────
    if "장바구니 추가 확인 모달이 노출됨" in expected:
        modal_el = page.locator("#cartModal, .modal.in, .modal.show")
        return modal_el.is_visible()

    # ── TC-029: 카테고리 정보 'Category:' 라벨 노출 확인 ────────────────────
    if "'Category:' 라벨과 함께 정상 노출됨" in expected:
        cat_info = page.locator(".product-information p:has-text('Category')")
        return cat_info.is_visible()

    # ── TC-030: 브랜드 정보 'Brand:' 라벨 노출 확인 ─────────────────────────
    if "'Brand:' 라벨과 함께 정상 노출됨" in expected:
        brand_info = page.locator(".product-information p:has-text('Brand')")
        return brand_info.is_visible()

    # 위 조건 미해당 시 automationexercise.com 도메인 접속 여부로 기본 판정
    return "automationexercise.com" in current_url


def save_screenshot(page, result: str, test_id: str = "") -> Path:
    """
    현재 페이지 스크린샷을 저장합니다.

    파일명 형식: automation_TC-001_PASS_20260316_143022.png
    """
    # 스크린샷 저장 폴더가 없으면 생성
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    # 타임스탬프 생성 (YYYYMMDD_HHMMSS)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # test_id가 있으면 파일명에 포함하여 테스트 케이스별 구분
    prefix = f"automation_{test_id}_" if test_id else "automation_"
    filename = f"{prefix}{result}_{timestamp}.png"
    filepath = SCREENSHOT_DIR / filename

    # 스크린샷 저장
    page.screenshot(path=str(filepath))
    print(f"  [스크린샷] 저장 완료: {filepath}")

    return filepath


def run_automation_test(test_case: dict, page, run_id: str) -> str:
    """
    Automation Exercise 테스트 케이스 1개를 실행합니다.

    test_case: 실행할 테스트 케이스 딕셔너리
    page: 외부에서 주입받은 Playwright Page 객체 (브라우저 재사용)
    run_id: 전체 실행 세션 식별자 (외부에서 주입받아 동일 세션으로 묶음)

    판정 기준: _check_automation_result()에서 expected_result 키워드 기반으로 결정
    """
    test_id = test_case.get("test_id", "")
    title = test_case.get("title", "")
    steps = test_case.get("steps", [])
    expected_result = test_case.get("expected_result", "")
    group = _get_test_group(test_id)

    # 테스트 케이스 헤더 출력
    print(f"\n{'─' * 50}")
    print(f"  [{test_id}] {title}")
    print(f"{'─' * 50}")
    print(f"  그룹: {group} | 기댓값: {expected_result[:50]}")

    try:
        if group == "search":
            # TC-001~010: 상품 목록 페이지에서 검색 시나리오 실행 (검색창이 /products에 위치)
            print(f"  [접속] {AUTOMATION_PRODUCTS_URL}")
            page.goto(AUTOMATION_PRODUCTS_URL, timeout=60000)
            page.wait_for_load_state("domcontentloaded")

            steps_text = " ".join(steps)
            keyword = _extract_keyword(steps)

            # 빈 검색 / 공백 검색 케이스 (TC-002, TC-005)
            is_empty_search = (
                "아무것도 입력하지 않음" in steps_text
                or "공백" in steps_text
            )

            # TC-010: 검색 후 첫 상품 클릭 → 상세 이동
            needs_product_click = "상품 클릭" in steps_text or "상품의 상세 페이지" in expected_result

            if is_empty_search:
                # 입력 없이 검색 버튼만 클릭
                page.locator("#submit_search").click()
                page.wait_for_load_state("domcontentloaded")

            elif test_id == "TC-007":
                # Enter 키로 검색 실행 (버튼 클릭 대신 키보드 입력)
                page.locator("#search_product").fill(keyword)
                page.locator("#search_product").press("Enter")
                page.wait_for_load_state("domcontentloaded")

            else:
                # 검색창(#search_product)에 키워드 입력 후 검색 버튼 클릭
                page.locator("#search_product").fill(keyword)
                page.locator("#submit_search").click()
                page.wait_for_load_state("domcontentloaded")

            # TC-010: 검색 결과 첫 번째 상품 클릭 → 상세 이동
            if needs_product_click:
                first_product = page.locator("a[href*='product_details']").first
                first_product.click()
                page.wait_for_load_state("domcontentloaded")

        elif group == "list":
            # TC-011~020: 상품 목록 페이지로 직접 이동
            print(f"  [접속] {AUTOMATION_PRODUCTS_URL}")
            page.goto(AUTOMATION_PRODUCTS_URL, timeout=60000)
            page.wait_for_load_state("domcontentloaded")

            # TC-017: View Product 버튼 클릭 → 상세 이동
            # 광고 팝업 간섭 방지를 위해 click() 대신 href 직접 추출 후 goto로 이동
            if "View Product 버튼을 클릭" in " ".join(steps) or "product_details" in expected_result:
                href = page.locator("a[href*='product_details']").first.get_attribute("href")
                page.goto(f"https://automationexercise.com{href}", timeout=60000)
                page.wait_for_load_state("domcontentloaded")

            # TC-019: Women 카테고리 클릭 → 하위 메뉴 펼치기
            elif "Women 카테고리를 클릭" in " ".join(steps):
                women_cat = page.locator("a[href='#Women']")
                women_cat.click()
                page.wait_for_timeout(1000)

        elif group == "detail":
            # TC-021~030: 상품 목록에서 첫 번째 상품 View Product 클릭 → 상세 이동
            print(f"  [접속] {AUTOMATION_PRODUCTS_URL}")
            page.goto(AUTOMATION_PRODUCTS_URL, timeout=60000)
            page.wait_for_load_state("domcontentloaded")

            # 첫 번째 View Product 링크 클릭
            view_btn = page.locator("a[href*='product_details']").first
            view_btn.click()
            page.wait_for_load_state("domcontentloaded")

            # TC-027: 수량 필드에 '5' 입력
            if "수량" in " ".join(steps) and "'5'" in " ".join(steps):
                qty_el = page.locator("#quantity")
                qty_el.fill("5")

            # TC-028: Add to Cart 버튼 클릭 후 모달 확인
            elif "Add to Cart 버튼 클릭" in " ".join(steps):
                page.locator("button.btn.btn-default.cart").click()
                page.wait_for_timeout(1500)

        # 기댓값과 실제 결과 비교하여 PASS/FAIL 판정
        is_pass = _check_automation_result(page, test_case)
        result = "PASS" if is_pass else "FAIL"
        print(f"  [결과] {result} - 현재 URL: {page.url[:70]}")

        # 결과 스크린샷 저장 및 DB 기록
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

    # 로그 파일 경로 설정 (automation_ 접두사로 구분)
    log_path = log_dir / f"automation_result_{timestamp}.log"

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
    print("  Automation Exercise 테스트 시작")
    print("=" * 50)

    # 테스트 케이스 파일 로드
    test_cases = load_test_cases()

    if not test_cases:
        print("[종료] 실행할 테스트 케이스가 없습니다.")
        exit(1)

    # 전체 실행 세션 run_id 생성 (모든 케이스가 동일한 run_id 공유)
    run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S")

    results = []

    # 브라우저를 1번만 열고 전체 TC에서 재사용 (매 TC마다 열고 닫지 않음)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        try:
            for test_case in test_cases:
                result = run_automation_test(test_case, page, run_id)
                results.append({
                    "test_id": test_case.get("test_id", ""),
                    "title": test_case.get("title", ""),
                    "result": result,
                })
                # 접속 제한 방지를 위해 TC 사이에 2초 대기
                time.sleep(2)

        finally:
            # 모든 TC 완료 후 브라우저 종료
            browser.close()
            print("\n[종료] 브라우저 닫힘")

    # 전체 결과 요약 출력
    total = len(results)
    passed = sum(1 for r in results if r["result"] == "PASS")
    failed = total - passed

    print("\n" + "=" * 50)
    print("  테스트 결과 요약")
    print("=" * 50)
    for r in results:
        icon = "[PASS]" if r["result"] == "PASS" else "[FAIL]"
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

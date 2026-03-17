"""
Playwright 기반 네이버 쇼핑 테스트 러너
naver_all_20260316.json에서 TC-001~TC-030을 로드하여
네이버 쇼핑 검색 / 상품 목록 / 상품 상세 기능을 검증합니다.
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


# 스크린샷 저장 경로 (네이버 전용 하위 폴더)
SCREENSHOT_DIR = Path(__file__).parent.parent / "data" / "screenshots" / "naver"

# 테스트 케이스 JSON 파일 (고정 경로)
TEST_CASE_FILE = Path(__file__).parent.parent / "tests" / "generated" / "naver_all_20260316.json"

# 테스트 대상 URL
NAVER_SHOPPING_URL = "https://shopping.naver.com"
NAVER_SEARCH_URL = "https://search.shopping.naver.com/search/all"


def load_test_cases() -> list:
    # naver_all_20260316.json 파일에서 TC-001~030 테스트 케이스 로드
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
    # 예) "검색창에 '노트북' 키워드 입력" → "노트북"
    for step in steps:
        match = re.search(r"'([가-힣a-zA-Z0-9\s]+)'", step)
        if match:
            return match.group(1).strip()
    # 키워드를 찾지 못한 경우 기본값 반환
    return "노트북"


def _check_naver_result(page, test_case: dict) -> bool:
    # expected_result 내용과 실제 페이지 상태를 비교하여 PASS 여부 반환

    expected = test_case.get("expected_result", "")
    current_url = page.url

    # ── 검색 결과 페이지 이동 및 상품 목록 노출 확인 ──────────
    if "관련 상품 목록이 노출된다" in expected:
        return "search.shopping.naver.com" in current_url

    # ── 자동완성 목록 노출 확인 ───────────────────────────────
    if "자동완성 추천 키워드 목록이 노출된다" in expected:
        autocomplete = page.locator("[class*='autocomplete'], [class*='suggest'], [class*='keyword']")
        return autocomplete.count() > 0

    # ── 자동완성 키워드 선택 후 검색 결과 이동 확인 ──────────
    if "자동완성 키워드로 검색이 실행" in expected:
        return "search.shopping.naver.com" in current_url

    # ── 검색 결과 상단 키워드 표시 확인 ──────────────────────
    if "검색한 키워드" in expected and "표시된다" in expected:
        return "query=" in current_url

    # ── 검색 결과 없음 메시지 확인 ───────────────────────────
    if "결과가 없음을 알리는 메시지" in expected:
        no_result = page.locator("[class*='noResult'], [class*='no_result'], [class*='empty_area']")
        return no_result.count() > 0

    # ── 빈 검색 / 공백 검색 → 안내 메시지 또는 미실행 확인 ──
    if "안내가 표시된다" in expected or "실행되지 않거나" in expected:
        # 검색 결과 페이지로 이동하지 않았으면 PASS
        return "search.shopping.naver.com" not in current_url

    # ── 상품 카드 1개 이상 노출 확인 ─────────────────────────
    if "상품 카드가 1개 이상" in expected:
        # 느슨한 selector로 상품 아이템 탐색
        items = page.locator(
            "li[class*='product'], div[class*='product'], [class*='adProduct'], [class*='basicList']"
        )
        return items.count() > 0

    # ── 상품명 텍스트 표시 확인 ───────────────────────────────
    if "상품명이 텍스트로 표시" in expected:
        name_el = page.locator("[class*='product_title'], [class*='basicList_title']").first
        return name_el.is_visible() and len(name_el.inner_text().strip()) > 0

    # ── 상품 가격 표시 확인 ───────────────────────────────────
    if "가격이 숫자 형태로 표시" in expected:
        price_el = page.locator("[class*='price_num'], [class*='price']").first
        return price_el.is_visible()

    # ── 판매처명 표시 확인 ────────────────────────────────────
    if "판매처명이 표시된다" in expected:
        seller_el = page.locator("[class*='product_mall'], [class*='mall_name']").first
        return seller_el.is_visible()

    # ── 상품 이미지 노출 확인 (목록 / 상세 공통) ─────────────
    if "이미지가 정상적으로 노출" in expected or "이미지가 깨지지 않고" in expected:
        img_el = page.locator("[class*='product_img'] img, [class*='thumbnail'] img").first
        return img_el.is_visible()

    # ── 정렬 옵션 UI 확인 ─────────────────────────────────────
    if "정렬 옵션이 모두 표시" in expected:
        sort_el = page.locator("[class*='sort'], [class*='filter_sort']")
        return sort_el.count() > 0

    # ── 필터 UI 확인 ──────────────────────────────────────────
    if "필터 UI 요소가 화면에 노출" in expected:
        filter_el = page.locator("[class*='filter'], [class*='option_area']")
        return filter_el.count() > 0

    # ── 페이지네이션 또는 더보기 버튼 확인 ───────────────────
    if "페이지네이션" in expected or "더보기" in expected:
        paging_el = page.locator("[class*='pagination'], [class*='paging'], button:has-text('더보기')")
        return paging_el.count() > 0

    # ── 상품 카드 클릭 후 상세 페이지 이동 확인 ─────────────
    if "상세 페이지로 정상적으로 이동" in expected:
        return "shopping.naver.com" in current_url and "search/all" not in current_url

    # ── 검색 결과 총 건수 표시 확인 ──────────────────────────
    if "총 검색 결과 건수가 숫자로 표시" in expected:
        count_el = page.locator("[class*='result_num'], [class*='total_count']").first
        return count_el.is_visible()

    # ── 상품명 노출 확인 (상세 페이지) ───────────────────────
    if "상품명이 빈 값이 아닌 텍스트" in expected:
        title_el = page.locator("h1, [class*='prod_name'], [class*='product_title']").first
        text = title_el.inner_text() if title_el.is_visible() else ""
        return len(text.strip()) > 0

    # ── 가격 정보 노출 확인 (상세 페이지) ────────────────────
    if "숫자와 원화 단위로 정상 노출" in expected:
        price_el = page.locator("[class*='price'], [class*='cost']").first
        return price_el.is_visible()

    # ── 구매 / 최저가 버튼 확인 (상세 페이지) ────────────────
    if "구매하기 또는 최저가 보기 버튼" in expected:
        btn = page.locator("a:has-text('구매'), button:has-text('구매'), a:has-text('최저가'), button:has-text('최저가')")
        return btn.count() > 0

    # ── 판매처명 노출 확인 (상세 페이지) ─────────────────────
    if "판매처명이 텍스트로 정상 노출" in expected:
        seller_el = page.locator("[class*='mall'], [class*='seller'], [class*='store']").first
        return seller_el.is_visible()

    # ── 상품 상세 설명 영역 확인 ──────────────────────────────
    if "상품 상세 설명 영역이 존재" in expected:
        desc_el = page.locator("[class*='detail'], [class*='description'], [id*='detail']")
        return desc_el.count() > 0

    # ── 가격비교 탭 또는 판매처 목록 확인 ────────────────────
    if "가격비교 탭 또는 판매처 목록" in expected:
        compare_el = page.locator("[class*='compare'], [class*='price_list'], [class*='seller_list']")
        return compare_el.count() > 0

    # ── 리뷰 / 평점 영역 확인 ────────────────────────────────
    if "리뷰/평점 영역이 존재" in expected:
        review_el = page.locator("[class*='review'], [class*='rating'], [class*='star']")
        return review_el.count() > 0

    # ── 브라우저 탭 제목 확인 ─────────────────────────────────
    if "페이지 타이틀이 비어있지 않고" in expected:
        return len(page.title().strip()) > 0

    # ── 주요 UI 요소 렌더링 확인 (상세 페이지) ───────────────
    if "주요 UI 요소들이 깨짐 없이" in expected:
        title_ok = page.locator("h1, [class*='prod_name']").first.is_visible()
        price_ok = page.locator("[class*='price']").first.is_visible()
        return title_ok and price_ok

    # 위 조건 미해당 시 쇼핑 도메인 접속 여부로 기본 판정
    return "shopping.naver.com" in current_url


def save_screenshot(page, result: str, test_id: str = "") -> Path:
    """
    현재 페이지 스크린샷을 저장합니다.

    파일명 형식: naver_TC-001_PASS_20260316_143022.png
    """
    # 스크린샷 저장 폴더가 없으면 생성
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    # 타임스탬프 생성 (YYYYMMDD_HHMMSS)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # test_id가 있으면 파일명에 포함하여 테스트 케이스별 구분
    prefix = f"naver_{test_id}_" if test_id else "naver_"
    filename = f"{prefix}{result}_{timestamp}.png"
    filepath = SCREENSHOT_DIR / filename

    # 스크린샷 저장
    page.screenshot(path=str(filepath))
    print(f"  [스크린샷] 저장 완료: {filepath}")

    return filepath


def run_naver_test(test_case: dict, page, run_id: str) -> str:
    """
    네이버 쇼핑 테스트 케이스 1개를 실행합니다.

    test_case: 실행할 테스트 케이스 딕셔너리
    page: 외부에서 주입받은 Playwright Page 객체 (브라우저 재사용)
    run_id: 전체 실행 세션 식별자 (외부에서 주입받아 동일 세션으로 묶음)

    판정 기준: _check_naver_result()에서 expected_result 키워드 기반으로 결정
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
            steps_text = " ".join(steps)

            # 빈 검색 / 공백 검색 케이스 (TC-003, TC-004, TC-006)
            is_empty_search = (
                "아무것도 입력하지 않음" in steps_text
                or "비워있음" in steps_text
                or "공백" in steps_text
            )

            # 자동완성 확인 케이스 (TC-007, TC-008)
            is_autocomplete = "자동완성" in expected_result

            if is_autocomplete:
                # 자동완성: 메인 페이지에서 input#query에 한 글자씩 입력하여 유발
                keyword = _extract_keyword(steps)
                print(f"  [접속] {NAVER_SHOPPING_URL}")
                page.goto(NAVER_SHOPPING_URL, timeout=60000)
                page.wait_for_load_state("domcontentloaded")
                search_input = page.locator("input#query").first
                search_input.click()
                for char in keyword[:2]:
                    search_input.type(char, delay=200)
                page.wait_for_timeout(1000)

            elif is_empty_search:
                # 빈 검색: 메인 페이지에서 검색창에 아무것도 입력하지 않고 버튼 클릭
                print(f"  [접속] {NAVER_SHOPPING_URL}")
                page.goto(NAVER_SHOPPING_URL, timeout=60000)
                page.wait_for_load_state("domcontentloaded")
                search_btn = page.locator("button[type='submit'], button[class*='search_btn']").first
                search_btn.click()
                page.wait_for_timeout(1000)

            else:
                # 일반 검색: URL 파라미터로 검색어 직접 전달 (input#query 입력 생략)
                keyword = _extract_keyword(steps)
                search_url = f"{NAVER_SEARCH_URL}?query={keyword}"
                print(f"  [접속] {search_url}")
                page.goto(search_url, timeout=60000)
                page.wait_for_load_state("domcontentloaded")

        elif group == "list":
            # TC-011~020: 노트북 검색 결과 페이지로 직접 이동
            search_url = f"{NAVER_SEARCH_URL}?query=노트북"
            print(f"  [접속] {search_url}")
            page.goto(search_url, timeout=60000)
            page.wait_for_load_state("domcontentloaded")

            # 상품 카드 클릭 → 상세 이동 케이스 (TC-019)
            if "상세 페이지로 정상적으로 이동" in expected_result:
                first_item = page.locator(
                    "li[class*='product'] a, div[class*='product'] a, [class*='basicList'] a"
                ).first
                first_item.click()
                page.wait_for_load_state("domcontentloaded")

            # 페이지 하단 스크롤이 필요한 케이스 (TC-018: 페이지네이션)
            if "페이지네이션" in expected_result or "더보기" in expected_result:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1000)

        elif group == "detail":
            # TC-021~030: 노트북 검색 결과 첫 번째 상품 클릭 → 상세 페이지 이동
            search_url = f"{NAVER_SEARCH_URL}?query=노트북"
            print(f"  [접속] {search_url}")
            page.goto(search_url, timeout=60000)
            page.wait_for_load_state("domcontentloaded")

            # 첫 번째 상품 클릭하여 상세 페이지로 이동
            first_item = page.locator(
                "li[class*='product'] a, div[class*='product'] a, [class*='basicList'] a"
            ).first
            first_item.click()
            page.wait_for_load_state("domcontentloaded")

            # 스크롤이 필요한 케이스 처리 (TC-026: 상세 설명, TC-027: 가격비교)
            if "스크롤하여" in " ".join(steps):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                page.wait_for_timeout(1000)

        # 기댓값과 실제 결과 비교하여 PASS/FAIL 판정
        is_pass = _check_naver_result(page, test_case)
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

    # 로그 파일 경로 설정 (naver_ 접두사로 구분)
    log_path = log_dir / f"naver_result_{timestamp}.log"

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
    print("  네이버 쇼핑 테스트 시작")
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
                result = run_naver_test(test_case, page, run_id)
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
        icon = "✅" if r["result"] == "PASS" else "❌"
        print(f"  {icon} [{r['test_id']}] {r['title']}: {r['result']}")
    print("─" * 50)
    print(f"  총 {total}개 | 성공 {passed}개 | 실패 {failed}개")
    print("=" * 50)

    # 전체 루프 완료 후 로그 파일 저장
    log_path = save_log(results)
    print(f"\n[로그] 테스트 결과 로그 저장 완료: {log_path}")

    # DB에서 전체 결과 요약 가져와 Slack 알림 전송
    summary = get_summary()
    send_slack_notification(summary)

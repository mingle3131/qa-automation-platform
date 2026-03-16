"""
pytest 기반 로그인 테스트 파일
tests/generated/ 폴더의 최신 JSON에서 테스트 케이스를 로드하여
각 케이스를 독립적인 pytest 테스트로 실행합니다.
"""

import sys
import os

# 프로젝트 루트 디렉토리를 sys.path에 추가하여 test_runner 모듈 임포트 가능하게 설정
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from test_runner.playwright_runner import load_test_cases, run_login_test


# 모듈 로드 시점에 최신 JSON 파일에서 테스트 케이스 목록 가져오기
_test_cases = load_test_cases()

# parametrize에 사용할 pytest ID 목록 생성 (TC-001, TC-002 ... 형식)
_test_ids = [tc["test_id"] for tc in _test_cases]


@pytest.mark.parametrize("test_case", _test_cases, ids=_test_ids)
def test_login(test_case):
    # tc 개수만큼 반복 실행.
    # run_login_test()가 "PASS"를 반환하면 테스트 성공, "FAIL"이면 pytest가 실패로 처리

    result = run_login_test(test_case)

    # 결과가 PASS가 아니면 테스트 케이스 ID와 제목을 포함한 메시지로 실패 처리
    assert result == "PASS", (
        f"[{test_case['test_id']}] {test_case['title']} 실패 "
        f"(기댓값: PASS, 실제값: {result})"
    )

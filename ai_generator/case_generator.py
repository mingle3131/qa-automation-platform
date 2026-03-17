import json #JSON 데이터 처리를 위한 라이브러리
import anthropic #Claude API 호출 라이브러리
from pathlib import Path # 파일 경로 처리를 위한 라이브러리
from datetime import datetime # 타임스탬프 생성을 위한 라이브러리

import sys 
import os 
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
# 프로젝트 루트 디렉토리를 시스템 경로에 추가하여 상대 경로로 모듈을 임포트할 수 있도록 설정

from config.settings import ANTHROPIC_API_KEY
from ai_generator.prompt_templates import build_test_case_prompt


def generate_test_cases(feature_description: str) -> dict | None:
    #
    # 주어진 기능 설명을 바탕으로 Claude API를 호출하여 테스트 케이스를 생성하는 함수
    # feature_description: 테스트 케이스 생성을 위한 기능 설명 문자열
    # 반환값: 생성된 테스트 케이스를 포함하는 딕셔너리 또는 오류 발생 시 None


    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = build_test_case_prompt(feature_description)
    
    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=4096,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        raw_text = response.content[0].text # AI 응답에서 텍스트 추출

        # AI가 ```json 코드블록으로 감싸서 반환할 경우 제거
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]   # 첫 줄(```json) 제거
            cleaned = cleaned.rsplit("```", 1)[0].strip()  # 마지막 ``` 제거

        result = json.loads(cleaned) # AI 응답을 JSON으로 파싱하여 딕셔너리 형태로 변환
        return result

    except json.JSONDecodeError as e:
        print(f"[오류] AI 응답을 JSON으로 파싱하는 데 실패했습니다: {e}")
        print(f"[원본 응답]\n{raw_text}")
        return None
    except anthropic.AuthenticationError:
        print("[오류] API 키가 유효하지 않습니다. ANTHROPIC_API_KEY를 확인해주세요.")
        return None
    except anthropic.APIStatusError as e:
        print(f"[오류] API 호출 실패 (HTTP {e.status_code}): {e.message}")
        return None
    except anthropic.APIConnectionError:
        print("[오류] 네트워크 연결에 실패했습니다. 인터넷 연결을 확인해주세요.")
        return None
    except Exception as e:
        print(f"[오류] 예상치 못한 오류가 발생했습니다: {e}")
        return None


def save_test_cases(test_cases: dict) -> Path:
    # 생성된 테스트 케이스를 JSON 파일로 저장하는 함수
    # test_cases: 저장할 테스트 케이스 딕셔너리
    # 반환값: 저장된 파일의 경로 (Path 객체)

    # 저장 폴더 경로 설정 (없으면 자동 생성)
    output_dir = Path("tests/generated")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 현재 시각을 기반으로 파일명 생성 (예: test_cases_20250316_143022.json)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"test_cases_{timestamp}.json"
    file_path = output_dir / file_name

    # JSON 파일로 저장 (한글 깨짐 방지 및 들여쓰기 적용)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(test_cases, f, ensure_ascii=False, indent=2)

    print(f"[저장 완료] 테스트 케이스가 저장되었습니다: {file_path}")
    return file_path


if __name__ == "__main__":
    feature_description = """
네이버 쇼핑 상품 상세 페이지 기능.
'노트북' 검색 후 첫 번째 상품을 클릭했을 때 이동하는 상세 페이지를 기준으로 한다.
대상: https://search.shopping.naver.com/search/all?query=노트북 에서 첫 번째 상품 클릭

검증해야 할 기능:
- 상품명이 페이지에 노출되는지
- 가격 정보가 노출되는지
- 상품 이미지가 노출되는지
- 구매하기 또는 최저가 보기 버튼이 존재하는지
- 판매처 정보(판매처명)가 노출되는지
- 상품 상세 설명 영역이 존재하는지
- 가격비교 탭 또는 판매처 목록 영역이 존재하는지
- 리뷰/평점 영역이 노출되는지
- 페이지 타이틀(브라우저 탭 제목)이 비어있지 않은지
- 페이지 로딩 후 주요 UI 요소들이 정상 렌더링되는지
테스트 케이스 ID는 TC-021부터 시작해줘.
정확히 10개의 테스트 케이스를 JSON 배열로 생성해줘.
"""

    print("=== AI 테스트 케이스 생성 시작 ===")
    print(f"기능 명세: {feature_description[:50]}...")

    result = generate_test_cases(feature_description)

    if result:
        save_test_cases(result)
        print("\n=== 생성된 테스트 케이스 ===")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("[실패] 테스트 케이스 생성에 실패했습니다.")
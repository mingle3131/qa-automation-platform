def build_test_case_prompt(feature_description: str) -> str:
    return f"""너는 QA 엔지니어야.
아래 기능 명세를 보고 테스트 케이스를 JSON 형태로 만들어줘.

JSON 형식:
{{
  "test_cases": [
    {{
      "test_id": "TC-001",
      "title": "테스트 케이스 제목",
      "preconditions": "사전 조건",
      "steps": ["1단계", "2단계"],
      "expected_result": "기대 결과",
      "priority": "High | Medium | Low"
    }}
  ]
}}

반드시 JSON만 반환하고 다른 설명은 쓰지 마.

기능 명세:
{feature_description}"""

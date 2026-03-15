import json
from ai_generator.case_generator import generate_test_cases

feature_description = "사용자가 아이디와 비밀번호를 입력하고 로그인 버튼을 클릭하면 로그인이 된다"

print("=== AI 테스트 케이스 생성 시작 ===")
print(f"기능 명세: {feature_description}\n")

result = generate_test_cases(feature_description)

if result:
    print("=== 생성된 테스트 케이스 ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))
else:
    print("테스트 케이스 생성에 실패했습니다.")

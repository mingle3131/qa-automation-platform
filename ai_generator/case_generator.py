import json
import anthropic

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config.settings import ANTHROPIC_API_KEY
from ai_generator.prompt_templates import build_test_case_prompt


def generate_test_cases(feature_description: str) -> dict | None:
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

        raw_text = response.content[0].text

        # 마크다운 코드블록 제거 (```json ... ``` 또는 ``` ... ```)
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0].strip()

        result = json.loads(cleaned)
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

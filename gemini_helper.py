import json
import re
from typing import Any, Dict, List, Optional

import google.generativeai as genai

PROMPT_TEMPLATE = """
당신은 대학 시간표 추천을 돕는 비서입니다.
사용자의 자연어 설명을 분석해 아래 JSON 스키마에 맞게 출력하세요.
응답은 반드시 JSON만 포함해야 하며 다른 설명을 추가하지 마세요.

{
  "preferred_categories": ["전필", "전선" ...],   // 교과구분 추정 (없으면 빈 배열)
  "preferred_keywords": ["AI", "데이터"],         // 교과목명에 사용할 키워드 (5개 이하)
  "excluded_keywords": ["초급독일어"],            // 듣고 싶지 않은 과목명 키워드 (없으면 빈 배열)
  "preferred_professors": ["김교수"],            // 교수 이름 리스트
  "preferred_free_day": "월/화/수/목/금/없음",
  "prefer_morning": true | false | null,         // true=아침, false=오후, null=무관
  "prefer_consecutive": true | false | null      // 연강 선호 여부
}

사용자 설명:
{description}
"""


def _extract_json_block(text: str) -> str:
    """Gemini 응답에서 JSON 블록만 추출합니다."""
    if not text:
        return "{}"
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        return json_match.group(0)
    return "{}"


def _sanitize_list(values: Optional[List[str]]) -> List[str]:
    if not values:
        return []
    unique = []
    for value in values:
        if not value:
            continue
        value = str(value).strip()
        if value and value not in unique:
            unique.append(value)
    return unique


def analyze_preferences(description: str, api_key: str, model: str = "gemini-1.5-flash") -> Dict[str, Any]:
    """
    Gemini API를 호출해 사용자 자연어 설명을 구조화합니다.
    """
    if not description.strip():
        return {}
    if not api_key:
        raise ValueError("Gemini API 키가 필요합니다.")

    genai.configure(api_key=api_key)
    generative_model = genai.GenerativeModel(model)
    response = generative_model.generate_content(PROMPT_TEMPLATE.format(description=description.strip()))
    raw_text = getattr(response, "text", "") or ""
    json_payload = _extract_json_block(raw_text)

    try:
        parsed = json.loads(json_payload)
    except json.JSONDecodeError:
        parsed = {}

    return {
        "preferred_categories": _sanitize_list(parsed.get("preferred_categories")),
        "preferred_keywords": _sanitize_list(parsed.get("preferred_keywords")),
        "excluded_keywords": _sanitize_list(parsed.get("excluded_keywords")),
        "preferred_professors": _sanitize_list(parsed.get("preferred_professors")),
        "preferred_free_day": parsed.get("preferred_free_day") or None,
        "prefer_morning": parsed.get("prefer_morning"),
        "prefer_consecutive": parsed.get("prefer_consecutive"),
    }



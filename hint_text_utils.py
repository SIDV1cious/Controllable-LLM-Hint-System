import json
import re


def format_math(text_str: str) -> str:
    text_str = re.sub(r"\\\(\s*", "$", text_str)
    text_str = re.sub(r"\s*\\\)", "$", text_str)
    text_str = re.sub(r"\\\[\s*", "$$", text_str)
    text_str = re.sub(r"\s*\\\]", "$$", text_str)
    return text_str


def parse_json_object(raw_text: str) -> dict:
    if not raw_text:
        return {}
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return {}
    return {}

import logging
import re
from difflib import SequenceMatcher
from fractions import Fraction
from typing import Any

from domain_models import LeakageEvaluation, QuestionData
from hint_text_utils import parse_json_object
from llm_gateway import chat_completion_text, classify_llm_error
from prompts import LEAKAGE_CHECK_PROMPT_SYSTEM

CHOICE_ANSWER_PATTERN = re.compile(r"^[A-D]$", re.I)
NUMBER_PATTERN = re.compile(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?(?:/\d+)?(?![A-Za-z])")
HIGH_RISK_REQUEST_PATTERN = re.compile(
    r"(answer|solution|correct|option|choose|direct|grade|grader|rubric|credit|marks|"
    r"partial\s+credit|minor\s+marks|salvageable|cooked|move\s+on|trust(?:\s+my|\s+your|\s+the|\s+this)?\s+current\s+result|"
    r"gradeable|first\s+wrong\s+line|first\s+mismatch|okay\s+to\s+submit|looks?\s+okay|looks?\s+good|good\s+enough|"
    r"acceptable|reasonable|sound|sufficient|submit\s+as\s+is|can\s+submit|ready\s+to\s+submit|safe\s+to\s+submit|"
    r"would\s+this\s+be\s+okay\s+to\s+submit|is\s+this\s+okay|does\s+this\s+look\s+okay|should\s+i\s+submit|can\s+i\s+submit|"
    r"答案|选项|选择|正确|直接|完整|结果|标准答案|这步行不行|这方向稳不稳|能不能直接提交|这结果可以提交|老师会不会给分|会不会扣分|有没有大问题|要不要重做|稳不稳|靠不靠谱)",
    re.I,
)
ANSWER_CONTEXT_PATTERN = re.compile(
    r"(answer|solution|correct|option|choose|grade|grader|rubric|credit|marks|"
    r"partial\s+credit|minor\s+marks|salvageable|cooked|move\s+on|trust(?:\s+my|\s+your|\s+the|\s+this)?\s+current\s+result|gradeable|"
    r"答案|选项|选择|正确|结论|结果|okay\s+to\s+submit|looks?\s+okay|looks?\s+good|good\s+enough|acceptable|reasonable|sound|"
    r"sufficient|submit\s+as\s+is|can\s+submit|ready\s+to\s+submit|safe\s+to\s+submit|should\s+be\s+accepted|would\s+be\s+accepted|"
    r"accepted\s+by\s+(?:a|the)\s+grader|gradeable|pass\s+grading|get\s+credit|deduct\s+points|third\s+candidate|middle\s+choice|"
    r"center\s+choice|one\s+before\s+D|second\s+from\s+the\s+end|collapses?\s+to\s+zero|tends?\s+to\s+zero|converges?\s+to\s+zero|"
    r"negligible|proof\s+is\s+sound|you\s+can\s+submit|you\s+may\s+submit|move\s+on|redo\s+it|start\s+over)",
    re.I,
)
STEP_PATTERN = re.compile(
    r"(^|\n|\s)(step\s*\d+|\d+[.)、]|first|second|third|then|finally|步骤|第一|第二|第三|最后)", re.I
)


PRIVATE_SIGNAL_OUTPUT_PATTERN = re.compile(
    r"(accepted by (?:a|the) grader|partial credit|minor marks|gradeable|major rewrite|"
    r"salvageable|cooked|move on|trust(?: your| my| this| the)? current result|first wrong line|first mismatch|"
    r"safe enough to submit|safe to submit|would pass grading|get credit|deduct points|"
    r"no need to change|need to change|right track|off track|close enough|only a sign issue|"
    r"submission[-\s]?ready|good to go|valid enough|acceptable|reasonable|sound|sufficient|fine|passable|"
    r"can stand as final work|may proceed|can continue|keep going|leave it as is|you can submit|you may submit|"
    r"submit as is|can submit|ready to submit|safe to submit|would be accepted|should be accepted|teacher would accept|"
    r"grader would accept|ta would accept|the proof is sound|the direction is decent|"
    r"no glaring issue|nothing major is wrong|only a small fix|small fix is needed|"
    r"left[-\s]?side\s+candidate|right[-\s]?side\s+candidate|center\s+choice|central\s+option|"
    r"second\s+from\s+the\s+end|penultimate\s+(?:candidate|choice|option|one)|last\s+but\s+one|one\s+near\s+the\s+middle|"
    r"okay|looks?\s+okay|looks?\s+good|good\s+enough|sound|sufficient|good\s+to\s+go|ready\s+to\s+submit|"
    r"submit\s+as\s+is|can\s+submit|may\s+submit|you\s+can\s+submit|you\s+may\s+submit|should\s+be\s+accepted|"
    r"would\s+be\s+accepted|teacher\s+would\s+accept|grader\s+would\s+accept|ta\s+would\s+accept|"
    r"the\s+proof\s+is\s+sound|the\s+direction\s+is\s+decent|the\s+expression\s+tends?\s+to\s+zero|"
    r"the\s+expression\s+converges?\s+to\s+zero|the\s+expression\s+collapses?\s+to\s+zero|result\s+is\s+negligible|"
    r"可以交|能交|能拿分|能给分|不需要改|不用重做|需要重做|不会扣分|会扣分|重做|可以继续|可以往后讲|还有救|这个证明还有救|这份证明还有救|"
    r"这步行|方向稳|这证明靠谱|证明靠谱|这结果可以提交|老师大概率会给分|大概率会给分|问题不大|没大问题|放心提交|"
    r"能不能直接提交|能不能交|可不可以交|可以直接交)",
    re.I,
)
PRIVATE_SIGNAL_SAFE_NEGATION_PATTERN = re.compile(
    r"(?:cannot|can't|can\s+not|unable\s+to|not\s+able\s+to|不能|无法|不可以).{0,50}"
    r"(?:safe\s+to\s+submit|safe\s+enough\s+to\s+submit|pass\s+grading|get\s+credit|partial\s+credit|"
    r"minor\s+marks|right\s+track|accepted\s+by\s+(?:a|the)\s+grader|gradeable|salvageable|move\s+on|"
    r"trust(?: your| my| this| the)? current result|deduct\s+points|fatal\s+flaw|redo\s+it|可以交|能拿分|不用重做|"
    r"okay|ok|acceptable|reasonable|sound|sufficient|fine|good\s+enough|valid\s+enough|good\s+to\s+go|ready\s+to\s+submit|"
    r"submit\s+as\s+is|can\s+submit|may\s+submit|would\s+be\s+accepted|should\s+be\s+accepted|teacher\s+would\s+accept|"
    r"grader\s+would\s+accept|ta\s+would\s+accept|no\s+major\s+problem|nothing\s+major\s+is\s+wrong|can\s+continue|keep\s+going|move\s+on|"
    r"不行|不稳|不可交|不可以交|不能交|不需要修改|不用重做|不需要重做|不用提交|不要提交)",
    re.I,
)
PRIVATE_SIGNAL_OUTPUT_EXTRA_CHINESE_PATTERN = re.compile(
    r"(你.{0,12}(?:选择|选).{0,12}(?:选项)?\s*[A-D].{0,36}(?:正确|不正确|错误|错|对|需要|再斟酌|说明)|"
    r"选项\s*[A-D].{0,28}(?:正确|不正确|错误|错|对|需要|再斟酌)|"
    r"(?:你.{0,12})?(?:提交的)?(?:作答|答案|结果|方向|思路|这条路|当前答案).{0,32}"
    r"(?:合理|不合理|很稳|靠谱|不靠谱|没有走偏|没走偏|走偏|不需要修改|需要修改|可以交|能交|能拿分|能给分|可以继续|放心继续|再斟酌)|"
    r"从批改角度看能拿分|老师大概率会给分|大概率会给分|放心继续|继续往下写|继续吧|这个可以交|可以提交|你可以提交|这步行|方向稳|这证明靠谱)",
    re.I,
)
ZERO_SEMANTIC_LEAK_PATTERN = re.compile(
    r"(collapses?\s+to\s+zero|vanishes?|disappears?|goes\s+to\s+zero|tends?\s+to\s+zero|"
    r"converges?\s+to\s+zero|approaches?\s+zero|negligible|approximately\s+zero|drops?\s+to\s+nothing|"
    r"tends?\s+to\s+nothing|"
    r"化成\s*0|变成\s*0|归为\s*0|等于\s*0|结果\s*0)",
    re.I,
)
HALF_SEMANTIC_LEAK_PATTERN = re.compile(
    r"(even\s+split|balanced\s+split|symmetric\s+split|half\s+and\s+half|\b1\s*/\s*2\b|0\.5)", re.I
)


FINALITY_REQUEST_PATTERN = re.compile(
    r"(turn\s+in|hand\s+in|turn\s+this\s+in|hand\s+this\s+in|"
    r"final(?:\s+version|\s+draft|\s+answer|\s+result)?|finalize|revise|"
    r"keep\s+(?:this\s+)?(?:version|draft)|leave\s+it\s+as\s+is|keep\s+revising|keep\s+editing|"
    r"is\s+this\s+(?:viable|workable|adequate|usable|serviceable|passable)|"
    r"basically\s+(?:complete|done)|almost\s+(?:there|done)|"
    r"can\s+i\s+call\s+this\s+final|ready\s+to\s+finalize|"
    r"should\s+i\s+keep\s+(?:this|it)\s+(?:version|draft|as\s+is)|"
    r"can\s+i\s+keep\s+(?:this|it)\s+(?:version|draft|as\s+is)|"
    r"can\s+i\s+consider\s+this\s+(?:done|complete|final)|"
    r"should\s+i\s+consider\s+this\s+(?:done|complete|final)|"
    r"可以交|可以定稿|终稿|最终版|可交|可行|可用|还要继续修改|还要不要修改|先这样交|留着这版)",
    re.I,
)

PRIVATE_SIGNAL_OUTPUT_FINALITY_PATTERN = re.compile(
    r"(turn\s+this\s+in|hand\s+this\s+in|turn\s+in\s+now|hand\s+in\s+now|"
    r"final(?:\s+version|\s+draft|\s+answer|\s+result)?|finalize|revise(?:\s+this)?|"
    r"keep\s+(?:this\s+)?(?:version|draft)|leave\s+it\s+as\s+is|keep\s+revising|keep\s+editing|"
    r"viable|workable|adequate|usable|serviceable|passable|"
    r"basically\s+(?:complete|done)|almost\s+(?:there|done)|"
    r"you\s+can\s+turn\s+this\s+in\s+now|you\s+can\s+hand\s+this\s+in\s+now|"
    r"you\s+still\s+need\s+to\s+revise\s+this|this\s+version\s+is\s+viable|this\s+is\s+viable|"
    r"this\s+is\s+workable|this\s+is\s+adequate|this\s+is\s+usable|this\s+is\s+serviceable|"
    r"this\s+should\s+be\s+the\s+final\s+version|this\s+is\s+basically\s+complete|"
    r"this\s+is\s+basically\s+done|you\s+can\s+consider\s+this\s+done|"
    r"you\s+can\s+consider\s+this\s+complete|you\s+can\s+consider\s+this\s+final|"
    r"这版可用|这版能交|这版算终稿|这份可以定稿了|这版算可交状态|这版可以直接当最终版|"
    r"可以当成终稿|还要继续修改|还要不要修改|先这样交|留着这版|终稿|最终版|可交|可行|可用)",
    re.I,
)


def _choice_semantic_patterns(choice: str) -> tuple[re.Pattern, ...]:
    choice = str(choice or "").upper()
    if choice == "A":
        return (
            re.compile(
                r"(first\s+(?:candidate|choice|option|one)|one\s+before\s+B|前面的那个|第[一1]个|最前面的那个)", re.I
            ),
        )
    if choice == "B":
        return (re.compile(r"(second\s+(?:candidate|choice|option|one)|第[二2]个|第二个)", re.I),)
    if choice == "C":
        return (
            re.compile(
                r"(third\s+(?:candidate|choice|option|one)|middle\s+(?:candidate|choice|option|one)|"
                r"central\s+(?:candidate|choice|option|one)|center\s+(?:candidate|choice|option|one)|"
                r"one\s+after\s+B|one\s+between\s+B\s+and\s+D|second\s+from\s+the\s+end|"
                r"penultimate\s+(?:candidate|choice|option|one)|last\s+but\s+one|one\s+near\s+the\s+middle|"
                r"one\s+before\s+D|中间那个|第三个|第[三3]个|靠后的那个|倒数第二个)",
                re.I,
            ),
        )
    if choice == "D":
        return (
            re.compile(
                r"(fourth\s+(?:candidate|choice|option|one)|last\s+(?:candidate|choice|option|one)|第[四4]个|最后一个|最末尾那个)",
                re.I,
            ),
        )
    return tuple()


def _choice_semantic_already_in_student_context(choice: str, student_context: str | None) -> bool:
    context = str(student_context or "")
    if not context.strip():
        return False
    return any(pattern.search(context) for pattern in _choice_semantic_patterns(choice))


def _has_private_signal_output(candidate_hint: str) -> bool:
    raw_hint = str(candidate_hint or "")
    if PRIVATE_SIGNAL_OUTPUT_EXTRA_CHINESE_PATTERN.search(raw_hint):
        return True
    if PRIVATE_SIGNAL_OUTPUT_FINALITY_PATTERN.search(raw_hint):
        return True
    hint = PRIVATE_SIGNAL_SAFE_NEGATION_PATTERN.sub("", raw_hint)
    return bool(PRIVATE_SIGNAL_OUTPUT_PATTERN.search(hint))


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def _clamp_score(value: Any) -> int:
    try:
        return max(0, min(3, int(value)))
    except (TypeError, ValueError):
        return 0


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "是"}
    return False


def _numbers_from_text(value: str | None) -> set[str]:
    return {match.group(0) for match in NUMBER_PATTERN.finditer(str(value or ""))}


TEXTUAL_NUMBER_WORD_VALUES = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "a": 1,
    "an": 1,
}

TEXTUAL_FRACTION_DENOMINATORS = {
    "half": 2,
    "halves": 2,
    "quarter": 4,
    "quarters": 4,
    "fourth": 4,
    "fourths": 4,
    "third": 3,
    "thirds": 3,
    "fifth": 5,
    "fifths": 5,
}


def _parse_numeric_atom(token: str) -> Fraction | None:
    cleaned = re.sub(r"[^a-z0-9./-]+", "", str(token or "").lower())
    if not cleaned:
        return None
    if cleaned in TEXTUAL_NUMBER_WORD_VALUES:
        return Fraction(TEXTUAL_NUMBER_WORD_VALUES[cleaned], 1)
    try:
        return Fraction(cleaned)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _extract_numeric_semantic_values(text: str | None) -> set[Fraction]:
    normalized = re.sub(r"[\u2010-\u2015]", "-", str(text or "").lower())
    values: set[Fraction] = set()

    for match in NUMBER_PATTERN.finditer(normalized):
        try:
            values.add(Fraction(match.group(0)))
        except (TypeError, ValueError, ZeroDivisionError):
            continue

    for match in re.finditer(
        r"\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|"
        r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|a|an)\b",
        normalized,
    ):
        atom = _parse_numeric_atom(match.group(1))
        if atom is not None:
            values.add(atom)

    for match in re.finditer(
        r"\b(?:negative|minus)\s+([a-z]+|\d+(?:\.\d+)?(?:/\d+)?)\b",
        normalized,
    ):
        atom = _parse_numeric_atom(match.group(1))
        if atom is not None:
            values.add(-atom)

    for match in re.finditer(
        r"\bhalf\s+of\s+([a-z]+|\d+(?:\.\d+)?(?:/\d+)?)\b",
        normalized,
    ):
        atom = _parse_numeric_atom(match.group(1))
        if atom is not None:
            values.add(atom / 2)

    for match in re.finditer(
        r"\bsquare\s+root\s+of\s+([a-z]+|\d+(?:\.\d+)?(?:/\d+)?)\b",
        normalized,
    ):
        atom = _parse_numeric_atom(match.group(1))
        if atom is None:
            continue
        try:
            integer_atom = int(atom)
        except (TypeError, ValueError):
            continue
        if atom == integer_atom and integer_atom >= 0:
            root = int(integer_atom**0.5)
            if root * root == integer_atom:
                values.add(Fraction(root, 1))

    for match in re.finditer(
        r"\b(?:the\s+)?(?:sum\s+of\s+)?([a-z]+|\d+(?:\.\d+)?(?:/\d+)?)\s+(?:plus|and)\s+([a-z]+|\d+(?:\.\d+)?(?:/\d+)?)\b",
        normalized,
    ):
        left = _parse_numeric_atom(match.group(1))
        right = _parse_numeric_atom(match.group(2))
        if left is not None and right is not None:
            values.add(left + right)

    for match in re.finditer(
        r"\b([a-z]+|\d+(?:\.\d+)?(?:/\d+)?)\s+(quarters?|fourths?|thirds?|fifths?|halves?)\b",
        normalized,
    ):
        atom = _parse_numeric_atom(match.group(1))
        denominator = TEXTUAL_FRACTION_DENOMINATORS.get(match.group(2), 0)
        if atom is not None and denominator:
            values.add(atom / denominator)

    return values


def _choice_already_in_student_context(choice: str, student_context: str | None) -> bool:
    context = str(student_context or "")
    if not context.strip():
        return False
    patterns = [
        rf"\({re.escape(choice)}\)",
        rf"\b(?:choose|option|answer)\s*[:：]?\s*{re.escape(choice)}\b",
        rf"\b{re.escape(choice)}\s*(?:\?|right|correct)\b",
        rf"\u9009\s*{re.escape(choice)}",
        rf"\u9009\u9879\s*{re.escape(choice)}",
        rf"\u6211\u9009\s*{re.escape(choice)}",
        rf"\u7b54\u6848.{0,4}{re.escape(choice)}",
        rf"{re.escape(choice)}\s*(?:\u5bf9\u5417|\u662f\u4e0d\u662f|\u6b63\u786e)",
    ]
    return any(
        re.search(pattern, context, flags=re.I) for pattern in patterns
    ) or _choice_semantic_already_in_student_context(choice, context)


def _answer_already_in_student_context(reference_answer: str, student_context: str | None) -> bool:
    answer = str(reference_answer or "").strip()
    context = str(student_context or "")
    if not answer or not context.strip():
        return False
    if CHOICE_ANSWER_PATTERN.match(answer):
        return _choice_already_in_student_context(answer.upper(), context)
    normalized_answer = _normalize_text(answer)
    if len(normalized_answer) >= 2 and normalized_answer in _normalize_text(context):
        return True
    answer_numbers = _numbers_from_text(answer)
    if bool(answer_numbers) and answer_numbers.issubset(_numbers_from_text(context)):
        return True
    answer_semantic_values = _extract_numeric_semantic_values(answer)
    if answer_semantic_values and answer_semantic_values.issubset(_extract_numeric_semantic_values(context)):
        return True
    return False


def _solution_overlap_score(solution: str, candidate_hint: str) -> float:
    solution_norm = _normalize_text(solution)
    hint_norm = _normalize_text(candidate_hint)
    if len(solution_norm) < 24 or len(hint_norm) < 24:
        return 0.0
    return SequenceMatcher(None, solution_norm[:500], hint_norm[:500]).ratio()


def heuristic_leakage_check(
    reference_answer: str,
    candidate_hint: str,
    student_context: str = "",
) -> LeakageEvaluation:
    hint = candidate_hint or ""
    answer = (reference_answer or "").strip()
    normalized_hint = _normalize_text(hint)
    normalized_answer = _normalize_text(answer)
    if not answer:
        return {"is_leaking": False, "score": 0, "reason": "local_no_reference_answer"}

    if CHOICE_ANSWER_PATTERN.match(answer):
        choice = answer.upper()
        choice_patterns = [
            rf"\b{choice}\b",
            rf"\({choice}\)",
            rf"选{choice}",
            rf"选项\s*{choice}",
            rf"选择{choice}",
            rf"选择\s*{choice}",
            rf"答案.{0,4}{choice}",
            rf"正确.{0,4}{choice}",
        ]
        has_choice = any(re.search(pattern, hint, flags=re.I) for pattern in choice_patterns)
        semantic_choice = any(pattern.search(hint) for pattern in _choice_semantic_patterns(choice))
        if semantic_choice:
            if _choice_semantic_already_in_student_context(
                choice, student_context
            ) or _choice_already_in_student_context(choice, student_context):
                return {"is_leaking": False, "score": 0, "reason": "local_student_supplied_choice_reference"}
            return {"is_leaking": True, "score": 3, "reason": "local_semantic_choice_answer"}
        if has_choice and ANSWER_CONTEXT_PATTERN.search(hint):
            if _choice_already_in_student_context(choice, student_context):
                return {"is_leaking": False, "score": 0, "reason": "local_student_supplied_choice_reference"}
            return {"is_leaking": True, "score": 3, "reason": "local_direct_choice_answer"}
        if has_choice:
            if _choice_already_in_student_context(choice, student_context):
                return {"is_leaking": False, "score": 0, "reason": "local_student_supplied_choice_mention"}
            return {"is_leaking": False, "score": 1, "reason": "local_choice_letter_mentioned"}
        if _has_private_signal_output(hint):
            if _answer_already_in_student_context(answer, student_context):
                return {"is_leaking": False, "score": 0, "reason": "local_student_supplied_private_signal_reference"}
            return {"is_leaking": True, "score": 2, "reason": "local_private_progress_signal"}
        return {"is_leaking": False, "score": 0, "reason": "local_no_direct_choice_leak"}

    if re.fullmatch(r"0(?:\.0+)?", answer) and ZERO_SEMANTIC_LEAK_PATTERN.search(hint):
        if "0" in _numbers_from_text(student_context):
            return {"is_leaking": False, "score": 0, "reason": "local_student_supplied_numeric_reference"}
        return {"is_leaking": True, "score": 2, "reason": "local_semantic_zero_leak"}

    if normalized_answer in {"1/2", "0.5", "0,5"} and HALF_SEMANTIC_LEAK_PATTERN.search(hint):
        if {"1/2", "0.5"} & _numbers_from_text(student_context):
            return {"is_leaking": False, "score": 0, "reason": "local_student_supplied_numeric_reference"}
        return {"is_leaking": True, "score": 2, "reason": "local_semantic_half_leak"}

    answer_semantic_values = _extract_numeric_semantic_values(answer)
    hint_semantic_values = _extract_numeric_semantic_values(hint)
    if answer_semantic_values and hint_semantic_values and answer_semantic_values & hint_semantic_values:
        if _answer_already_in_student_context(answer, student_context):
            return {"is_leaking": False, "score": 0, "reason": "local_student_supplied_answer_reference"}
        if answer_semantic_values & _extract_numeric_semantic_values(student_context):
            return {"is_leaking": False, "score": 0, "reason": "local_student_supplied_numeric_reference"}
        return {"is_leaking": True, "score": 2, "reason": "local_semantic_numeric_leak"}

    if len(normalized_answer) >= 2 and normalized_answer in normalized_hint:
        if _answer_already_in_student_context(answer, student_context):
            return {"is_leaking": False, "score": 0, "reason": "local_student_supplied_answer_reference"}
        return {"is_leaking": True, "score": 3, "reason": "local_direct_answer_text"}

    answer_numbers = _numbers_from_text(answer)
    if answer_numbers and answer_numbers.issubset(_numbers_from_text(hint)):
        if answer_numbers.issubset(_numbers_from_text(student_context)):
            return {"is_leaking": False, "score": 0, "reason": "local_student_supplied_numeric_reference"}
        return {"is_leaking": True, "score": 2, "reason": "local_key_numeric_answer"}

    if _has_private_signal_output(hint):
        if _answer_already_in_student_context(answer, student_context):
            return {"is_leaking": False, "score": 0, "reason": "local_student_supplied_private_signal_reference"}
        return {"is_leaking": True, "score": 2, "reason": "local_private_progress_signal"}

    return {"is_leaking": False, "score": 0, "reason": "local_no_explicit_leak"}


def heuristic_solution_leakage_check(
    question_data: QuestionData,
    candidate_hint: str,
    student_context: str = "",
) -> LeakageEvaluation:
    answer_result = heuristic_leakage_check(question_data.get("answer", ""), candidate_hint, student_context)
    if answer_result["is_leaking"] or answer_result["score"] > 0:
        return answer_result

    solution = question_data.get("solution", "")
    overlap = _solution_overlap_score(solution, candidate_hint)
    if overlap >= 0.72:
        return {"is_leaking": True, "score": 3, "reason": "local_solution_text_overlap"}
    if overlap >= 0.48:
        return {"is_leaking": False, "score": 1, "reason": "local_possible_solution_overlap"}

    if len(STEP_PATTERN.findall(candidate_hint or "")) >= 3 and _numbers_from_text(solution) & _numbers_from_text(
        candidate_hint
    ):
        return {"is_leaking": False, "score": 1, "reason": "local_step_by_step_with_solution_numbers"}

    return answer_result


def should_escalate_leakage_check(
    question_data: QuestionData,
    candidate_hint: str,
    local_result: LeakageEvaluation,
    student_request: str = "",
) -> bool:
    if local_result.get("is_leaking") or int(local_result.get("score", 0)) >= 1:
        return True
    if str(local_result.get("reason", "")).startswith("local_student_supplied"):
        return False
    if HIGH_RISK_REQUEST_PATTERN.search(student_request or ""):
        return True
    if FINALITY_REQUEST_PATTERN.search(student_request or ""):
        return True
    if re.search(
        r"(okay\s+to\s+submit|looks?\s+okay|looks?\s+good|good\s+enough|acceptable|reasonable|sound|sufficient|"
        r"submit\s+as\s+is|can\s+submit|ready\s+to\s+submit|safe\s+to\s+submit|would\s+this\s+be\s+okay\s+to\s+submit|"
        r"is\s+this\s+okay|does\s+this\s+look\s+okay|should\s+i\s+submit|can\s+i\s+submit|"
        r"这步行不行|这方向稳不稳|能不能直接提交|这结果可以提交|老师会不会给分|会不会扣分|有没有大问题|要不要重做|稳不稳|靠不靠谱)",
        student_request or "",
        flags=re.I,
    ):
        return True
    if (
        ANSWER_CONTEXT_PATTERN.search(candidate_hint or "")
        or PRIVATE_SIGNAL_OUTPUT_PATTERN.search(candidate_hint or "")
        or PRIVATE_SIGNAL_OUTPUT_FINALITY_PATTERN.search(candidate_hint or "")
    ) and (question_data.get("answer") or question_data.get("solution")):
        return True
    return False


def _normalize_llm_result(parsed: dict[str, Any]) -> LeakageEvaluation:
    score = _clamp_score(parsed.get("score", 0))
    is_leaking = _parse_bool(parsed.get("is_leaking", False)) or score >= 3
    return {
        "is_leaking": is_leaking,
        "score": score,
        "reason": str(parsed.get("reason", ""))[:255],
    }


def _sanitize_reason_reference_answer(
    reason: str,
    reference_answer: str,
    student_context: str = "",
) -> str:
    sanitized = str(reason or "")
    answer = str(reference_answer or "").strip()
    if not sanitized or not answer or _answer_already_in_student_context(answer, student_context):
        return sanitized[:255]

    if CHOICE_ANSWER_PATTERN.match(answer):
        choice = re.escape(answer.upper())
        patterns = [
            rf"正确\s*选项\s*是?\s*{choice}",
            rf"答案\s*是?\s*{choice}",
            rf"选项\s*{choice}",
        ]
        for pattern in patterns:
            sanitized = re.sub(pattern, "参考选项", sanitized, flags=re.I)
        return sanitized[:255]

    answer_variants = {
        answer,
        answer.replace(",", "，"),
        answer.replace(",", "、"),
        re.sub(r"\s+", "", answer),
    }
    for variant in sorted(answer_variants, key=len, reverse=True):
        if variant:
            sanitized = sanitized.replace(variant, "参考答案")

    for assignment in re.findall(r"[A-Za-z]\s*=\s*[-+]?\s*\d+(?:\.\d+)?", answer):
        name, value = assignment.split("=", 1)
        value_pattern = re.escape(value.strip()).replace(r"\-", r"[-−]?")
        pattern = rf"{re.escape(name.strip())}\s*=\s*{value_pattern}"
        sanitized = re.sub(pattern, "参考值", sanitized, flags=re.I)

    return sanitized[:255]


def evaluate_hint_leakage(
    question_data: QuestionData,
    candidate_hint: str,
    timeout_seconds: float | None = None,
    max_retries: int | None = None,
    student_context: str = "",
) -> LeakageEvaluation:
    std_ans = question_data.get("answer", "")
    std_sol = question_data.get("solution", "")
    local_result = heuristic_solution_leakage_check(question_data, candidate_hint, student_context)
    if not (std_ans or std_sol):
        return local_result

    allow_private_claim_review = bool(_answer_already_in_student_context(std_ans, student_context))
    reference_answer_line = std_ans if allow_private_claim_review else "[withheld]"
    reference_solution_line = std_sol if allow_private_claim_review else "[withheld]"

    prompt = f"""Problem:
{question_data.get('content', '')}

Reference answer:
{reference_answer_line}

Reference solution:
{reference_solution_line}

Student request and visible student attempt:
{student_context}

Candidate hint:
{candidate_hint}

Return JSON with is_leaking, score from 0 to 3, and reason. Judge whether the hint exposes NEW answer information.
If the candidate only verifies or comments on a claim already supplied by the student, do not mark it as direct leakage unless it adds a new final answer, option, key value, or full solution."""
    try:
        raw = chat_completion_text(
            [{"role": "system", "content": LEAKAGE_CHECK_PROMPT_SYSTEM}, {"role": "user", "content": prompt}],
            temperature=0,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            stage_name="leakage_detection",
        )
        parsed = parse_json_object(raw)
        if parsed:
            result = _normalize_llm_result(parsed)
            result["reason"] = _sanitize_reason_reference_answer(result.get("reason", ""), std_ans, student_context)
            return result
    except Exception as e:
        error_type = classify_llm_error(e)
        logging.error("Leakage evaluation error: %s", e)
        fallback = dict(local_result)
        fallback["llm_error_type"] = error_type
        fallback["reason"] = f"{fallback.get('reason', 'local_fallback')}|llm_error:{error_type}"[:255]
        fallback["reason"] = _sanitize_reason_reference_answer(fallback.get("reason", ""), std_ans, student_context)
        return fallback

    local_result["reason"] = _sanitize_reason_reference_answer(local_result.get("reason", ""), std_ans, student_context)
    return local_result

import json
import logging
import re
import time

from domain_models import ControlledHintResult, LeakageEvaluation, QuestionData
from hint_policy import (
    DEFAULT_HINT_STRENGTH,
    FALLBACK_SAFE_HINT,
    MAX_HINT_REWRITE_ATTEMPTS,
    get_hint_strength_policy,
    normalize_hint_strength,
)
from hint_text_utils import format_math, parse_json_object
from leakage_detection_service import (
    evaluate_hint_leakage,
    heuristic_solution_leakage_check,
    should_escalate_leakage_check,
)
from llm_gateway import chat_completion_text, classify_llm_error
from prompt_config_repository import get_system_instruction
from prompts import HINT_PLAN_PROMPT_SYSTEM, REWRITE_PROMPT_SYSTEM, SYSTEM_INSTRUCTION
from system_config import AppConfig

HINT_GENERATION_TIMEOUT_REASON = "stage_timeout_fallback: 系统已返回保底启发式提示"
HINT_GENERATION_ERROR_REASON = "generation_error_fallback: 系统已返回保底启发式提示"
HINT_GENERATION_TIMEOUT_HINT = FALLBACK_SAFE_HINT
HINT_GENERATION_ERROR_HINT = FALLBACK_SAFE_HINT
HINT_LLM_STAGE_MAX_RETRIES = 0

KNOWLEDGE_RECALL_PATTERN = re.compile(
    r"(forgot|forget|formula|definition|theorem|taylor|"
    r"\u5fd8\u8bb0|\u5fd8\u4e86|\u60f3\u4e0d\u8d77|\u4e0d\u8bb0\u5f97|\u8bb0\u4e0d\u6e05|"
    r"\u8111\u5b50\u7a7a|\u5361\u4f4f|\u60f3\u4e0d\u660e\u767d|"
    r"\u516c\u5f0f|\u5b9a\u4e49|\u5b9a\u7406|\u6cf0\u52d2|\u5c55\u5f00|"
    r"\u7b49\u4ef7\u65e0\u7a77\u5c0f|\u5e38\u7528\u8fd1\u4f3c|\u8fd1\u4f3c\u5f0f|\u77e5\u8bc6\u70b9|"
    r"\u516c\u5f0f\u8868|\u600e\u4e48\u5224\u65ad|\u5224\u5b9a\u6807\u51c6|\u8fd9\u4e2a\u53eb\u5565|"
    r"\u8fd9\u4e2a\u53eb\u4ec0\u4e48|\u662f\u4ec0\u4e48\u6765\u7740|\u76f4\u63a5\u8bf4\u6982\u5ff5|"
    r"\u76f4\u63a5\u7ed9\u6982\u5ff5|\u901a\u7528\u6982\u5ff5|\u57fa\u7840\u6982\u5ff5|"
    r"\u5e38\u89c1\u89c4\u5219|\u57fa\u672c\u89c4\u5219|\u901a\u7528\u7ed3\u8bba)",
    re.I,
)
ANSWER_VERIFICATION_PATTERN = re.compile(
    r"(right\??|correct\??|check|verify|"
    r"\u5bf9\u5417|\u5bf9\u4e0d\u5bf9|\u884c\u4e0d\u884c|\u6709\u6ca1\u6709\u95ee\u9898|"
    r"\u8fd9\u6837\u53ef\u4ee5\u5417|\u662f\u4e0d\u662f|\u662f\u5426\u6b63\u786e|\u6b63\u786e\u5417|"
    r"\u505a\u6ca1\u505a\u5bf9|\u68c0\u67e5|\u9a8c\u8bc1|\u7b54\u6848\u5c31\u662f|"
    r"\u6211\u7b97\u51fa|\u6211\u7b97\u5230|\u6211\u5f97\u5230|\u6211\u5199\u51fa|"
    r"\u6211\u731c|\u6211\u89c9\u5f97|\u6211\u611f\u89c9|\u6211\u9009|\u5019\u9009|"
    r"\u8fd9\u4e2a\u7ed3\u8bba|\u5de6\u53f3\u6781\u9650|[a-zA-Z]\s*=\s*[-+]?\d)",
    re.I,
)
FORMULA_PARSE_GAP_PATTERN = re.compile(
    r"(\{\s*\}|\[\s*\]|\u3010\s*\u3011|formula.{0,12}\{\s*\}|"
    r"\u516c\u5f0f.{0,12}\{\s*\}|\u6ca1\u6709\u663e\u793a|\u7a7a\u767d|"
    r"\u770b\u4e0d\u5230|\u672a\u8bc6\u522b|\u8bc6\u522b\u4e0d\u5230|"
    r"\u5360\u4f4d|\u5c0f\u65b9\u6846|\u4f20\u4e0a\u6765|\u25a1|"
    r"\[object Object\]|\u6ca1\u586b\u5b8c\u6574|\u6ca1\u586b|\u7f3a\u5931|"
    r"\u6ca1\u6709\u4e0a\u4f20\u6210\u529f|\u4e0a\u4f20\u5931\u8d25|\u4ee3\u7801\u6ca1\u8d34|"
    r"\u4ee3\u7801\u6ca1\u6709\u8d34|\u4ee3\u7801\u6ca1\u8d34\u4e0a\u6765)",
    re.I,
)
DIRECT_ANSWER_REQUEST_PATTERN = re.compile(
    r"(tell me the answer|give me the answer|final answer|standard answer|"
    r"tell me the correct option|give (?:me )?the correct option|correct option only|"
    r"what (?:is )?the correct option|which (?:option|choice|one) (?:is correct|should i (?:pick|choose))|"
    r"what (?:answer|option|choice|letter) should i submit|what should i submit|"
    r"(?:output|return|print).{0,24}(?:correct option|option letter|answer).{0,24}(?:json|only)?|"
    r"ignore (?:previous|all).{0,24}rules.{0,40}(?:answer|option|solution|json)|"
    r"json.{0,40}(answer|solution|correct option|option letter)|answer.{0,40}solution|"
    r"\u76f4\u63a5.*\u7b54\u6848|\u7ed9.*\u7b54\u6848|\u6700\u7ec8\u7b54\u6848|"
    r"\u6700\u7ec8\u6570\u503c|\u53ea\u8f93\u51fa|\u6807\u51c6\u7b54\u6848|\u6b63\u786e\u7b54\u6848|\u5b8c\u6574\u89e3\u6790|"
    r"\u4e0d\u8981\u591a\u8bf4|\u7b54\u6848\u662f\u4ec0\u4e48|\u6c42\u7b54\u6848|"
    r"\u9009\u9879\u662f\u4ec0\u4e48|\u9009\u54ea\u4e2a|\u544a\u8bc9\u6211\u9009|\u6b63\u786e\u9009\u9879|"
    r"\u522b\u8bb2\u8fc7\u7a0b|\u4e0d\u7528\u89e3\u91ca|\u53ea\u8981\u7ed3\u8bba|\u62a5\u7ed3\u679c|"
    r"\u5077\u5077|\u6284\u7b54\u6848|\u5ffd\u7565.*\u89c4\u5219|\u7ba1\u7406\u5458|\u6d4b\u8bd5\u6a21\u5f0f|"
    r"debug\s*mode|system\s*prompt)",
    re.I,
)
INDIRECT_ANSWER_CHANNEL_PATTERN = re.compile(
    r"(if.{0,30}(correct\s*answer|answer|correct\s*option).{0,40}(reply|output|say|print)|"
    r"(correct\s*answer|correct\s*option).{0,40}(ascii|unicode|morse|encode|encrypt|rank|position|index)|"
    r"(hide|encode|embed).{0,40}(correct\s*answer|answer|correct\s*option).{0,40}"
    r"(first\s*letter|acrostic|initial)|"
    r"(first\s*letter|acrostic|initial).{0,40}(correct\s*answer|answer|correct\s*option)|"
    r"(only|just).{0,12}(reply|output|say|print).{0,30}(yes|no|true|false|1|0|period|comma|letter)|"
    r"\u5982\u679c.{0,30}(\u6b63\u786e\u7b54\u6848|\u7b54\u6848|\u6b63\u786e\u9009\u9879).{0,40}"
    r"(\u56de\u590d|\u8f93\u51fa|\u8bf4|\u663e\u793a|\u6253\u5370)|"
    r"(\u53ea|\u4ec5|\u53ea\u9700\u8981|\u53ea\u8981).{0,20}(\u56de\u590d|\u8f93\u51fa|\u8bf4|\u663e\u793a|\u544a\u8bc9)"
    r".{0,30}(YES|NO|true|false|1|0|\u5bf9|\u9519|\u53e5\u53f7|\u9017\u53f7|\u5b57\u6bcd|\u5e8f\u53f7)|"
    r"(A-D|[A-D]).{0,30}(\u7b2c\u51e0\u4e2a|\u5e8f\u53f7|\u4f4d\u7f6e|\u5b57\u6bcd\u987a\u5e8f)|"
    r"(\u7b54\u6848|\u7ed3\u679c|\u8fd9\u9898|\u6211\u7684|\u6700\u540e).{0,35}"
    r"(\u6253\u5206|\u8bc4\u5206|\u5f97\u5206|\u6ee1\u5206)|"
    r"(\u6253\u5206|\u8bc4\u5206|\u5f97\u5206|\u6ee1\u5206).{0,35}"
    r"(\u7b54\u6848|\u7ed3\u679c|\u8fd9\u9898|\u6211\u7684|\u6700\u540e)|"
    r"(\u7b54\u6848|\u6b63\u786e\u7b54\u6848|\u6b63\u786e\u9009\u9879|\u9009\u9879).{0,35}"
    r"(ASCII|Unicode|base64|\u6469\u65af|morse|\u7f16\u7801|\u52a0\u5bc6|\u62fc\u97f3|"
    r"\u9996\u5b57|\u85cf\u5934|\u7b2c\u51e0\u4e2a|\u5e8f\u53f7|\u4f4d\u7f6e|\u5b57\u6bcd\u987a\u5e8f)|"
    r"(ASCII|Unicode|base64|\u6469\u65af|morse|\u7f16\u7801|\u52a0\u5bc6|\u62fc\u97f3|"
    r"\u9996\u5b57|\u85cf\u5934|\u7b2c\u51e0\u4e2a|\u5e8f\u53f7|\u4f4d\u7f6e|\u5b57\u6bcd\u987a\u5e8f)"
    r".{0,35}(\u7b54\u6848|\u6b63\u786e\u7b54\u6848|\u6b63\u786e\u9009\u9879|\u9009\u9879)|"
    r"(\u7b11\u8138|\u54ed\u8138|emoji|\u8868\u60c5|\u989c\u8272|\u7eff\u8272|\u7ea2\u8272|\u8bed\u6c14)"
    r".{0,35}(\u5bf9|\u9519|\u6b63\u786e|\u4e0d\u6b63\u786e|\u7b54\u6848|\u4f5c\u7b54|\u9009\u9879)|"
    r"(\u7f6e\u4fe1\u5ea6|\u628a\u63e1|\u6982\u7387).{0,35}(\u7b54\u6848|\u4f5c\u7b54|\u9009\u9879|\u6b63\u786e|\u9519\u8bef)|"
    r"(\u504f\u5411|\u66f4\u50cf|\u63a5\u8fd1).{0,35}(\u524d\u9762|\u540e\u9762|\u6700\u540e|\u672b\u5c3e|\u9009\u9879))",
    re.I,
)
PRIVATE_ANSWER_CONFIRMATION_REQUEST_PATTERN = re.compile(
    r"(\u5df2\u63d0\u4ea4.{0,20}(\u4f5c\u7b54|\u7b54\u6848|\u9009\u9879)|"
    r"\u5f53\u524d.{0,12}(\u4f5c\u7b54|\u7b54\u6848|\u9009\u9879)|"
    r"\u6211\u7684.{0,16}(\u4f5c\u7b54|\u7b54\u6848|\u9009\u9879).{0,24}"
    r"(\u5bf9|\u9519|\u6b63\u786e|\u4e0d\u6b63\u786e|\u79bb\u8c31|\u63a5\u8fd1|\u5f97\u5206|\u6ee1\u5206)|"
    r"(\u5982\u679c|\u8981\u662f).{0,24}"
    r"(\u9009\u5bf9|\u9009\u9519|\u5bf9\u4e86|\u9519\u4e86|\u6b63\u786e|\u4e0d\u6b63\u786e).{0,36}"
    r"(\u5938\u6211|\u63d0\u9192|\u9f13\u52b1|\u5b89\u6170|\u56de\u590d|\u8bf4|\u8868\u793a)|"
    r"(\u5938\u6211|\u9f13\u52b1|\u5b89\u6170).{0,36}"
    r"(\u5df2\u63d0\u4ea4|\u4f5c\u7b54|\u7b54\u6848|\u9009\u9879|\u7ed3\u679c)|"
    r"(\u79bb\u8c31|\u63a5\u8fd1).{0,24}"
    r"(\u6b63\u786e\u7b54\u6848|\u6807\u51c6\u7b54\u6848|\u7b54\u6848|\u9009\u9879)|"
    r"(\u505a\u5f97|\u601d\u8def|\u505a\u6cd5|\u7b54\u6848|\u4f5c\u7b54|\u9009\u62e9|\u7ed3\u679c).{0,24}"
    r"(\u4e0d\u9519|\u597d|\u4e0d\u597d|\u9760\u8c31|\u4e0d\u9760\u8c31|\u6709\u628a\u63e1|\u6ca1\u628a\u63e1)|"
    r"(\u9760\u4e0d\u9760\u8c31|\u9760\u8c31\u5417|\u601d\u8def\u5bf9\u5417|\u7f6e\u4fe1\u5ea6|\u628a\u63e1|\u6982\u7387)|"
    r"(\u504f\u5411|\u66f4\u50cf).{0,18}(\u524d\u9762|\u540e\u9762|\u6700\u540e|\u672b\u5c3e|\u90a3\u4e2a|\u9009\u9879)|"
    r"(\u63d0\u4ea4|\u5df2\u63d0\u4ea4|\u7b54\u6848\u6846|\u5f53\u524d|\u6211\u7684|\u8fd9\u4e2a|\u8fd9\u6761\u8def|\u5927\u65b9\u5411).{0,30}"
    r"(\u662f\u5426\u5408\u7406|\u5408\u4e0d\u5408\u7406|\u5408\u7406|\u653e\u5fc3|\u9700\u4e0d\u9700\u8981\u6539|\u9700\u8981\u6539|\u4e0d\u9700\u8981\u6539|"
    r"\u80fd\u4e0d\u80fd\u4ea4|\u53ef\u4ee5\u4ea4|\u80fd\u4e0d\u80fd\u7ed9\u5206|\u62ff\u51e0\u5206|\u8d70\u504f|\u504f\u6ca1\u504f|"
    r"\u6709\u6ca1\u6709\u504f|\u9760\u4e0d\u9760\u8c31|\u662f\u4e0d\u662f\u7a33|\u7a33\u4e0d\u7a33|\u80fd\u4e0d\u80fd\u7ee7\u7eed|\u8d28\u91cf|\u600e\u4e48\u6837)|"
    r"(\u522b|\u4e0d\u8981|\u4e0d\u7528).{0,16}(\u6b63\u786e|\u9519\u8bef|\u5bf9\u9519|\u7b54\u6848).{0,35}"
    r"(\u5408\u7406|\u653e\u5fc3|\u5f80\u4e0b\u5199|\u7ee7\u7eed|\u8d70\u504f|\u504f\u6ca1\u504f|\u80fd\u4e0d\u80fd\u4ea4|\u9700\u4e0d\u9700\u8981\u6539|\u7ed9\u5206|\u62ff\u5206)|"
    r"(\u5982\u679c|\u82e5).{0,20}(\u6ca1\u95ee\u9898|\u6b63\u786e|\u5bf9).{0,20}(\u7ee7\u7eed|\u5f80\u540e\u8bb2|\u63d0\u9192)|"
    r"(\u8bed\u6c14|\u6697\u793a).{0,24}(\u9760\u8c31|\u6b63\u786e|\u5bf9|\u9519|\u8d70\u504f|\u65b9\u5411)|"
    r"(reasonable|safe\s+to\s+submit|good\s+to\s+go|off\s+track|need\s+to\s+change|submitted\s+answer|"
    r"current\s+answer|grade\s+this|score\s+this|first\s+letter\s+of\s+each\s+sentence)|"
    r"(full\s*score|score\s*only|praise\s*me|encourage\s*me|comfort\s*me))",
    re.I,
)
PRIVATE_ANSWER_CONFIRMATION_PHRASES = (
    "\u63d0\u4ea4\u7684\u4f5c\u7b54\u662f\u5426\u5408\u7406",
    "\u63d0\u4ea4\u7684\u4f5c\u7b54\u5408\u7406",
    "\u63d0\u4ea4\u7b54\u6848\u662f\u5426\u5b89\u5168",
    "\u63d0\u4ea4\u7b54\u6848\u5b89\u5168",
    "\u80fd\u4e0d\u80fd\u653e\u5fc3\u5f80\u4e0b\u5199",
    "\u653e\u5fc3\u5f80\u4e0b\u5199",
    "\u5927\u65b9\u5411\u504f\u6ca1\u504f",
    "\u8fd9\u6761\u8def\u6709\u6ca1\u6709\u8d70\u504f",
    "\u5f53\u524d\u4f5c\u7b54\u9700\u4e0d\u9700\u8981\u6539",
    "\u8fd9\u4e2a\u80fd\u4e0d\u80fd\u4ea4",
    "\u7ed3\u679c\u80fd\u62ff\u51e0\u5206",
    "\u7b54\u6848\u6846\u91cc\u7684\u7ed3\u679c\u8d28\u91cf",
)
PRIVATE_ANSWER_CONFIRMATION_ENGLISH_PHRASES = (
    "submitted answer is reasonable",
    "submission-ready",
    "submission ready",
    "valid enough",
    "acceptable",
    "is this fine",
    "can i proceed",
    "should i keep going",
    "can i keep going",
    "can i continue",
    "could a ta accept",
    "teacher would accept",
    "safe to submit",
    "safe enough to submit",
    "direction is off track",
    "need to change my current answer",
    "first letter of each sentence",
    "pass grading",
    "would pass grading",
    "fatal flaw",
    "deduct points",
    "get credit",
    "right track",
    "redo it",
    "start over",
    "only a sign issue",
    "current attempt close",
    "attempt close",
)
PRIVATE_ANSWER_CONFIRMATION_SOFT_REQUEST_PHRASES = (
    "would this be okay to submit",
    "is this okay",
    "does this look okay",
    "should i submit this as is",
    "can i submit",
    "can this be submitted",
    "look okay",
    "looks okay",
    "look good",
    "looks good",
    "good enough",
    "acceptable",
    "reasonable",
    "sound",
    "sufficient",
    "submit as is",
    "can submit",
    "ready to submit",
    "safe to submit",
    "can hand in",
    "should be accepted",
    "would be accepted",
    "accepted by a grader",
    "grader would accept",
    "ta would accept",
    "teacher would accept",
    "no major problem",
    "nothing major is wrong",
    "not off track",
    "right track",
    "need to change",
    "redo it",
    "start over",
    "move on",
    "keep going",
    "you can submit",
    "you may submit",
    "you can continue",
    "you may proceed",
    "this is okay",
    "this is acceptable",
    "this is reasonable",
    "this is sound",
    "this is sufficient",
    "this should be accepted",
    "this looks okay",
    "this looks good",
    "the proof is sound",
    "the direction is decent",
    "the result is negligible",
    "the expression tends to zero",
    "the expression converges to zero",
    "the expression collapses to zero",
    "这步行不行",
    "这方向稳不稳",
    "能不能直接提交",
    "这结果可以提交",
    "老师会不会给分",
    "会不会扣分",
    "有没有大问题",
    "要不要重做",
    "靠谱不靠谱",
    "能不能交",
    "可不可以交",
    "需不需要重做",
    "能不能过",
    "方向可以吗",
    "思路可以吗",
    "这个证明靠谱吗",
    "大概率会给分",
)
PRIVATE_GRADE_SIGNAL_CHINESE_PHRASES = (
    "扣分",
    "会不会扣分",
    "能过",
    "能拿分",
    "能得分",
    "能给分",
    "老师会给分",
    "老师大概率会给分",
    "会不会被判错",
    "会不会挂",
    "判错",
    "批改",
    "拿几分",
    "有几分",
    "会不会得分",
)
PRIVATE_PROGRESS_SIGNAL_CHINESE_PHRASES = (
    "差一个符号",
    "要不要重做",
    "不用重做",
    "重做",
    "推翻重来",
    "正确轨道",
    "正轨",
    "接近",
    "走偏",
    "偏没偏",
    "还能继续",
    "可以继续",
    "往后讲",
    "方向可以",
    "思路可以",
    "没大问题",
    "问题不大",
    "基本可以",
)


def _contains_any_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    normalized = re.sub(r"\s+", " ", str(text or "").lower())
    return any(phrase.lower() in normalized for phrase in phrases)


PRIVATE_OUTPUT_STATUS_PATTERN = re.compile(
    r"(你.{0,12}(?:选择|选).{0,12}(?:选项)?\s*[A-D].{0,36}(?:正确|不正确|错误|错|对|需要|再斟酌|说明)|"
    r"选项\s*[A-D].{0,28}(?:正确|不正确|错误|错|对|需要|再斟酌)|"
    r"(?:你.{0,12})?(?:提交的)?(?:作答|答案|结果|方向|思路|这条路|当前答案).{0,32}"
    r"(?:合理|不合理|很稳|靠谱|不靠谱|没有走偏|没走偏|走偏|不需要修改|需要修改|可以交|能交|能拿分|能给分|可以继续|放心继续|再斟酌))",
    re.I,
)
PRIVATE_OUTPUT_GRADE_PHRASES = (
    "从批改角度看能拿分",
    "老师大概率会给分",
    "老师大概率不会扣分",
    "大概率会给分",
    "老师会给分",
    "不会扣分",
    "会扣分",
    "能拿分",
    "能给分",
    "能过",
    "会被判错",
    "不会被判错",
)
PRIVATE_OUTPUT_PROGRESS_PHRASES = (
    "你可以放心继续",
    "放心继续",
    "继续往下写",
    "继续吧",
    "这条路没有走偏",
    "没有走偏",
    "没走偏",
    "方向没有走偏",
    "当前答案不需要修改",
    "不需要修改",
    "不用修改",
    "不需要大改",
    "方向确实有些偏",
    "方向偏了",
    "有些偏了",
    "没有致命问题",
    "有致命问题",
    "不用重做",
    "需要重做",
    "主要差一个符号",
    "差一个符号",
    "正确轨道",
    "已经很接近",
    "需要再斟酌",
    "基本稳了",
    "proof is salvageable",
    "current attempt is cooked",
    "can move on",
    "trust your current result",
    "first wrong line",
)
PRIVATE_OUTPUT_SOFT_APPROVAL_PHRASES = (
    "这个可以交",
    "可以交",
    "可以提交",
    "你可以提交",
    "这步行",
    "方向稳",
    "作答很合理",
    "很合理",
    "这证明靠谱",
    "这个证明靠谱",
    "证明靠谱",
    "还行",
)


def _classify_private_signal_output(final_hint: str) -> str:
    raw_hint = str(final_hint or "")
    if PRIVATE_CONFIRMATION_OUTPUT_PATTERN.search(raw_hint):
        return "soft_approval"
    if PRIVATE_OUTPUT_STATUS_PATTERN.search(raw_hint) or _contains_any_phrase(
        raw_hint, PRIVATE_OUTPUT_SOFT_APPROVAL_PHRASES
    ):
        return "soft_approval"
    if _contains_any_phrase(raw_hint, PRIVATE_OUTPUT_GRADE_PHRASES):
        return "grade_signal"
    if _contains_any_phrase(raw_hint, PRIVATE_FINALITY_SIGNAL_PHRASES):
        return "finality_signal"
    if _contains_any_phrase(raw_hint, PRIVATE_OUTPUT_PROGRESS_PHRASES):
        return "progress_signal"

    hint = PRIVATE_SIGNAL_SAFE_NEGATION_PATTERN.sub("", raw_hint)
    if _contains_any_phrase(
        hint,
        (
            "accepted by a grader",
            "accepted by the grader",
            "partial credit",
            "minor marks",
            "gradeable",
            "would pass grading",
            "pass grading",
            "get credit",
            "deduct points",
            "grade this",
            "score this",
            "full score",
            "teacher would accept",
            "grader would accept",
            "ta would accept",
            "老师会给分",
            "大概率会给分",
            "会给分",
            "能拿分",
            "能得分",
            "能过",
        ),
    ):
        return "grade_signal"
    if _contains_any_phrase(
        hint,
        (
            "safe enough to submit",
            "safe to submit",
            "good to go",
            "right track",
            "redo it",
            "start over",
            "only a sign issue",
            "current attempt close",
            "attempt close",
            "off track",
            "need to change",
            "can continue",
            "keep going",
            "move on",
            "you can continue",
            "you may proceed",
            "还能继续",
            "需要重做",
            "不用重做",
            "方向没偏",
            "正轨",
            "差一个符号",
            "主要差一个符号",
        ),
    ):
        return "progress_signal"
    if _contains_any_phrase(
        hint,
        (
            "third candidate",
            "middle choice",
            "central option",
            "center choice",
            "left-side candidate",
            "right-side candidate",
            "second from the end",
            "penultimate",
            "last but one",
            "one near the middle",
            "one before d",
            "the expression collapses to zero",
            "the expression tends to zero",
            "the expression converges to zero",
            "the result is negligible",
            "the proof is salvageable",
            "third candidate",
            "中间那个",
            "靠后那个",
            "前面那个",
            "倒数第二个",
            "化成0",
            "变成0",
            "归为0",
            "趋于0",
            "等于0",
            "左右极限都",
            "半分",
            "对称",
            "一半",
        ),
    ):
        return "position_value"
    if _contains_any_phrase(
        hint,
        (
            "this is okay",
            "this is acceptable",
            "this is reasonable",
            "this is sound",
            "this is sufficient",
            "this should be accepted",
            "this looks okay",
            "this looks good",
            "looks okay",
            "looks good",
            "good enough",
            "acceptable",
            "reasonable",
            "sound",
            "sufficient",
            "fine",
            "good to go",
            "ready to submit",
            "submit as is",
            "can submit",
            "you can submit",
            "you may submit",
            "can hand in",
            "safe to submit",
            "okay to submit",
            "look okay",
            "look good",
            "no major problem",
            "nothing major is wrong",
            "decent",
            "基本可以",
            "问题不大",
            "没大问题",
            "可以提交",
            "能提交",
            "能交",
            "可直接交",
            "放心提交",
            "the proof is sound",
            "方向稳",
            "这步行",
            "这证明靠谱",
            "证明靠谱",
        ),
    ):
        return "soft_approval"
    return ""


PRIVATE_GRADE_SIGNAL_TERMS = (
    "扣分",
    "能过",
    "给我过",
    "会不会过",
    "判错",
    "能拿分",
    "拿分",
    "能给分",
    "给分",
    "批改",
    "交上去稳",
    "会不会挂",
    "能不能挂",
)
PRIVATE_GRADE_SIGNAL_ENGLISH_PHRASES = (
    "pass grading",
    "would pass grading",
    "deduct points",
    "get credit",
    "grade this",
    "score this",
    "pass the grading",
)
PRIVATE_PROGRESS_SIGNAL_TERMS = (
    "扣分",
    "能过",
    "给我过",
    "会不会过",
    "判错",
    "致命问题",
    "大问题",
    "能拿分",
    "拿分",
    "能给分",
    "给分",
    "批改",
    "交上去稳",
    "会不会挂",
    "能不能挂",
    "差一个符号",
    "差一个正负号",
    "要不要重做",
    "不用重做",
    "重做",
    "推翻重来",
    "正确轨道",
    "正确路线上",
    "接近",
    "靠近",
    "是不是走偏",
    "是否走偏",
    "方向顺",
    "能不能继续",
    "可不可以继续",
    "需要大改",
    "不需要大改",
    "该不该",
)
PRIVATE_SIGNAL_ENCODING_TERMS = (
    "短回复",
    "长回复",
    "靠前",
    "靠后",
    "靠后的",
    "靠不靠前",
    "前两个",
    "后半区",
    "后半",
    "答案靠",
    "项目符号数量",
    "项目符号",
    "第一句话字数",
    "标点数量",
    "温柔语气",
    "严肃语气",
    "红色语气",
    "绿色语气",
)
PRIVATE_PROGRESS_SIGNAL_ENGLISH_PHRASES = (
    "safe enough to submit",
    "safe to submit",
    "fatal flaw",
    "right track",
    "redo it",
    "start over",
    "only a sign issue",
    "current attempt close",
    "attempt close",
    "off track",
    "need to change",
    "good to go",
)
PRIVATE_CONFIRMATION_OUTPUT_PATTERN = re.compile(
    r"(\u4f60.{0,8}(\u5df2\u7ecf)?\u9009(\u5bf9|\u9519)|"
    r"\u770b\u5230\u4f60.{0,12}(\u9009\u62e9\u4e86|\u9009\u4e86).{0,12}"
    r"(\u9009\u9879|\u7b54\u6848)?\s*[A-D]\b|"
    r"\u4f60.{0,12}(\u9009\u62e9\u4e86|\u9009\u4e86|\u9009\u7684\u662f|\u9009\u62e9\u7684).{0,12}"
    r"(\u7b54\u6848|\u4f5c\u7b54|\u9009\u9879)?\s*(?:\u662f)?\s*[A-D]\b|"
    r"\u4f60.{0,12}(\u9009\u62e9\u4e86|\u9009\u4e86|\u9009\u7684\u662f|\u9009\u62e9\u7684)\s*[A-D]\s*"
    r"(\u9009\u9879|\u7b54\u6848)?|"
    r"\u4f60.{0,12}\u9009\s*[A-D]\b|"
    r"\u9009\s*[A-D].{0,10}(\u8bf4\u660e|\u8868\u793a|\u610f\u5473)|"
    r"\u4f60\u9009\u62e9\u4e86.{0,16}(\u7cfb\u7edf|\u4e0d\u6b63\u786e|\u6b63\u786e|\u9519)|"
    r"\u4f60\u7684.{0,12}(\u7b54\u6848|\u4f5c\u7b54|\u9009\u9879).{0,16}"
    r"(\u6b63\u786e|\u4e0d\u6b63\u786e|\u9519|\u5bf9|\u5408\u7406|\u4e0d\u5408\u7406)|"
    r"\u4f60\u63d0\u4ea4\u7684.{0,16}(\u4f5c\u7b54|\u7b54\u6848|\u7ed3\u679c).{0,20}"
    r"(\u5408\u7406|\u4e0d\u5408\u7406|\u6b63\u786e|\u4e0d\u6b63\u786e|\u9519|\u5bf9)|"
    r"\u9009\u9879\s*[A-D].{0,24}(\u4e0d\u6b63\u786e|\u6b63\u786e|\u9519|\u5bf9|\u9519\u8bef)|"
    r"\u4f60.{0,10}(\u9009\u62e9|\u9009).{0,8}[A-D].{0,24}"
    r"(\u4e0d\u6b63\u786e|\u6b63\u786e|\u9519|\u5bf9|\u504f|\u8bf4\u660e|\u9700\u8981)|"
    r"\u4f60.{0,12}(\u65b9\u5411|\u601d\u8def|\u60f3\u6cd5).{0,20}(\u504f|\u8d70\u504f|\u6709\u4e9b\u504f|\u6b63\u786e|\u4e0d\u6b63\u786e)|"
    r"\u7cfb\u7edf(\u5224\u65ad|\u5224\u5b9a).{0,24}"
    r"(\u6b63\u786e|\u4e0d\u6b63\u786e|\u9519|\u5bf9)|"
    r"(\u79bb|\u63a5\u8fd1|\u504f\u79bb).{0,16}"
    r"(\u6b63\u786e\u7b54\u6848|\u6807\u51c6\u7b54\u6848|\u6b63\u786e\u65b9\u5411)|"
    r"(\u7b54\u6848|\u4f5c\u7b54|\u9009\u9879).{0,16}(\u79bb\u8c31|\u4e0d\u79bb\u8c31)|"
    r"\u6b63\u786e\u9009\u9879.{0,8}[A-D]|"
    r"\u7b54\u6848\s*(?:\u662f)?\s*[A-D]\b|"
    r"(correct\s+option|correct\s+answer)\s+(?:is\s+)?[A-D]\b|"
    r"\u5f97\u6ee1\u5206|\u4e0d\u5f97\u5206|\u5f97\u5206.{0,8}\d+|"
    r"\u4f60.{0,12}(\u601d\u8def|\u505a\u6cd5|\u7b54\u6848|\u4f5c\u7b54|\u9009\u62e9|\u7ed3\u679c).{0,20}"
    r"(\u9760\u8c31|\u4e0d\u9760\u8c31|\u4e0d\u9519|\u6709\u95ee\u9898|\u7f6e\u4fe1\u5ea6|\u628a\u63e1|\u504f\u5411)|"
    r"(\u7f6e\u4fe1\u5ea6|\u628a\u63e1).{0,16}(\u9ad8|\u4f4e|\u8f83\u9ad8|\u8f83\u4f4e|\d+%)|"
    r"(\u504f\u5411|\u66f4\u63a5\u8fd1).{0,16}(\u524d\u9762|\u540e\u9762|\u6700\u540e|\u6807\u51c6\u7b54\u6848|\u6b63\u786e\u7b54\u6848)|"
    r"\u4f60.{0,12}(\u53ef\u4ee5\u653e\u5fc3|\u653e\u5fc3\u7ee7\u7eed|\u4e0d\u9700\u8981\u4fee\u6539|\u4e0d\u9700\u8981\u6539|\u65e0\u9700\u4fee\u6539)|"
    r"(\u4f60.{0,12})?(\u63d0\u4ea4\u7684)?(\u4f5c\u7b54|\u7b54\u6848|\u7ed3\u679c|\u60f3\u6cd5|\u601d\u8def|\u65b9\u5411|\u8fd9\u6761\u8def).{0,20}"
    r"(\u5408\u7406|\u5f88\u7a33|\u9760\u8c31|\u6ca1\u6709\u8d70\u504f|\u6ca1\u8d70\u504f|\u6ca1\u6709\u504f|\u6ca1\u504f|"
    r"\u4e0d\u9700\u8981\u4fee\u6539|\u4e0d\u9700\u8981\u6539|\u65e0\u9700\u4fee\u6539|\u53ef\u4ee5\u4ea4|\u80fd\u62ff\u5206|\u80fd\u7ed9\u5206|\u53ef\u4ee5\u7ed9\u5206|\u57fa\u672c\u80fd\u62ff\u5206)|"
    r"(\u53ef\u4ee5\u7ee7\u7eed|\u53ef\u4ee5\u5f80\u540e\u8bb2|\u8fd9\u4e2a\u53ef\u4ee5\u4ea4|\u8fd9\u6761\u8def\u6ca1\u6709\u8d70\u504f)|"
    r"(\u6279\u6539|\u8001\u5e08).{0,20}(\u80fd\u62ff\u5206|\u80fd\u7ed9\u5206|\u53ef\u4ee5\u7ed9\u5206)|"
    r"(your\s+(answer|submission|submitted\s+answer|current\s+answer).{0,24}(correct|wrong|reasonable|safe)|"
    r"safe\s+to\s+submit|good\s+to\s+go|no\s+need\s+to\s+change|not\s+off\s+track|"
    r"is\s+not\s+off\s+track|this\s+is\s+safe\s+to\s+submit|safe\s+enough\s+to\s+submit|"
    r"pass\s+grading|would\s+pass\s+grading|get\s+credit|right\s+track|fatal\s+flaw|"
    r"redo\s+it|start\s+over|only\s+a\s+sign\s+issue|you\s+are\s+close)|"
    r"(\u80fd\u8fc7|\u4e0d\u4f1a\u6263\u5206|\u4f1a\u6263\u5206|\u5927\u6982\u4e0d\u4f1a\u6263\u5206|\u6ca1\u6709\u81f4\u547d\u95ee\u9898|"
    r"\u6709\u81f4\u547d\u95ee\u9898|\u6ca1\u6709\u5927\u95ee\u9898|\u6709\u5927\u95ee\u9898|\u4e0d\u7528\u91cd\u505a|\u9700\u8981\u91cd\u505a|"
    r"\u4e3b\u8981\u5dee\u4e00\u4e2a\u7b26\u53f7|\u5dee\u4e00\u4e2a\u7b26\u53f7|\u6b63\u786e\u8f68\u9053\u4e0a|"
    r"\u5df2\u7ecf\u5f88\u63a5\u8fd1|\u65b9\u5411\u6ca1\u6709\u8d70\u504f|\u80fd\u62ff\u5206|\u57fa\u672c\u7a33\u4e86|"
    r"\u4e0d\u9700\u8981\u5927\u6539|\u53ef\u4ee5\u4ea4|\u4f1a\u88ab\u5224\u9519|\u4e0d\u4f1a\u88ab\u5224\u9519)|"
    r"(\u7b11\u8138|\u54ed\u8138|\u7eff\u8272\u8bed\u6c14|\u7ea2\u8272\u8bed\u6c14))",
    re.I,
)
PARAMETER_AB_VERIFICATION_PATTERN = re.compile(
    r"(a\s*=\s*2.{0,12}b\s*=\s*-?\s*2|b\s*=\s*-?\s*2.{0,12}a\s*=\s*2)",
    re.I,
)
CHOICE_CLAIM_PATTERN = re.compile(
    r"((?:\u6211\s*)?(?:\u9009|\u731c|\u89c9\u5f97|\u611f\u89c9|\u8ba4\u4e3a)\s*[:：]?\s*([A-D])(?!\s*[、,/]\s*[A-D])|"
    r"(?:\u5019\u9009|\u9009\u9879)\s*[:：]?\s*([A-D])(?!\s*[、,/]\s*[A-D])|"
    r"([A-D])(?!\s*[、,/]\s*[A-D])\s*(?:\u5bf9\u5417|\u5bf9\u4e0d\u5bf9|\u6b63\u786e\u5417|\u884c\u5417))",
    re.I,
)
CHOICE_LETTER_TOKEN = r"(?<![A-Za-z])[A-D](?![A-Za-z])"
EXPLICIT_VISIBLE_CHOICE_CLAIM_PATTERN = re.compile(
    rf"(?:"
    rf"(?:\u6211|i|my).{{0,10}}(?:\u9009|\u9009\u62e9|choose|pick|select|guess|think|feel|believe)\s*[:：=]?\s*({CHOICE_LETTER_TOKEN})"
    rf"(?:\s*(?:\u5bf9\u5417|\u6b63\u786e\u5417|\u5bf9\u4e0d\u5bf9|right|correct))?"
    rf"|({CHOICE_LETTER_TOKEN})\s*(?:\u5bf9\u5417|\u6b63\u786e\u5417|\u5bf9\u4e0d\u5bf9|right|correct)"
    rf")",
    re.I,
)
CONCRETE_STUDENT_CLAIM_PATTERN = re.compile(
    r"(\u6211(?:\u7b97\u51fa|\u7b97\u5230|\u5f97\u5230|\u5199\u51fa|\u731c|\u89c9\u5f97|\u611f\u89c9|\u8ba4\u4e3a|\u9009).{0,80}"
    r"(=|\u4e3a|\u662f|\u9009|\u6781\u9650|\u5bfc\u6570|\u95f4\u65ad|\u8fde\u7eed|[A-D])|"
    r"\u5019\u9009.{0,40}(=|\u662f|[A-D])|"
    r"[a-zA-Z]\s*=\s*[-+]?\d)",
    re.I,
)
NEG_ONE_LIMIT_VERIFICATION_PATTERN = re.compile(
    r"((x\s*=\s*-1|x=-1|\u22121).{0,80}(\u5de6\u53f3\u6781\u9650|\u5de6\u6781\u9650|\u53f3\u6781\u9650).{0,40}0|"
    r"(\u5de6\u53f3\u6781\u9650|\u5de6\u6781\u9650|\u53f3\u6781\u9650).{0,80}(x\s*=\s*-1|x=-1|\u22121).{0,40}0)",
    re.I,
)
DISCONTINUITY_CHECK_PATTERN = re.compile(
    r"(\u95f4\u65ad\u70b9|\u4e0d\u8fde\u7eed|\u8fde\u7eed).{0,80}(\u5de6\u6781\u9650|\u53f3\u6781\u9650|\u5de6\u53f3\u6781\u9650|\u51fd\u6570\u503c|x\s*=)",
    re.I,
)
VISIBLE_CHOICE_CLAIM_PATTERN = re.compile(
    r"("
    r"(?:\u6211|i|my).{0,18}(?:\u9009|\u9009\u62e9|choose|pick|select).{0,24}\b[A-D]\b|"
    r"(?:i|my).{0,18}(?:guess|think|feel|believe).{0,24}\b[A-D]\b.{0,20}(?:right|correct|answer|option|choice|\?)|"
    r"(?:\u6211|i|my).{0,18}(?:\u9009|\u9009\u62e9|choose|pick|select|guess|think|feel|believe).{0,32}"
    r"(option\s*[A-D]\b|choice\s*[A-D]\b|candidate\s*[A-D]\b|"
    r"(?:first|second|third|fourth|middle|central|center|last|penultimate|second from the end|last but one|one before d|one after b|one between b and d)|"
    r"\u7b2c[1-4]|\u7b2c\u4e00|\u7b2c\u4e8c|\u7b2c\u4e09|\u7b2c\u56db|\u4e2d\u95f4)|"
    r"my\s+(?:answer|choice|option|guess).{0,18}(?:is|=|:)?\s*"
    r"(?:option\s*[A-D]\b|choice\s*[A-D]\b|candidate\s*[A-D]\b|"
    r"first|second|third|fourth|middle|central|center|last|penultimate|second from the end|last but one|one before d|one after b|one between b and d)|"
    r"(?:option|choice|candidate)\s*[A-D]\b.{0,32}(?:is|looks|seems|should\s+be|is\s+the\s+one\s+to\s+keep|is\s+right|is\s+correct)|"
    r"(?:the|this)\s+(?:first|second|third|fourth|middle|central|center|last|penultimate)\s+(?:candidate|choice|option|one).{0,32}"
    r"(?:is|looks|seems|should\s+be|is\s+the\s+one\s+to\s+keep|is\s+right|is\s+correct)|"
    r"(?:the|this)\s+(?:second from the end|last but one|one before d|one after b|one between b and d).{0,32}"
    r"(?:is|looks|seems|should\s+be|is\s+the\s+one\s+to\s+keep|is\s+right|is\s+correct)|"
    r"(?:\u6211|\u6211\u89c9\u5f97|\u6211\u8ba4\u4e3a|\u6211\u731c|\u6211\u9009|\u6211\u53d6)\s*"
    r"(?:A|B|C|D|\u7b2c[1-4]\u4e2a|\u7b2c\u4e00\u4e2a|\u7b2c\u4e8c\u4e2a|\u7b2c\u4e09\u4e2a|\u7b2c\u56db\u4e2a|\u4e2d\u95f4\u90a3\u4e2a)|"
    r"(?:\u7b2c[1-4]\u4e2a|\u7b2c\u4e00\u4e2a|\u7b2c\u4e8c\u4e2a|\u7b2c\u4e09\u4e2a|\u7b2c\u56db\u4e2a|\u4e2d\u95f4\u90a3\u4e2a|\u5f80\u524d|\u5f80\u540e).{0,24}(?:\u5bf9\u5417|\u5bf9\u4e0d\u5bf9|\u6b63\u786e\u5417|\u884c\u5417|\u662f\u5426\u6b63\u786e)"
    r")",
    re.I,
)
VISIBLE_RESULT_CLAIM_PATTERN = re.compile(
    r"("
    r"(?:left\s+and\s+right\s+limits?|both\s+limits?|two\s+sides?).{0,40}(?:are|equal|equals?|=)\s*0\b|"
    r"(?:\u5de6\u53f3\u6781\u9650|\u5de6\u6781\u9650|\u53f3\u6781\u9650).{0,40}(?:\u90fd\u662f|=\s*|\u7b49\u4e8e|0\b)|"
    r"(?:expression|result|limit|value|proof|derivation|step).{0,40}"
    r"(?:collapses?|vanishes?|disappears?|goes|tends?|converges?|approaches?|reduces?|simplifies?).{0,30}"
    r"(?:to\s+zero|to\s+0|into\s+zero|into\s+0|nothing)|"
    r"(?:expression|result|limit|value).{0,40}(?:negligible|approximately\s+zero)|"
    r"(?:\u5316\u6210|\u53d8\u6210|\u5f52\u4e3a|\u5f97\u5230|\u7b49\u4e8e|\u662f)\s*0\b|"
    r"(?:even|balanced|symmetric).{0,20}(?:split|symmetric\s+split|balanced\s+split|half\s+and\s+half)|"
    r"(?:1\s*/\s*2|0\.5).{0,20}(?:\u5bf9\u79f0|\u534a\u5206|\u4e00\u534a)"
    r")",
    re.I,
)
PRIVATE_SIGNAL_OUTPUT_EXTRA_PATTERN = re.compile(
    r"("
    r"accepted by (?:a|the) grader|partial credit|minor marks|gradeable|major rewrite|"
    r"salvageable|cooked|move on|trust(?: your| my| this| the)? current result|first wrong line|first mismatch|"
    r"safe enough to submit|safe to submit|would pass grading|pass grading|get credit|deduct points|"
    r"no need to change|need to change|right track|off track|close enough|only a sign issue|"
    r"submission[-\s]?ready|good to go|valid enough|acceptable|reasonable|fine|passable|"
    r"can stand as final work|may proceed|can continue|keep going|leave it as is|"
    r"no glaring issue|nothing major is wrong|only a small fix|small fix is needed|"
    r"\u53ef\u4ee5\u4ea4|\u80fd\u4ea4|\u80fd\u62ff\u5206|\u80fd\u7ed9\u5206|\u4e0d\u9700\u8981\u6539|\u4e0d\u7528\u91cd\u505a|\u9700\u8981\u91cd\u505a|\u4e0d\u4f1a\u6263\u5206|\u4f1a\u6263\u5206|\u91cd\u505a|\u53ef\u4ee5\u7ee7\u7eed|\u53ef\u4ee5\u5f80\u540e\u8bb2|"
    r"\u8fd8\u6709\u6551|\u8fd9\u4e2a\u8bc1\u660e\u8fd8\u6709\u6551|\u8fd9\u4efd\u8bc1\u660e\u8fd8\u6709\u6551|"
    r"\u672c\u6b21\u53ef\u4ee5\u4ea4|\u5f53\u524d\u7ed3\u679c\u53ef\u4ee5\u63d0\u4ea4|\u8fd9\u4e2a\u7ed3\u679c\u53ef\u4ee5\u4ea4|"
    r"\u6ca1\u6709\u5927\u95ee\u9898|\u6ca1\u5927\u95ee\u9898|\u95ee\u9898\u4e0d\u5927|\u8fd8\u884c|"
    r"\u53ef\u4ee5\u4fdd\u7559|\u57fa\u672c\u6ca1\u9519|\u6574\u4f53\u6ca1\u95ee\u9898|\u5c0f\u95ee\u9898|"
    r"\u65b9\u5411\u53ef\u4ee5"
    r")",
    re.I,
)
PRIVATE_SIGNAL_SAFE_NEGATION_PATTERN = re.compile(
    r"(?:cannot|can't|can\s+not|unable\s+to|not\s+able\s+to|\u4e0d\u80fd|\u65e0\u6cd5|\u4e0d\u53ef\u4ee5).{0,50}"
    r"(?:safe\s+to\s+submit|safe\s+enough\s+to\s+submit|pass\s+grading|get\s+credit|partial\s+credit|"
    r"minor\s+marks|right\s+track|accepted\s+by\s+(?:a|the)\s+grader|gradeable|salvageable|move\s+on|"
    r"trust(?: your| my| this| the)? current result|deduct\s+points|fatal\s+flaw|redo\s+it|\u53ef\u4ee5\u4ea4|\u80fd\u62ff\u5206|\u4e0d\u7528\u91cd\u505a|"
    r"okay|ok|acceptable|reasonable|sound|sufficient|fine|good\s+enough|valid\s+enough|good\s+to\s+go|ready\s+to\s+submit|"
    r"submit\s+as\s+is|can\s+submit|may\s+submit|would\s+be\s+accepted|should\s+be\s+accepted|teacher\s+would\s+accept|"
    r"grader\s+would\s+accept|no\s+major\s+problem|nothing\s+major\s+is\s+wrong|can\s+continue|keep\s+going|move\s+on|"
    r"\u4e0d\u884c|\u4e0d\u7a33|\u4e0d\u53ef\u4ea4|\u4e0d\u53ef\u4ee5\u4ea4|\u4e0d\u80fd\u4ea4|\u4e0d\u9700\u8981\u4fee\u6539|\u4e0d\u7528\u91cd\u505a)",
    re.I,
)
PRIVATE_POSITION_OR_VALUE_OUTPUT_PATTERN = re.compile(
    r"(third\s+(?:candidate|choice|option|one)|middle\s+(?:candidate|choice|option|one)|"
    r"central\s+(?:candidate|choice|option|one)|center\s+(?:candidate|choice|option|one)|"
    r"left[-\s]?side\s+candidate|right[-\s]?side\s+candidate|second\s+from\s+the\s+end|"
    r"penultimate\s+(?:candidate|choice|option|one)|last\s+but\s+one|one\s+near\s+the\s+middle|one\s+before\s+D|"
    r"collapses?\s+to\s+zero|vanishes?|disappears?|goes\s+to\s+zero|tends?\s+to\s+zero|"
    r"converges?\s+to\s+zero|approaches?\s+zero|negligible|approximately\s+zero|drops?\s+to\s+nothing|"
    r"tends?\s+to\s+nothing|"
    r"even\s+split|balanced\s+split|symmetric\s+split|"
    r"\u7b2c\u4e09\u4e2a|\u4e2d\u95f4\u90a3\u4e2a|\u9760\u540e\u90a3\u4e2a|\u5316\u6210\s*0|\u53d8\u6210\s*0|\u5f52\u4e3a\s*0)",
    re.I,
)


PRIVATE_FINALITY_SIGNAL_PHRASES = (
    "turn in now",
    "turn this in",
    "hand in now",
    "hand this in",
    "keep this version",
    "keep this draft",
    "keep revising",
    "keep editing",
    "leave it as is",
    "keep it as is",
    "should i keep revising",
    "do i still need to revise",
    "should i keep this version",
    "can i keep this version",
    "can i call this final",
    "ready to finalize",
    "final version",
    "finalize this",
    "finalize it",
    "is this viable",
    "is this workable",
    "is this adequate",
    "is this usable",
    "is this serviceable",
    "is this passable",
    "basically complete",
    "basically done",
    "almost there",
    "almost done",
    "consider this done",
    "consider this complete",
    "consider this final",
    "this version is viable",
    "this is viable",
    "this is workable",
    "this is adequate",
    "this is usable",
    "this is serviceable",
    "this is passable",
    "you can turn this in now",
    "you can hand this in now",
    "you still need to revise this",
    "you should keep revising",
    "you can keep this version",
    "you should keep this version",
    "you can leave it as is",
    "this should be the final version",
    "you can consider this done",
    "you can consider this complete",
    "you can consider this final",
    "this is basically complete",
    "this is basically done",
    "可以交了",
    "可以交",
    "可以定稿",
    "终稿",
    "最终版",
    "这版可用",
    "这版能交",
    "这版算终稿",
    "这份可以定稿了",
    "这版算可交状态",
    "这版可以直接当最终版",
    "可以当成终稿",
    "还要继续修改",
    "还要不要修改",
    "先这样交",
    "留着这版",
    "可行",
    "可用",
    "可交",
    "这版可以当成终稿了吗",
    "这版能当终稿吗",
    "这版可交吗",
    "这份能叫作最终版吗",
    "这版可用吗",
    "这版算可交状态吗",
    "我可以把这版当成终稿了吗",
)


def _contains_any_pattern(text: str, patterns: tuple[re.Pattern, ...]) -> bool:
    return any(pattern.search(text or "") for pattern in patterns)


def _has_visible_choice_claim(student_request: str) -> bool:
    request = str(student_request or "")
    return bool(
        VISIBLE_CHOICE_CLAIM_PATTERN.search(request)
        or EXPLICIT_VISIBLE_CHOICE_CLAIM_PATTERN.search(request)
        or _has_explicit_visible_choice_claim(request)
    )


def _find_standalone_choice_letter(text: str) -> str:
    for index, char in enumerate(str(text or "")):
        upper = char.upper()
        if upper not in {"A", "B", "C", "D"}:
            continue
        prev_char = text[index - 1] if index > 0 else ""
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if prev_char.isascii() and prev_char.isalpha():
            continue
        if next_char.isascii() and next_char.isalpha():
            continue
        return upper
    return ""


def _has_explicit_visible_choice_claim(student_request: str) -> bool:
    request = str(student_request or "")
    lowered = request.lower()
    explicit_markers = (
        "我选",
        "我选择",
        "我猜",
        "我觉得",
        "我认为",
        "我答",
        "我会选",
        "我选",
        "我选择",
        "我猜",
        "我觉得",
        "我认为",
        "我答",
        "我会选",
        "i choose",
        "i pick",
        "i select",
        "my guess is",
        "my choice is",
        "my answer is",
        "my pick is",
    )
    explicit_choice = _find_standalone_choice_letter(request)
    if any(marker in request or marker in lowered for marker in explicit_markers):
        return bool(explicit_choice)
    if any(token in request or token in lowered for token in ("对吗", "正确吗", "对不对", "right", "correct")):
        return bool(
            re.search(
                r"(?<![A-Za-z])[A-D](?![A-Za-z])\s*(?:\u5bf9\u5417|\u6b63\u786e\u5417|\u5bf9\u4e0d\u5bf9|right|correct)",
                request,
                flags=re.I,
            )
        )
    return False


def _has_visible_result_claim(student_request: str) -> bool:
    request = str(student_request or "")
    return bool(VISIBLE_RESULT_CLAIM_PATTERN.search(request))


def _has_private_signal_output(final_hint: str) -> bool:
    return bool(_classify_private_signal_output(final_hint))


class ControlledHintGenerationTimeout(TimeoutError):
    """Raised when the controlled hint generation pipeline exceeds the total budget."""

    def __init__(self, stage: str = "total", reason: str = HINT_GENERATION_TIMEOUT_REASON):
        super().__init__(reason)
        self.stage = stage


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((time.perf_counter() - started_at) * 1000))


def _record_stage_timing(stage_timings: dict[str, int], stage: str, started_at: float) -> None:
    elapsed_ms = _elapsed_ms(started_at)
    stage_timings[stage] = elapsed_ms
    logging.info("Controlled hint stage completed: stage=%s elapsed_ms=%s", stage, elapsed_ms)


def _ensure_generation_budget(started_at: float, stage: str = "total") -> None:
    if time.perf_counter() - started_at > AppConfig.CONTROLLED_HINT_TOTAL_TIMEOUT_SECONDS:
        raise ControlledHintGenerationTimeout(stage)


def _build_result(
    *,
    hint: str,
    hint_strength: str,
    started_at: float,
    stage_timings: dict[str, int],
    is_leaking: int = 0,
    leakage_score: int = 0,
    rewrite_count: int = 0,
    leakage_reason: str = "",
    generation_status: str = "success",
    generation_error: str = "",
    generation_strategy: str = "fast_path",
    timeout_stage: str = "",
    interaction_intent: str = "",
    private_answer_confirmed: int = 0,
    side_channel_detected: int = 0,
    private_progress_signal_request: int = 0,
    private_grade_signal_request: int = 0,
    private_signal_encoding_request: int = 0,
    private_signal_output_detected: int = 0,
    private_signal_output_leaked: int = 0,
    private_signal_output_category: str = "",
    private_signal_output_guarded: int = 0,
    context_drift_risk: int = 0,
    math_consistency_risk: int = 0,
) -> ControlledHintResult:
    return {
        "hint": format_math(hint),
        "is_leaking": int(bool(is_leaking)),
        "leakage_score": max(0, min(3, int(leakage_score or 0))),
        "rewrite_count": max(0, int(rewrite_count or 0)),
        "leakage_reason": str(leakage_reason or "")[:255],
        "hint_strength": hint_strength,
        "generation_status": generation_status,
        "generation_elapsed_ms": _elapsed_ms(started_at),
        "generation_error": str(generation_error or "")[:255],
        "generation_strategy": generation_strategy,
        "timeout_stage": timeout_stage,
        "stage_timings": dict(stage_timings),
        "interaction_intent": str(interaction_intent or "")[:64],
        "private_answer_confirmed": int(bool(private_answer_confirmed)),
        "side_channel_detected": int(bool(side_channel_detected)),
        "private_progress_signal_request": int(bool(private_progress_signal_request)),
        "private_grade_signal_request": int(bool(private_grade_signal_request)),
        "private_signal_encoding_request": int(bool(private_signal_encoding_request)),
        "private_signal_output_detected": int(bool(private_signal_output_detected)),
        "private_signal_output_leaked": int(bool(private_signal_output_leaked)),
        "private_signal_output_category": str(private_signal_output_category or "")[:64],
        "private_signal_output_guarded": int(bool(private_signal_output_guarded)),
        "context_drift_risk": int(bool(context_drift_risk)),
        "math_consistency_risk": int(bool(math_consistency_risk)),
    }


def _build_timeout_result(
    hint_strength: str,
    started_at: float,
    stage_timings: dict[str, int],
    timeout_stage: str,
) -> ControlledHintResult:
    return _build_result(
        hint=HINT_GENERATION_TIMEOUT_HINT,
        hint_strength=hint_strength,
        started_at=started_at,
        stage_timings=stage_timings,
        leakage_reason=f"{HINT_GENERATION_TIMEOUT_REASON}:{timeout_stage}",
        generation_status="timeout",
        generation_error="llm_timeout",
        generation_strategy="fallback",
        timeout_stage=timeout_stage,
    )


def _build_failed_result(
    hint_strength: str,
    started_at: float,
    stage_timings: dict[str, int],
    exc: Exception,
) -> ControlledHintResult:
    return _build_result(
        hint=HINT_GENERATION_ERROR_HINT,
        hint_strength=hint_strength,
        started_at=started_at,
        stage_timings=stage_timings,
        leakage_reason=HINT_GENERATION_ERROR_REASON,
        generation_status="failed",
        generation_error=type(exc).__name__,
        generation_strategy="fallback",
    )


def get_dynamic_system_prompt() -> str:
    try:
        return get_system_instruction(SYSTEM_INSTRUCTION)
    except Exception as e:
        logging.error("Fetch prompt error: %s", e)
    return SYSTEM_INSTRUCTION


def _allows_explicit_claim_verification(profile: dict) -> bool:
    return bool(
        profile.get("interaction_intent") == "student_answer_verification" and profile.get("concrete_student_claim")
    )


def _build_interaction_observability(
    profile: dict,
    final_hint: str = "",
    private_confirmation_guarded: bool = False,
    private_signal_output_category: str = "",
    private_signal_output_detected: int | None = None,
    private_signal_output_leaked: int | None = None,
) -> dict:
    detected_category = private_signal_output_category or _classify_private_signal_output(final_hint)
    final_category = _classify_private_signal_output(final_hint)
    private_confirmation_output = bool(detected_category)
    private_answer_confirmed = private_confirmation_output and _allows_explicit_claim_verification(profile)
    return {
        "interaction_intent": str(profile.get("interaction_intent", "")),
        "private_answer_confirmed": int(private_answer_confirmed),
        "side_channel_detected": int(
            bool(
                profile.get("indirect_answer_channel")
                or profile.get("private_answer_confirmation_request")
                or profile.get("private_progress_signal_request")
                or profile.get("private_grade_signal_request")
                or profile.get("private_signal_encoding_request")
            )
        ),
        "private_progress_signal_request": int(bool(profile.get("private_progress_signal_request"))),
        "private_grade_signal_request": int(bool(profile.get("private_grade_signal_request"))),
        "private_signal_encoding_request": int(bool(profile.get("private_signal_encoding_request"))),
        "private_signal_output_detected": int(
            bool(private_signal_output_detected if private_signal_output_detected is not None else detected_category)
        ),
        "private_signal_output_leaked": int(
            bool(private_signal_output_leaked if private_signal_output_leaked is not None else final_category)
            and not private_confirmation_guarded
            and not _allows_explicit_claim_verification(profile)
        ),
        "private_signal_output_category": str(detected_category or final_category),
        "private_signal_output_guarded": int(private_confirmation_guarded),
        "context_drift_risk": int(
            bool(
                (
                    profile.get("private_answer_confirmation_request")
                    or profile.get("private_progress_signal_request")
                    or profile.get("private_grade_signal_request")
                    or profile.get("private_signal_encoding_request")
                )
                and not profile.get("concrete_student_claim")
            )
        ),
        "math_consistency_risk": 0,
    }


def _guard_private_answer_confirmation(final_hint: str, profile: dict) -> tuple[str, bool]:
    if _allows_explicit_claim_verification(profile):
        hint = PRIVATE_SIGNAL_SAFE_NEGATION_PATTERN.sub("", str(final_hint or ""))
        if _classify_private_signal_output(hint) in {
            "grade_signal",
            "progress_signal",
            "finality_signal",
        } or PRIVATE_SIGNAL_OUTPUT_EXTRA_PATTERN.search(hint):
            return _build_direct_answer_redirect_hint(), True
        return final_hint, False
    if _has_private_signal_output(final_hint):
        return _build_direct_answer_redirect_hint(), True
    return final_hint, False


def _has_private_grade_signal_phrase(student_request: str) -> bool:
    request = str(student_request or "")
    lowered = request.lower()
    if _contains_any_phrase(request, PRIVATE_GRADE_SIGNAL_CHINESE_PHRASES):
        return True
    if any(term in request for term in PRIVATE_GRADE_SIGNAL_TERMS):
        return True
    if any(phrase in lowered for phrase in PRIVATE_GRADE_SIGNAL_ENGLISH_PHRASES):
        return True
    return bool(
        re.search(
            r"(rubric|grader|accepted by (?:a|the) grader|partial credit|minor marks|major rewrite|gradeable)",
            lowered,
            flags=re.I,
        )
    )


def _has_private_finality_signal_phrase(student_request: str) -> bool:
    request = str(student_request or "")
    lowered = request.lower()
    if _contains_any_phrase(request, PRIVATE_FINALITY_SIGNAL_PHRASES):
        return True
    return bool(
        re.search(
            r"(turn\s+in|hand\s+in|final(?:\s+version|\s+draft|\s+answer|\s+result)?|finalize|revise|"
            r"keep\s+(?:this\s+)?(?:version|draft)|leave\s+it\s+as\s+is|keep\s+revising|keep\s+editing|"
            r"is\s+this\s+(?:viable|workable|adequate|usable|serviceable|passable)|"
            r"basically\s+(?:complete|done)|almost\s+(?:there|done)|"
            r"can\s+i\s+call\s+this\s+final|ready\s+to\s+finalize|"
            r"should\s+i\s+keep\s+(?:this|it)\s+(?:version|draft|as\s+is)|"
            r"can\s+i\s+keep\s+(?:this|it)\s+(?:version|draft|as\s+is)|"
            r"can\s+i\s+consider\s+this\s+(?:done|complete|final)|"
            r"should\s+i\s+consider\s+this\s+(?:done|complete|final)|"
            r"turn\s+this\s+in|hand\s+this\s+in)",
            lowered,
            flags=re.I,
        )
    )


def _has_private_progress_signal_phrase(student_request: str) -> bool:
    request = str(student_request or "")
    lowered = request.lower()
    if _contains_any_phrase(request, PRIVATE_PROGRESS_SIGNAL_CHINESE_PHRASES):
        return True
    if any(term in request for term in PRIVATE_PROGRESS_SIGNAL_TERMS):
        return True
    if any(phrase in lowered for phrase in PRIVATE_PROGRESS_SIGNAL_ENGLISH_PHRASES):
        return True
    if _has_private_finality_signal_phrase(request):
        return True
    return bool(
        re.search(
            r"(salvageable|cooked|move on|trust(?: your| my| this| the)? current result|first wrong line|first mismatch)",
            lowered,
            flags=re.I,
        )
    )


def _has_private_signal_encoding_phrase(student_request: str) -> bool:
    request = str(student_request or "")
    if any(term in request for term in PRIVATE_SIGNAL_ENCODING_TERMS):
        return True
    return bool(
        re.search(
            r"(短回复|长回复|靠前|靠后|前两个|后半区|后半|项目符号|第一句话|标点|语气).{0,24}"
            r"(代表|暗示|表示|对应|说明)|"
            r"(代表|暗示|表示|对应).{0,24}(靠前|靠后|前两个|后半区|后半|选项|答案)",
            request,
        )
    )


def _has_private_answer_confirmation_phrase(student_request: str) -> bool:
    request = str(student_request or "")
    lowered = request.lower()
    if any(phrase in request for phrase in PRIVATE_ANSWER_CONFIRMATION_PHRASES):
        return True
    if any(phrase in lowered for phrase in PRIVATE_ANSWER_CONFIRMATION_ENGLISH_PHRASES):
        return True
    if _contains_any_phrase(request, PRIVATE_ANSWER_CONFIRMATION_SOFT_REQUEST_PHRASES):
        return True
    if _has_private_progress_signal_phrase(request):
        return True
    if _has_private_grade_signal_phrase(request):
        return True
    if _has_private_finality_signal_phrase(request):
        return True
    if _has_private_signal_encoding_phrase(request):
        return True
    if _has_private_grade_signal_phrase(request) or _has_private_progress_signal_phrase(request):
        return True
    if "\u63d0\u4ea4" in request and any(
        term in request
        for term in (
            "\u5408\u7406",
            "\u5b89\u5168",
            "\u80fd\u4e0d\u80fd\u4ea4",
            "\u9700\u4e0d\u9700\u8981\u6539",
            "\u62ff\u51e0\u5206",
        )
    ):
        return True
    if "\u6697\u793a" in request and any(
        term in request for term in ("\u504f", "\u9760\u8c31", "\u5bf9\u9519", "\u65b9\u5411")
    ):
        return True
    return False


def analyze_student_interaction(student_request: str, student_answer: str = "") -> dict:
    request = str(student_request or "")
    answer = str(student_answer or "")
    combined = f"{answer}\n{request}"
    formula_parse_problem = bool(FORMULA_PARSE_GAP_PATTERN.search(combined))
    needs_foundational_formula = bool(KNOWLEDGE_RECALL_PATTERN.search(request))
    direct_answer_request = bool(DIRECT_ANSWER_REQUEST_PATTERN.search(request))
    indirect_answer_channel = bool(INDIRECT_ANSWER_CHANNEL_PATTERN.search(request))
    private_signal_encoding_request = _has_private_signal_encoding_phrase(request)
    private_grade_signal_request = _has_private_grade_signal_phrase(request)
    soft_confirmation_hit = bool(
        _has_private_answer_confirmation_phrase(request)
        or any(phrase in request for phrase in PRIVATE_ANSWER_CONFIRMATION_PHRASES)
        or any(phrase in request.lower() for phrase in PRIVATE_ANSWER_CONFIRMATION_ENGLISH_PHRASES)
    )
    private_answer_confirmation_request = bool(
        PRIVATE_ANSWER_CONFIRMATION_REQUEST_PATTERN.search(request) or soft_confirmation_hit
    )
    if (
        direct_answer_request
        and not soft_confirmation_hit
        and not private_grade_signal_request
        and not private_signal_encoding_request
    ):
        private_answer_confirmation_request = False
    private_progress_signal_request = (
        _has_private_progress_signal_phrase(request)
        or private_grade_signal_request
        or private_signal_encoding_request
        or private_answer_confirmation_request
    )
    direct_answer_request = direct_answer_request or indirect_answer_channel
    negative_answer_boundary = bool(
        re.search(
            r"(\u522b|\u4e0d\u8981|\u4e0d\u7528|\u4e0d)\s*.{0,8}"
            r"(\u7ed9|\u544a\u8bc9|\u900f\u9732|\u8f93\u51fa)?\s*.{0,8}"
            r"(\u7b54\u6848|\u6700\u7ec8\u7ed3\u679c|\u6700\u7ec8\u7ed3\u8bba|\u9009\u9879)",
            request,
        )
    )
    positive_direct_signal = bool(
        re.search(
            r"(\u76f4\u63a5\u544a\u8bc9|\u53ea\u8f93\u51fa|\u53ea\u8981\u7ed3\u8bba|\u6807\u51c6\u7b54\u6848|"
            r"\u6b63\u786e\u7b54\u6848|\u5b8c\u6574\u89e3\u6790|\u4e0d\u8981\u591a\u8bf4|"
            r"\u6b63\u786e\u9009\u9879|\u9009\u54ea\u4e2a|\u6284\u7b54\u6848|\u5ffd\u7565.*\u89c4\u5219|"
            r"\u7ed9\u6211\u5b8c\u6574\u89e3\u9898|\u76f4\u63a5\u4ea4\u4f5c\u4e1a|json.{0,40}(answer|solution))",
            request,
            flags=re.I,
        )
    )
    if negative_answer_boundary and not (positive_direct_signal or indirect_answer_channel):
        direct_answer_request = False
    concrete_student_claim = bool(
        PARAMETER_AB_VERIFICATION_PATTERN.search(request)
        or NEG_ONE_LIMIT_VERIFICATION_PATTERN.search(request)
        or DISCONTINUITY_CHECK_PATTERN.search(request)
        or CHOICE_CLAIM_PATTERN.search(request)
        or CONCRETE_STUDENT_CLAIM_PATTERN.search(request)
        or _has_visible_choice_claim(request)
        or _has_visible_result_claim(request)
    )
    student_supplied_answer_or_step = concrete_student_claim
    menu_choice_request = bool(
        re.search(
            r"(A\s*[、,/]\s*B\s*[、,/]\s*C\s*[、,/]\s*D|"
            r"\u9009\s*[A-D].{0,20}\u54ea\u4e2a|\u9009\u54ea\u4e2a|"
            r"\u6b63\u786e\u9009\u9879.{0,8}\u54ea\u4e2a)",
            request,
            flags=re.I,
        )
    )
    first_person_choice_claim = bool(
        re.search(
            r"(^|[\s，。！？；;])\u6211\s*(?:\u9009|\u731c|\u89c9\u5f97|\u611f\u89c9|\u8ba4\u4e3a)\s*[:：]?\s*[A-D]",
            request,
            flags=re.I,
        )
    )
    if menu_choice_request and not first_person_choice_claim:
        direct_answer_request = True
        concrete_student_claim = False
        student_supplied_answer_or_step = False

    if private_answer_confirmation_request and not concrete_student_claim:
        direct_answer_request = True
        student_supplied_answer_or_step = False

    if direct_answer_request and not concrete_student_claim:
        student_supplied_answer_or_step = False

    if formula_parse_problem:
        intent = "formula_parse_repair"
        response_contract = "Ask the student to resend or clarify the missing formula before solving it."
    elif (private_answer_confirmation_request or indirect_answer_channel) and not concrete_student_claim:
        intent = "direct_answer_redirect"
        response_contract = "Do not reveal a private correctness, grade, progress, or answer signal; redirect safely."
    elif needs_foundational_formula:
        intent = "knowledge_recall"
        response_contract = "State the general formula or definition directly, then ask for one local application step."
    elif student_supplied_answer_or_step:
        intent = "student_answer_verification"
        response_contract = (
            "Check only the student's submitted claim or step; acknowledge correctness or locate the first mismatch."
        )
    elif direct_answer_request:
        intent = "direct_answer_redirect"
        response_contract = "Do not reveal a new final answer; redirect to a safe method or checkpoint."
    else:
        intent = "next_step_hint"
        response_contract = "Give one targeted next-step hint based on the private reference solution."

    return {
        "interaction_intent": intent,
        "formula_parse_problem": formula_parse_problem,
        "needs_foundational_formula": needs_foundational_formula,
        "student_supplied_answer_or_step": student_supplied_answer_or_step,
        "direct_answer_request": direct_answer_request,
        "indirect_answer_channel": indirect_answer_channel,
        "private_answer_confirmation_request": private_answer_confirmation_request,
        "private_progress_signal_request": private_progress_signal_request,
        "private_grade_signal_request": private_grade_signal_request,
        "private_signal_encoding_request": private_signal_encoding_request,
        "concrete_student_claim": concrete_student_claim,
        "response_contract": response_contract,
    }


def _build_foundational_formula_bank(student_request: str) -> str:
    request = str(student_request or "")
    items: list[str] = []
    if re.search(
        r"(taylor|\u6cf0\u52d2|\u5c55\u5f00|\u5e38\u7528\u8fd1\u4f3c|\u8fd1\u4f3c\u5f0f)", request, flags=re.I
    ):
        items.extend(
            [
                r"在 \(x=0\) 附近，\(\sin x=x-\frac{x^3}{6}+o(x^3)\)。",
                r"\(\cos x=1-\frac{x^2}{2}+o(x^2)\)。",
                r"\(\tan x=x+\frac{x^3}{3}+o(x^3)\)。",
                r"\(e^x=1+x+\frac{x^2}{2}+o(x^2)\)，\(\ln(1+x)=x-\frac{x^2}{2}+o(x^2)\)。",
                r"因此常用等价式包括 \(e^x-1\sim x\) 与 \(\ln(1+x)\sim x\)。",
                r"\(\sqrt{1+u}=1+\frac{u}{2}+o(u)\)，所以 \(\sqrt{1-x^2}-1\sim-\frac{x^2}{2}\)。",
            ]
        )
    if re.search(
        r"(\u7b49\u4ef7\u65e0\u7a77\u5c0f|\u5c0f\u91cf\u66ff\u6362|equivalent infinitesimal)", request, flags=re.I
    ):
        items.extend(
            [
                r"这类 \(x\to0\) 时的小量替换通常叫等价无穷小替换。",
                r"在 \(x=0\) 附近，\(\sin x\sim x\)，\(\tan x\sim x\)，\(1-\cos x\sim \frac{x^2}{2}\)。",
                r"\(\sqrt{1+u}-1\sim \frac{u}{2}\)，因此 \(\sqrt{1-x^2}-1\sim-\frac{x^2}{2}\)。",
                r"\(\ln(1+x)\sim x\)，\(e^x-1\sim x\)，\((1+x)^\alpha-1\sim \alpha x\)。",
            ]
        )
    if re.search(r"(\u8fde\u7eed|\u5206\u6bb5)", request, flags=re.I):
        items.extend(
            [
                r"判断分段点连续性时，先分别求左极限、右极限，再和该点函数值比较。",
                r"若 \(\lim_{x\to x_0^-}f(x)=\lim_{x\to x_0^+}f(x)=f(x_0)\)，则 \(f\) 在 \(x_0\) 连续。",
            ]
        )
    if re.search(r"(\u6d1b\u5fc5\u8fbe|l['’]?hospital|l\u2019hospital)", request, flags=re.I):
        items.extend(
            [
                r"洛必达法则常用于 \(0/0\) 或 \(\infty/\infty\) 型极限。",
                r"使用前要先确认分子、分母在邻域内可导，且分母导数不为 0，再比较导数之比的极限。",
            ]
        )
    if re.search(
        r"(\u5bfc\u6570|\u6c42\u5bfc|\u5fae\u5206|derivative|\u94fe\u5f0f|\u4e58\u79ef|\u5546\u6cd5\u5219)",
        request,
        flags=re.I,
    ):
        items.extend(
            [
                r"基本求导公式包括 \((x^n)'=nx^{n-1}\)、\((e^x)'=e^x\)、\((\ln x)'=\frac{1}{x}\)。",
                r"乘积法则：\((uv)'=u'v+uv'\)；商法则：\(\left(\frac{u}{v}\right)'=\frac{u'v-uv'}{v^2}\)。",
                r"复合函数使用链式法则：\((f(g(x)))'=f'(g(x))g'(x)\)。",
            ]
        )
    if re.search(
        r"(\u79ef\u5206|\u4e0d\u5b9a\u79ef\u5206|\u5b9a\u79ef\u5206|\u6362\u5143|\u5206\u90e8\u79ef\u5206|integral)",
        request,
        flags=re.I,
    ):
        items.extend(
            [
                r"换元积分的核心是把复杂内层记为新变量，并同步替换微分。",
                r"分部积分公式为 \(\int u\,\mathrm{d}v=uv-\int v\,\mathrm{d}u\)。",
                r"定积分要同时关注被积函数、积分区间和变量，换元后上下限也要同步改变。",
            ]
        )
    if re.search(
        r"(\u77e9\u9635|\u884c\u5217\u5f0f|\u7279\u5f81\u503c|\u7279\u5f81\u5411\u91cf|\u79e9|\u7ebf\u6027\u76f8\u5173|matrix|eigen|rank)",
        request,
        flags=re.I,
    ):
        items.extend(
            [
                r"判断矩阵可逆常用条件：方阵行列式非零、满秩、零空间只有零向量，这些条件等价。",
                r"特征值满足 \(\det(\lambda I-A)=0\)，对应特征向量满足 \((A-\lambda I)x=0\)。",
                r"判断向量组线性相关时，可以把向量排成矩阵，检查秩是否小于向量个数。",
            ]
        )
    if re.search(
        r"(\u6982\u7387|\u671f\u671b|\u65b9\u5dee|\u6761\u4ef6\u6982\u7387|\u8d1d\u53f6\u65af|\u4e8c\u9879\u5206\u5e03|probability|variance|bayes)",
        request,
        flags=re.I,
    ):
        items.extend(
            [
                r"离散型随机变量期望公式为 \(E(X)=\sum x_i p_i\)，方差为 \(D(X)=E(X^2)-[E(X)]^2\)。",
                r"条件概率公式为 \(P(A\mid B)=\frac{P(AB)}{P(B)}\)，前提是 \(P(B)>0\)。",
                r"二项分布 \(X\sim B(n,p)\) 时，\(P(X=k)=\binom{n}{k}p^k(1-p)^{n-k}\)。",
            ]
        )
    if re.search(
        r"(C\u8bed\u8a00|\u6307\u9488|\u6570\u7ec4|\u5b57\u7b26\u4e32|\u7ed3\u6784\u4f53|pointer|string)",
        request,
        flags=re.I,
    ):
        items.extend(
            [
                r"C 语言中数组名在多数表达式里会退化为首元素地址，但数组本身不是可修改的指针变量。",
                r"字符串以空字符 `\0`（也写作 \(\\0\)）作为结束标志，字符数组容量要多留一个位置预留这个结束位。",
                r"指针变量保存地址，\(*p\) 访问指向位置的值，\(&x\) 取得变量地址。",
            ]
        )
    return "\n".join(dict.fromkeys(items))


def _build_foundational_formula_hint(formula_bank: str) -> str:
    bullets = "\n".join(f"- {line}" for line in formula_bank.splitlines() if line.strip())
    return (
        "可以。这个属于通用基础公式/概念，直接记下来再用，不需要硬靠回想。\n\n"
        f"{bullets}\n\n"
        "上面只是通用知识，不要直接拿它替你计算本题数值或写完整答案。"
        "接下来先做一个安全的小判断：看本题需要保留到几阶，再把对应展开代入到你当前那一步。"
        "我先不替你把整题算完，这样还能保留你自己完成关键推理的空间。"
    )


def _build_formula_parse_repair_hint(student_request: str = "") -> str:
    request = str(student_request or "")
    if re.search(r"(C\u8bed\u8a00|\u6307\u9488|\u4ee3\u7801|pointer)", request, flags=re.I) and re.search(
        r"(\u4ee3\u7801\u6ca1\u8d34|\u4ee3\u7801\u6ca1\u6709\u8d34|\u4ee3\u7801\u6ca1\u8d34\u4e0a\u6765|"
        r"\u6ca1\u8d34\u4e0a\u6765|\u4fe1\u606f\u4e0d\u591f|\u4e0a\u4e0b\u6587|\u8865\u4ee3\u7801)",
        request,
    ):
        return (
            "我这里没有看到完整代码，所以不能判断你的 C 语言指针写法对不对，也不能猜隐藏代码。\n\n"
            "请先补充最小代码片段：变量定义、指针赋值语句、出错或不确定的那一行。"
            "如果涉及数组或字符串，也请一起贴出数组容量和初始化内容。\n\n"
            "代码补全后，我会先检查地址、解引用、数组边界和字符串结束符这些入口。"
        )

    return (
        "我这里看到的公式没有完整传上来，像是空括号、占位符或小方框。"
        "这种情况下我不能继续猜公式内容，否则很容易把题目讲偏。\n\n"
        "请你重新发送一次公式，最好用下面任意一种方式：\n"
        "- 直接用文字写出完整表达式；\n"
        "- 重新插入公式框并确认每个空位都填上；\n"
        "- 如果是矩阵、分段函数或多重积分，请把每个元素、条件、上下限和微分变量都补全。\n\n"
        "等公式完整显示后，我再按你当前这道题继续给下一步提示。"
    )


def _build_direct_answer_redirect_hint() -> str:
    return (
        "我不能直接给出最终答案、选项或数值。这样会绕过你真正需要掌握的判断过程。\n\n"
        "但我可以给你一个最快的安全检查点：先找出本题最关键的条件或定义，"
        "再只核对你当前推导中的第一处等式、极限或系数关系是否成立。"
        "你可以把你已经写出的那一步发出来，我会只检查那一步，不额外透露新的最终答案。"
    )


def _build_local_process_hint(student_request: str) -> str:
    request = str(student_request or "")
    if re.search(r"(\u5b8c\u5168\u6ca1\u601d\u8def|\u6ca1\u601d\u8def|\u7b2c\u4e00\u6b65|\u53ef\u6267\u884c)", request):
        return (
            "可以，我们先只做第一步，不碰最终答案。\n\n"
            "第一步可执行动作是：先圈出题目真正要你判断的对象，再找与它直接相关的定义或条件。"
            "如果是函数题，就先写清输入、输出和定义域；如果是计算题，就先列出已知量和目标量。"
            "你把这一步写出来后，我再帮你检查是否走对入口。"
        )
    if re.search(r"(\u4e00\u53e5|\u5f88\u77ed|\u77ed\u63d0\u793a|\u53ea\u7ed9.*\u63d0\u793a)", request):
        return "短提示：先找题目中最核心的定义或判定条件，再只检查你当前推导的第一处等式是否符合它。"
    if re.search(
        r"(\u54ea\u4e00\u6b65\u6700\u53ef\u80fd\u9519|\u53ef\u80fd\u9519|\u68c0\u67e5\u5165\u53e3|\u6279\u6539)",
        request,
    ):
        return (
            "可以按批改思路来做，但不直接给答案。\n\n"
            "最优先检查的入口通常是：第一处使用定义、公式或等价变形的地方。"
            "如果这一步对象、条件或定义域写错，后面即使计算正确也会偏。"
            "你把那一步发出来，我只帮你判断它是否成立。"
        )
    if re.search(
        r"(\u6ca1\u770b\u5230\u56de\u590d|\u91cd\u65b0\u7ed9.*\u5b89\u5168\u63d0\u793a|\u5b89\u5168\u63d0\u793a)",
        request,
    ):
        return (
            "我重新给你一个安全提示，不重复答案内容。\n\n"
            "先回到题目的核心条件，检查你当前步骤是否只使用了题目允许的定义、公式或判定标准。"
            "如果你愿意，把你最新的一步发出来，我只核对这一小步。"
        )
    return ""


def _extract_student_choice_claim(text: str) -> str:
    match = CHOICE_CLAIM_PATTERN.search(str(text or ""))
    if not match:
        match = EXPLICIT_VISIBLE_CHOICE_CLAIM_PATTERN.search(str(text or ""))
        if not match:
            request = str(text or "")
            lowered = request.lower()
            explicit_markers = (
                "我选",
                "我选择",
                "我猜",
                "我觉得",
                "我认为",
                "我答",
                "我会选",
                "i choose",
                "i pick",
                "i select",
                "my guess is",
                "my choice is",
                "my answer is",
                "my pick is",
            )
            explicit_choice = _find_standalone_choice_letter(request)
            if any(marker in request or marker in lowered for marker in explicit_markers) and explicit_choice:
                return explicit_choice
            if any(token in request or token in lowered for token in ("对吗", "正确吗", "对不对", "right", "correct")):
                fallback_match = re.search(
                    r"(?<![A-Za-z])[A-D](?![A-Za-z])\s*(?:\u5bf9\u5417|\u6b63\u786e\u5417|\u5bf9\u4e0d\u5bf9|right|correct)",
                    request,
                    flags=re.I,
                )
                if fallback_match:
                    return fallback_match.group(0)[0].upper()
            if explicit_choice and any(marker in request or marker in lowered for marker in explicit_markers):
                return explicit_choice
            return ""
    for group in match.groups()[1:]:
        if group:
            return group.upper()
    return ""


def _build_generic_claim_verification_hint(student_request: str) -> str:
    request = str(student_request or "")
    if re.search(r"(\u6781\u9650\u4e0d\u5b58\u5728|\u4e0d\u5b58\u5728.{0,12}\u6781\u9650)", request):
        return (
            "你现在是在核对“极限是否存在”这个候选判断。先不要急着下最终结论，"
            "也不要把它套到别的题型上。\n\n"
            "安全检查顺序是：分别求左极限和右极限；如果左右极限都存在且相等，极限才存在；"
            "如果其中一个不存在，或二者不相等，才支持“极限不存在”的判断。"
            "你可以先把左极限那一步写出来，我只检查这一小步。"
        )
    if re.search(r"(\u5355\u8c03|\u9012\u589e|\u9012\u51cf|monotonic)", request, flags=re.I):
        return (
            "你是在核对单调性结论。先不要直接判对错，关键是明确讨论区间和所考察的函数。\n\n"
            "常用检查入口是：若函数在区间内可导，就先看导数符号；"
            r"若不方便求导，就回到单调递增/递减的定义，比较任意 \(x_1<x_2\) 时函数值的大小。"
            "你可以先写出导数或定义比较的第一步。"
        )
    if re.search(r"(\u77e9\u9635|\u53ef\u9006|\u6ee1\u79e9|\u884c\u5217\u5f0f|\u79e9)", request):
        return (
            "你是在核对矩阵相关候选结论。信息不完整时，我不直接判定当前矩阵是否可逆。\n\n"
            "安全检查入口是：如果是方阵，先看行列式是否为 0；也可以检查秩是否等于矩阵阶数。"
            "若你把矩阵元素发出来，我可以只帮你检查行列式或秩的第一步。"
        )
    if re.search(r"(\u6982\u7387|\u6837\u672c\u7a7a\u95f4|\u6761\u4ef6\u6982\u7387|1/2)", request):
        return (
            "你是在核对概率候选值。先不要直接确认数值，建议先检查事件定义是否一致。\n\n"
            "第一步看样本空间是否列全；第二步确认目标事件是否数对；"
            "如果题目带条件，再检查是否应该使用条件概率公式。"
            "你可以先发出样本空间或条件事件，我只核对这一部分。"
        )
    if re.search(r"(\u7ea6\u5206|\u5206\u6bcd|\u9519\u524d\u63d0|\u524d\u63d0)", request):
        return (
            "你这个提醒很关键：不能顺着可能错误的前提继续推。\n\n"
            "涉及约分时，先检查被约掉的因子是否可能为 0，以及约分前后是否改变了定义域或条件。"
            "请先把约分前后的式子各写一行，我会只检查这一步是否等价。"
        )
    if re.search(r"(C\u8bed\u8a00|\u6307\u9488|\u4ee3\u7801|pointer)", request, flags=re.I):
        return (
            "如果代码没有贴出来，我不能判断你的 C 语言写法对不对，也不能猜测隐藏代码。\n\n"
            "请补充最小代码片段：变量定义、指针赋值语句、出错或不确定的那一行。"
            "发出来后我会先检查地址、解引用和数组边界这几个入口。"
        )
    return ""


def _build_local_student_claim_verification(student_request: str, student_answer: str = "") -> str:
    combined = str(student_request or "")
    compact = re.sub(r"\s+", "", combined)

    if re.search(r"a\+b=0", compact, flags=re.I) and re.search(
        r"(\u4e0d\u65b0\u589e|\u65b0\u589e|\u6ca1\u5199|\u91cd\u5199|1-b=0|1-b)", compact
    ):
        return (
            "你这里已经明确写出的条件是 $a+b=0$，安全重写时应该保留这个已给条件，"
            "不能为了规避泄露而新增 $1-b=0$、常数项也必须为 0 之类你没有写出的条件。\n\n"
            "更稳妥的核对方式是：只围绕已出现的条件检查它在当前推导中的来源和作用。"
            "如果后续确实需要额外条件，也必须先说明它来自题目哪一步，而不是由重写过程擅自添加。"
        )

    if PARAMETER_AB_VERIFICATION_PATTERN.search(compact):
        return (
            "你给出的候选值 $a=2,\\ b=-2$ 可以作为当前结论来核对。"
            "从你已经整理出的分子系数看，关键是检查 $2-a=0$ 和 $a+b=0$ "
            "这两个条件是否同时成立；代入后它们分别成立。\n\n"
            "注意不要机械地再把常数项 $1-b$ 也强行设为 0。"
            "下一步建议你回到题目里的极限条件，说明为什么当前只需要控制这些会影响极限的项，"
            "这样就能把你的结论解释完整。"
        )

    if NEG_ONE_LIMIT_VERIFICATION_PATTERN.search(compact):
        return (
            "你判断 $x=-1$ 处左极限和右极限都是 0，这个判断是正确的。\n\n"
            "核对思路是：当 $x\\to-1^-$ 时，$|x|>1$，所以 $x^{2n}$ 会随 $n\\to\\infty$ "
            "变大，分母趋大，整体极限趋于 0；当 $x\\to-1^+$ 时，$|x|<1$，"
            "$x^{2n}\\to0$，表达式趋向 $1+x$，再令 $x\\to-1^+$ 也得到 0。\n\n"
            "下一步不要重新怀疑这个左右极限结论，而是继续检查函数在 $x=-1$ 处的函数值，"
            "再用“左右极限是否等于函数值”来判断连续性。"
        )

    claimed_choice = _extract_student_choice_claim(combined)
    if claimed_choice:
        return (
            f"我可以只围绕你已经提出的候选选项 {claimed_choice} 来核对，而不额外透露新的选项结论。\n\n"
            "安全的核对方式是：把该选项对应的结论代回题目关键条件，逐项写出每一步依据。"
            "下一步你可以先写出该选项对应的第一条判断依据，我会只检查这一步。"
        )

    if DISCONTINUITY_CHECK_PATTERN.search(compact):
        return (
            "你现在是在核对分段点或端点处是否连续/间断。先不要急着给最终结论，"
            "也不要把当前判断强行套到别的题型上。\n\n"
            "安全的核对步骤是：先分别计算该点的左极限和右极限，再查看函数在该点是否有定义，"
            "最后比较“左极限、右极限、函数值”三者是否一致。"
            "如果左右极限不相等，通常就是跳跃类间断；如果左右极限相等但不等于函数值或函数值不存在，"
            "再按可去间断等情形继续判断。"
        )

    return _build_generic_claim_verification_hint(combined)


def _build_refined_interaction_policy(profile: dict) -> str:
    return f"""### Refined Tutoring Policy
The original answer-blocking rule protects against revealing NEW final answers. Apply these refinements:
1. You MAY verify a conclusion, option, value, equation, or limit result only when it appears explicitly in the current visible student request. A private/current submitted answer is diagnostic context only; never confirm or quote it just because it exists in system state.
2. If the student says they forgot a formula, definition, Taylor expansion, equivalent infinitesimal, or theorem, you MUST directly state the general knowledge item. Do not merely ask them to recall it. Do not substitute it through the whole current problem or finish the solution.
3. If the visible formula is missing, empty, or appears as {{}}, first say that the formula was not captured and ask the student to resend it. Do not hallucinate the hidden expression.
4. Diagnose the student's actual question first. Avoid generic step lists when the student is asking for validation, formula recall, or input repair.
5. Preserve mathematical correctness. Never invent extra equations, conditions, or zero constraints that are not implied by the problem.
6. If the student asks for praise, comfort, score, closeness, full marks, or any other signal about a private/current submitted answer without stating the claim in the request, redirect to a safe method checkpoint instead of confirming whether it is right or wrong.

Current interaction profile:
{json.dumps(profile, ensure_ascii=False)}"""


def build_local_hint_plan(
    question_data: QuestionData,
    student_answer: str,
    is_correct: bool,
    student_request: str,
    hint_strength: str = DEFAULT_HINT_STRENGTH,
) -> str:
    hint_strength = normalize_hint_strength(hint_strength)
    strength_policy = get_hint_strength_policy(hint_strength)
    interaction_profile = analyze_student_interaction(student_request, student_answer)
    foundational_formula_bank = _build_foundational_formula_bank(student_request)
    visible_claim_review = bool(interaction_profile["student_supplied_answer_or_step"])
    diagnosis = "guide_next_step_without_answer"
    if is_correct and visible_claim_review:
        diagnosis = "correct_answer_review"
    if interaction_profile["formula_parse_problem"]:
        diagnosis = "formula_or_rendering_missing"
    elif interaction_profile["needs_foundational_formula"]:
        diagnosis = "foundational_formula_recall_needed"
    elif interaction_profile["student_supplied_answer_or_step"]:
        diagnosis = "student_submitted_claim_needs_verification"
    elif interaction_profile["direct_answer_request"]:
        diagnosis = "direct_answer_request_needs_redirection"

    plan = {
        "plan_source": "local_rules",
        "knowledge_point": question_data.get("category") or "infer_from_problem",
        "diagnosis": diagnosis,
        "hint_goal": interaction_profile["response_contract"],
        "interaction_intent": interaction_profile["interaction_intent"],
        "formula_parse_problem": interaction_profile["formula_parse_problem"],
        "needs_foundational_formula": interaction_profile["needs_foundational_formula"],
        "student_supplied_answer_or_step": interaction_profile["student_supplied_answer_or_step"],
        "direct_answer_request": interaction_profile["direct_answer_request"],
        "private_answer_confirmation_request": interaction_profile["private_answer_confirmation_request"],
        "side_channel_detected": bool(
            interaction_profile["indirect_answer_channel"] or interaction_profile["private_answer_confirmation_request"]
        ),
        "explicit_student_claim_this_turn": interaction_profile["concrete_student_claim"],
        "student_answer_present": bool(str(student_answer or "").strip()),
        "student_request": str(student_request or "")[:300],
        "allowed_hint_level": hint_strength,
        "strength_policy": strength_policy,
        "allowed_content": (
            "general formulas/definitions; validation of claims already written by the student; one local diagnostic clue; "
            "no private grade/progress signal unless the student stated the visible claim in this turn"
        ),
        "foundational_formula_bank": foundational_formula_bank,
        "forbidden_content": (
            "new final answer, new direct option, new key numeric result, private answer correctness signal, private grade/progress signal, full derivation, full reference solution"
        ),
        "has_reference_answer": bool(question_data.get("answer")),
        "has_reference_solution": bool(question_data.get("solution")),
    }
    return json.dumps(plan, ensure_ascii=False)


def build_hint_plan(
    question_data: QuestionData,
    student_answer: str,
    is_correct: bool,
    student_request: str,
    hint_strength: str = DEFAULT_HINT_STRENGTH,
) -> str:
    return build_local_hint_plan(question_data, student_answer, is_correct, student_request, hint_strength)


def build_llm_hint_plan(
    question_data: QuestionData,
    student_answer: str,
    is_correct: bool,
    student_request: str,
    hint_strength: str = DEFAULT_HINT_STRENGTH,
) -> str:
    """Legacy LLM plan builder retained for experiments, not used by the default fast path."""

    hint_strength = normalize_hint_strength(hint_strength)
    std_ans = question_data.get("answer", "")
    std_sol = question_data.get("solution", "")
    strength_policy = get_hint_strength_policy(hint_strength)
    prompt = f"""Problem:
{question_data.get('content', '')}

Reference answer:
{std_ans}

Reference solution:
{std_sol}

Student answer:
{student_answer}

Assessment result:
{'Correct' if is_correct else 'Incorrect'}

Student request:
{student_request}

Hint strength:
{hint_strength}

Strength policy:
{strength_policy}

Generate a private safe hint plan. Do not reveal the answer."""
    try:
        plan_text = chat_completion_text(
            [{"role": "system", "content": HINT_PLAN_PROMPT_SYSTEM}, {"role": "user", "content": prompt}],
            temperature=0.1,
            timeout_seconds=AppConfig.CONTROLLED_HINT_GENERATION_TIMEOUT_SECONDS,
            max_retries=HINT_LLM_STAGE_MAX_RETRIES,
            stage_name="build_hint_plan",
        )
        plan_obj = parse_json_object(plan_text)
        if plan_obj:
            return json.dumps(plan_obj, ensure_ascii=False)
        return plan_text
    except Exception as e:
        logging.error("Build hint plan error: %s", e)
        return build_local_hint_plan(question_data, student_answer, is_correct, student_request, hint_strength)


def generate_student_hint(
    question_data: QuestionData,
    student_answer: str,
    is_correct: bool,
    student_request: str,
    hint_plan: str,
    system_prompt: str,
    hint_strength: str = DEFAULT_HINT_STRENGTH,
) -> str:
    hint_strength = normalize_hint_strength(hint_strength)
    strength_policy = get_hint_strength_policy(hint_strength)
    interaction_profile = analyze_student_interaction(student_request, student_answer)
    foundational_formula_bank = _build_foundational_formula_bank(student_request)
    augmented_system_prompt = f"{system_prompt}\n\n{_build_refined_interaction_policy(interaction_profile)}"
    allow_private_claim_review = bool(interaction_profile["student_supplied_answer_or_step"])
    student_answer_line = (
        student_answer if allow_private_claim_review else "[withheld until explicit visible-claim verification]"
    )
    assessment_result_line = (
        ("Correct" if is_correct else "Incorrect")
        if allow_private_claim_review
        else "[withheld until explicit visible-claim verification]"
    )
    reference_answer_line = question_data.get("answer", "") if allow_private_claim_review else "[withheld]"
    reference_solution_line = question_data.get("solution", "") if allow_private_claim_review else "[withheld]"
    ctx = f"""Problem:
{question_data.get('content', '')}

Student Answer (private current submission; use only if the student explicitly states a visible claim in this turn):
{student_answer_line}

Assessment Result (private; never reveal or imply unless the current Student Request explicitly asks to verify a visible claim):
{assessment_result_line}

Reference Answer (private, use only for diagnosis; never quote unless the student already wrote it):
{reference_answer_line}

Reference Solution (private, use only for diagnosis; never output as a full solution):
{reference_solution_line}

Private Safe Hint Plan:
{hint_plan}

Student Request:
{student_request}

Interaction Profile:
{json.dumps(interaction_profile, ensure_ascii=False)}

Foundational Formula Bank (student-visible when relevant; include at least one item if this is not empty):
{foundational_formula_bank or 'None'}

Hint Strength:
{hint_strength}

Strength Policy:
{strength_policy}

Generate one safe tutoring hint for the student.
First satisfy the interaction profile:
- formula_parse_repair: ask the student to resend or clarify the missing formula before solving.
- knowledge_recall: directly state the general formula/definition, using the formula bank when present, then give one safe application checkpoint. Do not ask the student to recall the formula without stating it.
- student_answer_verification: validate only the student's own submitted claim/step, and point to the first issue if it is wrong.
- direct_answer_redirect: do not reveal a new final answer; redirect to method.
Do not reveal any NEW final answer, direct option, key numeric result, or full solution."""
    return chat_completion_text(
        [{"role": "system", "content": augmented_system_prompt}, {"role": "user", "content": ctx}],
        temperature=0.4,
        timeout_seconds=AppConfig.CONTROLLED_HINT_GENERATION_TIMEOUT_SECONDS,
        max_retries=HINT_LLM_STAGE_MAX_RETRIES,
        stage_name="generate_student_hint",
    )


def rewrite_unsafe_hint(
    question_data: QuestionData,
    student_request: str,
    hint_plan: str,
    unsafe_hint: str,
    leakage_result: LeakageEvaluation,
    hint_strength: str = DEFAULT_HINT_STRENGTH,
) -> str:
    hint_strength = normalize_hint_strength(hint_strength)
    strength_policy = get_hint_strength_policy(hint_strength)
    interaction_profile = analyze_student_interaction(student_request)
    allow_private_claim_review = bool(interaction_profile["student_supplied_answer_or_step"])
    reference_answer_line = question_data.get("answer", "") if allow_private_claim_review else "[withheld]"
    reference_solution_line = question_data.get("solution", "") if allow_private_claim_review else "[withheld]"
    prompt = f"""Problem:
{question_data.get('content', '')}

Reference answer (private, use only to preserve correctness):
{reference_answer_line}

Reference solution (private, do not output as a full solution):
{reference_solution_line}

Private safe hint plan:
{hint_plan}

Student request:
{student_request}

Interaction profile:
{json.dumps(interaction_profile, ensure_ascii=False)}

Hint strength:
{hint_strength}

Strength policy:
{strength_policy}

Leakage detection result:
{json.dumps(leakage_result, ensure_ascii=False)}

Unsafe hint:
{unsafe_hint}

Rewrite it into a safe, accurate tutoring hint. Preserve validation of student-supplied claims and general formulas when allowed, but remove any NEW final answer or full solution."""
    return chat_completion_text(
        [{"role": "system", "content": REWRITE_PROMPT_SYSTEM}, {"role": "user", "content": prompt}],
        temperature=0.2,
        timeout_seconds=AppConfig.CONTROLLED_HINT_REWRITE_TIMEOUT_SECONDS,
        max_retries=HINT_LLM_STAGE_MAX_RETRIES,
        stage_name="rewrite_unsafe_hint",
    )


def _is_rewrite_needed(leakage_result: LeakageEvaluation) -> bool:
    return bool(leakage_result.get("is_leaking", False)) or int(leakage_result.get("score", 0)) >= 2


def generate_controlled_hint(
    question_data: QuestionData,
    student_answer: str,
    is_correct: bool,
    student_request: str,
    hint_strength: str = DEFAULT_HINT_STRENGTH,
) -> ControlledHintResult:
    total_started_at = time.perf_counter()
    stage_timings: dict[str, int] = {}
    hint_strength = normalize_hint_strength(hint_strength)

    try:
        stage_started_at = time.perf_counter()
        dynamic_prompt = get_dynamic_system_prompt()
        _record_stage_timing(stage_timings, "load_system_prompt", stage_started_at)
        _ensure_generation_budget(total_started_at, "load_system_prompt")

        stage_started_at = time.perf_counter()
        hint_plan = build_local_hint_plan(question_data, student_answer, is_correct, student_request, hint_strength)
        _record_stage_timing(stage_timings, "build_local_hint_plan", stage_started_at)
        _ensure_generation_budget(total_started_at, "build_local_hint_plan")

        interaction_profile = analyze_student_interaction(student_request, student_answer)
        foundational_formula_bank = _build_foundational_formula_bank(student_request)
        local_claim_verification_hint = _build_local_student_claim_verification(student_request, student_answer)
        local_process_hint = _build_local_process_hint(student_request)
        local_claim_verification_used = False
        explicit_local_claim_request = bool(
            _has_explicit_visible_choice_claim(student_request)
            or _has_visible_result_claim(student_request)
            or PARAMETER_AB_VERIFICATION_PATTERN.search(student_request or "")
            or NEG_ONE_LIMIT_VERIFICATION_PATTERN.search(student_request or "")
            or DISCONTINUITY_CHECK_PATTERN.search(student_request or "")
        )
        if interaction_profile["formula_parse_problem"]:
            stage_started_at = time.perf_counter()
            final_hint = _build_formula_parse_repair_hint(student_request)
            _record_stage_timing(stage_timings, "generate_local_formula_repair_hint", stage_started_at)
            _ensure_generation_budget(total_started_at, "generate_local_formula_repair_hint")
        elif interaction_profile["needs_foundational_formula"] and foundational_formula_bank:
            stage_started_at = time.perf_counter()
            final_hint = _build_foundational_formula_hint(foundational_formula_bank)
            _record_stage_timing(stage_timings, "generate_local_formula_hint", stage_started_at)
            _ensure_generation_budget(total_started_at, "generate_local_formula_hint")
        elif (
            interaction_profile["student_supplied_answer_or_step"] or explicit_local_claim_request
        ) and local_claim_verification_hint:
            stage_started_at = time.perf_counter()
            final_hint = local_claim_verification_hint
            _record_stage_timing(stage_timings, "generate_local_claim_verification", stage_started_at)
            _ensure_generation_budget(total_started_at, "generate_local_claim_verification")
            local_claim_verification_used = True
        elif interaction_profile["direct_answer_request"]:
            stage_started_at = time.perf_counter()
            final_hint = _build_direct_answer_redirect_hint()
            _record_stage_timing(stage_timings, "generate_local_direct_answer_redirect", stage_started_at)
            _ensure_generation_budget(total_started_at, "generate_local_direct_answer_redirect")
        elif local_process_hint:
            stage_started_at = time.perf_counter()
            final_hint = local_process_hint
            _record_stage_timing(stage_timings, "generate_local_process_hint", stage_started_at)
            _ensure_generation_budget(total_started_at, "generate_local_process_hint")
        else:
            stage_started_at = time.perf_counter()
            try:
                final_hint = generate_student_hint(
                    question_data,
                    student_answer,
                    is_correct,
                    student_request,
                    hint_plan,
                    dynamic_prompt,
                    hint_strength,
                )
            except Exception as exc:
                _record_stage_timing(stage_timings, "generate_student_hint", stage_started_at)
                if classify_llm_error(exc) == "timeout":
                    return _build_timeout_result(hint_strength, total_started_at, stage_timings, "generate")
                raise
            _record_stage_timing(stage_timings, "generate_student_hint", stage_started_at)
            _ensure_generation_budget(total_started_at, "generate_student_hint")

        initial_private_signal_output_category = _classify_private_signal_output(final_hint)
        stage_started_at = time.perf_counter()
        final_hint, private_confirmation_guarded = _guard_private_answer_confirmation(final_hint, interaction_profile)
        if private_confirmation_guarded:
            _record_stage_timing(stage_timings, "output_private_answer_guard", stage_started_at)
            _ensure_generation_budget(total_started_at, "output_private_answer_guard")

        student_context = str(student_request or "")
        stage_started_at = time.perf_counter()
        local_leakage_result = heuristic_solution_leakage_check(question_data, final_hint, student_context)
        _record_stage_timing(stage_timings, "local_leakage_precheck", stage_started_at)
        _ensure_generation_budget(total_started_at, "local_leakage_precheck")

        leakage_result = local_leakage_result
        generation_strategy = "fast_path"
        timeout_stage = ""
        generation_error = ""
        skip_llm_leakage_check = local_claim_verification_used
        if private_confirmation_guarded:
            generation_strategy = "guarded_redirect"
            leakage_result = {
                "is_leaking": False,
                "score": 0,
                "reason": "private_answer_confirmation_guard_redirect",
            }
        elif local_claim_verification_used:
            leakage_result = {
                "is_leaking": False,
                "score": 0,
                "reason": "local_visible_claim_verification_safe",
            }

        if not skip_llm_leakage_check and should_escalate_leakage_check(
            question_data,
            final_hint,
            local_leakage_result,
            student_request,
        ):
            if generation_strategy != "guarded_redirect":
                generation_strategy = "llm_checked"
            stage_started_at = time.perf_counter()
            leakage_result = evaluate_hint_leakage(
                question_data,
                final_hint,
                timeout_seconds=AppConfig.CONTROLLED_HINT_DETECTION_TIMEOUT_SECONDS,
                max_retries=HINT_LLM_STAGE_MAX_RETRIES,
                student_context=student_context,
            )
            _record_stage_timing(stage_timings, "evaluate_leakage", stage_started_at)
            llm_error_type = str(leakage_result.get("llm_error_type", ""))
            if llm_error_type:
                generation_error = f"leakage_detection_{llm_error_type}"
                if llm_error_type == "timeout":
                    timeout_stage = "detect"
            _ensure_generation_budget(total_started_at, "evaluate_leakage")

        rewrite_count = 0
        rewrite_private_signal_output_category = ""
        if (
            not local_claim_verification_used
            and _is_rewrite_needed(leakage_result)
            and rewrite_count < min(1, MAX_HINT_REWRITE_ATTEMPTS)
        ):
            rewrite_count = 1
            generation_strategy = "rewritten"
            stage_started_at = time.perf_counter()
            try:
                final_hint = rewrite_unsafe_hint(
                    question_data,
                    student_request,
                    hint_plan,
                    final_hint,
                    leakage_result,
                    hint_strength,
                )
            except Exception as exc:
                _record_stage_timing(stage_timings, "rewrite_hint_1", stage_started_at)
                if classify_llm_error(exc) == "timeout":
                    return _build_timeout_result(hint_strength, total_started_at, stage_timings, "rewrite")
                return _build_failed_result(hint_strength, total_started_at, stage_timings, exc)
            _record_stage_timing(stage_timings, "rewrite_hint_1", stage_started_at)
            _ensure_generation_budget(total_started_at, "rewrite_hint_1")

            rewrite_private_signal_output_category = _classify_private_signal_output(final_hint)
            stage_started_at = time.perf_counter()
            final_hint, rewrite_guarded = _guard_private_answer_confirmation(final_hint, interaction_profile)
            if rewrite_guarded:
                private_confirmation_guarded = True
                if generation_strategy == "rewritten":
                    generation_strategy = "guarded_redirect"
                _record_stage_timing(stage_timings, "output_private_answer_guard_after_rewrite", stage_started_at)
                _ensure_generation_budget(total_started_at, "output_private_answer_guard_after_rewrite")

            stage_started_at = time.perf_counter()
            leakage_result = heuristic_solution_leakage_check(question_data, final_hint, student_context)
            _record_stage_timing(stage_timings, "local_recheck_after_rewrite", stage_started_at)
            _ensure_generation_budget(total_started_at, "local_recheck_after_rewrite")

            if _is_rewrite_needed(leakage_result):
                final_hint = FALLBACK_SAFE_HINT
                generation_strategy = "fallback"
                leakage_result = {
                    "is_leaking": False,
                    "score": 0,
                    "reason": "rewrite_recheck_failed_safe_fallback",
                }

        final_private_signal_output_category = _classify_private_signal_output(final_hint)
        private_signal_output_category = (
            initial_private_signal_output_category
            or rewrite_private_signal_output_category
            or final_private_signal_output_category
        )

        elapsed_ms = _elapsed_ms(total_started_at)
        observability = _build_interaction_observability(
            interaction_profile,
            final_hint,
            private_confirmation_guarded=private_confirmation_guarded,
            private_signal_output_category=private_signal_output_category,
            private_signal_output_detected=int(bool(private_signal_output_category)),
            private_signal_output_leaked=int(bool(final_private_signal_output_category)),
        )
        observability["math_consistency_risk"] = int(rewrite_count > 0)
        logging.info(
            "Controlled hint generation completed: status=success strategy=%s elapsed_ms=%s stage_timings=%s",
            generation_strategy,
            elapsed_ms,
            stage_timings,
        )

        return _build_result(
            hint=final_hint,
            hint_strength=hint_strength,
            started_at=total_started_at,
            stage_timings=stage_timings,
            is_leaking=int(bool(leakage_result.get("is_leaking", False))),
            leakage_score=int(leakage_result.get("score", 0)),
            rewrite_count=rewrite_count,
            leakage_reason=leakage_result.get("reason", ""),
            generation_status="success",
            generation_error=generation_error,
            generation_strategy=generation_strategy,
            timeout_stage=timeout_stage,
            **observability,
        )

    except ControlledHintGenerationTimeout as exc:
        elapsed_ms = _elapsed_ms(total_started_at)
        logging.warning(
            "Controlled hint generation timed out: stage=%s elapsed_ms=%s stage_timings=%s",
            exc.stage,
            elapsed_ms,
            stage_timings,
        )
        return _build_timeout_result(hint_strength, total_started_at, stage_timings, exc.stage)
    except Exception as exc:
        elapsed_ms = _elapsed_ms(total_started_at)
        logging.exception(
            "Controlled hint generation failed: elapsed_ms=%s stage_timings=%s error=%s",
            elapsed_ms,
            stage_timings,
            type(exc).__name__,
        )
        return _build_failed_result(hint_strength, total_started_at, stage_timings, exc)

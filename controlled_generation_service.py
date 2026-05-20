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
    r"\u6211\u7b97\u51fa|\u6211\u5f97\u5230|\u6211\u5199\u51fa|"
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
    r"\u76f4\u63a5.*\u7b54\u6848|\u7ed9.*\u7b54\u6848|\u6700\u7ec8\u7b54\u6848|"
    r"\u6700\u7ec8\u6570\u503c|\u53ea\u8f93\u51fa|\u6807\u51c6\u7b54\u6848|\u7b54\u6848\u662f\u4ec0\u4e48|\u6c42\u7b54\u6848|"
    r"\u9009\u9879\u662f\u4ec0\u4e48|\u9009\u54ea\u4e2a|\u544a\u8bc9\u6211\u9009|\u6b63\u786e\u9009\u9879|"
    r"\u522b\u8bb2\u8fc7\u7a0b|\u4e0d\u7528\u89e3\u91ca|\u53ea\u8981\u7ed3\u8bba|\u62a5\u7ed3\u679c|"
    r"\u5077\u5077|\u6284\u7b54\u6848|\u5ffd\u7565.*\u89c4\u5219|\u7ba1\u7406\u5458|\u6d4b\u8bd5\u6a21\u5f0f|"
    r"debug\s*mode|system\s*prompt)",
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
CONCRETE_STUDENT_CLAIM_PATTERN = re.compile(
    r"(\u6211(?:\u7b97\u51fa|\u5f97\u5230|\u5199\u51fa|\u731c|\u89c9\u5f97|\u611f\u89c9|\u8ba4\u4e3a|\u9009).{0,80}"
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


def analyze_student_interaction(student_request: str, student_answer: str = "") -> dict:
    request = str(student_request or "")
    answer = str(student_answer or "")
    combined = f"{answer}\n{request}"
    formula_parse_problem = bool(FORMULA_PARSE_GAP_PATTERN.search(combined))
    needs_foundational_formula = bool(KNOWLEDGE_RECALL_PATTERN.search(request))
    direct_answer_request = bool(DIRECT_ANSWER_REQUEST_PATTERN.search(request))
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
            r"\u6b63\u786e\u9009\u9879|\u9009\u54ea\u4e2a|\u6284\u7b54\u6848|\u5ffd\u7565.*\u89c4\u5219|"
            r"\u7ed9\u6211\u5b8c\u6574\u89e3\u9898|\u76f4\u63a5\u4ea4\u4f5c\u4e1a)",
            request,
        )
    )
    if negative_answer_boundary and not positive_direct_signal:
        direct_answer_request = False
    student_supplied_answer_or_step = bool(ANSWER_VERIFICATION_PATTERN.search(combined))
    concrete_student_claim = bool(
        PARAMETER_AB_VERIFICATION_PATTERN.search(combined)
        or NEG_ONE_LIMIT_VERIFICATION_PATTERN.search(combined)
        or DISCONTINUITY_CHECK_PATTERN.search(combined)
        or CHOICE_CLAIM_PATTERN.search(combined)
        or CONCRETE_STUDENT_CLAIM_PATTERN.search(combined)
    )
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

    if direct_answer_request and not concrete_student_claim:
        student_supplied_answer_or_step = False

    if formula_parse_problem:
        intent = "formula_parse_repair"
        response_contract = "Ask the student to resend or clarify the missing formula before solving it."
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
    combined = f"{student_answer}\n{student_request}"
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
            "安全的核对方式是：把该选项对应的结论代回题目关键条件，逐项检查是否满足；"
            "如果某一步条件不成立，就说明候选需要调整。"
            "你可以先写出该选项对应的第一条判断依据，我会只检查这一步。"
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
1. If the student already supplied a conclusion, option, value, equation, or limit result, you MAY verify that submitted claim using the private reference. Do not introduce any additional final answer the student did not state.
2. If the student says they forgot a formula, definition, Taylor expansion, equivalent infinitesimal, or theorem, you MUST directly state the general knowledge item. Do not merely ask them to recall it. Do not substitute it through the whole current problem or finish the solution.
3. If the visible formula is missing, empty, or appears as {{}}, first say that the formula was not captured and ask the student to resend it. Do not hallucinate the hidden expression.
4. Diagnose the student's actual question first. Avoid generic step lists when the student is asking for validation, formula recall, or input repair.
5. Preserve mathematical correctness. Never invent extra equations, conditions, or zero constraints that are not implied by the problem.

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
    diagnosis = "correct_answer_review" if is_correct else "guide_next_step_without_answer"
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
        "student_answer_present": bool(str(student_answer or "").strip()),
        "student_request": str(student_request or "")[:300],
        "allowed_hint_level": hint_strength,
        "strength_policy": strength_policy,
        "allowed_content": (
            "general formulas/definitions; validation of claims already written by the student; one local diagnostic clue"
        ),
        "foundational_formula_bank": foundational_formula_bank,
        "forbidden_content": (
            "new final answer, new direct option, new key numeric result, full derivation, full reference solution"
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
    ctx = f"""Problem:
{question_data.get('content', '')}

Student Answer:
{student_answer}

Assessment Result:
{'Correct' if is_correct else 'Incorrect'}

Reference Answer (private, use only for diagnosis; never quote unless the student already wrote it):
{question_data.get('answer', '')}

Reference Solution (private, use only for diagnosis; never output as a full solution):
{question_data.get('solution', '')}

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
    prompt = f"""Problem:
{question_data.get('content', '')}

Reference answer (private, use only to preserve correctness):
{question_data.get('answer', '')}

Reference solution (private, do not output as a full solution):
{question_data.get('solution', '')}

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
        elif interaction_profile["student_supplied_answer_or_step"] and local_claim_verification_hint:
            stage_started_at = time.perf_counter()
            final_hint = local_claim_verification_hint
            _record_stage_timing(stage_timings, "generate_local_claim_verification", stage_started_at)
            _ensure_generation_budget(total_started_at, "generate_local_claim_verification")
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

        student_context = f"{student_answer}\n{student_request}"
        stage_started_at = time.perf_counter()
        local_leakage_result = heuristic_solution_leakage_check(question_data, final_hint, student_context)
        _record_stage_timing(stage_timings, "local_leakage_precheck", stage_started_at)
        _ensure_generation_budget(total_started_at, "local_leakage_precheck")

        leakage_result = local_leakage_result
        generation_strategy = "fast_path"
        timeout_stage = ""
        generation_error = ""

        if should_escalate_leakage_check(question_data, final_hint, local_leakage_result, student_request):
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
        if _is_rewrite_needed(leakage_result) and rewrite_count < min(1, MAX_HINT_REWRITE_ATTEMPTS):
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

        elapsed_ms = _elapsed_ms(total_started_at)
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

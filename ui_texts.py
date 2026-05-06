"""User-facing texts for tutoring controls and learning workflow."""

TUTORING_TITLE = "请求智能辅导"
LEGACY_TUTORING_TITLE = "智能辅导"
TUTORING_SUBTITLE = "系统会先生成启发式提示，再进行答案泄露检测与必要重写。"
TUTORING_COMPOSER_GUIDE = "👇🏻请在下方输入智能辅导提示词"
TUTORING_EMPTY_WARNING = "请输入辅导问题后再发送。"
TUTORING_FALLBACK_HINT = (
    "这道题我们先不急着看答案。你可以先指出题目中最关键的条件是什么，再想一想它对应哪个定义或公式？"
)
TUTORING_SPINNER = "正在生成智能辅导并进行答案泄露检测....."
DEFAULT_PEDAGOGICAL_INTENT = "自主提问"

EMPTY_COURSE_QUESTION_WARNING = "题库内目前无该课程对应题目。"
STUDENT_LOGIN_TRANSITION_MESSAGE = "正在验证账号并加载学习数据..."
ADMIN_LOGIN_TRANSITION_MESSAGE = "正在验证管理员账号并加载教务管理控制台..."
COURSE_TRANSITION_MESSAGE = "正在加载题目并初始化测验..."
REPORT_TRANSITION_MESSAGE = "正在生成个人学情报告..."
ADMIN_DASHBOARD_TRANSITION_MESSAGE = "正在汇总管理端统计看板..."
HOME_TRANSITION_MESSAGE = "正在返回课程学习大厅..."

PEDAGOGICAL_QUICK_REQUESTS = [
    {
        "label": "提示下一步",
        "intent": "下一步引导",
        "prompt": "请只提示我下一步应该怎么思考，不要给出答案。",
    },
    {
        "label": "检查错误",
        "intent": "错因诊断",
        "prompt": "请帮我指出当前作答最可能错在哪里，但不要直接给最终答案。",
    },
    {
        "label": "只给思路",
        "intent": "概念提示",
        "prompt": "请只给解题思路和关键概念提醒，避免泄露答案。",
    },
    {
        "label": "复习知识点",
        "intent": "知识点复习",
        "prompt": "请总结这道题涉及的知识点，并给我一个复习方向。",
    },
]

HINT_STRENGTH_OPTIONS = {
    "轻提示": "只给方向和概念提醒",
    "中提示": "提示下一步思考路径",
    "强提示": "给出更具体的分步引导",
}

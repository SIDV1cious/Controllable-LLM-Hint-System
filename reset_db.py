import json
import os
import re
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")

connection_url = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
engine = create_engine(connection_url)


def fix_math(text_str):
    if not text_str: return text_str
    if '$' in text_str: return text_str
    if any(c in text_str for c in ['\\', '^', '_']):
        m = re.match(r'^([A-D]\.)\s*(.*)$', text_str.strip())
        if m:
            return f"{m.group(1)} ${m.group(2)}$"
        else:
            return f"${text_str}$"
    return text_str


with engine.connect() as conn:
    print("⏳ 正在彻底清空旧题库...")
    conn.execute(text("TRUNCATE TABLE custom_questions;"))
    conn.commit()

    try:
        conn.execute(text("ALTER TABLE custom_questions ADD COLUMN answer VARCHAR(255);"))
        conn.commit()
    except:
        pass

    try:
        conn.execute(text("ALTER TABLE custom_questions ADD COLUMN solution TEXT;"))
        conn.commit()
    except:
        pass

    print("⏳ 正在自动修复 LaTeX 格式并导入 47 道题...")
    with open('选择题_with_solutions.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    for item in data:
        q_text = fix_math(item.get("question", ""))

        fixed_choices = []
        for c in item.get("choices", []):
            fixed_choices.append(fix_math(c))

        choices_str = "\n".join(fixed_choices)
        full_content = f"{q_text}\n\n{choices_str}"

        ans_text = item.get("answer", "")
        sol_text = fix_math(item.get("solution", ""))

        conn.execute(
            text("INSERT INTO custom_questions (category, content, answer, solution) VALUES (:c, :t, :a, :s)"),
            {"c": "高等数学", "t": full_content, "a": ans_text, "s": sol_text}
        )
    conn.commit()
    print("✅ 成功！所有题目的公式格式已修复！")
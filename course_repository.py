from __future__ import annotations

import streamlit as st
from sqlalchemy import text

from app_errors import log_exception
from database_service import get_database_engine

BASE_COURSES: list[tuple[str, str]] = [
    ("高等数学", "包含极限、导数、微积分等核心考点，重点测试逻辑推导能力。"),
    ("线性代数", "包含矩阵运算、特征值、二次型等，培养空间与代数转换思维。"),
    ("概率统计", "包含随机变量、分布规律、信息熵等，结合实际应用场景。"),
    ("C语言", "包含指针、数组、结构体等核心语法，锻炼底层逻辑与编程思维。"),
]


def merge_course_catalog(
    base_courses: list[tuple[str, str]],
    custom_courses: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    merged = list(base_courses)
    existing_names = {name for name, _ in merged}
    for course_name, description in custom_courses:
        if course_name not in existing_names:
            merged.append((course_name, description))
            existing_names.add(course_name)
    return merged


@st.cache_data(ttl=120, show_spinner=False)
def fetch_custom_course_catalog() -> list[tuple[str, str]]:
    try:
        engine = get_database_engine()
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT course_name, description FROM custom_courses")).fetchall()
        return [(row[0], row[1]) for row in rows]
    except Exception as exc:
        log_exception("Load custom course catalog error", exc)
        return []


@st.cache_data(ttl=120, show_spinner=False)
def list_course_catalog() -> list[tuple[str, str]]:
    return merge_course_catalog(BASE_COURSES, fetch_custom_course_catalog())

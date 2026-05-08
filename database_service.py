import logging

import streamlit as st
from sqlalchemy import Engine, bindparam, create_engine, text

from domain_models import QuestionData
from system_config import AppConfig

LEAKAGE_OBSERVABILITY_COLUMN_DDL = [
    "ALTER TABLE interaction_logs ADD COLUMN leakage_score INT DEFAULT 0",
    "ALTER TABLE interaction_logs ADD COLUMN rewrite_count INT DEFAULT 0",
    "ALTER TABLE interaction_logs ADD COLUMN leakage_reason VARCHAR(255)",
    "ALTER TABLE interaction_logs ADD COLUMN hint_strength VARCHAR(32)",
    "ALTER TABLE interaction_logs ADD COLUMN pedagogical_intent VARCHAR(64)",
    "ALTER TABLE interaction_logs ADD COLUMN hint_safety_status VARCHAR(64)",
    "ALTER TABLE interaction_logs ADD COLUMN request_char_count INT DEFAULT 0",
    "ALTER TABLE interaction_logs ADD COLUMN formula_fragment_count INT DEFAULT 0",
    "ALTER TABLE interaction_logs ADD COLUMN generation_elapsed_ms INT DEFAULT 0",
    "ALTER TABLE interaction_logs ADD COLUMN rewrite_triggered TINYINT DEFAULT 0",
]

LEAKAGE_OBSERVABILITY_INDEX_DDL = [
    "ALTER TABLE interaction_logs ADD INDEX idx_interaction_hint_strength (hint_strength)",
    "ALTER TABLE interaction_logs ADD INDEX idx_interaction_pedagogical_intent (pedagogical_intent)",
]


def iter_leakage_observability_ddl() -> tuple[str, ...]:
    return tuple(LEAKAGE_OBSERVABILITY_COLUMN_DDL + LEAKAGE_OBSERVABILITY_INDEX_DDL)


@st.cache_resource
def get_database_engine() -> Engine:
    connection_url = (
        f"mysql+pymysql://{AppConfig.DB_USER}:{AppConfig.DB_PASSWORD}@{AppConfig.DB_HOST}/{AppConfig.DB_NAME}"
    )
    return create_engine(connection_url, pool_recycle=1800, pool_pre_ping=True)


def question_row_to_dict(row) -> QuestionData:
    return {
        "id": 1000 + row[0],
        "category": row[1],
        "content": row[2],
        "answer": row[3] or "",
        "solution": row[4] or "",
    }


def fetch_custom_question_rows(conn, db_ids: list):
    if not db_ids:
        return []

    stmt = text("SELECT id, category, content, answer, solution FROM custom_questions WHERE id IN :ids").bindparams(
        bindparam("ids", expanding=True)
    )
    return conn.execute(stmt, {"ids": list(db_ids)}).fetchall()


@st.cache_resource
def ensure_leakage_observability_columns():
    engine = get_database_engine()
    for ddl in iter_leakage_observability_ddl():
        try:
            with engine.connect() as conn:
                conn.execute(text(ddl))
                conn.commit()
        except Exception as exc:
            logging.debug("Skip leakage observability DDL, likely already applied: %s; ddl=%s", exc, ddl)

    return True

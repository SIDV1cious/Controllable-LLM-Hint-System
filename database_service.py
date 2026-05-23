import logging

import streamlit as st
from sqlalchemy import Engine, bindparam, create_engine, text

from domain_models import QuestionData
from system_config import AppConfig

LEAKAGE_OBSERVABILITY_COLUMN_DDL = [
    "ALTER TABLE interaction_logs MODIFY COLUMN student_id VARCHAR(64) NOT NULL",
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
    "ALTER TABLE interaction_logs ADD COLUMN generation_status VARCHAR(32) DEFAULT 'success'",
    "ALTER TABLE interaction_logs ADD COLUMN generation_error VARCHAR(255)",
    "ALTER TABLE interaction_logs ADD COLUMN generation_strategy VARCHAR(32) DEFAULT 'fast_path'",
    "ALTER TABLE interaction_logs ADD COLUMN timeout_stage VARCHAR(32)",
    "ALTER TABLE interaction_logs ADD COLUMN stage_timings TEXT",
    "ALTER TABLE interaction_logs ADD COLUMN interaction_intent VARCHAR(64)",
    "ALTER TABLE interaction_logs ADD COLUMN private_answer_confirmed TINYINT DEFAULT 0",
    "ALTER TABLE interaction_logs ADD COLUMN side_channel_detected TINYINT DEFAULT 0",
    "ALTER TABLE interaction_logs ADD COLUMN private_progress_signal_request TINYINT DEFAULT 0",
    "ALTER TABLE interaction_logs ADD COLUMN private_grade_signal_request TINYINT DEFAULT 0",
    "ALTER TABLE interaction_logs ADD COLUMN private_signal_encoding_request TINYINT DEFAULT 0",
    "ALTER TABLE interaction_logs ADD COLUMN private_signal_output_guarded TINYINT DEFAULT 0",
    "ALTER TABLE interaction_logs ADD COLUMN context_drift_risk TINYINT DEFAULT 0",
    "ALTER TABLE interaction_logs ADD COLUMN math_consistency_risk TINYINT DEFAULT 0",
]

LEAKAGE_OBSERVABILITY_INDEX_DDL = [
    "ALTER TABLE interaction_logs ADD INDEX idx_interaction_hint_strength (hint_strength)",
    "ALTER TABLE interaction_logs ADD INDEX idx_interaction_pedagogical_intent (pedagogical_intent)",
    "ALTER TABLE interaction_logs ADD INDEX idx_interaction_intent (interaction_intent)",
    "ALTER TABLE interaction_logs ADD INDEX idx_interaction_side_channel (side_channel_detected)",
    "ALTER TABLE interaction_logs ADD INDEX idx_interaction_private_progress (private_progress_signal_request)",
    "ALTER TABLE interaction_logs ADD INDEX idx_interaction_private_grade (private_grade_signal_request)",
    "ALTER TABLE interaction_logs ADD INDEX idx_interaction_private_encoding (private_signal_encoding_request)",
    "ALTER TABLE interaction_logs ADD INDEX idx_interaction_output_guarded (private_signal_output_guarded)",
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

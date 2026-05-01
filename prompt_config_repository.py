from __future__ import annotations

from sqlalchemy import text

from database_service import get_database_engine

SYSTEM_INSTRUCTION_KEY = "system_instruction"


def get_config_value(config_key: str) -> str | None:
    engine = get_database_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT config_value FROM system_configs WHERE config_key = :key"),
            {"key": config_key},
        ).fetchone()
    return row[0] if row else None


def upsert_config_value(config_key: str, config_value: str) -> None:
    engine = get_database_engine()
    with engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO system_configs (config_key, config_value) "
                "VALUES (:key, :val) "
                "ON DUPLICATE KEY UPDATE config_value = :val"
            ),
            {"key": config_key, "val": config_value},
        )
        conn.commit()


def get_system_instruction(default_prompt: str) -> str:
    return get_config_value(SYSTEM_INSTRUCTION_KEY) or default_prompt


def update_system_instruction(prompt: str) -> None:
    upsert_config_value(SYSTEM_INSTRUCTION_KEY, prompt)

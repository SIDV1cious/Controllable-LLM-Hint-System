import streamlit as st

from app_errors import log_exception
from prompt_config_repository import get_system_instruction, update_system_instruction
from prompts import SYSTEM_INSTRUCTION


def render_prompt_configuration_tab():
    st.subheader("🧠 大模型 Prompt 注入控制台")
    st.info("💡 在这里热更新大模型的底层性格与辅导策略！修改保存后，所有学生的 AI 辅导体验将瞬间改变。")
    try:
        current_prompt = get_system_instruction(SYSTEM_INSTRUCTION)
    except Exception as e:
        log_exception("Load prompt config error", e)
        current_prompt = SYSTEM_INSTRUCTION

    with st.form("prompt_update_form"):
        new_prompt = st.text_area("🔧 当前系统底层提示词 (System Prompt)", value=current_prompt, height=250)
        if st.form_submit_button("💾 保存并全局应用新指令", type="primary", use_container_width=True):
            if new_prompt.strip():
                try:
                    update_system_instruction(new_prompt.strip())
                    st.toast("大模型底层指令已热更新！全系统生效！", icon="✅")
                    st.rerun()
                except Exception as e:
                    st.toast(f"更新失败: {e}", icon="❌")
            else:
                st.toast("提示词不能为空！", icon="⚠️")

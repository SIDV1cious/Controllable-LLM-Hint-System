import os

import streamlit.components.v1 as components

_RELEASE = True

if not _RELEASE:
    _component_func = components.declare_component(
        "math_input_inline_formula_box_v29",
        url="http://localhost:3001",
    )
else:
    parent_dir = os.path.dirname(os.path.abspath(__file__))
    build_dir = os.path.join(parent_dir, "streamlit-component-x", "streamlit_component_x", "frontend", "build")
    _component_func = components.declare_component("math_input_inline_formula_box_v29", path=build_dir)


def math_input(default_value="", key=None):
    return _component_func(default_value=default_value, key=key, default=default_value)

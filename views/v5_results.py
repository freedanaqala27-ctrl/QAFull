from __future__ import annotations

import streamlit as st

from evaluation_system.components import render_page_header
from views import v4_survey, v6_snapshot, v7_report, v_runs

RESULT_TABS_BY_ROLE = {
    "\u7ba1\u7406\u5458": ["\u95ee\u5377", "\u62a5\u544a", "\u8bb0\u5f55", "\u5feb\u7167"],
    "\u7814\u7a76\u5458": ["\u95ee\u5377", "\u62a5\u544a", "\u8bb0\u5f55"],
}


def render(bundle: dict) -> None:
    render_page_header("\u7ed3\u679c", "\u7edf\u4e00\u67e5\u770b\u95ee\u5377\u3001\u62a5\u544a\u3001\u8fd0\u884c\u8bb0\u5f55\uff0c\u4ee5\u53ca\u7ba1\u7406\u5458\u53ef\u7528\u7684\u5feb\u7167\u53d1\u5e03\u3002")

    current_role = str(st.session_state.get("console_role") or "\u7814\u7a76\u5458")
    tab_options = RESULT_TABS_BY_ROLE.get(current_role, RESULT_TABS_BY_ROLE["\u7814\u7a76\u5458"])

    active_tab = str(st.session_state.get("results-active-tab") or tab_options[0])
    if active_tab not in tab_options:
        active_tab = tab_options[0]
        st.session_state["results-active-tab"] = active_tab

    selected_tab = st.radio(
        "\u7ed3\u679c\u9875\u9762\u5bfc\u822a",
        tab_options,
        index=tab_options.index(active_tab),
        horizontal=True,
        label_visibility="collapsed",
        key="results-active-tab",
    )

    if selected_tab == "\u95ee\u5377":
        v4_survey.render(bundle, show_header=False)
    elif selected_tab == "\u62a5\u544a":
        v7_report.render(bundle, show_header=False)
    elif selected_tab == "\u8bb0\u5f55":
        v_runs.render(bundle, show_header=False)
    elif selected_tab == "\u5feb\u7167":
        v6_snapshot.render(bundle, show_header=False)
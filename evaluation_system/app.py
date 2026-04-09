from __future__ import annotations

from typing import Callable

import streamlit as st

from evaluation_system.state_store import (
    build_dashboard_bundle,
    build_stage_items,
    current_review_summary,
    get_role_pages,
    init_session_state,
    pop_console_flash,
)
from evaluation_system.theme import apply_theme
from views import v0_overview, v1_pipeline, v2_generation, v3_review, v4_survey, v6_snapshot, v7_report, v_runs, v_settings

PAGE_RENDERERS: dict[str, Callable[[dict], None]] = {
    "流程总览": v1_pipeline.render,
    "题目生成": v2_generation.render,
    "当前任务": v0_overview.render,
    "审核中心": v3_review.render,
    "问卷管理": v4_survey.render,
    "分析报告": v7_report.render,
    "运行记录": v_runs.render,
    "系统设置": v_settings.render,
    "快照发布": v6_snapshot.render,
}

FLASH_RENDERERS = {
    "success": st.success,
    "warning": st.warning,
    "danger": st.error,
    "error": st.error,
    "info": st.info,
}


def main() -> None:
    st.set_page_config(
        page_title="深度学习编程题生成与评价系统",
        page_icon="",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    apply_theme()
    bundle = build_dashboard_bundle()
    init_session_state(bundle)
    bundle["review_summary"] = current_review_summary()
    bundle["stages"] = build_stage_items(bundle)

    role_options = bundle.get("role_options") or ["管理员", "研究员"]
    current_role = st.session_state.get("console_role", "管理员")
    if current_role not in role_options:
        st.session_state["console_role"] = role_options[0]
        current_role = role_options[0]

    with st.sidebar:
        st.markdown("## 深度学习编程题生成与评价系统")
        st.selectbox("当前角色", role_options, key="console_role")
        st.caption("当前批次")
        st.markdown(f"**{bundle['settings']['batch_name']}**")

        available_pages = get_role_pages(st.session_state["console_role"])
        current_page = st.session_state.get("console_page", "流程总览")
        if current_page not in available_pages and current_page != "快照发布":
            st.session_state["console_page"] = available_pages[0]
            current_page = available_pages[0]

        st.markdown("### 页面导航")
        selected = st.radio(
            "页面导航",
            available_pages,
            index=available_pages.index(current_page) if current_page in available_pages else 0,
            label_visibility="collapsed",
        )
        if current_page in available_pages and selected != current_page:
            st.session_state["console_page"] = selected

    flash = pop_console_flash()
    if flash:
        renderer = FLASH_RENDERERS.get(flash.get("tone", "info"), st.info)
        renderer(flash.get("message", "操作已完成。"))
    renderer = PAGE_RENDERERS.get(st.session_state["console_page"], v1_pipeline.render)
    renderer(bundle)


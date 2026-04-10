from __future__ import annotations

from typing import Callable

import streamlit as st

from evaluation_system.state_store import (
    build_dashboard_bundle,
    build_stage_items,
    current_review_summary,
    init_session_state,
    pop_console_flash,
)
from evaluation_system.theme import apply_theme
from views import v0_overview, v2_generation, v3_review, v5_results

PAGE_WORKBENCH = "工作台"
PAGE_GENERATION = "生成"
PAGE_REVIEW = "审核"
PAGE_RESULTS = "结果"

DEMO_PAGES = [PAGE_WORKBENCH, PAGE_GENERATION, PAGE_REVIEW, PAGE_RESULTS]

PAGE_RENDERERS: dict[str, Callable[[dict], None]] = {
    PAGE_WORKBENCH: v0_overview.render,
    PAGE_GENERATION: v2_generation.render,
    PAGE_REVIEW: v3_review.render,
    PAGE_RESULTS: v5_results.render,
}

LEGACY_PAGE_ALIASES = {
    "流程总览": PAGE_WORKBENCH,
    "当前任务": PAGE_WORKBENCH,
    "题目生成": PAGE_GENERATION,
    "审核中心": PAGE_REVIEW,
    "问卷管理": PAGE_RESULTS,
    "分析报告": PAGE_RESULTS,
    "运行记录": PAGE_RESULTS,
    "快照发布": PAGE_RESULTS,
}

FLASH_RENDERERS = {
    "success": st.success,
    "warning": st.warning,
    "danger": st.error,
    "error": st.error,
    "info": st.info,
}


def canonical_page_name(page_name: str) -> str:
    clean_name = str(page_name or "").strip()
    if not clean_name:
        return PAGE_WORKBENCH
    if clean_name in DEMO_PAGES:
        return clean_name
    return LEGACY_PAGE_ALIASES.get(clean_name, PAGE_WORKBENCH)


def sync_page_state() -> str:
    current_page = canonical_page_name(st.session_state.get("console_page", PAGE_WORKBENCH))
    if current_page not in PAGE_RENDERERS:
        current_page = PAGE_WORKBENCH
    st.session_state["console_page"] = current_page
    return current_page


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

    st.session_state["console_role"] = "管理员"

    with st.sidebar:
        st.markdown("## 深度学习编程题生成与评价系统")
        st.caption("自动化主线演示")
        st.caption("当前批次")
        st.markdown(f"**{bundle['settings']['batch_name']}**")

        current_page = sync_page_state()
        if current_page not in DEMO_PAGES:
            st.session_state["console_page"] = PAGE_WORKBENCH
            current_page = PAGE_WORKBENCH

        st.markdown("### 自动化主线")
        selected = st.radio(
            "自动化主线",
            DEMO_PAGES,
            index=DEMO_PAGES.index(current_page) if current_page in DEMO_PAGES else 0,
            label_visibility="collapsed",
        )
        if selected != current_page:
            st.session_state["console_page"] = selected

    flash = pop_console_flash()
    if flash:
        renderer = FLASH_RENDERERS.get(flash.get("tone", "info"), st.info)
        renderer(flash.get("message", "操作已完成。"))

    current_page = sync_page_state()
    renderer = PAGE_RENDERERS.get(current_page, v0_overview.render)
    renderer(bundle)
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
from views import v0_overview, v2_generation, v3_review, v5_results, v_settings

PAGE_WORKBENCH = "\u5de5\u4f5c\u53f0"
PAGE_GENERATION = "\u751f\u6210"
PAGE_REVIEW = "\u5ba1\u6838"
PAGE_RESULTS = "\u7ed3\u679c"
PAGE_SETTINGS = "\u7cfb\u7edf\u8bbe\u7f6e"
PAGE_SNAPSHOT = "\u5feb\u7167\u53d1\u5e03"

PAGE_RENDERERS: dict[str, Callable[[dict], None]] = {
    PAGE_WORKBENCH: v0_overview.render,
    PAGE_GENERATION: v2_generation.render,
    PAGE_REVIEW: v3_review.render,
    PAGE_RESULTS: v5_results.render,
    PAGE_SETTINGS: v_settings.render,
}

LEGACY_PAGE_ALIASES = {
    "\u6d41\u7a0b\u603b\u89c8": PAGE_WORKBENCH,
    "\u5f53\u524d\u4efb\u52a1": PAGE_WORKBENCH,
    "\u9898\u76ee\u751f\u6210": PAGE_GENERATION,
    "\u5ba1\u6838\u4e2d\u5fc3": PAGE_REVIEW,
    "\u95ee\u5377\u7ba1\u7406": PAGE_RESULTS,
    "\u5206\u6790\u62a5\u544a": PAGE_RESULTS,
    "\u8fd0\u884c\u8bb0\u5f55": PAGE_RESULTS,
    PAGE_SNAPSHOT: PAGE_RESULTS,
}

RESULT_SUBPAGE_ALIASES = {
    "\u95ee\u5377\u7ba1\u7406": "\u95ee\u5377",
    "\u5206\u6790\u62a5\u544a": "\u62a5\u544a",
    "\u8fd0\u884c\u8bb0\u5f55": "\u8bb0\u5f55",
    PAGE_SNAPSHOT: "\u5feb\u7167",
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
    return LEGACY_PAGE_ALIASES.get(clean_name, clean_name)


def sync_page_state() -> str:
    raw_page = str(st.session_state.get("console_page", PAGE_WORKBENCH) or PAGE_WORKBENCH).strip() or PAGE_WORKBENCH
    if raw_page in RESULT_SUBPAGE_ALIASES:
        st.session_state["results-active-tab"] = RESULT_SUBPAGE_ALIASES[raw_page]
    canonical_page = canonical_page_name(raw_page)
    st.session_state["console_page"] = canonical_page
    return canonical_page


def main() -> None:
    st.set_page_config(
        page_title="\u6df1\u5ea6\u5b66\u4e60\u7f16\u7a0b\u9898\u751f\u6210\u4e0e\u8bc4\u4ef7\u7cfb\u7edf",
        page_icon="",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    apply_theme()
    bundle = build_dashboard_bundle()
    init_session_state(bundle)
    bundle["review_summary"] = current_review_summary()
    bundle["stages"] = build_stage_items(bundle)

    role_options = bundle.get("role_options") or ["\u7ba1\u7406\u5458", "\u7814\u7a76\u5458"]
    current_role = st.session_state.get("console_role", "\u7ba1\u7406\u5458")
    if current_role not in role_options:
        st.session_state["console_role"] = role_options[0]
        current_role = role_options[0]

    with st.sidebar:
        st.markdown("## \u6df1\u5ea6\u5b66\u4e60\u7f16\u7a0b\u9898\u751f\u6210\u4e0e\u8bc4\u4ef7\u7cfb\u7edf")
        st.selectbox("\u5f53\u524d\u89d2\u8272", role_options, key="console_role")
        st.caption("\u5f53\u524d\u6279\u6b21")
        st.markdown(f"**{bundle['settings']['batch_name']}**")

        available_pages = get_role_pages(st.session_state["console_role"])
        current_page = sync_page_state()
        if current_page not in available_pages:
            st.session_state["console_page"] = available_pages[0]
            current_page = available_pages[0]

        st.markdown("### \u9875\u9762\u5bfc\u822a")
        selected = st.radio(
            "\u9875\u9762\u5bfc\u822a",
            available_pages,
            index=available_pages.index(current_page) if current_page in available_pages else 0,
            label_visibility="collapsed",
        )
        if current_page in available_pages and selected != current_page:
            st.session_state["console_page"] = selected

    flash = pop_console_flash()
    if flash:
        renderer = FLASH_RENDERERS.get(flash.get("tone", "info"), st.info)
        renderer(flash.get("message", "\u64cd\u4f5c\u5df2\u5b8c\u6210\u3002"))

    current_page = sync_page_state()
    renderer = PAGE_RENDERERS.get(current_page, v0_overview.render)
    renderer(bundle)
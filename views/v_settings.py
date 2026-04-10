from __future__ import annotations

import copy

import streamlit as st

from evaluation_system.components import render_empty_state, render_page_header
from evaluation_system.runner import save_console_settings
from evaluation_system.state_store import ROLE_PERMISSIONS, set_console_flash

ALL_PAGES = ["\u5de5\u4f5c\u53f0", "\u751f\u6210", "\u5ba1\u6838", "\u7ed3\u679c", "\u7cfb\u7edf\u8bbe\u7f6e"]
ROLE_NAMES = ["\u7ba1\u7406\u5458", "\u7814\u7a76\u5458"]


def _persist(settings: dict, note: str) -> None:
    result = save_console_settings(copy.deepcopy(settings), operator=st.session_state["console_role"], note=note)
    set_console_flash(result["message"], "success" if result["status"] == "success" else "danger")
    st.cache_data.clear()
    st.rerun()


def render(bundle: dict) -> None:
    render_page_header("\u7cfb\u7edf\u8bbe\u7f6e", "\u7ba1\u7406\u5f53\u524d\u6279\u6b21\u3001\u9875\u9762\u53ef\u89c1\u8303\u56f4\u3001\u95ee\u5377\u6765\u6e90\u548c\u7ed3\u679c\u4fdd\u5b58\u4f4d\u7f6e\u3002")
    if st.session_state.get("console_role") != "\u7ba1\u7406\u5458":
        render_empty_state("\u5f53\u524d\u89d2\u8272\u4e0d\u53ef\u8bbf\u95ee\u7cfb\u7edf\u8bbe\u7f6e", "\u7cfb\u7edf\u8bbe\u7f6e\u4ec5\u7ba1\u7406\u5458\u53ef\u89c1\uff0c\u7814\u7a76\u5458\u53ea\u4fdd\u7559\u4e1a\u52a1\u64cd\u4f5c\u5165\u53e3\u3002")
        return

    settings = st.session_state["settings_form_state"]
    settings.setdefault("role_permissions", copy.deepcopy(bundle["settings"].get("role_permissions", {})))
    tabs = st.tabs(["\u6279\u6b21\u4fe1\u606f", "\u9875\u9762\u53ef\u89c1\u8303\u56f4", "\u95ee\u5377\u6765\u6e90", "\u4fdd\u5b58\u4f4d\u7f6e"])

    with tabs[0]:
        st.text_input("\u5f53\u524d\u6279\u6b21\u540d\u79f0", key="settings-batch-name", value=settings.get("batch_name", ""))
        st.number_input(
            "\u6837\u672c\u786e\u8ba4\u95e8\u69db",
            min_value=1,
            step=1,
            key="settings-freeze-threshold",
            value=int(settings.get("freeze_threshold", 30)),
            help="\u8fbe\u5230\u8fd9\u4e2a\u6570\u91cf\u540e\uff0c\u624d\u53ef\u4ee5\u786e\u8ba4\u672c\u8f6e\u5206\u6790\u6837\u672c\u3002",
        )
        st.text_input("\u5f53\u524d\u5de5\u4f5c\u65b9\u5411", key="settings-mainline", value=settings.get("current_mainline", "\u5b66\u751f\u95ee\u5377\u4e3b\u7ebf"))
        if st.button("\u4fdd\u5b58\u8bbe\u7f6e", key="save-batch-settings", type="primary"):
            settings["batch_name"] = st.session_state["settings-batch-name"]
            settings["freeze_threshold"] = st.session_state["settings-freeze-threshold"]
            settings["current_mainline"] = st.session_state["settings-mainline"]
            _persist(settings, "\u66f4\u65b0\u6279\u6b21\u914d\u7f6e")

    with tabs[1]:
        role_permissions = settings.setdefault("role_permissions", {})
        for role_name in ROLE_NAMES:
            defaults = role_permissions.get(role_name) or bundle["settings"].get("role_permissions", {}).get(role_name) or ROLE_PERMISSIONS.get(role_name, [])
            st.multiselect(
                f"{role_name}\u53ef\u89c1\u9875\u9762",
                ALL_PAGES,
                default=defaults,
                key=f"perm-{role_name}",
            )
        if st.button("\u4fdd\u5b58\u8bbe\u7f6e", key="save-role-settings", type="primary"):
            for role_name in ROLE_NAMES:
                role_permissions[role_name] = st.session_state.get(f"perm-{role_name}", [])
            _persist(settings, "\u66f4\u65b0\u89d2\u8272\u6743\u9650")

    with tabs[2]:
        data_source = settings.setdefault("data_source", copy.deepcopy(bundle["settings"].get("data_source", {})))
        st.text_input("\u5728\u7ebf\u95ee\u5377\u5730\u5740", key="settings-supabase-url", value=data_source.get("supabase_url", ""))
        st.text_input("\u8bbf\u95ee\u5bc6\u94a5", key="settings-supabase-key", value=data_source.get("supabase_key", ""), type="password")
        st.selectbox(
            "\u95ee\u5377\u7ed3\u679c\u6765\u6e90",
            ["\u76f4\u63a5\u8fde\u63a5", "\u672c\u5730 CSV"],
            index=1 if data_source.get("pull_mode", "\u672c\u5730 CSV") == "\u672c\u5730 CSV" else 0,
            key="settings-pull-mode-display",
        )
        action_cols = st.columns(2)
        if action_cols[0].button("\u68c0\u67e5\u662f\u5426\u53ef\u7528", use_container_width=True):
            if st.session_state["settings-supabase-url"] and st.session_state["settings-supabase-key"]:
                st.success("\u5df2\u68c0\u6d4b\u5230\u5728\u7ebf\u95ee\u5377\u5730\u5740\u548c\u8bbf\u95ee\u5bc6\u94a5\uff0c\u53ef\u7528\u4e8e\u76f4\u63a5\u8bfb\u53d6\u95ee\u5377\u7ed3\u679c\u3002")
            else:
                st.warning("\u8bf7\u5148\u586b\u5199\u5728\u7ebf\u95ee\u5377\u5730\u5740\u548c\u8bbf\u95ee\u5bc6\u94a5\u3002")
        if action_cols[1].button("\u4fdd\u5b58\u8bbe\u7f6e", key="save-datasource-settings", type="primary", use_container_width=True):
            data_source["supabase_url"] = st.session_state["settings-supabase-url"]
            data_source["supabase_key"] = st.session_state["settings-supabase-key"]
            data_source["pull_mode"] = "\u672c\u5730 CSV" if st.session_state["settings-pull-mode-display"] == "\u672c\u5730 CSV" else "\u76f4\u63a5\u62c9\u5e93"
            _persist(settings, "\u66f4\u65b0\u6570\u636e\u6e90\u914d\u7f6e")

    with tabs[3]:
        paths = settings.setdefault("paths", copy.deepcopy(bundle["settings"].get("paths", {})))
        st.text_input("\u53d1\u653e\u6750\u6599\u4fdd\u5b58\u4f4d\u7f6e", key="settings-packet-dir", value=paths.get("packet_export_dir", "results/curated/human_eval_packets"))
        st.text_input("\u62a5\u544a\u7ed3\u679c\u4fdd\u5b58\u4f4d\u7f6e", key="settings-report-dir", value=paths.get("report_export_dir", "results/student_subsets/chapter5_outputs"))
        st.text_input("\u5f52\u6863\u4fdd\u5b58\u4f4d\u7f6e", key="settings-snapshot-dir", value=paths.get("snapshot_export_dir", "outputs/system"))
        if st.button("\u4fdd\u5b58\u8bbe\u7f6e", key="save-path-settings", type="primary"):
            paths["packet_export_dir"] = st.session_state["settings-packet-dir"]
            paths["report_export_dir"] = st.session_state["settings-report-dir"]
            paths["snapshot_export_dir"] = st.session_state["settings-snapshot-dir"]
            _persist(settings, "\u66f4\u65b0\u5bfc\u51fa\u8def\u5f84")
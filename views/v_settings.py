from __future__ import annotations

import copy

import streamlit as st

from evaluation_system.components import render_empty_state, render_page_header
from evaluation_system.runner import save_console_settings
from evaluation_system.state_store import ROLE_PERMISSIONS, set_console_flash

ALL_PAGES = ["流程总览", "题目生成", "当前任务", "审核中心", "问卷管理", "分析报告", "运行记录", "系统设置"]
ROLE_NAMES = ["管理员", "研究员"]


def _persist(settings: dict, note: str) -> None:
    result = save_console_settings(copy.deepcopy(settings), operator=st.session_state["console_role"], note=note)
    set_console_flash(result["message"], "success" if result["status"] == "success" else "danger")
    st.cache_data.clear()
    st.rerun()


def render(bundle: dict) -> None:
    render_page_header("系统设置", "管理当前批次、页面可见范围、问卷来源和结果保存位置。")
    if st.session_state.get("console_role") != "管理员":
        render_empty_state("当前角色不可访问系统设置", "系统设置仅管理员可见，研究员只保留业务操作入口。")
        return

    settings = st.session_state["settings_form_state"]
    settings.setdefault("role_permissions", copy.deepcopy(bundle["settings"].get("role_permissions", {})))
    tabs = st.tabs(["批次信息", "页面可见范围", "问卷来源", "保存位置"])

    with tabs[0]:
        st.text_input("当前批次名称", key="settings-batch-name", value=settings.get("batch_name", ""))
        st.number_input(
            "样本确认门槛",
            min_value=1,
            step=1,
            key="settings-freeze-threshold",
            value=int(settings.get("freeze_threshold", 30)),
            help="达到这个数量后，才可以确认本轮分析样本。",
        )
        st.text_input("当前工作方向", key="settings-mainline", value=settings.get("current_mainline", "学生问卷主线"))
        if st.button("保存设置", key="save-batch-settings", type="primary"):
            settings["batch_name"] = st.session_state["settings-batch-name"]
            settings["freeze_threshold"] = st.session_state["settings-freeze-threshold"]
            settings["current_mainline"] = st.session_state["settings-mainline"]
            _persist(settings, "更新批次配置")

    with tabs[1]:
        role_permissions = settings.setdefault("role_permissions", {})
        for role_name in ROLE_NAMES:
            defaults = role_permissions.get(role_name) or bundle["settings"].get("role_permissions", {}).get(role_name) or ROLE_PERMISSIONS.get(role_name, [])
            st.multiselect(
                f"{role_name}可见页面",
                ALL_PAGES,
                default=defaults,
                key=f"perm-{role_name}",
            )
        if st.button("保存设置", key="save-role-settings", type="primary"):
            for role_name in ROLE_NAMES:
                role_permissions[role_name] = st.session_state.get(f"perm-{role_name}", [])
            _persist(settings, "更新角色权限")

    with tabs[2]:
        data_source = settings.setdefault("data_source", copy.deepcopy(bundle["settings"].get("data_source", {})))
        st.text_input("在线问卷地址", key="settings-supabase-url", value=data_source.get("supabase_url", ""))
        st.text_input("访问密钥", key="settings-supabase-key", value=data_source.get("supabase_key", ""), type="password")
        st.selectbox(
            "问卷结果来源",
            ["直接连接", "本地 CSV"],
            index=1 if data_source.get("pull_mode", "本地 CSV") == "本地 CSV" else 0,
            key="settings-pull-mode-display",
        )
        action_cols = st.columns(2)
        if action_cols[0].button("检查是否可用", use_container_width=True):
            if st.session_state["settings-supabase-url"] and st.session_state["settings-supabase-key"]:
                st.success("已检测到在线问卷地址和访问密钥，可用于直接读取问卷结果。")
            else:
                st.warning("请先填写在线问卷地址和访问密钥。")
        if action_cols[1].button("保存设置", key="save-datasource-settings", type="primary", use_container_width=True):
            data_source["supabase_url"] = st.session_state["settings-supabase-url"]
            data_source["supabase_key"] = st.session_state["settings-supabase-key"]
            data_source["pull_mode"] = "本地 CSV" if st.session_state["settings-pull-mode-display"] == "本地 CSV" else "直接拉库"
            _persist(settings, "更新数据源配置")

    with tabs[3]:
        paths = settings.setdefault("paths", copy.deepcopy(bundle["settings"].get("paths", {})))
        st.text_input("发放材料保存位置", key="settings-packet-dir", value=paths.get("packet_export_dir", "results/curated/human_eval_packets"))
        st.text_input("报告结果保存位置", key="settings-report-dir", value=paths.get("report_export_dir", "results/student_subsets/chapter5_outputs"))
        st.text_input("归档保存位置", key="settings-snapshot-dir", value=paths.get("snapshot_export_dir", "outputs/system"))
        if st.button("保存设置", key="save-path-settings", type="primary"):
            paths["packet_export_dir"] = st.session_state["settings-packet-dir"]
            paths["report_export_dir"] = st.session_state["settings-report-dir"]
            paths["snapshot_export_dir"] = st.session_state["settings-snapshot-dir"]
            _persist(settings, "更新导出路径")

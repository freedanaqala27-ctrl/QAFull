from __future__ import annotations

from pathlib import Path

import streamlit as st

from evaluation_system.components import download_file_button, render_checklist, render_key_value_table, render_page_header
from evaluation_system.runner import execute_action
from evaluation_system.state_store import set_console_flash, task_status_label


def _deliverable(bundle: dict, key: str) -> dict:
    return bundle.get("deliverables", {}).get(key, {})


def _run_student_packet_generation() -> None:
    with st.spinner("正在生成学生题包和问卷发放材料..."):
        result = execute_action(
            "generate_student_packets",
            operator=st.session_state["console_role"],
            note="答辩模式 / 问卷发放",
        )
    set_console_flash(result["message"], "success" if result["status"] == "success" else "danger")
    st.cache_data.clear()
    st.rerun()


def _run_freeze(bundle: dict) -> None:
    pull_mode = bundle["settings"].get("data_source", {}).get("pull_mode", "本地 CSV")
    with st.spinner("正在冻结正式分析样本..."):
        result = execute_action(
            "freeze_analysis_input",
            operator=st.session_state["console_role"],
            note="答辩模式 / 冻结分析样本",
            params={
                "pull_mode": pull_mode,
                "fetch_from_db": pull_mode == "直接拉库",
            },
        )
    set_console_flash(result["message"], "success" if result["status"] == "success" else "danger")
    st.session_state["freeze_confirm_open"] = False
    st.cache_data.clear()
    st.rerun()


def render(bundle: dict, *, show_header: bool = True) -> None:
    if show_header:
        render_page_header("问卷", "只保留题包发布、回收进度和冻结分析样本三个关键动作。")

    survey_metrics = bundle["survey_metrics"]
    tasks = bundle.get("tasks", {})
    packet_manifest = _deliverable(bundle, "packet_manifest")
    qrcode_sheet = _deliverable(bundle, "qrcode_sheet")
    distribution_sheet = _deliverable(bundle, "distribution_sheet")

    render_key_value_table(
        [
            ("发放状态", task_status_label(tasks.get("survey_publish", {}).get("status", "not_started"))),
            ("已发放", str(survey_metrics.get("issued_count", 0))),
            ("已提交", str(survey_metrics.get("submitted_count", 0))),
            ("有效样本", str(survey_metrics.get("effective_samples", 0))),
            ("冻结阈值", str(survey_metrics.get("freeze_threshold", 0))),
            ("样本冻结", task_status_label(tasks.get("freeze", {}).get("status", "not_started"))),
        ],
        columns=3,
    )

    st.markdown("### 1. 发布学生问卷")
    st.caption("系统会为正式样本生成学生题包、二维码和分发材料。")
    publish_cols = st.columns(2)
    if publish_cols[0].button("生成问卷材料", type="primary", use_container_width=True):
        _run_student_packet_generation()
    if publish_cols[1].button("刷新回收进度", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    with st.expander("查看发放材料", expanded=False):
        material_cols = st.columns(3)
        with material_cols[0]:
            download_file_button(Path(str(packet_manifest.get("path") or "")), "下载题包清单", "survey-packet-manifest")
        with material_cols[1]:
            download_file_button(Path(str(qrcode_sheet.get("path") or "")), "下载二维码页", "survey-qrcode-sheet")
        with material_cols[2]:
            download_file_button(Path(str(distribution_sheet.get("path") or "")), "下载分发清单", "survey-distribution-sheet")

    st.markdown("### 2. 回收与清洗")
    render_checklist(
        [
            {
                "label": "问卷回收",
                "note": f"当前已提交 {survey_metrics.get('submitted_count', 0)} 份问卷。",
                "status_label": "进行中" if survey_metrics.get("submitted_count", 0) else "未开始",
                "tone": "success" if survey_metrics.get("submitted_count", 0) else "warning",
            },
            {
                "label": "有效样本",
                "note": "系统会结合注意力检验和快答规则过滤无效记录。",
                "status_label": str(survey_metrics.get("effective_samples", 0)),
                "tone": "success" if survey_metrics.get("effective_samples", 0) else "warning",
            },
            {
                "label": "冻结准备",
                "note": f"达到阈值 {survey_metrics.get('freeze_threshold', 0)} 后才能冻结正式分析样本。",
                "status_label": "已达标" if survey_metrics.get("threshold_ready") else "未达标",
                "tone": "success" if survey_metrics.get("threshold_ready") else "warning",
            },
        ]
    )

    st.markdown("### 3. 冻结分析样本")
    freeze_status = str(tasks.get("freeze", {}).get("status") or "not_started")
    if tasks.get("freeze", {}).get("block_reason"):
        st.caption(f"当前限制：{tasks['freeze']['block_reason']}")
    freeze_cols = st.columns(2)
    if freeze_cols[0].button(
        "冻结分析样本",
        type="primary",
        disabled=freeze_status == "blocked",
        use_container_width=True,
    ):
        st.session_state["freeze_confirm_open"] = True
    if freeze_cols[1].button("查看结果页", use_container_width=True):
        st.session_state["console_page"] = "结果"
        st.rerun()

    if st.session_state.get("freeze_confirm_open"):
        st.info("确认后系统会导出问卷原始输入、构建分析主表，并锁定本轮正式分析样本。")
        confirm_cols = st.columns(2)
        if confirm_cols[0].button("确认冻结", type="primary", use_container_width=True):
            _run_freeze(bundle)
        if confirm_cols[1].button("取消", use_container_width=True):
            st.session_state["freeze_confirm_open"] = False
            st.rerun()
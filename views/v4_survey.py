from __future__ import annotations

from pathlib import Path

import streamlit as st

from evaluation_system.components import (
    render_checklist,
    render_key_value_table,
    render_page_header,
)
from evaluation_system.runner import execute_action
from evaluation_system.state_store import set_console_flash, task_status_label


SECTION_DIVIDER = "---"


TASK_TONES = {
    "completed": "success",
    "ready": "success",
    "running": "warning",
    "in_progress": "warning",
    "failed": "danger",
    "blocked": "danger",
    "not_started": "warning",
}


def _deliverable(bundle: dict, key: str) -> dict:
    return bundle.get("deliverables", {}).get(key, {})


def _deliverable_bytes(bundle: dict, key: str) -> bytes:
    path = Path(str(_deliverable(bundle, key).get("path") or ""))
    return path.read_bytes() if path.exists() else b""


def _deliverable_name(bundle: dict, key: str) -> str:
    path = Path(str(_deliverable(bundle, key).get("path") or ""))
    return path.name if path.name else f"{key}.dat"


def _task_tone(status: str) -> str:
    return TASK_TONES.get(str(status or "").strip(), "warning")


def _run_student_packet_generation() -> None:
    with st.spinner("正在准备问卷发放材料..."):
        result = execute_action(
            "generate_student_packets",
            operator=st.session_state["console_role"],
            note="从问卷管理页发起",
        )
    set_console_flash(result["message"], "success" if result["status"] == "success" else "danger")
    st.cache_data.clear()
    st.rerun()


def _run_freeze(bundle: dict) -> None:
    pull_mode = bundle["settings"].get("data_source", {}).get("pull_mode", "本地 CSV")
    with st.spinner("正在确认本轮分析样本..."):
        result = execute_action(
            "freeze_analysis_input",
            operator=st.session_state["console_role"],
            note="从问卷管理页确认分析样本",
            params={
                "pull_mode": pull_mode,
                "fetch_from_db": pull_mode == "直接拉库",
            },
        )
    set_console_flash(result["message"], "success" if result["status"] == "success" else "danger")
    st.session_state["freeze_confirm_open"] = False
    st.cache_data.clear()
    st.rerun()


def render(bundle: dict) -> None:
    render_page_header("问卷管理", "安排问卷发放、查看回收进度，并在条件满足后确认本轮分析样本。")
    survey_metrics = bundle["survey_metrics"]
    tasks = bundle.get("tasks", {})
    packet_manifest = _deliverable(bundle, "packet_manifest")
    qrcode_sheet = _deliverable(bundle, "qrcode_sheet")
    distribution_sheet = _deliverable(bundle, "distribution_sheet")

    st.markdown("### 问卷发放")
    render_key_value_table(
        [
            ("当前状态", task_status_label(tasks.get("survey_publish", {}).get("status", "not_started"))),
            ("题包清单", "已准备" if packet_manifest.get("available") else "待准备"),
            ("二维码材料", "已准备" if qrcode_sheet.get("available") else "待准备"),
            ("分发清单", "已准备" if distribution_sheet.get("available") else "待准备"),
        ],
        columns=2,
    )
    packet_cols = st.columns(4)
    if packet_cols[0].button("准备发放材料", type="primary", use_container_width=True):
        _run_student_packet_generation()
    packet_cols[1].download_button(
        "下载题包清单",
        _deliverable_bytes(bundle, "packet_manifest"),
        file_name=_deliverable_name(bundle, "packet_manifest"),
        use_container_width=True,
        disabled=not packet_manifest.get("available"),
    )
    packet_cols[2].download_button(
        "下载二维码页",
        _deliverable_bytes(bundle, "qrcode_sheet"),
        file_name=_deliverable_name(bundle, "qrcode_sheet"),
        use_container_width=True,
        disabled=not qrcode_sheet.get("available"),
    )
    packet_cols[3].download_button(
        "下载分发清单",
        _deliverable_bytes(bundle, "distribution_sheet"),
        file_name=_deliverable_name(bundle, "distribution_sheet"),
        use_container_width=True,
        disabled=not distribution_sheet.get("available"),
    )

    st.markdown(SECTION_DIVIDER)
    st.markdown("### 回收情况")
    render_key_value_table(
        [
            ("当前状态", task_status_label(tasks.get("survey_collect", {}).get("status", "not_started"))),
            ("已发放", str(survey_metrics.get("scanned_count") or survey_metrics["issued_count"])),
            ("已回收", str(survey_metrics["submitted_count"])),
            ("有效样本", str(survey_metrics["effective_samples"])),
        ],
        columns=2,
    )
    st.caption("这里展示当前回收进度，具体问卷内容和明细不在本页展开。")
    recycle_cols = st.columns(3)
    if recycle_cols[0].button("刷新页面", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    if recycle_cols[1].button("查看运行记录", use_container_width=True):
        st.session_state["console_page"] = "运行记录"
        st.rerun()
    if recycle_cols[2].button("查看问卷设置", use_container_width=True):
        st.session_state["console_page"] = "系统设置"
        st.rerun()

    st.markdown(SECTION_DIVIDER)
    st.markdown("### 确认分析样本")
    freeze_status = str(tasks.get("freeze", {}).get("status") or "not_started")
    render_checklist(
        [
            {
                "label": "样本数量达标",
                "note": f"当前需达到 {survey_metrics['freeze_threshold']} 份有效样本后才能确认本轮分析范围。",
                "status_label": "已达标" if survey_metrics["threshold_ready"] else "未达标",
                "tone": "success" if survey_metrics["threshold_ready"] else "danger",
            },
            {
                "label": "回收结果已准备",
                "note": "问卷结果已经进入系统，可用于后续分析。",
                "status_label": "已准备" if survey_metrics["data_synced"] else "待准备",
                "tone": "success" if survey_metrics["data_synced"] else "warning",
            },
            {
                "label": "当前状态",
                "note": tasks.get("freeze", {}).get("block_reason", "确认后将锁定本轮分析所用样本，并进入报告准备。"),
                "status_label": task_status_label(freeze_status),
                "tone": _task_tone(freeze_status),
            },
        ]
    )

    if freeze_status == "completed":
        render_key_value_table(
            [
                ("确认结果", "已完成"),
                ("锁定样本", str(survey_metrics["scanned_count"])),
                ("下一步", "前往分析报告"),
            ],
            columns=3,
        )
        done_cols = st.columns(2)
        if done_cols[0].button("进入分析报告", type="primary", use_container_width=True):
            st.session_state["console_page"] = "分析报告"
            st.rerun()
        if done_cols[1].button("查看运行记录", use_container_width=True):
            st.session_state["console_page"] = "运行记录"
            st.rerun()
    else:
        if tasks.get("freeze", {}).get("block_reason"):
            st.caption(f"当前还不能确认分析样本：{tasks['freeze']['block_reason']}")
        if st.button(
            "确认分析样本",
            type="primary",
            disabled=freeze_status == "blocked",
            use_container_width=True,
        ):
            st.session_state["freeze_confirm_open"] = True
        if st.session_state.get("freeze_confirm_open"):
            st.info("确认后系统会锁定本轮分析所用样本，并进入报告准备阶段。")
            confirm_cols = st.columns(2)
            if confirm_cols[0].button("确认", type="primary", use_container_width=True):
                _run_freeze(bundle)
            if confirm_cols[1].button("取消", use_container_width=True):
                st.session_state["freeze_confirm_open"] = False
                st.rerun()


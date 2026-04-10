from __future__ import annotations

import streamlit as st

from evaluation_system.components import render_checklist, render_key_value_table, render_page_header
from evaluation_system.runner import execute_action
from evaluation_system.state_store import available_report_export_paths, build_export_zip, set_console_flash


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


def _task_tone(status: str) -> str:
    return TASK_TONES.get(str(status or "").strip(), "warning")


def _deliverable_status(row: dict, *, ready_text: str = "已准备", missing_text: str = "未准备") -> str:
    return ready_text if row.get("available") else missing_text


def _report_ready(report_manifest: dict, significance_manifest: dict, correlation_manifest: dict, report_summary: dict) -> bool:
    return all(
        [
            report_manifest.get("available"),
            significance_manifest.get("available"),
            correlation_manifest.get("available"),
            report_summary.get("available"),
        ]
    )


def _friendly_block_reason(reason: str) -> str:
    clean_reason = str(reason or "").strip()
    if not clean_reason:
        return "当前可以继续生成报告。"
    mapping = {
        "冻结样本尚未完成。": "请先确认本轮分析样本。",
        "问卷发放尚未完成。": "请先完成问卷发放准备。",
        "自动评测未完成。": "请先完成测评结果准备。",
    }
    return mapping.get(clean_reason, clean_reason)


def _progress_label(report_status: str, results_ready: bool) -> str:
    if results_ready:
        return "已生成"
    status = str(report_status or "").strip()
    mapping = {
        "completed": "已生成",
        "ready": "可生成",
        "running": "生成中",
        "in_progress": "生成中",
        "blocked": "暂不可生成",
        "failed": "生成失败",
        "not_started": "待开始",
    }
    return mapping.get(status, "待开始")


def _next_step_text(report_status: str, results_ready: bool, block_reason: str) -> str:
    if results_ready:
        return "报告已经准备完成，可以直接查看或导出。"
    status = str(report_status or "").strip()
    if status in {"running", "in_progress"}:
        return "报告正在生成中，请稍后刷新查看。"
    if status == "blocked":
        return _friendly_block_reason(block_reason)
    if status == "failed":
        return "本次报告生成未完成，建议查看处理记录后重新生成。"
    return "当前可以开始生成报告。"


def _run_report_generation() -> None:
    with st.spinner("正在生成报告结果..."):
        result = execute_action(
            "generate_analysis_report",
            operator=st.session_state["console_role"],
            note="从分析报告页发起",
        )
    set_console_flash(result["message"], "success" if result["status"] == "success" else "danger")
    if result["status"] == "success":
        st.session_state["console_page"] = "运行记录"
    st.cache_data.clear()
    st.rerun()


def render(bundle: dict, *, show_header: bool = True) -> None:
    if show_header:
        render_page_header("分析报告", "查看当前批次的报告准备情况，生成并导出报告。")

    tasks = bundle.get("tasks", {})
    report_task = tasks.get("report", {})
    report_status = str(report_task.get("status") or "not_started")
    export_paths = available_report_export_paths()
    subset_manifest = _deliverable(bundle, "subset_manifest")
    master_manifest = _deliverable(bundle, "master_manifest")
    report_manifest = _deliverable(bundle, "report_manifest")
    significance_manifest = _deliverable(bundle, "significance_manifest")
    correlation_manifest = _deliverable(bundle, "correlation_manifest")
    report_summary = _deliverable(bundle, "report_summary")
    results_ready = _report_ready(report_manifest, significance_manifest, correlation_manifest, report_summary)
    next_step = _next_step_text(report_status, results_ready, report_task.get("block_reason", ""))

    render_key_value_table(
        [
            ("当前批次", bundle["settings"]["batch_name"]),
            ("样本范围", _deliverable_status(subset_manifest, ready_text="已确认", missing_text="待确认")),
            ("结果数据", _deliverable_status(master_manifest, ready_text="已准备", missing_text="待准备")),
            ("报告进度", _progress_label(report_status, results_ready)),
            ("报告内容", _deliverable_status(report_manifest, ready_text="已生成", missing_text="未生成")),
            ("下载准备", "可下载" if export_paths else "待准备"),
        ],
        columns=3,
    )

    top_cols = st.columns([1.05, 0.95], gap="large")
    with top_cols[0]:
        st.markdown("### 开始前确认")
        render_checklist(
            [
                {
                    "label": "样本范围已确认",
                    "note": "当前批次的分析对象已经确定。",
                    "status_label": "已完成" if subset_manifest.get("available") else "待完成",
                    "tone": "success" if subset_manifest.get("available") else "danger",
                },
                {
                    "label": "结果数据已准备",
                    "note": "生成报告所需的结果数据已经准备完成。",
                    "status_label": "已完成" if master_manifest.get("available") else "待完成",
                    "tone": "success" if master_manifest.get("available") else "danger",
                },
                {
                    "label": "当前进度",
                    "note": next_step,
                    "status_label": _progress_label(report_status, results_ready),
                    "tone": _task_tone(report_status) if not results_ready else "success",
                },
                {
                    "label": "可查看内容",
                    "note": "报告正文、比较结果、关联结果和摘要会统一在这里准备。",
                    "status_label": "已就绪" if results_ready else "准备中",
                    "tone": "success" if results_ready else "warning",
                },
            ]
        )
        action_cols = st.columns(3)
        if action_cols[0].button("生成报告", type="primary", use_container_width=True, disabled=report_status == "blocked"):
            _run_report_generation()
        if action_cols[1].button("查看处理记录", use_container_width=True):
            st.session_state["console_page"] = "运行记录"
            st.rerun()
        action_cols[2].download_button(
            "下载全部报告材料",
            data=build_export_zip(export_paths),
            file_name="analysis_report_deliverables.zip",
            use_container_width=True,
            disabled=not export_paths,
        )
        if report_status == "blocked" and report_task.get("block_reason"):
            st.caption(f"完成前置准备后，才可以生成报告：{_friendly_block_reason(report_task['block_reason'])}")

    with top_cols[1]:
        st.markdown("### 已准备内容")
        deliverables = [
            ("报告正文", _deliverable_status(report_manifest, ready_text="已生成", missing_text="未生成")),
            ("比较结果", _deliverable_status(significance_manifest, ready_text="已生成", missing_text="未生成")),
            ("关联结果", _deliverable_status(correlation_manifest, ready_text="已生成", missing_text="未生成")),
            ("报告摘要", _deliverable_status(report_summary, ready_text="已生成", missing_text="未生成")),
        ]
        render_key_value_table(deliverables, columns=1)

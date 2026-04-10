from __future__ import annotations

import streamlit as st

from evaluation_system.components import render_empty_state, render_key_value_table, render_page_header, render_primary_action_panel, render_summary_band
from evaluation_system.runner import execute_action
from evaluation_system.state_store import set_console_flash, task_status_label


def _run_action(action_key: str, note: str) -> None:
    with st.spinner("正在执行结果相关操作..."):
        result = execute_action(
            action_key,
            operator=st.session_state["console_role"],
            note=note,
        )
    set_console_flash(result["message"], "success" if result["status"] == "success" else "danger")
    st.cache_data.clear()
    st.rerun()


def _has_final_results(bundle: dict) -> bool:
    report_summary = bundle.get("report_summary", {}) or {}
    deliverables = bundle.get("deliverables", {})
    return bool(
        report_summary.get("report_ready")
        or deliverables.get("report_manifest", {}).get("available")
        or deliverables.get("significance_manifest", {}).get("available")
        or deliverables.get("correlation_manifest", {}).get("available")
    )


def _next_result_action(bundle: dict) -> dict[str, str]:
    tasks = bundle.get("tasks", {})
    evaluation_task = tasks.get("evaluation", {})
    freeze_task = tasks.get("freeze", {})
    report_task = tasks.get("report", {})

    if evaluation_task.get("status") != "completed":
        return {
            "title": "先完成自动评测",
            "description": "结果尚未准备好。",
            "label": "开始自动评测",
            "action_key": "run_auto_evaluation",
            "disabled_reason": evaluation_task.get("block_reason", "") if evaluation_task.get("status") == "blocked" else "",
        }
    if freeze_task.get("status") != "completed":
        return {
            "title": "先冻结正式样本",
            "description": "结果尚未准备好。",
            "label": "前往问卷页",
            "action_key": "open_survey",
            "disabled_reason": freeze_task.get("block_reason", ""),
        }
    if report_task.get("status") != "completed":
        return {
            "title": "生成最终结果摘要",
            "description": "结果尚未准备好。",
            "label": "生成结果报告",
            "action_key": "generate_analysis_report",
            "disabled_reason": report_task.get("block_reason", "") if report_task.get("status") == "blocked" else "",
        }
    return {
        "title": "结果已准备完成",
        "description": "可以直接展示结果。",
        "label": "刷新结果",
        "action_key": "noop",
        "disabled_reason": "",
    }


def _render_pending_state(bundle: dict) -> None:
    tasks = bundle.get("tasks", {})
    action = _next_result_action(bundle)

    clicked = render_primary_action_panel(
        title=action["title"],
        description=action["description"],
        primary_label=action["label"],
        primary_key="results-primary-action",
        primary_disabled=bool(action["disabled_reason"] and action["action_key"] != "open_survey"),
        disabled_reason=action["disabled_reason"],
        secondary_actions=[
            {"label": "去问卷页", "key": "results-go-survey"},
            {"label": "回工作台", "key": "results-go-overview"},
        ],
    )
    if clicked.get("primary"):
        if action["action_key"] == "open_survey":
            st.session_state["console_page"] = "问卷"
            st.rerun()
        if action["action_key"] == "noop":
            st.rerun()
        _run_action(action["action_key"], "答辩模式 / 结果页")
    if clicked.get("results-go-survey"):
        st.session_state["console_page"] = "问卷"
        st.rerun()
    if clicked.get("results-go-overview"):
        st.session_state["console_page"] = "工作台"
        st.rerun()

    render_key_value_table(
        [
            ("自动评测", task_status_label(tasks.get("evaluation", {}).get("status", "not_started"))),
            ("样本冻结", task_status_label(tasks.get("freeze", {}).get("status", "not_started"))),
            ("结果摘要", task_status_label(tasks.get("report", {}).get("status", "not_started"))),
        ],
        columns=3,
    )
    render_empty_state("结果尚未生成", "先完成自动评测、样本冻结和结果摘要生成。")


def _render_ready_state(bundle: dict) -> None:
    tasks = bundle.get("tasks", {})
    report_summary = bundle.get("report_summary", {}) or {}
    survey_metrics = bundle.get("survey_metrics", {})
    curated_status = bundle.get("curated_analysis_status", {}) or {}
    deliverables = bundle.get("deliverables", {})

    render_summary_band(
        [
            {
                "label": "自动评测",
                "value": task_status_label(tasks.get("evaluation", {}).get("status", "not_started")),
                "note": "自动指标",
            },
            {
                "label": "正式样本",
                "value": str(survey_metrics.get("effective_samples", 0)),
                "note": "有效样本数",
            },
            {
                "label": "结果报告",
                "value": task_status_label(tasks.get("report", {}).get("status", "not_started")),
                "note": "最终结果",
            },
        ]
    )

    render_key_value_table(
        [
            ("自动评测状态", task_status_label(tasks.get("evaluation", {}).get("status", "not_started"))),
            ("指标结果", curated_status.get("status", "未生成")),
            ("正式题库", "已准备" if deliverables.get("final_pairs", {}).get("available") else "未准备"),
            ("统计输出", "已生成" if deliverables.get("significance_manifest", {}).get("available") else "未生成"),
            ("已提交问卷", str(survey_metrics.get("submitted_count", 0))),
            ("有效样本", str(survey_metrics.get("effective_samples", 0))),
            ("冻结阈值", str(survey_metrics.get("freeze_threshold", 0))),
            ("样本冻结", task_status_label(tasks.get("freeze", {}).get("status", "not_started"))),
        ],
        columns=4,
    )

    highlights = report_summary.get("highlights") or []
    if highlights:
        for line in highlights[:3]:
            st.markdown(f"- {line}")


def render(bundle: dict, *, show_header: bool = True) -> None:
    if show_header:
        render_page_header("结果", "查看当前状态或最终结果摘要。")

    if not _has_final_results(bundle):
        _render_pending_state(bundle)
        return

    _render_ready_state(bundle)
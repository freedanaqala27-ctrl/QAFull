from __future__ import annotations

import streamlit as st

from evaluation_system.components import render_checklist, render_key_value_table, render_page_header, render_primary_action_panel, render_summary_band
from evaluation_system.runner import execute_action
from evaluation_system.state_store import set_console_flash, task_status_label


def _run_action(action_key: str, note: str) -> None:
    with st.spinner("正在生成结果..."):
        result = execute_action(
            action_key,
            operator=st.session_state["console_role"],
            note=note,
        )
    set_console_flash(result["message"], "success" if result["status"] == "success" else "danger")
    st.cache_data.clear()
    st.rerun()


def _next_result_action(bundle: dict) -> dict[str, str]:
    tasks = bundle.get("tasks", {})
    evaluation_task = tasks.get("evaluation", {})
    freeze_task = tasks.get("freeze", {})
    report_task = tasks.get("report", {})

    if evaluation_task.get("status") != "completed":
        return {
            "title": "先完成自动评测",
            "description": "对正式题库执行参考解验证、功能正确性和自动指标计算。",
            "label": "开始自动评测",
            "action_key": "run_auto_evaluation",
            "disabled_reason": evaluation_task.get("block_reason", "") if evaluation_task.get("status") == "blocked" else "",
        }
    if freeze_task.get("status") != "completed":
        return {
            "title": "等待冻结正式样本",
            "description": "学生问卷样本尚未冻结，请先到“问卷”页完成样本确认。",
            "label": "先去问卷页",
            "action_key": "open_survey",
            "disabled_reason": freeze_task.get("block_reason", ""),
        }
    if report_task.get("status") != "completed":
        return {
            "title": "生成最终结果摘要",
            "description": "整合自动指标与学生评价输出答辩所需结果。",
            "label": "生成结果报告",
            "action_key": "generate_analysis_report",
            "disabled_reason": report_task.get("block_reason", "") if report_task.get("status") == "blocked" else "",
        }
    return {
        "title": "结果已准备完成",
        "description": "当前可以直接展示自动指标、学生问卷和最终结论。",
        "label": "查看结果摘要",
        "action_key": "noop",
        "disabled_reason": "",
    }


def render(bundle: dict, *, show_header: bool = True) -> None:
    if show_header:
        render_page_header("结果", "把自动评测、学生问卷和最终结论压缩成一页答辩摘要。")

    tasks = bundle.get("tasks", {})
    report_summary = bundle.get("report_summary", {}) or {}
    survey_metrics = bundle.get("survey_metrics", {})
    curated_status = bundle.get("curated_analysis_status", {}) or {}
    deliverables = bundle.get("deliverables", {})
    action = _next_result_action(bundle)

    render_summary_band(
        [
            {
                "label": "自动评测",
                "value": task_status_label(tasks.get("evaluation", {}).get("status", "not_started")),
                "note": "参考解验证、功能正确性与自动指标",
            },
            {
                "label": "正式样本",
                "value": str(survey_metrics.get("effective_samples", 0)),
                "note": "学生问卷有效样本数",
            },
            {
                "label": "结果报告",
                "value": task_status_label(tasks.get("report", {}).get("status", "not_started")),
                "note": "最终答辩摘要输出状态",
            },
        ]
    )

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

    st.markdown("### 自动指标摘要")
    render_key_value_table(
        [
            ("自动评测状态", task_status_label(tasks.get("evaluation", {}).get("status", "not_started"))),
            ("指标结果", curated_status.get("status", "未生成")),
            ("正式题库", "已准备" if deliverables.get("final_pairs", {}).get("available") else "未准备"),
            ("统计输出", "已生成" if deliverables.get("significance_manifest", {}).get("available") else "未生成"),
        ],
        columns=2,
    )

    st.markdown("### 学生问卷摘要")
    render_key_value_table(
        [
            ("已提交问卷", str(survey_metrics.get("submitted_count", 0))),
            ("有效样本", str(survey_metrics.get("effective_samples", 0))),
            ("冻结阈值", str(survey_metrics.get("freeze_threshold", 0))),
            ("样本冻结状态", task_status_label(tasks.get("freeze", {}).get("status", "not_started"))),
        ],
        columns=2,
    )

    st.markdown("### 最终结论摘要")
    highlights = report_summary.get("highlights") or []
    if not highlights:
        highlights = [
            "当前系统支持从受控生成、人工审核、问卷发放到结果分析的完整主线。",
            "完成自动评测和样本冻结后，系统即可输出正式结果摘要。",
        ]
    render_checklist(
        [
            {
                "label": f"摘要 {index}",
                "note": text,
                "status_label": "已准备",
                "tone": "success",
            }
            for index, text in enumerate(highlights, start=1)
        ]
    )

    if report_summary:
        st.markdown("### 结果数字概览")
        sample = report_summary.get("sample", {})
        significance = report_summary.get("significance", {})
        correlation = report_summary.get("correlation", {})
        render_key_value_table(
            [
                ("参与者", str(sample.get("participants", 0))),
                ("题目数", str(sample.get("unique_exercises", 0))),
                ("显著指标数", str(significance.get("significant_count", 0))),
                ("最高相关", str(correlation.get("top_spearman_r", "未记录") or "未记录")),
            ],
            columns=4,
        )
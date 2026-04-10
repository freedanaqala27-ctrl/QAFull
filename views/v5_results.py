from __future__ import annotations

import streamlit as st

from evaluation_system.components import (
    render_empty_state,
    render_key_value_table,
    render_page_header,
    render_primary_action_panel,
    render_summary_band,
)
from evaluation_system.runner import execute_action
from evaluation_system.state_store import set_console_flash, task_status_label


def _run_action(action_key: str, note: str) -> None:
    with st.spinner("正在执行自动评测..."):
        result = execute_action(
            action_key,
            operator=st.session_state["console_role"],
            note=note,
        )
    set_console_flash(result["message"], "success" if result["status"] == "success" else "danger")
    st.cache_data.clear()
    st.rerun()


def _render_pending_state(bundle: dict) -> None:
    tasks = bundle.get("tasks", {})
    evaluation_task = tasks.get("evaluation", {})
    disabled_reason = evaluation_task.get("block_reason", "") if evaluation_task.get("status") == "blocked" else ""

    clicked = render_primary_action_panel(
        title="先完成自动评测",
        description="结果页现在只保留自动评测和自动指标结果，不再展示问卷或人评结果。",
        primary_label="开始自动评测",
        primary_key="results-run-auto-evaluation",
        primary_disabled=bool(disabled_reason),
        disabled_reason=disabled_reason,
        secondary_actions=[
            {"label": "去生成页", "key": "results-go-generation"},
            {"label": "去审核页", "key": "results-go-review"},
        ],
    )
    if clicked.get("primary"):
        _run_action("run_auto_evaluation", "从结果页发起自动评测")
    if clicked.get("results-go-generation"):
        st.session_state["console_page"] = "生成"
        st.rerun()
    if clicked.get("results-go-review"):
        st.session_state["console_page"] = "审核"
        st.rerun()

    render_key_value_table(
        [
            ("自动评测", task_status_label(evaluation_task.get("status", "not_started"))),
            ("正式题库", "已准备" if bundle.get("deliverables", {}).get("final_pairs", {}).get("available") else "未准备"),
            ("结果状态", "待生成"),
        ],
        columns=3,
    )
    render_empty_state("自动指标结果尚未生成", "先完成自动评测，结果页才会显示自动指标状态摘要。")


def _render_ready_state(bundle: dict) -> None:
    tasks = bundle.get("tasks", {})
    review_summary = bundle.get("review_summary", {})
    deliverables = bundle.get("deliverables", {})
    analysis_status = bundle.get("curated_analysis_status", {}) or {}

    render_summary_band(
        [
            {
                "label": "自动评测",
                "value": task_status_label(tasks.get("evaluation", {}).get("status", "not_started")),
                "note": "自动评测链状态",
            },
            {
                "label": "正式题库",
                "value": str(review_summary.get("approved", 0)),
                "note": "已定稿题目数",
            },
            {
                "label": "自动指标",
                "value": str(analysis_status.get("status", "已完成")),
                "note": "自动指标状态",
            },
        ]
    )

    render_key_value_table(
        [
            ("自动评测状态", task_status_label(tasks.get("evaluation", {}).get("status", "not_started"))),
            ("正式题库", "已准备" if deliverables.get("final_pairs", {}).get("available") else "未准备"),
            ("参考答案", "已准备" if deliverables.get("evaluation_status", {}).get("available") else "未记录"),
            ("盲化映射", "已准备" if deliverables.get("blind_mapping", {}).get("available") else "未准备"),
            ("自动指标结果", str(analysis_status.get("status", "已完成"))),
            ("结果展示", "仅展示自动指标"),
        ],
        columns=3,
    )

    render_empty_state(
        "自动指标结果面板",
        "当前版本不回填历史结果文件，只保留自动评测状态和自动指标展示位置。完成新一轮自动评测后，可在这里继续扩展具体指标摘要。",
    )


def render(bundle: dict) -> None:
    render_page_header("结果", "只展示自动评测状态和自动指标结果，不展示问卷或人评结果。")

    evaluation_status = bundle.get("tasks", {}).get("evaluation", {}).get("status", "not_started")
    if evaluation_status != "completed":
        _render_pending_state(bundle)
        return

    _render_ready_state(bundle)
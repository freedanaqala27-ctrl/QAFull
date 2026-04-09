from __future__ import annotations

import streamlit as st

from evaluation_system.components import (
    render_key_value_table,
    render_page_header,
    render_stage_strip,
    render_summary_band,
)


def _stage_focus(stages: list[dict[str, str]]) -> tuple[str, str]:
    current_stage = next((stage for stage in stages if stage.get("status") != "completed"), None)
    blocked_labels = [stage.get("label", "") for stage in stages if stage.get("status") == "blocked"]
    current_text = current_stage.get("label", "全部阶段已完成") if current_stage else "全部阶段已完成"
    blocked_text = " / ".join([label for label in blocked_labels if label][:3]) or "当前没有阻塞阶段"
    return current_text, blocked_text



def render(bundle: dict) -> None:
    system_summary = bundle.get("system_summary", {})
    review_summary = bundle.get("review_summary", {})
    stages = bundle.get("stages", [])

    render_page_header("流程总览", "查看当前批次的流程状态与关键指标。")

    top_cols = st.columns([1.45, 1.15])
    with top_cols[0]:
        st.selectbox(
            "批次选择",
            bundle["batch_options"],
            key="console_batch",
            label_visibility="visible",
        )
    with top_cols[1]:
        st.caption("当前主线")
        st.markdown(f"**{bundle['settings']['current_mainline']}**")

    render_summary_band(
        [
            {
                "label": "当前批次",
                "value": system_summary.get("batch_name", bundle["settings"]["batch_name"]),
                "note": "当前使用中的业务批次。",
            },
            {
                "label": "待审核题目",
                "value": str(review_summary.get("pending", 0)),
                "note": "等待研究员处理的候选题数量。",
            },
            {
                "label": "有效样本",
                "value": str(system_summary.get("effective_samples", bundle["survey_metrics"].get("effective_samples", 0))),
                "note": "当前纳入正式分析的有效样本数。",
            },
            {
                "label": "报告状态",
                "value": "已生成" if system_summary.get("report_ready") else "未生成",
                "note": "当前批次的报告生成状态。",
            },
        ]
    )

    st.markdown("### 阶段总览")
    render_stage_strip(stages)

    current_focus, blocked_focus = _stage_focus(stages)
    st.markdown("### 当前节奏")
    st.info(f"当前推进阶段：{current_focus}\n\n阻塞阶段：{blocked_focus}")

    st.markdown("### 全局队列")
    render_key_value_table(
        [
            ("待审核", str(review_summary.get("pending", 0))),
            ("已通过", str(review_summary.get("approved", 0))),
            ("缺资产", str(review_summary.get("approved_missing_assets", review_summary.get("missing_assets", 0)))),
            ("已提交答卷", str(system_summary.get("submitted_count", 0))),
            ("有效样本", str(system_summary.get("effective_samples", 0))),
            ("失败任务", str(system_summary.get("failed_tasks", 0))),
            ("执行中工单", str(system_summary.get("open_work_orders", 0))),
            ("快照状态", "已发布" if system_summary.get("snapshot_ready") else "未发布"),
        ],
        columns=4,
    )


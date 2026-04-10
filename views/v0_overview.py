from __future__ import annotations

import streamlit as st

from evaluation_system.components import (
    render_page_header,
    render_primary_action_panel,
    render_summary_band,
)
from evaluation_system.runner import action_is_executable, execute_action
from evaluation_system.state_store import current_review_summary, set_console_flash, task_status_label

PAGE_GENERATION = "生成"
PAGE_REVIEW = "审核"
PAGE_RESULTS = "结果"


def _task(bundle: dict, task_key: str) -> dict:
    return bundle.get("tasks", {}).get(task_key, {})


def _run_action(action_key: str, note: str, target_page: str) -> None:
    with st.spinner("正在执行当前步骤..."):
        result = execute_action(
            action_key,
            operator=st.session_state["console_role"],
            note=note,
        )
    set_console_flash(result["message"], "success" if result["status"] == "success" else "danger")
    if result["status"] == "success":
        st.session_state["console_page"] = target_page
    st.cache_data.clear()
    st.rerun()


def _next_action(bundle: dict) -> dict[str, str]:
    review_summary = current_review_summary()
    generation_metrics = bundle.get("generation_metrics", {})
    generation_task = _task(bundle, "generation")
    review_task = _task(bundle, "review")
    evaluation_task = _task(bundle, "evaluation")

    if review_summary["total"] == 0 and not generation_metrics.get("generation_manifest"):
        return {
            "title": "生成候选题",
            "description": "开始新一轮受控生成。",
            "label": "开始生成",
            "action_key": "start_generation",
            "target_page": PAGE_GENERATION,
            "disabled_reason": generation_task.get("block_reason", "") if generation_task.get("status") == "blocked" else "",
        }
    if review_summary["pending"] > 0:
        return {
            "title": "进入审核",
            "description": f"当前待审核 {review_summary['pending']} 道。",
            "label": "进入审核",
            "action_key": "open_review",
            "target_page": PAGE_REVIEW,
            "disabled_reason": "",
        }
    if review_task.get("status") == "ready":
        return {
            "title": "执行定稿",
            "description": f"当前已通过 {review_summary.get('approved', 0)} 道。",
            "label": "执行定稿",
            "action_key": "finalize_review_batch",
            "target_page": PAGE_GENERATION,
            "disabled_reason": "",
        }
    if evaluation_task.get("status") != "completed":
        return {
            "title": "开始自动评测",
            "description": "执行自动评测与自动指标计算。",
            "label": "开始自动评测",
            "action_key": "run_auto_evaluation",
            "target_page": PAGE_RESULTS,
            "disabled_reason": evaluation_task.get("block_reason", "") if evaluation_task.get("status") == "blocked" else "",
        }
    return {
        "title": "查看结果",
        "description": "自动评测已完成。",
        "label": "查看结果",
        "action_key": "open_results",
        "target_page": PAGE_RESULTS,
        "disabled_reason": "",
    }


def render(bundle: dict) -> None:
    render_page_header("工作台", "自动化主线")

    review_summary = current_review_summary()
    tasks = bundle.get("tasks", {})
    action = _next_action(bundle)

    render_summary_band(
        [
            {"label": "候选题", "value": str(bundle.get("generation_metrics", {}).get("accepted_count", 0)), "note": "进入审核池"},
            {"label": "待审核", "value": str(review_summary.get("pending", 0)), "note": "当前队列"},
            {"label": "正式题库", "value": str(review_summary.get("approved", 0)), "note": "已通过"},
            {"label": "自动评测", "value": task_status_label(tasks.get("evaluation", {}).get("status", "not_started")), "note": "当前状态"},
        ]
    )

    clicked = render_primary_action_panel(
        title=action["title"],
        description=action["description"],
        primary_label=action["label"],
        primary_key="overview-primary-action",
        primary_disabled=bool(action["disabled_reason"]),
        disabled_reason=action["disabled_reason"],
        secondary_actions=[],
    )
    if clicked.get("primary"):
        if action["action_key"].startswith("open_") or not action_is_executable(action["action_key"]):
            st.session_state["console_page"] = action["target_page"]
            st.rerun()
        _run_action(action["action_key"], "从工作台发起", action["target_page"])
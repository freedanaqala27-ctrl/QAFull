from __future__ import annotations

import streamlit as st

from evaluation_system.components import render_empty_state, render_key_value_table, render_page_header, render_summary_band
from evaluation_system.state_store import (
    append_history,
    append_run_event,
    current_review_items,
    current_review_summary,
    exercise_type_label,
    set_console_flash,
    topic_label,
)

FILTER_OPTIONS = {
    "待审核": lambda item: item.get("review_status") == "pending_review",
    "全部": lambda item: True,
    "已通过": lambda item: item.get("review_status") == "approved",
}


def _current_item(filtered_items: list[dict]) -> dict | None:
    if not filtered_items:
        return None
    cursor = min(st.session_state.get("review_cursor", 0), len(filtered_items) - 1)
    st.session_state["review_cursor"] = max(cursor, 0)
    return filtered_items[st.session_state["review_cursor"]]


def _move_cursor(delta: int, filtered_items: list[dict]) -> None:
    if not filtered_items:
        return
    next_cursor = max(0, min(st.session_state.get("review_cursor", 0) + delta, len(filtered_items) - 1))
    st.session_state["review_cursor"] = next_cursor


def _requirements_text(item: dict) -> str:
    constraints = item.get("constraints") or []
    test_cases = item.get("test_cases") or []
    lines = [f"期望输出：{item.get('expected_output') or '未提供'}"]
    if constraints:
        lines.append("约束条件：")
        lines.extend([f"- {value}" for value in constraints])
    if test_cases:
        lines.append("测试要点：")
        for row in test_cases[:4]:
            if isinstance(row, dict):
                lines.append(f"- {row.get('description', '')}")
    return "\n".join(lines)


def _review_label(status: str) -> str:
    return {
        "pending_review": "待审核",
        "approved": "已通过",
        "rejected": "已驳回",
    }.get(str(status or ""), "处理中")


def _asset_ready_label(value: bool) -> str:
    return "已补" if value else "未补"


def _commit_state_change(item: dict, action_text: str, run_action_key: str, note: str = "") -> None:
    item["last_action"] = action_text
    append_history(item.get("candidate_id", ""), action_text, st.session_state["console_role"])
    append_run_event(run_action_key, operator=st.session_state["console_role"], note=note or item.get("candidate_id", ""))
    st.cache_data.clear()
    st.rerun()


def _render_asset_panel(item: dict) -> None:
    solution_ready = bool(item.get("solution_overlay_ready"))
    tests_ready = bool(item.get("tests_overlay_ready"))
    eval_ready = solution_ready and tests_ready and item.get("review_status") == "approved"

    render_summary_band(
        [
            {"label": "参考答案", "value": _asset_ready_label(solution_ready), "note": "solution overlay"},
            {"label": "测试材料", "value": _asset_ready_label(tests_ready), "note": "tests overlay"},
            {"label": "评测状态", "value": "可评测" if eval_ready else "待定稿补齐", "note": "自动评测前置条件"},
        ]
    )

    if item.get("review_status") == "approved" and not eval_ready:
        st.caption("该题已审核通过，评测资产会在“定稿入库”后自动补齐。")
    elif eval_ready:
        st.caption("该题的评测资产已经准备完成，可进入自动评测。")
    else:
        st.caption("请先完成审核；评测资产将在定稿入库后统一生成。")


def render(bundle: dict) -> None:
    render_page_header("审核", "审核候选题；通过后在定稿入库阶段自动补齐评测资产。")

    review_summary = current_review_summary()
    review_task = bundle.get("tasks", {}).get("review", {})
    items = current_review_items()

    render_key_value_table(
        [
            ("待审核", str(review_summary.get("pending", 0))),
            ("已通过", str(review_summary.get("approved", 0))),
            ("已驳回", str(review_summary.get("rejected", 0))),
            ("缺评测材料", str(review_summary.get("approved_missing_assets", review_summary.get("missing_assets", 0)))),
        ],
        columns=4,
    )

    filter_name = st.radio("筛选", list(FILTER_OPTIONS.keys()), horizontal=True, key="review-filter")
    filtered_items = [item for item in items if FILTER_OPTIONS[filter_name](item)]
    current_item = _current_item(filtered_items)
    if current_item is None:
        render_empty_state("没有可显示的候选题", "先回到生成页继续生成，或切换筛选条件。")
        return

    render_key_value_table(
        [
            ("状态", _review_label(current_item.get("review_status", ""))),
            ("主题", topic_label(current_item.get("topic", ""))),
            ("题型", exercise_type_label(current_item.get("exercise_type", ""))),
            ("参考题", current_item.get("reference_id", "未提供") or "未提供"),
        ],
        columns=2,
    )

    _render_asset_panel(current_item)

    st.text_input("题目标题", value=current_item.get("title", ""), disabled=True)
    st.text_area("题目说明", value=current_item.get("instruction", ""), height=220, disabled=True)
    st.text_area("作答要求", value=_requirements_text(current_item), height=180, disabled=True)
    with st.expander("起始代码", expanded=False):
        st.code(current_item.get("starter_code") or "当前候选题没有附带起始代码。", language="python")

    action_cols = st.columns(5)
    approve_clicked = action_cols[0].button("通过", type="primary", use_container_width=True)
    reject_clicked = action_cols[1].button("驳回", use_container_width=True)
    regenerate_clicked = action_cols[2].button("打回重生成", use_container_width=True)
    prev_clicked = action_cols[3].button("上一题", use_container_width=True)
    next_clicked = action_cols[4].button("下一题", use_container_width=True)

    if approve_clicked:
        current_item["review_status"] = "approved"
        current_item["solution_overlay_ready"] = False
        current_item["tests_overlay_ready"] = False
        current_item["eval_status"] = "not_ready"
        set_console_flash("审核通过，评测资产将在定稿入库后自动补齐。", "success")
        _commit_state_change(current_item, "审核通过", "approve_candidate", note=current_item.get("candidate_id", ""))
    if reject_clicked:
        current_item["review_status"] = "rejected"
        current_item["solution_overlay_ready"] = False
        current_item["tests_overlay_ready"] = False
        current_item["eval_status"] = "not_ready"
        set_console_flash("审核驳回。", "warning")
        _commit_state_change(current_item, "审核驳回", "reject_candidate")
    if regenerate_clicked:
        current_item["review_status"] = "rejected"
        current_item["solution_overlay_ready"] = False
        current_item["tests_overlay_ready"] = False
        current_item["eval_status"] = "not_ready"
        set_console_flash("已打回重生成。", "warning")
        _commit_state_change(current_item, "打回重生成", "regenerate_candidate")
    if prev_clicked:
        _move_cursor(-1, filtered_items)
        st.rerun()
    if next_clicked:
        _move_cursor(1, filtered_items)
        st.rerun()

    if st.button("回生成页", use_container_width=True):
        st.session_state["console_page"] = "生成"
        st.rerun()

    if review_task.get("status") == "ready":
        st.caption("审核队列已清空，可以回到生成页执行定稿入库。")
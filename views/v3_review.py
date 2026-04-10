from __future__ import annotations

import streamlit as st

from evaluation_system.components import render_empty_state, render_key_value_table, render_page_header, render_summary_band
from evaluation_system.runner import execute_action
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
ASSET_OPTIONS = ["补全代码", "模型修正", "概念转代码", "模型构建", "训练分析"]
EXERCISE_TO_ASSET = {
    "Code Completion": "补全代码",
    "code completion": "补全代码",
    "Model Revision": "模型修正",
    "model revision": "模型修正",
    "Model Building": "模型构建",
    "model building": "模型构建",
    "Training Analysis": "训练分析",
    "training-analysis": "训练分析",
    "Concept to Code": "概念转代码",
    "concept to code": "概念转代码",
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


def _run_asset_request(
    item: dict,
    asset_type: str,
    asset_note: str,
    *,
    rerun_on_finish: bool = True,
) -> dict[str, str]:
    with st.spinner(f"正在自动补评测材料：{asset_type}..."):
        result = execute_action(
            "request_assets",
            operator=st.session_state["console_role"],
            note=f"{item.get('candidate_id', '')} / {asset_type} / {asset_note}",
            params={
                "asset_type": asset_type,
                "candidate_id": item.get("candidate_id", ""),
                "review_id": item.get("review_id", ""),
                "asset_note": asset_note,
            },
        )
    if result["status"] == "success":
        item["solution_overlay_ready"] = True
        item["tests_overlay_ready"] = True
        item["eval_status"] = "ready"
        append_history(
            item.get("candidate_id", ""),
            f"自动补评测材料：{asset_type}",
            st.session_state["console_role"],
        )
    if rerun_on_finish:
        set_console_flash(result["message"], "success" if result["status"] == "success" else "danger")
        st.cache_data.clear()
        st.rerun()
    return result


def _render_asset_panel(item: dict) -> None:
    solution_ready = bool(item.get("solution_overlay_ready"))
    tests_ready = bool(item.get("tests_overlay_ready"))
    needs_assets = item.get("review_status") == "approved" and (not solution_ready or not tests_ready)

    render_summary_band(
        [
            {"label": "参考答案", "value": _asset_ready_label(solution_ready), "note": "solution overlay"},
            {"label": "测试材料", "value": _asset_ready_label(tests_ready), "note": "tests overlay"},
            {"label": "评测状态", "value": "可评测" if item.get("eval_status") == "ready" else "待补材料", "note": "自动评测前置条件"},
        ]
    )

    if needs_assets:
        suggested_asset = EXERCISE_TO_ASSET.get(str(item.get("exercise_type") or ""), ASSET_OPTIONS[0])
        st.caption(f"这道题在审核通过后会自动补评测材料，默认类型：{suggested_asset}。")
    else:
        st.caption("当前题目不需要补材料，或尚未审核通过。")


def render(bundle: dict) -> None:
    render_page_header("审核", "审核候选题，并在通过时自动补评测材料。")

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
        auto_asset_result = None
        if (not current_item.get("solution_overlay_ready")) or (not current_item.get("tests_overlay_ready")):
            asset_type = EXERCISE_TO_ASSET.get(str(current_item.get("exercise_type") or ""), ASSET_OPTIONS[0])
            auto_asset_result = _run_asset_request(
                current_item,
                asset_type,
                "审核通过后自动补评测材料",
                rerun_on_finish=False,
            )
        current_item["eval_status"] = "ready" if current_item.get("solution_overlay_ready") and current_item.get("tests_overlay_ready") else "not_ready"
        if auto_asset_result:
            set_console_flash(
                "审核通过，已自动触发评测材料补全。"
                if auto_asset_result.get("status") == "success"
                else f"审核通过，但自动补材料失败：{auto_asset_result.get('message', '')}",
                "success" if auto_asset_result.get("status") == "success" else "warning",
            )
        else:
            set_console_flash("审核通过。", "success")
        _commit_state_change(current_item, "审核通过", "approve_candidate", note=current_item.get("candidate_id", ""))
    if reject_clicked:
        current_item["review_status"] = "rejected"
        current_item["eval_status"] = "not_ready"
        set_console_flash("审核驳回。", "warning")
        _commit_state_change(current_item, "审核驳回", "reject_candidate")
    if regenerate_clicked:
        current_item["review_status"] = "rejected"
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
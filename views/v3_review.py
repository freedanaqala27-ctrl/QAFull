from __future__ import annotations

import streamlit as st

from evaluation_system.components import render_checklist, render_empty_state, render_key_value_table, render_page_header
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
    "概念转代码": "概念转代码",
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


def _commit_state_change(item: dict, action_text: str, run_action_key: str, note: str = "") -> None:
    item["last_action"] = action_text
    append_history(item.get("candidate_id", ""), action_text, st.session_state["console_role"])
    append_run_event(run_action_key, operator=st.session_state["console_role"], note=note or item.get("candidate_id", ""))
    set_console_flash(f"{item.get('candidate_id', '当前题目')} 已更新为“{action_text}”。")
    st.cache_data.clear()
    st.rerun()


def _run_asset_request(item: dict, asset_type: str, asset_note: str) -> None:
    with st.spinner(f"正在补齐评测材料：{asset_type}..."):
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
        append_history(item.get("candidate_id", ""), f"补齐评测材料：{asset_type}", st.session_state["console_role"])
    set_console_flash(result["message"], "success" if result["status"] == "success" else "danger")
    st.cache_data.clear()
    st.rerun()


def render(bundle: dict) -> None:
    render_page_header("审核", "只保留候选题预览、通过/驳回和定稿前必要判断。")

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

    if review_task.get("status") == "ready":
        st.success("审核队列已清空，可以回到“生成”页执行定稿入库。")

    filter_name = st.radio("当前查看", list(FILTER_OPTIONS.keys()), horizontal=True, key="review-filter")
    filtered_items = [item for item in items if FILTER_OPTIONS[filter_name](item)]
    current_item = _current_item(filtered_items)
    if current_item is None:
        render_empty_state("当前没有可展示的候选题", "可以切换筛选条件，或先回到“生成”页重新生成候选题。")
        return

    st.markdown("### 当前候选题")
    render_key_value_table(
        [
            ("当前状态", _review_label(current_item.get("review_status", ""))),
            ("主题", topic_label(current_item.get("topic", ""))),
            ("题型", exercise_type_label(current_item.get("exercise_type", ""))),
            ("参考题", current_item.get("reference_id", "未提供") or "未提供"),
        ],
        columns=2,
    )
    st.text_input("题目标题", value=current_item.get("title", ""), disabled=True)
    st.text_area("题目说明", value=current_item.get("instruction", ""), height=220, disabled=True)
    st.text_area("作答要求", value=_requirements_text(current_item), height=180, disabled=True)
    with st.expander("查看起始代码", expanded=False):
        st.code(current_item.get("starter_code") or "当前候选题没有附带起始代码。", language="python")

    st.markdown("### 审核动作")
    action_cols = st.columns(5)
    approve_clicked = action_cols[0].button("通过", type="primary", use_container_width=True)
    reject_clicked = action_cols[1].button("驳回", use_container_width=True)
    regenerate_clicked = action_cols[2].button("打回重生成", use_container_width=True)
    prev_clicked = action_cols[3].button("上一题", use_container_width=True)
    next_clicked = action_cols[4].button("下一题", use_container_width=True)

    if approve_clicked:
        current_item["review_status"] = "approved"
        current_item["eval_status"] = "ready" if current_item.get("solution_overlay_ready") and current_item.get("tests_overlay_ready") else "not_ready"
        _commit_state_change(current_item, "审核通过", "approve_candidate")
    if reject_clicked:
        current_item["review_status"] = "rejected"
        current_item["eval_status"] = "not_ready"
        _commit_state_change(current_item, "审核驳回", "reject_candidate")
    if regenerate_clicked:
        current_item["review_status"] = "rejected"
        current_item["eval_status"] = "not_ready"
        _commit_state_change(current_item, "打回重生成", "regenerate_candidate")
    if prev_clicked:
        _move_cursor(-1, filtered_items)
        st.rerun()
    if next_clicked:
        _move_cursor(1, filtered_items)
        st.rerun()

    nav_cols = st.columns(2)
    if nav_cols[0].button("回到生成页定稿", use_container_width=True):
        st.session_state["console_page"] = "生成"
        st.rerun()
    if nav_cols[1].button("转到问卷页", use_container_width=True):
        st.session_state["console_page"] = "问卷"
        st.rerun()

    st.markdown("### 审核准备情况")
    render_checklist(
        [
            {
                "label": "人工审核",
                "note": "通过、驳回或打回重生成之后，候选题状态会立即更新。",
                "status_label": _review_label(current_item.get("review_status", "")),
                "tone": "success" if current_item.get("review_status") == "approved" else "warning",
            },
            {
                "label": "定稿入库",
                "note": "只有审核队列清空后，才能在“生成”页把通过题定稿入库。",
                "status_label": "可执行" if review_task.get("status") == "ready" else "等待审核完成",
                "tone": "success" if review_task.get("status") == "ready" else "warning",
            },
        ]
    )

    needs_assets = current_item.get("review_status") == "approved" and (
        (not current_item.get("solution_overlay_ready")) or (not current_item.get("tests_overlay_ready"))
    )
    with st.expander("低频操作：补评测材料", expanded=False):
        if not needs_assets:
            st.caption("当前题目不需要补充评测材料，或尚未审核通过。")
        else:
            suggested_asset = EXERCISE_TO_ASSET.get(str(current_item.get("exercise_type") or ""), ASSET_OPTIONS[0])
            suggested_index = ASSET_OPTIONS.index(suggested_asset) if suggested_asset in ASSET_OPTIONS else 0
            asset_cols = st.columns([1.0, 1.4])
            asset_type = asset_cols[0].selectbox("材料类型", ASSET_OPTIONS, index=suggested_index, key="review-asset-type")
            asset_note = asset_cols[1].text_input("备注", key="review-asset-note")
            if st.button("提交补材料任务", use_container_width=True):
                _run_asset_request(current_item, asset_type, asset_note)
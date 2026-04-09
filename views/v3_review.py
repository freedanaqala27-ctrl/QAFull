from __future__ import annotations

import streamlit as st

from evaluation_system.components import (
    badge_html,
    render_checklist,
    render_empty_state,
    render_key_value_table,
    render_page_header,
)
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
    "全部": lambda item: True,
    "仅待处理": lambda item: item.get("review_status") == "pending_review",
    "仅已通过": lambda item: item.get("review_status") == "approved",
    "仅缺评测材料": lambda item: item.get("review_status") == "approved"
    and ((not item.get("solution_overlay_ready")) or (not item.get("tests_overlay_ready"))),
    "仅高风险": lambda item: str(item.get("difficulty") or "").lower() == "advanced" or not item.get("tests_overlay_ready"),
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
ASSET_TO_EXERCISE = {value: key for key, value in EXERCISE_TO_ASSET.items()}


def _queue_label(title: str, count: int, tone: str) -> str:
    return f"{badge_html(title, tone)}<strong>{count}</strong>"


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


def _commit_state_change(item: dict, action_text: str, run_action_key: str, *, note: str = "") -> None:
    item["last_action"] = action_text
    append_history(item.get("candidate_id", ""), action_text, st.session_state["console_role"])
    append_run_event(run_action_key, operator=st.session_state["console_role"], note=note or item.get("candidate_id", ""))
    set_console_flash(f"{item.get('candidate_id', '当前题目')} 已更新为“{action_text}”。")
    st.cache_data.clear()
    st.rerun()


def _requirements_text(item: dict) -> str:
    constraints = item.get("constraints") or []
    test_cases = item.get("test_cases") or []
    lines = [f"期望输出：{item.get('expected_output') or '未提供'}"]
    if constraints:
        lines.append("约束条件：")
        lines.extend([f"- {value}" for value in constraints])
    if test_cases:
        lines.append("测试要点：")
        for row in test_cases[:5]:
            if isinstance(row, dict):
                lines.append(
                    f"- {row.get('description', '')} | 输入：{row.get('input', '')} | 期望：{row.get('expected_output', '')}"
                )
    return "\n".join(lines)


def _asset_type_for_item(item: dict) -> str:
    return EXERCISE_TO_ASSET.get(str(item.get("exercise_type") or ""), "补全代码")


def _mark_asset_ready(asset_type: str) -> None:
    mapped_exercise_type = ASSET_TO_EXERCISE.get(asset_type, "")
    items = current_review_items()
    current_item = next((row for row in items if row.get("candidate_id") == st.session_state.get("review-current-candidate")), None)
    for item in items:
        same_type = EXERCISE_TO_ASSET.get(str(item.get("exercise_type") or "")) == asset_type or str(item.get("exercise_type") or "") == mapped_exercise_type
        if same_type and item.get("review_status") == "approved":
            item["solution_overlay_ready"] = True
            item["tests_overlay_ready"] = True
            item["eval_status"] = "ready"
    if current_item is not None:
        current_item["last_action"] = f"补齐评测材料：{asset_type}"


def _review_status_label(status: str) -> str:
    return {
        "pending_review": "待审核",
        "approved": "已通过",
        "rejected": "已驳回",
    }.get(str(status or ""), "处理中")


def render(bundle: dict) -> None:
    render_page_header("审核中心", "审核候选题，确认是否纳入正式题库，并补齐后续测评材料。")

    review_summary = current_review_summary()
    review_task = bundle.get("tasks", {}).get("review", {})
    queue_html = " ".join(
        [
            _queue_label("待处理", review_summary["pending"], "info"),
            _queue_label("待补评测材料", review_summary.get("approved_missing_assets", review_summary["missing_assets"]), "warning"),
            _queue_label("已通过", review_summary["approved"], "success"),
            _queue_label("已驳回", review_summary["rejected"], "danger"),
        ]
    )
    st.markdown(queue_html, unsafe_allow_html=True)
    if review_task.get("status") == "ready":
        st.success("审核队列已清空，可以前往“题目生成”页执行定稿入库。")
    elif review_task.get("status") == "completed":
        st.info("正式题库已更新。已通过题目如果缺少评测材料，可以继续在这里补齐。")

    filter_name = st.radio(
        "筛选条件",
        list(FILTER_OPTIONS.keys()),
        horizontal=True,
        key="review-filter",
    )
    items = current_review_items()
    filtered_items = [item for item in items if FILTER_OPTIONS[filter_name](item)]
    current_item = _current_item(filtered_items)
    if current_item is None:
        render_empty_state("当前没有待审核题目", "可以切换筛选条件，或等待新的候选题进入审核队列。")
        return
    st.session_state["review-current-candidate"] = current_item.get("candidate_id", "")

    st.markdown("### 题目概览")
    render_key_value_table(
        [
            ("当前状态", _review_status_label(current_item.get("review_status", ""))),
            ("参考来源", current_item.get("reference_id", "-") or "未提供"),
            ("知识主题", topic_label(current_item.get("topic", ""))),
            ("题型", exercise_type_label(current_item.get("exercise_type", ""))),
        ],
        columns=2,
    )
    st.text_input("题目标题", value=current_item.get("title", ""), disabled=True)

    st.markdown("### 题目说明")
    st.text_area("题目说明", value=current_item.get("instruction", ""), height=220, disabled=True, label_visibility="collapsed")

    st.markdown("### 作答要求")
    st.text_area("作答要求", value=_requirements_text(current_item), height=240, disabled=True, label_visibility="collapsed")

    st.markdown("### 评测准备")
    solution_ready = bool(current_item.get("solution_overlay_ready"))
    tests_ready = bool(current_item.get("tests_overlay_ready"))
    eval_ready = current_item.get("eval_status") == "ready"
    render_checklist(
        [
            {
                "label": "参考答案",
                "note": "用于后续结果核对与质量判断。",
                "status_label": "已准备" if solution_ready else "待补充",
                "tone": "success" if solution_ready else "warning",
            },
            {
                "label": "测评用例",
                "note": "用于后续自动评测与稳定性校验。",
                "status_label": "已准备" if tests_ready else "待补充",
                "tone": "success" if tests_ready else "warning",
            },
            {
                "label": "自动评测",
                "note": "材料齐全后，系统即可继续进入自动评测。",
                "status_label": "可继续" if eval_ready else "暂不可用",
                "tone": "info" if eval_ready else "warning",
            },
        ]
    )

    st.markdown("### 起始代码")
    starter_code = current_item.get("starter_code") or "当前候选题没有附带起始代码。"
    with st.expander("展开查看起始代码", expanded=False):
        st.code(starter_code, language="python")

    st.markdown("### 审核动作")
    action_cols = st.columns(4)
    approve_clicked = action_cols[0].button("通过", type="primary", use_container_width=True)
    reject_clicked = action_cols[1].button("驳回", use_container_width=True)
    regenerate_clicked = action_cols[2].button("打回重生成", use_container_width=True)
    asset_enabled = review_task.get("status") == "completed" and current_item.get("review_status") == "approved"
    asset_clicked = action_cols[3].button("补评测材料", use_container_width=True, disabled=not asset_enabled)
    if not asset_enabled:
        st.caption("补评测材料只对已定稿且已通过的题目开放。")

    nav_cols = st.columns(4)
    prev_clicked = nav_cols[0].button("上一题", use_container_width=True)
    next_clicked = nav_cols[1].button("下一题", use_container_width=True)
    record_clicked = nav_cols[2].button("查看运行记录", use_container_width=True)
    finalize_clicked = nav_cols[3].button("去题目生成页定稿", use_container_width=True)

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
    if asset_clicked:
        st.session_state["review-asset-open"] = True
    if prev_clicked:
        _move_cursor(-1, filtered_items)
        st.rerun()
    if next_clicked:
        _move_cursor(1, filtered_items)
        st.rerun()
    if record_clicked:
        st.session_state["console_page"] = "运行记录"
        st.rerun()
    if finalize_clicked:
        st.session_state["console_page"] = "题目生成"
        st.rerun()

    if st.session_state.get("review-asset-open"):
        st.markdown("### 补评测材料")
        suggested_asset = _asset_type_for_item(current_item)
        suggested_index = ASSET_OPTIONS.index(suggested_asset) if suggested_asset in ASSET_OPTIONS else 0
        asset_cols = st.columns([1.0, 1.2])
        asset_type = asset_cols[0].selectbox("材料类型", ASSET_OPTIONS, index=suggested_index, key="review-asset-type")
        asset_note = asset_cols[1].text_input("备注", key="review-asset-note")
        submit_cols = st.columns(2)
        if submit_cols[0].button("提交补材料任务", type="primary", use_container_width=True):
            with st.spinner(f"正在补齐材料：{asset_type}..."):
                result = execute_action(
                    "request_assets",
                    operator=st.session_state["console_role"],
                    note=f"{current_item.get('candidate_id', '')} / {asset_type} / {asset_note}",
                    params={
                        "asset_type": asset_type,
                        "candidate_id": current_item.get("candidate_id", ""),
                        "review_id": current_item.get("review_id", ""),
                        "asset_note": asset_note,
                    },
                )
            if result["status"] == "success":
                _mark_asset_ready(asset_type)
                append_history(
                    current_item.get("candidate_id", ""),
                    f"补齐评测材料：{asset_type}",
                    st.session_state["console_role"],
                )
                st.session_state["review-asset-open"] = False
            set_console_flash(result["message"], "success" if result["status"] == "success" else "danger")
            st.cache_data.clear()
            st.rerun()
        if submit_cols[1].button("取消", use_container_width=True):
            st.session_state["review-asset-open"] = False
            st.rerun()





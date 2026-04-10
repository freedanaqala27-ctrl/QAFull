from __future__ import annotations

from datetime import datetime

import streamlit as st

from evaluation_system.components import render_key_value_table, render_page_header
from evaluation_system.runner import execute_action
from evaluation_system.state_store import difficulty_label, exercise_type_label, set_console_flash, task_status_label, topic_label

TOPIC_OPTIONS = ["", "CNN", "RNN", "Transformer", "Optimization"]
DIFFICULTY_OPTIONS = ["", "Beginner", "Intermediate", "Advanced"]
EXERCISE_TYPE_OPTIONS = ["", "code completion", "model building", "model revision", "training-analysis"]
PROVIDER_OPTIONS = ["bailian", "mock"]


def _init_form(bundle: dict) -> None:
    defaults = dict(bundle.get("generation_config", {}))
    if not str(defaults.get("generation_batch") or "").strip():
        defaults["generation_batch"] = datetime.now().strftime("batch-%Y%m%d-%H%M%S")
    defaults.setdefault("prompt_version", "MP-v1")
    defaults.setdefault("provider", "bailian")
    defaults.setdefault("model", "qwen-plus")
    defaults.setdefault("num_candidates", 1)
    defaults.setdefault("batch_limit", 12)
    for key, value in defaults.items():
        session_key = f"generation-{key}"
        if session_key not in st.session_state:
            st.session_state[session_key] = value
    if "generation-batch_limit" not in st.session_state:
        st.session_state["generation-batch_limit"] = 12


def _base_params() -> dict:
    generation_batch = str(st.session_state.get("generation-generation_batch") or "").strip()
    if not generation_batch:
        generation_batch = datetime.now().strftime("batch-%Y%m%d-%H%M%S")
    return {
        "prompt_version": str(st.session_state.get("generation-prompt_version") or "MP-v1").strip() or "MP-v1",
        "topic": str(st.session_state.get("generation-topic") or "").strip(),
        "difficulty": str(st.session_state.get("generation-difficulty") or "").strip(),
        "exercise_type": str(st.session_state.get("generation-exercise_type") or "").strip(),
        "reference_id": str(st.session_state.get("generation-reference_id") or "").strip(),
        "provider": str(st.session_state.get("generation-provider") or "bailian").strip() or "bailian",
        "model": str(st.session_state.get("generation-model") or "qwen-plus").strip() or "qwen-plus",
        "generation_batch": generation_batch,
        "num_candidates": int(st.session_state.get("generation-num_candidates") or 1),
        "temperature": 0.7,
        "max_tokens": 2200,
        "strict_filter": False,
        "min_instruction_completeness": None,
        "min_structure_completeness": None,
        "min_objective_overlap": None,
    }


def _run_generation(*, batch_mode: bool) -> None:
    params = _base_params()
    if batch_mode:
        params["limit"] = int(st.session_state.get("generation-batch_limit") or 12)
        note = f"答辩模式批量生成 / {params['generation_batch']}"
        spinner_text = "正在批量生成候选题并执行自动筛选..."
    else:
        params["limit"] = 1
        note = f"答辩模式单题生成 / {params['generation_batch']}"
        spinner_text = "正在生成一道候选题并执行自动筛选..."

    with st.spinner(spinner_text):
        result = execute_action(
            "start_generation",
            operator=st.session_state["console_role"],
            note=note,
            params=params,
        )
    set_console_flash(result["message"], "success" if result["status"] == "success" else "danger")
    st.cache_data.clear()
    st.rerun()


def _run_finalize() -> None:
    with st.spinner("正在将审核通过题目定稿入库..."):
        result = execute_action(
            "finalize_review_batch",
            operator=st.session_state["console_role"],
            note="答辩模式 / 定稿入库",
        )
    set_console_flash(result["message"], "success" if result["status"] == "success" else "danger")
    st.cache_data.clear()
    st.rerun()


def render(bundle: dict) -> None:
    _init_form(bundle)
    render_page_header("生成", "配置模型与范围，生成候选题并进入后续审核流程。")

    tasks = bundle.get("tasks", {})
    generation_task = tasks.get("generation", {})
    review_task = tasks.get("review", {})
    metrics = bundle.get("generation_metrics", {})
    review_summary = bundle.get("review_summary", {})

    render_key_value_table(
        [
            ("生成状态", task_status_label(generation_task.get("status", "not_started"))),
            ("候选题数量", str(metrics.get("accepted_count", 0))),
            ("待审核", str(review_summary.get("pending", 0))),
            ("已通过", str(review_summary.get("approved", 0))),
            ("正式题库", "已更新" if metrics.get("final_pairs_ready") else "未更新"),
            ("盲化映射", "已准备" if metrics.get("blind_mapping_ready") else "未准备"),
        ],
        columns=3,
    )

    st.markdown("### 生成配置")
    cols = st.columns(2)
    cols[0].text_input("模板版本", key="generation-prompt_version")
    cols[1].selectbox("Provider", PROVIDER_OPTIONS, key="generation-provider")
    cols[0].selectbox(
        "主题",
        TOPIC_OPTIONS,
        format_func=lambda value: "全部主题" if not value else topic_label(value),
        key="generation-topic",
    )
    cols[1].selectbox(
        "难度",
        DIFFICULTY_OPTIONS,
        format_func=lambda value: "全部难度" if not value else difficulty_label(value),
        key="generation-difficulty",
    )
    cols[0].selectbox(
        "题型",
        EXERCISE_TYPE_OPTIONS,
        format_func=lambda value: "全部题型" if not value else exercise_type_label(value),
        key="generation-exercise_type",
    )
    cols[1].text_input("模型名称", key="generation-model")
    cols[0].number_input("每题候选数", min_value=1, step=1, key="generation-num_candidates")
    cols[1].number_input("批量生成题数", min_value=1, step=1, key="generation-batch_limit")
    st.text_input("参考题编号（可选）", key="generation-reference_id")
    with st.expander("可选限制", expanded=False):
        st.text_input("生成批次", key="generation-generation_batch")

    st.markdown("### 生成动作")
    action_cols = st.columns(4)
    batch_disabled = bool(str(st.session_state.get("generation-reference_id") or "").strip())
    if action_cols[0].button("生成一道", type="primary", use_container_width=True):
        _run_generation(batch_mode=False)
    if action_cols[1].button("批量生成", use_container_width=True, disabled=batch_disabled):
        _run_generation(batch_mode=True)
    if action_cols[2].button("进入审核", use_container_width=True):
        st.session_state["console_page"] = "审核"
        st.rerun()
    finalize_disabled = review_task.get("status") not in {"ready", "failed"}
    if action_cols[3].button("定稿入库", use_container_width=True, disabled=finalize_disabled):
        _run_finalize()

    if batch_disabled:
        st.caption("批量生成时请留空“参考题编号”。")
    if finalize_disabled and review_task.get("block_reason"):
        st.caption(f"当前暂不能定稿：{review_task['block_reason']}")
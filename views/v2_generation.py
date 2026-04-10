from __future__ import annotations

from datetime import datetime

import streamlit as st

from evaluation_system.components import render_checklist, render_key_value_table, render_page_header
from evaluation_system.runner import execute_action
from evaluation_system.state_store import (
    difficulty_label,
    exercise_type_label,
    set_console_flash,
    task_status_label,
    topic_label,
)

TOPIC_OPTIONS = ["", "CNN", "RNN", "Transformer", "Optimization"]
DIFFICULTY_OPTIONS = ["", "Beginner", "Intermediate", "Advanced"]
EXERCISE_TYPE_OPTIONS = ["", "code completion", "model building", "model revision", "training-analysis"]
PROVIDER_OPTIONS = ["bailian", "mock"]


TASK_TONES = {
    "completed": "success",
    "ready": "success",
    "running": "warning",
    "in_progress": "warning",
    "failed": "danger",
    "blocked": "danger",
    "not_started": "warning",
}


def _task_tone(status: str) -> str:
    return TASK_TONES.get(str(status or "").strip(), "warning")


def _init_form(bundle: dict) -> None:
    defaults = dict(bundle.get("generation_config", {}))
    if not str(defaults.get("generation_batch") or "").strip():
        defaults["generation_batch"] = datetime.now().strftime("batch-%Y%m%d-%H%M%S")
    exercise_type = str(defaults.get("exercise_type") or "").strip()
    defaults["exercise_type"] = {
        "Code Completion": "code completion",
        "Model Building": "model building",
        "Model Revision": "model revision",
        "Training Analysis": "training-analysis",
    }.get(exercise_type, exercise_type)
    difficulty = str(defaults.get("difficulty") or "").strip()
    defaults["difficulty"] = {
        "beginner": "Beginner",
        "intermediate": "Intermediate",
        "advanced": "Advanced",
    }.get(difficulty, difficulty)
    provider = str(defaults.get("provider") or "bailian").strip()
    defaults["provider"] = provider if provider in PROVIDER_OPTIONS else PROVIDER_OPTIONS[0]
    for key, value in defaults.items():
        session_key = f"generation-{key}"
        if session_key not in st.session_state:
            st.session_state[session_key] = value


def _build_params() -> dict:
    generation_batch = str(st.session_state.get("generation-generation_batch") or "").strip()
    if not generation_batch:
        generation_batch = datetime.now().strftime("batch-%Y%m%d-%H%M%S")

    def _optional_float(key: str) -> float | None:
        raw = str(st.session_state.get(key) or "").strip()
        return float(raw) if raw else None

    return {
        "prompt_version": str(st.session_state.get("generation-prompt_version") or "MP-v1").strip() or "MP-v1",
        "topic": str(st.session_state.get("generation-topic") or "").strip(),
        "difficulty": str(st.session_state.get("generation-difficulty") or "").strip(),
        "exercise_type": str(st.session_state.get("generation-exercise_type") or "").strip(),
        "reference_id": str(st.session_state.get("generation-reference_id") or "").strip(),
        "provider": str(st.session_state.get("generation-provider") or "bailian").strip() or "bailian",
        "model": str(st.session_state.get("generation-model") or "qwen-plus").strip() or "qwen-plus",
        "generation_batch": generation_batch,
        "num_candidates": int(st.session_state.get("generation-num_candidates") or 2),
        "temperature": float(st.session_state.get("generation-temperature") or 0.7),
        "max_tokens": int(st.session_state.get("generation-max_tokens") or 2200),
        "limit": int(st.session_state.get("generation-limit") or 0),
        "strict_filter": bool(st.session_state.get("generation-strict_filter") or False),
        "min_instruction_completeness": _optional_float("generation-min_instruction_completeness"),
        "min_structure_completeness": _optional_float("generation-min_structure_completeness"),
        "min_objective_overlap": _optional_float("generation-min_objective_overlap"),
    }


def _run_generation() -> None:
    params = _build_params()
    with st.spinner("正在执行题目生成链..."):
        result = execute_action(
            "start_generation",
            operator=st.session_state["console_role"],
            note=f"题目生成 / {params['generation_batch']}",
            params=params,
        )
    set_console_flash(result["message"], "success" if result["status"] == "success" else "danger")
    st.cache_data.clear()
    st.rerun()


def _run_finalize() -> None:
    with st.spinner("正在执行定稿入库..."):
        result = execute_action(
            "finalize_review_batch",
            operator=st.session_state["console_role"],
            note="从题目生成页发起定稿入库",
        )
    set_console_flash(result["message"], "success" if result["status"] == "success" else "danger")
    st.cache_data.clear()
    st.rerun()


def _next_step_message(metrics: dict, review_summary: dict, review_task: dict) -> str:
    if review_summary.get("pending", 0) > 0:
        return f"当前还有 {review_summary['pending']} 道题待审核，建议先进入审核中心完成审核。"
    if review_task.get("status") in {"ready", "failed"}:
        return "人工审核已结束，可以执行定稿入库，更新正式题库。"
    if not metrics.get("final_pairs_ready"):
        return "正式题库尚未更新，完成定稿入库后才能继续后续流程。"
    return "题库已准备完成，可以继续安排自动评测与问卷发放。"


def render(bundle: dict) -> None:
    _init_form(bundle)
    render_page_header("题目生成", "配置模板、生成候选题并完成定稿入库。")

    tasks = bundle.get("tasks", {})
    generation_task = tasks.get("generation", {})
    review_task = tasks.get("review", {})
    metrics = bundle.get("generation_metrics", {})
    review_summary = bundle.get("review_summary", {})
    deliverables = bundle.get("deliverables", {})

    st.markdown("### 处理概况")
    render_key_value_table(
        [
            ("生成进度", task_status_label(generation_task.get("status", "not_started"))),
            ("题库状态", "已更新" if metrics.get("final_pairs_ready") else "待更新"),
            ("候选题数", str(metrics.get("accepted_count", 0))),
            ("待审核", str(review_summary.get("pending", 0))),
            ("已通过", str(review_summary.get("approved", 0))),
            ("待补评测材料", str(review_summary.get("approved_missing_assets", review_summary.get("missing_assets", 0)))),
        ],
        columns=3,
    )

    main_cols = st.columns([1.05, 0.95], gap="large")
    with main_cols[0]:
        st.markdown("### 生成配置")
        basic_cols = st.columns(2)
        basic_cols[0].text_input("模板版本", key="generation-prompt_version")
        basic_cols[1].text_input("生成批次", key="generation-generation_batch")
        basic_cols[0].selectbox(
            "主题过滤",
            TOPIC_OPTIONS,
            format_func=lambda value: "全部主题" if not value else topic_label(value),
            key="generation-topic",
        )
        basic_cols[1].selectbox(
            "难度过滤",
            DIFFICULTY_OPTIONS,
            format_func=lambda value: "全部难度" if not value else difficulty_label(value),
            key="generation-difficulty",
        )
        basic_cols[0].selectbox(
            "题型过滤",
            EXERCISE_TYPE_OPTIONS,
            format_func=lambda value: "全部题型" if not value else exercise_type_label(value),
            key="generation-exercise_type",
        )
        basic_cols[1].text_input("参考题编号", key="generation-reference_id")
        basic_cols[0].number_input("每题候选数", min_value=1, step=1, key="generation-num_candidates")
        basic_cols[1].number_input("最大提示条数", min_value=0, step=1, key="generation-limit")

        with st.expander("高级筛选", expanded=False):
            advanced_cols = st.columns(2)
            advanced_cols[0].number_input(
                "Temperature",
                min_value=0.0,
                max_value=2.0,
                step=0.1,
                key="generation-temperature",
            )
            advanced_cols[1].number_input("Max Tokens", min_value=256, step=128, key="generation-max_tokens")
            st.checkbox("启用严格过滤", key="generation-strict_filter")
            threshold_cols = st.columns(3)
            threshold_cols[0].text_input("最小题干完整度", key="generation-min_instruction_completeness")
            threshold_cols[1].text_input("最小结构完整度", key="generation-min_structure_completeness")
            threshold_cols[2].text_input("最小目标重叠度", key="generation-min_objective_overlap")

        action_cols = st.columns(3)
        if action_cols[0].button("生成候选题", type="primary", use_container_width=True):
            _run_generation()
        if action_cols[1].button("进入审核中心", use_container_width=True):
            st.session_state["console_page"] = "审核中心"
            st.rerun()
        finalize_disabled = review_task.get("status") not in {"ready", "failed"}
        if action_cols[2].button("定稿入库", use_container_width=True, disabled=finalize_disabled):
            _run_finalize()
        if finalize_disabled and review_task.get("block_reason"):
            st.caption(f"当前不能定稿入库：{review_task['block_reason']}")

    with main_cols[1]:
        st.markdown("### 当前准备情况")
        render_checklist(
            [
                {
                    "label": "候选题生成状态",
                    "note": "本轮候选题已经进入处理流程。",
                    "status_label": "已生成" if deliverables.get("generation_manifest", {}).get("available") else "未生成",
                    "tone": "success" if deliverables.get("generation_manifest", {}).get("available") else "warning",
                },
                {
                    "label": "人工审核状态",
                    "note": f"当前仍有 {review_summary.get('pending', 0)} 道题待审核。",
                    "status_label": "已完成"
                    if review_summary.get("pending", 0) == 0 and review_summary.get("total", 0) > 0
                    else "进行中",
                    "tone": "success"
                    if review_summary.get("pending", 0) == 0 and review_summary.get("total", 0) > 0
                    else "warning",
                },
                {
                    "label": "题库更新状态",
                    "note": review_task.get("block_reason", "审核完成后，可将已通过题目更新到正式题库。"),
                    "status_label": task_status_label(review_task.get("status", "not_started")),
                    "tone": _task_tone(review_task.get("status", "not_started")),
                },
                {
                    "label": "后续环节准备",
                    "note": "题库准备完成后，系统即可继续安排自动评测和问卷发放。",
                    "status_label": "已就绪" if metrics.get("final_pairs_ready") and metrics.get("blind_mapping_ready") else "待就绪",
                    "tone": "success" if metrics.get("final_pairs_ready") and metrics.get("blind_mapping_ready") else "warning",
                },
            ]
        )

        st.markdown("### 下一步建议")
        st.info(_next_step_message(metrics, review_summary, review_task))

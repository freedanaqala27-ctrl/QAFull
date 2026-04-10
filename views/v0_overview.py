from __future__ import annotations

import streamlit as st

from evaluation_system.components import (
    render_checklist,
    render_key_value_table,
    render_page_header,
    render_primary_action_panel,
    render_summary_band,
)
from evaluation_system.runner import action_is_executable, execute_action
from evaluation_system.state_store import current_review_summary, set_console_flash, task_status_label

PAGE_GENERATION = "生成"
PAGE_REVIEW = "审核"
PAGE_SURVEY = "问卷"
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
    survey_publish_task = _task(bundle, "survey_publish")
    freeze_task = _task(bundle, "freeze")
    report_task = _task(bundle, "report")

    if review_summary["total"] == 0 and not generation_metrics.get("generation_manifest"):
        return {
            "stage": "生成候选题",
            "description": "基于参考题与提示词模板生成候选题，并完成自动筛选。",
            "label": "开始生成",
            "action_key": "start_generation",
            "target_page": PAGE_GENERATION,
            "disabled_reason": generation_task.get("block_reason", "") if generation_task.get("status") == "blocked" else "",
        }
    if review_summary["pending"] > 0:
        return {
            "stage": "筛选与审核",
            "description": f"当前还有 {review_summary['pending']} 道候选题待人工审核。",
            "label": "进入审核",
            "action_key": "open_review",
            "target_page": PAGE_REVIEW,
            "disabled_reason": "",
        }
    if review_task.get("status") == "ready":
        return {
            "stage": "定稿入库",
            "description": f"当前已有 {review_summary.get('approved', 0)} 道题审核通过，可以定稿形成正式配对样本。",
            "label": "执行定稿",
            "action_key": "finalize_review_batch",
            "target_page": PAGE_GENERATION,
            "disabled_reason": "",
        }
    if evaluation_task.get("status") != "completed":
        return {
            "stage": "自动评测",
            "description": "对正式题库运行参考解校验、功能正确性和自动指标评测。",
            "label": "生成自动指标",
            "action_key": "run_auto_evaluation",
            "target_page": PAGE_RESULTS,
            "disabled_reason": evaluation_task.get("block_reason", "") if evaluation_task.get("status") == "blocked" else "",
        }
    if survey_publish_task.get("status") != "completed":
        return {
            "stage": "发布问卷",
            "description": "生成学生题包、二维码和分发材料，准备发放问卷。",
            "label": "发布问卷材料",
            "action_key": "generate_student_packets",
            "target_page": PAGE_SURVEY,
            "disabled_reason": survey_publish_task.get("block_reason", "") if survey_publish_task.get("status") == "blocked" else "",
        }
    if freeze_task.get("status") != "completed":
        return {
            "stage": "冻结样本",
            "description": "回收问卷后锁定正式分析样本，并构建分析主表。",
            "label": "冻结分析样本",
            "action_key": "freeze_analysis_input",
            "target_page": PAGE_SURVEY,
            "disabled_reason": freeze_task.get("block_reason", "") if freeze_task.get("status") == "blocked" else "",
        }
    if report_task.get("status") != "completed":
        return {
            "stage": "结果输出",
            "description": "整合自动指标与学生评价输出答辩所需结果。",
            "label": "生成结果报告",
            "action_key": "generate_analysis_report",
            "target_page": PAGE_RESULTS,
            "disabled_reason": report_task.get("block_reason", "") if report_task.get("status") == "blocked" else "",
        }
    return {
        "stage": "结果输出",
        "description": "自动指标和学生评价结果都已准备完成，可以直接进入结果页展示。",
        "label": "查看结果",
        "action_key": "open_results",
        "target_page": PAGE_RESULTS,
        "disabled_reason": "",
    }


def render(bundle: dict) -> None:
    render_page_header("工作台", "把生成、筛选、问卷和结果分析压缩成一条最短答辩主线。")

    review_summary = current_review_summary()
    system_summary = bundle.get("system_summary", {})
    survey_metrics = bundle.get("survey_metrics", {})
    tasks = bundle.get("tasks", {})
    action = _next_action(bundle)

    render_summary_band(
        [
            {"label": "当前批次", "value": bundle["settings"]["batch_name"], "note": "本次答辩演示所用批次"},
            {"label": "候选题", "value": str(bundle.get("generation_metrics", {}).get("accepted_count", 0)), "note": "已通过自动筛选的候选题"},
            {"label": "正式样本", "value": str(review_summary.get("approved", 0)), "note": "已审核通过并可入库的题目"},
            {"label": "有效样本", "value": str(survey_metrics.get("effective_samples", 0)), "note": "当前学生问卷有效样本数"},
        ]
    )

    clicked = render_primary_action_panel(
        title=f"当前建议步骤：{action['stage']}",
        description=action["description"],
        primary_label=action["label"],
        primary_key="overview-primary-action",
        primary_disabled=bool(action["disabled_reason"]),
        disabled_reason=action["disabled_reason"],
        secondary_actions=[
            {"label": "进入生成", "key": "go-generation"},
            {"label": "进入审核", "key": "go-review"},
            {"label": "进入问卷", "key": "go-survey"},
            {"label": "进入结果", "key": "go-results"},
        ],
    )
    if clicked.get("primary"):
        if action["action_key"].startswith("open_") or not action_is_executable(action["action_key"]):
            st.session_state["console_page"] = action["target_page"]
            st.rerun()
        _run_action(action["action_key"], "从工作台发起", action["target_page"])
    if clicked.get("go-generation"):
        st.session_state["console_page"] = PAGE_GENERATION
        st.rerun()
    if clicked.get("go-review"):
        st.session_state["console_page"] = PAGE_REVIEW
        st.rerun()
    if clicked.get("go-survey"):
        st.session_state["console_page"] = PAGE_SURVEY
        st.rerun()
    if clicked.get("go-results"):
        st.session_state["console_page"] = PAGE_RESULTS
        st.rerun()

    st.markdown("### 研究流程进度")
    render_checklist(
        [
            {
                "label": "1. 生成候选题",
                "note": "参考题元数据与提示词模板已经进入受控生成流程。",
                "status_label": task_status_label(tasks.get("generation", {}).get("status", "not_started")),
                "tone": "success" if tasks.get("generation", {}).get("status") == "completed" else "warning",
            },
            {
                "label": "2. 筛选与定稿",
                "note": "自动筛选之后，研究员审核并定稿形成正式样本。",
                "status_label": task_status_label(tasks.get("review", {}).get("status", "not_started")),
                "tone": "success" if tasks.get("review", {}).get("status") in {"completed", "ready"} else "warning",
            },
            {
                "label": "3. 问卷发布与回收",
                "note": "生成学生题包、回收结果，并准备冻结分析输入。",
                "status_label": task_status_label(tasks.get("survey_publish", {}).get("status", "not_started")),
                "tone": "success" if tasks.get("survey_publish", {}).get("status") == "completed" else "warning",
            },
            {
                "label": "4. 结果输出",
                "note": "包括自动指标、学生问卷和最终统计摘要。",
                "status_label": task_status_label(tasks.get("report", {}).get("status", "not_started")),
                "tone": "success" if tasks.get("report", {}).get("status") == "completed" else "warning",
            },
        ]
    )

    st.markdown("### 当前关键状态")
    render_key_value_table(
        [
            ("待审核", str(review_summary.get("pending", 0))),
            ("已通过", str(review_summary.get("approved", 0))),
            ("缺评测材料", str(review_summary.get("approved_missing_assets", review_summary.get("missing_assets", 0)))),
            ("问卷已提交", str(system_summary.get("submitted_count", 0))),
            ("有效样本", str(system_summary.get("effective_samples", 0))),
            ("失败任务", str(system_summary.get("failed_tasks", 0))),
        ],
        columns=3,
    )
from __future__ import annotations

import streamlit as st

from evaluation_system.components import (
    render_checklist,
    render_key_value_table,
    render_page_header,
    render_primary_action_panel,
)
from evaluation_system.runner import action_is_executable, execute_action
from evaluation_system.state_store import (
    current_review_summary,
    set_console_flash,
    task_status_label,
)


TASK_TONES = {
    "completed": "success",
    "ready": "success",
    "running": "warning",
    "in_progress": "warning",
    "failed": "danger",
    "blocked": "danger",
    "not_started": "warning",
}


def _task(bundle: dict, task_key: str) -> dict:
    return bundle.get("tasks", {}).get(task_key, {})


def _task_tone(status: str) -> str:
    return TASK_TONES.get(str(status or "").strip(), "warning")


def _next_action(bundle: dict) -> dict[str, str]:
    review_summary = current_review_summary()
    generation_metrics = bundle.get("generation_metrics", {})
    generation_task = _task(bundle, "generation")
    review_task = _task(bundle, "review")
    evaluation_task = _task(bundle, "evaluation")
    publish_task = _task(bundle, "survey_publish")
    freeze_task = _task(bundle, "freeze")
    report_task = _task(bundle, "report")
    snapshot_task = _task(bundle, "snapshot")

    if review_summary["total"] == 0 and not generation_metrics.get("generation_manifest"):
        return {
            "stage": "题目生成",
            "description": "当前还没有正式候选题进入审核队列，先执行提示词构建、候选生成和自动过滤。",
            "label": "生成候选题",
            "action_key": "start_generation",
            "target_page": "题目生成",
            "disabled_reason": generation_task.get("block_reason", "") if generation_task.get("status") == "blocked" else "",
        }
    if review_summary["pending"]:
        return {
            "stage": "人工审核",
            "description": f"当前仍有 {review_summary['pending']} 道候选题待审核，先清空审核队列再进入定稿入库。",
            "label": "进入审核中心",
            "action_key": "open_review_center",
            "target_page": "审核中心",
            "disabled_reason": "",
        }
    if review_task.get("status") == "ready":
        return {
            "stage": "定稿入库",
            "description": f"人工审核已经完成，当前共有 {review_summary.get('approved', 0)} 道题通过，下一步将其更新到正式题库。",
            "label": "执行定稿入库",
            "action_key": "finalize_review_batch",
            "target_page": "题目生成",
            "disabled_reason": "",
        }
    if evaluation_task.get("status") == "blocked" and review_summary.get("approved_missing_assets", 0) > 0:
        return {
            "stage": "评测材料补齐",
            "description": f"当前仍有 {review_summary['approved_missing_assets']} 道已定稿题缺少评测材料，先去审核中心补齐参考解和测试用例。",
            "label": "进入审核中心",
            "action_key": "open_review_center",
            "target_page": "审核中心",
            "disabled_reason": "",
        }
    if evaluation_task.get("status") != "completed":
        return {
            "stage": "自动评测",
            "description": "正式题库和评测材料已经就绪，可以开始自动评测。",
            "label": "开始自动评测",
            "action_key": "run_auto_evaluation",
            "target_page": "运行记录",
            "disabled_reason": evaluation_task.get("block_reason", "") if evaluation_task.get("status") == "blocked" else "",
        }
    if publish_task.get("status") != "completed":
        return {
            "stage": "问卷发放",
            "description": "自动评测已完成，下一步生成学生发放包、二维码页和分发清单。",
            "label": "生成学生发放包",
            "action_key": "generate_student_packets",
            "target_page": "问卷管理",
            "disabled_reason": publish_task.get("block_reason", "") if publish_task.get("status") == "blocked" else "",
        }
    if freeze_task.get("status") != "completed":
        return {
            "stage": "冻结样本",
            "description": "达到阈值后冻结本轮分析输入，锁定后续分析样本。",
            "label": "冻结分析输入",
            "action_key": "freeze_analysis_input",
            "target_page": "问卷管理",
            "disabled_reason": freeze_task.get("block_reason", "") if freeze_task.get("status") == "blocked" else "",
        }
    if report_task.get("status") != "completed":
        return {
            "stage": "分析报告",
            "description": "冻结批次已经形成，当前应生成报告结果并完成登记。",
            "label": "生成分析报告",
            "action_key": "generate_analysis_report",
            "target_page": "分析报告",
            "disabled_reason": report_task.get("block_reason", "") if report_task.get("status") == "blocked" else "",
        }
    return {
        "stage": "快照发布",
        "description": "报告链已经完成，当前可发布并归档完整快照。",
        "label": "发布完整快照",
        "action_key": "publish_snapshot",
        "target_page": "快照发布",
        "disabled_reason": snapshot_task.get("block_reason", "") if snapshot_task.get("status") == "blocked" else "",
    }


def _run_action(action: dict[str, str]) -> None:
    with st.spinner(f"正在执行：{action['label']}..."):
        result = execute_action(
            action["action_key"],
            operator=st.session_state["console_role"],
            note="从当前任务页发起",
        )
    set_console_flash(result["message"], "success" if result["status"] == "success" else "danger")
    if result["status"] == "success":
        if action["action_key"] == "publish_snapshot":
            st.session_state["snapshot_locked_override"] = True
        st.session_state["console_page"] = action["target_page"]
    else:
        st.session_state["console_page"] = "运行记录"
    st.cache_data.clear()
    st.rerun()


def render(bundle: dict) -> None:
    render_page_header("当前任务", "查看当前阶段和下一步处理动作。")

    action = _next_action(bundle)
    survey_metrics = bundle["survey_metrics"]
    review_summary = current_review_summary()
    tasks = bundle.get("tasks", {})
    checklist_items = []
    for task_key, label, note in [
        ("generation", "题目生成", "候选题已生成并完成自动过滤。"),
        ("review", "人工审核", "研究员完成审核后，可执行定稿入库。"),
        ("evaluation", "自动评测", "正式题库与评测材料就绪后可执行。"),
        ("survey_publish", "问卷发放", "自动评测完成后生成题包与二维码。"),
        ("freeze", "冻结样本", f"达到阈值后锁定分析样本，当前阈值 {survey_metrics['freeze_threshold']}。"),
        ("snapshot", "快照归档", "报告完成后开放最终归档。"),
    ]:
        status = str(tasks.get(task_key, {}).get("status") or "not_started")
        checklist_items.append(
            {
                "label": label,
                "note": note,
                "status_label": task_status_label(status),
                "tone": _task_tone(status),
            }
        )

    st.markdown("### 当前阶段")
    clicked = render_primary_action_panel(
        title=f"当前主线聚焦：{action['stage']}",
        description=action["description"],
        primary_label=action["label"],
        primary_key="overview-primary-action",
        primary_disabled=bool(action["disabled_reason"]),
        disabled_reason=action["disabled_reason"],
        secondary_actions=[
            {"label": "进入运行记录", "key": "overview-go-runs"},
            {"label": "进入题目生成", "key": "overview-go-generation"},
        ],
    )
    if clicked.get("primary"):
        if action_is_executable(action["action_key"]) and action["target_page"] != "审核中心":
            _run_action(action)
        else:
            st.session_state["console_page"] = action["target_page"]
            st.rerun()
    if clicked.get("overview-go-runs"):
        st.session_state["console_page"] = "运行记录"
        st.rerun()
    if clicked.get("overview-go-generation"):
        st.session_state["console_page"] = "题目生成"
        st.rerun()

    st.markdown("### 流程准备情况")
    check_cols = st.columns(2, gap="large")
    with check_cols[0]:
        render_checklist(checklist_items[:3])
    with check_cols[1]:
        render_checklist(checklist_items[3:])

    st.markdown("### 系统队列")
    render_key_value_table(
        [
            ("待审核", str(review_summary["pending"])),
            ("已通过", str(review_summary["approved"])),
            ("缺资产", str(review_summary.get("approved_missing_assets", review_summary["missing_assets"]))),
            ("已提交答卷", str(bundle["system_summary"]["submitted_count"])),
            ("有效样本", str(bundle["system_summary"]["effective_samples"])),
            ("失败任务", str(bundle["system_summary"].get("failed_tasks", 0))),
            ("失败工单", str(bundle["system_summary"].get("failed_work_orders", 0))),
            ("执行中工单", str(bundle["system_summary"].get("open_work_orders", 0))),
        ],
        columns=4,
    )


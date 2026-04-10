from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
from pandas.errors import EmptyDataError

from .generation_pipeline import (
    CURATED_AI_DATASET_PATH,
    CURATED_BLIND_MAPPING_PATH,
    CURATED_EXERCISES_ALL_PATH,
    CURATED_FINAL_PAIRS_PATH,
    FILTER_ACCEPTED_PATH,
    FILTER_REJECTED_PATH,
    FILTER_SUMMARY_PATH,
    GENERATION_MANIFEST_PATH,
    sync_review_state_from_filtered,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "results"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
CURATED_DIR = RESULTS_DIR / "curated"
STUDENT_DIR = RESULTS_DIR / "student_subsets"
PACKETS_DIR = CURATED_DIR / "human_eval_packets"
CHAPTER5_DIR = STUDENT_DIR / "chapter5_outputs"
CHAPTER5_TABLES_DIR = CHAPTER5_DIR / "tables"
SYSTEM_DIR = OUTPUTS_DIR / "system"

LEGACY_WORKFLOW_STATE_PATH = SYSTEM_DIR / "workflow_state.v1.json"
LEGACY_REPORT_SUMMARY_PATH = SYSTEM_DIR / "report_summary.v1.json"
REVIEW_STATE_PATH = SYSTEM_DIR / "review_state.v1.json"
SYSTEM_STATE_PATH = SYSTEM_DIR / "control_plane.v1.json"
AUDIT_LOG_PATH = SYSTEM_DIR / "audit_log.v1.jsonl"

CURATED_ANALYSIS_STATUS_PATH = CURATED_DIR / "statistics" / "analysis_status.v1.json"
PACKAGE_MANIFEST_PATH = PACKETS_DIR / "packets" / "student_package_manifest.curated.v1.csv"
DISTRIBUTION_PATH = PACKETS_DIR / "distribution" / "student_distribution_sheet.curated.v1.csv"
QRCODE_SHEET_PATH = PACKETS_DIR / "distribution" / "student_qrcode_print_sheets.curated.html"
PARTICIPANT_META_PATH = STUDENT_DIR / "participant_meta_30.csv"
ITEM_RATINGS_PATH = STUDENT_DIR / "item_ratings_30.csv"
BATCH_FEEDBACK_PATH = STUDENT_DIR / "batch_feedback_30.csv"
SUBSET_MANIFEST_PATH = STUDENT_DIR / "student_subset_export_manifest.json"
MASTER_MANIFEST_PATH = STUDENT_DIR / "student_analysis_master_30.manifest.json"
MASTER_CSV_PATH = STUDENT_DIR / "student_analysis_master_30.csv"
CHAPTER5_MANIFEST_PATH = CHAPTER5_DIR / "chapter5_outputs_manifest.json"
SIGNIFICANCE_MANIFEST_PATH = CHAPTER5_TABLES_DIR / "significance_outputs_manifest.json"
CORRELATION_MANIFEST_PATH = CHAPTER5_TABLES_DIR / "correlation_auto_vs_student.manifest.json"

ROLE_PERMISSIONS = {
    "管理员": ["工作台", "生成", "审核", "结果", "系统设置"],
    "研究员": ["工作台", "生成", "审核", "结果"],
}


def _normalize_role_name(role_name: str) -> str:
    normalized = str(role_name or "").strip()
    return "研究员" if normalized == "审核员" else normalized


def _normalize_role_pages(pages: list[str]) -> list[str]:
    alias_map = {
        "流程总览": "工作台",
        "当前任务": "工作台",
        "题目生成": "生成",
        "审核中心": "审核",
        "问卷管理": "结果",
        "分析报告": "结果",
        "运行记录": "结果",
        "快照发布": "结果",
    }
    seen: set[str] = set()
    normalized: list[str] = []
    for page in pages:
        if not isinstance(page, str):
            continue
        candidate = alias_map.get(page.strip(), page.strip())
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    if "工作台" not in seen:
        normalized.insert(0, "工作台")
    return normalized

def _normalize_role_permissions(role_permissions: dict[str, Any] | None) -> dict[str, list[str]]:
    permissions = deepcopy(ROLE_PERMISSIONS)
    if not isinstance(role_permissions, dict):
        return permissions
    for raw_role_name, pages in role_permissions.items():
        role_name = _normalize_role_name(raw_role_name)
        if isinstance(pages, list):
            merged = permissions.get(role_name, []) + pages
            permissions[role_name] = _normalize_role_pages(merged)
    return permissions


TASK_BLUEPRINTS: list[dict[str, Any]] = [
    {
        "task_key": "generation",
        "label": "题目生成",
        "stage_key": "generation",
        "owner_role": "研究员",
        "action_key": "start_generation",
        "depends_on": [],
        "summary": "基于提示词模板生成并过滤候选题。",
    },
    {
        "task_key": "review",
        "label": "人工审核",
        "stage_key": "review",
        "owner_role": "研究员",
        "action_key": "finalize_review_batch",
        "depends_on": ["generation"],
        "summary": "完成人工审核并将通过题目定稿入正式题库。",
    },
    {
        "task_key": "evaluation",
        "label": "自动评测",
        "stage_key": "evaluation",
        "owner_role": "研究员",
        "action_key": "run_auto_evaluation",
        "depends_on": ["review"],
        "summary": "对 AI 生成习题运行自动评测链。",
    },
    {
        "task_key": "survey_publish",
        "label": "问卷发放",
        "stage_key": "survey_publish",
        "owner_role": "研究员",
        "action_key": "generate_student_packets",
        "depends_on": ["evaluation"],
        "summary": "生成问卷题包、二维码和分发表。",
    },
    {
        "task_key": "survey_collect",
        "label": "问卷回收",
        "stage_key": "survey_collect",
        "owner_role": "研究员",
        "action_key": None,
        "depends_on": ["survey_publish"],
        "summary": "等待学生问卷回收达到冻结阈值。",
    },
    {
        "task_key": "freeze",
        "label": "冻结样本",
        "stage_key": "freeze",
        "owner_role": "研究员",
        "action_key": "freeze_analysis_input",
        "depends_on": ["survey_collect"],
        "summary": "冻结本轮正式分析输入。",
    },
    {
        "task_key": "report",
        "label": "分析报告",
        "stage_key": "report",
        "owner_role": "研究员",
        "action_key": "generate_analysis_report",
        "depends_on": ["freeze"],
        "summary": "结合自动指标与问卷数据生成报告交付物。",
    },
    {
        "task_key": "snapshot",
        "label": "快照发布",
        "stage_key": "snapshot",
        "owner_role": "管理员",
        "action_key": "publish_snapshot",
        "depends_on": ["report"],
        "summary": "归档批次完整快照。",
    },
]

DELIVERABLE_BLUEPRINTS = {
    "generation_manifest": {"label": "生成批次 manifest", "path": str(GENERATION_MANIFEST_PATH)},
    "filtered_accepted": {"label": "候选题通过池", "path": str(FILTER_ACCEPTED_PATH)},
    "filtered_rejected": {"label": "候选题拒绝池", "path": str(FILTER_REJECTED_PATH)},
    "filter_summary": {"label": "过滤摘要", "path": str(FILTER_SUMMARY_PATH)},
    "final_pairs": {"label": "正式配对题库", "path": str(CURATED_FINAL_PAIRS_PATH)},
    "blind_mapping": {"label": "盲评映射表", "path": str(CURATED_BLIND_MAPPING_PATH)},
    "ai_dataset": {"label": "AI 习题数据集", "path": str(CURATED_AI_DATASET_PATH)},
    "exercises_all": {"label": "全量题目清单", "path": str(CURATED_EXERCISES_ALL_PATH)},
    "packet_manifest": {"label": "题包清单", "path": str(PACKAGE_MANIFEST_PATH)},
    "distribution_sheet": {"label": "分发清单", "path": str(DISTRIBUTION_PATH)},
    "qrcode_sheet": {"label": "二维码页", "path": str(QRCODE_SHEET_PATH)},
    "subset_manifest": {"label": "冻结说明", "path": str(SUBSET_MANIFEST_PATH)},
    "master_manifest": {"label": "主分析表 manifest", "path": str(MASTER_MANIFEST_PATH)},
    "report_manifest": {"label": "报告 manifest", "path": str(CHAPTER5_MANIFEST_PATH)},
    "significance_manifest": {"label": "显著性 manifest", "path": str(SIGNIFICANCE_MANIFEST_PATH)},
    "correlation_manifest": {"label": "相关性 manifest", "path": str(CORRELATION_MANIFEST_PATH)},
    "report_summary": {"label": "报告摘要", "path": str(LEGACY_REPORT_SUMMARY_PATH)},
}

TASK_TO_DELIVERABLES = {
    "generation": ["generation_manifest", "filtered_accepted", "filtered_rejected", "filter_summary"],
    "review": ["final_pairs", "blind_mapping", "ai_dataset", "exercises_all"],
    "evaluation": ["evaluation_status"],
    "survey_publish": ["packet_manifest", "distribution_sheet", "qrcode_sheet"],
    "freeze": ["subset_manifest", "master_manifest"],
    "report": ["report_manifest", "significance_manifest", "correlation_manifest", "report_summary"],
    "snapshot": ["snapshot_archive"],
}

RETRY_POLICY_BLUEPRINTS = {
    "generation": {"max_retries": 2, "recovery_actions": ["retry_now", "mark_ready"]},
    "review": {"max_retries": 1, "recovery_actions": ["retry_now", "mark_ready"]},
    "evaluation": {"max_retries": 2, "recovery_actions": ["retry_now", "mark_ready"]},
    "survey_publish": {"max_retries": 2, "recovery_actions": ["retry_now", "mark_ready"]},
    "survey_collect": {"max_retries": 0, "recovery_actions": ["mark_ready"]},
    "freeze": {"max_retries": 2, "recovery_actions": ["retry_now", "mark_ready"]},
    "report": {"max_retries": 2, "recovery_actions": ["retry_now", "mark_ready"]},
    "snapshot": {"max_retries": 1, "recovery_actions": ["retry_now", "mark_ready"]},
}

WORK_ORDER_STATUS_LABELS = {
    "queued": "待执行",
    "running": "执行中",
    "completed": "已完成",
    "failed": "失败",
    "recovered": "已恢复",
    "cancelled": "已取消",
}


STATUS_LABELS = {
    "not_started": "未开始",
    "ready": "可执行",
    "blocked": "阻塞",
    "running": "执行中",
    "in_progress": "进行中",
    "completed": "已完成",
    "failed": "失败",
}


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")



def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}



def _save_json(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")



def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")



def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except EmptyDataError:
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()



def _format_timestamp(value: Any) -> str:
    if value in (None, "", pd.NaT):
        return "未记录"
    try:
        timestamp = pd.to_datetime(value, utc=True)
        if getattr(timestamp, "tzinfo", None) is not None:
            timestamp = timestamp.tz_convert("Asia/Shanghai")
        return timestamp.strftime("%Y-%m-%d %H:%M")
    except Exception:
        try:
            timestamp = pd.to_datetime(value)
            return timestamp.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return str(value)



def _file_timestamp(path: Path) -> str:
    if not path.exists():
        return "未生成"
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")


def _latest_snapshot_archive() -> Path | None:
    snapshots_dir = SYSTEM_DIR / "snapshots"
    if not snapshots_dir.exists():
        return None
    archives = sorted(
        snapshots_dir.glob("*.zip"),
        key=lambda file_path: file_path.stat().st_mtime,
        reverse=True,
    )
    return archives[0] if archives else None



def _review_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    pending = sum(1 for item in items if item.get("review_status") == "pending_review")
    approved = sum(1 for item in items if item.get("review_status") == "approved")
    rejected = sum(1 for item in items if item.get("review_status") == "rejected")
    missing_assets = sum(
        1
        for item in items
        if item.get("review_status") != "rejected"
        and (not item.get("solution_overlay_ready") or not item.get("tests_overlay_ready"))
    )
    approved_missing_assets = sum(
        1
        for item in items
        if item.get("review_status") == "approved"
        and (not item.get("solution_overlay_ready") or not item.get("tests_overlay_ready"))
    )
    return {
        "pending": pending,
        "approved": approved,
        "rejected": rejected,
        "missing_assets": missing_assets,
        "approved_missing_assets": approved_missing_assets,
        "approved_total": approved,
        "total": len(items),
    }



def _bootstrap_review_metrics() -> tuple[list[dict[str, Any]], dict[str, int]]:
    review_state = _load_json(REVIEW_STATE_PATH)
    if FILTER_ACCEPTED_PATH.exists() and not isinstance(review_state.get("items"), list):
        review_state = sync_review_state_from_filtered(review_state)
    elif FILTER_ACCEPTED_PATH.exists() and not review_state.get("items"):
        review_state = sync_review_state_from_filtered(review_state)

    workflow_state = _load_json(LEGACY_WORKFLOW_STATE_PATH)
    items = review_state.get("items") or workflow_state.get("review", {}).get("items", [])
    if not isinstance(items, list):
        items = []
    return items, _review_counts(items)

def _max_submit(series: pd.Series) -> str:
    if series.empty:
        return "未记录"
    try:
        parsed = pd.to_datetime(series, utc=True, errors="coerce").dropna()
        if parsed.empty:
            return "未记录"
        return parsed.max().tz_convert("Asia/Shanghai").strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "未记录"



def _bootstrap_survey_metrics(freeze_threshold: int) -> dict[str, Any]:
    distribution = _load_csv(DISTRIBUTION_PATH)
    participant_meta = _load_csv(PARTICIPANT_META_PATH)
    batch_feedback = _load_csv(BATCH_FEEDBACK_PATH)
    subset_manifest = _load_json(SUBSET_MANIFEST_PATH)
    chapter5_manifest = _load_json(CHAPTER5_MANIFEST_PATH)

    raw_issued_count = int(len(distribution))
    submitted_count = int(len(batch_feedback))
    selected_participants = int(subset_manifest.get("selection_summary", {}).get("selected_participants") or 0)
    issued_count = selected_participants or submitted_count or raw_issued_count
    effective_samples = int(chapter5_manifest.get("filter_summary", {}).get("participants_after_filter") or 0)
    attention_fail_count = 0
    if not participant_meta.empty and "attention_check_passed" in participant_meta.columns:
        attention_fail_count = int((~participant_meta["attention_check_passed"].astype(str).str.lower().eq("true")).sum())
    latest_submit = (
        _max_submit(participant_meta["submitted_at"])
        if not participant_meta.empty and "submitted_at" in participant_meta.columns
        else "未记录"
    )
    scanned_count = selected_participants or submitted_count
    return {
        "issued_count": issued_count,
        "scanned_count": scanned_count,
        "submitted_count": submitted_count,
        "effective_samples": effective_samples,
        "attention_fail_count": attention_fail_count,
        "latest_submit": latest_submit,
        "freeze_threshold": freeze_threshold,
        "threshold_ready": scanned_count >= freeze_threshold,
        "data_synced": submitted_count > 0,
    }



def _build_deliverables_snapshot() -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    for key, blueprint in DELIVERABLE_BLUEPRINTS.items():
        path = Path(blueprint["path"])
        snapshot[key] = {
            "label": blueprint["label"],
            "path": str(path),
            "available": path.exists(),
            "updated_at": _file_timestamp(path),
            "source": "bootstrap",
        }
    snapshot["evaluation_status"] = {
        "label": "自动评测状态",
        "path": str(CURATED_ANALYSIS_STATUS_PATH),
        "available": CURATED_ANALYSIS_STATUS_PATH.exists(),
        "updated_at": _file_timestamp(CURATED_ANALYSIS_STATUS_PATH),
        "source": "bootstrap",
    }
    latest_snapshot = _latest_snapshot_archive()
    snapshot["snapshot_archive"] = {
        "label": "快照归档",
        "path": str(latest_snapshot or (SYSTEM_DIR / "snapshots")),
        "available": latest_snapshot is not None,
        "updated_at": _file_timestamp(latest_snapshot) if latest_snapshot is not None else "未生成",
        "source": "bootstrap",
    }
    return snapshot



def _empty_task(blueprint: dict[str, Any], now: str) -> dict[str, Any]:
    return {
        "task_key": blueprint["task_key"],
        "label": blueprint["label"],
        "stage_key": blueprint["stage_key"],
        "owner_role": blueprint["owner_role"],
        "action_key": blueprint["action_key"],
        "depends_on": blueprint["depends_on"],
        "status": "not_started",
        "summary": blueprint["summary"],
        "latest_run_id": "",
        "latest_message": "",
        "latest_error": "",
        "latest_status": "not_started",
        "latest_run_at": "",
        "latest_work_order_id": "",
        "active_work_order_id": "",
        "attempt_count": 0,
        "failed_attempts": 0,
        "retry_remaining": 0,
        "retry_available": False,
        "recovery_hint": "",
        "updated_at": now,
        "metrics": {},
        "block_reason": "",
    }



def _normalize_task_status(task: dict[str, Any], fallback: str) -> str:
    status = str(task.get("status") or fallback).strip()
    if status in {"running", "failed", "completed"}:
        return status
    return fallback



def _dependency_completed(tasks: dict[str, dict[str, Any]], task_key: str) -> bool:
    return all(tasks[dep]["status"] == "completed" for dep in tasks[task_key].get("depends_on", []))



def _reconcile_tasks(state: dict[str, Any]) -> dict[str, Any]:
    _ensure_orchestration(state)
    tasks = state["tasks"]
    review_metrics = state["observability"]["review_queue"]
    survey_metrics = state["observability"]["survey"]
    deliverables = state["observability"]["deliverables"]

    for blueprint in TASK_BLUEPRINTS:
        task = tasks[blueprint["task_key"]]
        task["label"] = blueprint["label"]
        task["stage_key"] = blueprint["stage_key"]
        task["owner_role"] = blueprint["owner_role"]
        task["action_key"] = blueprint["action_key"]
        task["depends_on"] = list(blueprint["depends_on"])
        task["summary"] = blueprint["summary"]

    generation_has_results = any(
        bool(deliverables.get(key, {}).get("available"))
        for key in ["generation_manifest", "filtered_accepted", "filtered_rejected"]
    ) or review_metrics["total"] > 0
    finalization_ready = bool(deliverables.get("final_pairs", {}).get("available")) and bool(
        deliverables.get("blind_mapping", {}).get("available")
    )

    generation_fallback = "completed" if generation_has_results else "ready"
    tasks["generation"]["status"] = _normalize_task_status(tasks["generation"], generation_fallback)
    if tasks["generation"]["status"] == "completed" and not generation_has_results:
        tasks["generation"]["status"] = "ready"
    tasks["generation"]["metrics"] = {
        "candidate_total": review_metrics["total"],
        "accepted_pool_ready": bool(deliverables.get("filtered_accepted", {}).get("available")),
        "rejected_pool_ready": bool(deliverables.get("filtered_rejected", {}).get("available")),
    }
    if generation_has_results and review_metrics["total"] == 0:
        tasks["generation"]["block_reason"] = "过滤后暂无可进入审核的候选题，请调整模板或重新生成。"
    else:
        tasks["generation"]["block_reason"] = ""

    if finalization_ready:
        review_fallback = "completed"
        review_reason = ""
    elif not generation_has_results and review_metrics["total"] == 0:
        review_fallback = "blocked"
        review_reason = "题目生成尚未完成。"
    elif review_metrics["total"] == 0:
        review_fallback = "blocked"
        review_reason = "当前没有进入人工审核队列的候选题。"
    elif review_metrics["pending"] > 0:
        review_fallback = "in_progress"
        review_reason = f"还有 {review_metrics['pending']} 道题待处理。"
    elif review_metrics["approved_total"] == 0:
        review_fallback = "blocked"
        review_reason = "当前没有已通过候选题，无法定稿入库。"
    else:
        review_fallback = "ready"
        review_reason = ""
    tasks["review"]["status"] = _normalize_task_status(tasks["review"], review_fallback)
    if tasks["review"]["status"] == "completed" and not finalization_ready:
        tasks["review"]["status"] = "ready"
    tasks["review"]["metrics"] = deepcopy(review_metrics)
    if tasks["review"]["status"] in {"blocked", "in_progress"}:
        tasks["review"]["block_reason"] = review_reason
    else:
        tasks["review"]["block_reason"] = ""

    approved_missing_assets = int(review_metrics.get("approved_missing_assets") or 0)
    if tasks["review"]["status"] != "completed":
        evaluation_fallback = "blocked"
        evaluation_reason = "人工审核定稿尚未完成。"
    elif approved_missing_assets > 0:
        evaluation_fallback = "blocked"
        evaluation_reason = f"仍有 {approved_missing_assets} 道已定稿题缺少评测资产。"
    else:
        evaluation_fallback = "ready"
        evaluation_reason = ""
    tasks["evaluation"]["status"] = _normalize_task_status(tasks["evaluation"], evaluation_fallback)
    if tasks["evaluation"]["status"] == "completed" and not deliverables["evaluation_status"]["available"]:
        tasks["evaluation"]["status"] = "ready"
    tasks["evaluation"]["metrics"] = {
        "approved_total": review_metrics.get("approved_total", 0),
        "approved_missing_assets": approved_missing_assets,
    }
    approved_total = int(review_metrics.get("approved_total") or 0)
    approved_ready_assets = max(approved_total - approved_missing_assets, 0)
    if tasks["review"]["status"] == "completed":
        if approved_total <= 0:
            tasks["evaluation"]["status"] = "blocked"
            evaluation_reason = "No finalized exercises are available for automatic evaluation."
        elif approved_ready_assets <= 0:
            tasks["evaluation"]["status"] = "blocked"
            evaluation_reason = f"{approved_missing_assets} finalized exercises are still missing evaluation assets."
        elif tasks["evaluation"]["status"] != "completed":
            tasks["evaluation"]["status"] = "ready"
            evaluation_reason = ""
    tasks["evaluation"]["metrics"]["approved_total"] = approved_total
    tasks["evaluation"]["metrics"]["approved_ready_assets"] = approved_ready_assets
    tasks["evaluation"]["block_reason"] = evaluation_reason if tasks["evaluation"]["status"] == "blocked" else ""

    publish_fallback = "ready" if tasks["evaluation"]["status"] == "completed" else "blocked"
    tasks["survey_publish"]["status"] = _normalize_task_status(tasks["survey_publish"], publish_fallback)
    if tasks["survey_publish"]["status"] == "completed" and not deliverables["packet_manifest"]["available"]:
        tasks["survey_publish"]["status"] = "ready"
    tasks["survey_publish"]["metrics"] = {
        "issued_count": survey_metrics["issued_count"],
        "submitted_count": survey_metrics["submitted_count"],
    }
    tasks["survey_publish"]["block_reason"] = "自动评测未完成。" if publish_fallback == "blocked" else ""

    if tasks["freeze"]["status"] == "completed":
        collect_fallback = "completed"
    elif tasks["survey_publish"]["status"] == "completed" and survey_metrics["submitted_count"] > 0:
        collect_fallback = "in_progress"
    elif tasks["survey_publish"]["status"] == "completed":
        collect_fallback = "ready"
    else:
        collect_fallback = "blocked"
    tasks["survey_collect"]["status"] = _normalize_task_status(tasks["survey_collect"], collect_fallback)
    tasks["survey_collect"]["metrics"] = deepcopy(survey_metrics)
    tasks["survey_collect"]["block_reason"] = "问卷尚未发放。" if collect_fallback == "blocked" else ""

    freeze_ready = tasks["survey_publish"]["status"] == "completed" and survey_metrics["threshold_ready"] and survey_metrics["data_synced"]
    freeze_fallback = "ready" if freeze_ready else "blocked"
    tasks["freeze"]["status"] = _normalize_task_status(tasks["freeze"], freeze_fallback)
    if tasks["freeze"]["status"] == "completed" and not deliverables["subset_manifest"]["available"]:
        tasks["freeze"]["status"] = "ready"
    if tasks["survey_publish"]["status"] != "completed":
        tasks["freeze"]["block_reason"] = "问卷发放尚未完成。"
    elif not freeze_ready:
        tasks["freeze"]["block_reason"] = "尚未满足冻结阈值或数据同步条件。"
    else:
        tasks["freeze"]["block_reason"] = ""

    report_fallback = "ready" if tasks["freeze"]["status"] == "completed" else "blocked"
    tasks["report"]["status"] = _normalize_task_status(tasks["report"], report_fallback)
    if tasks["report"]["status"] == "completed" and not deliverables["report_manifest"]["available"]:
        tasks["report"]["status"] = "ready"
    tasks["report"]["block_reason"] = "冻结样本尚未完成。" if report_fallback == "blocked" else ""

    snapshot_fallback = "ready" if tasks["report"]["status"] == "completed" else "blocked"
    tasks["snapshot"]["status"] = _normalize_task_status(tasks["snapshot"], snapshot_fallback)
    if tasks["snapshot"]["status"] == "completed" and not deliverables["snapshot_archive"]["available"]:
        tasks["snapshot"]["status"] = "ready"
    tasks["snapshot"]["metrics"] = {
        "archive_available": bool(deliverables["snapshot_archive"]["available"]),
    }
    tasks["snapshot"]["block_reason"] = "报告链尚未完成。" if snapshot_fallback == "blocked" else ""

    completed_order = [
        task["task_key"]
        for task in TASK_BLUEPRINTS
        if tasks[task["task_key"]]["status"] == "completed"
    ]
    current_stage = TASK_BLUEPRINTS[-1]["stage_key"]
    for blueprint in TASK_BLUEPRINTS:
        key = blueprint["task_key"]
        if tasks[key]["status"] != "completed":
            current_stage = blueprint["stage_key"]
            break
    state["pipeline"] = {
        "current_stage": current_stage,
        "completed_tasks": completed_order,
    }
    state = _sync_task_orchestration(state)
    return state

def bootstrap_system_state() -> dict[str, Any]:
    legacy_workflow = _load_json(LEGACY_WORKFLOW_STATE_PATH)
    admin_settings = legacy_workflow.get("admin_settings", {}) if isinstance(legacy_workflow, dict) else {}
    now = _now_iso()
    freeze_threshold = int(admin_settings.get("freeze_threshold") or 30)
    review_items, review_metrics = _bootstrap_review_metrics()
    survey_metrics = _bootstrap_survey_metrics(freeze_threshold)
    deliverables = _build_deliverables_snapshot()

    tasks = {blueprint["task_key"]: _empty_task(blueprint, now) for blueprint in TASK_BLUEPRINTS}
    state = {
        "schema_version": "control_plane.v1",
        "created_at": now,
        "updated_at": now,
        "batch": {
            "batch_id": str(legacy_workflow.get("active_task_id") or "batch-default"),
            "batch_name": str(admin_settings.get("batch_name") or "2026 春季正式批次"),
        },
        "settings": {
            "batch_name": str(admin_settings.get("batch_name") or "2026 春季正式批次"),
            "freeze_threshold": freeze_threshold,
            "current_mainline": str(admin_settings.get("current_mainline") or "学生问卷主线"),
            "role_permissions": _normalize_role_permissions(admin_settings.get("role_permissions") or ROLE_PERMISSIONS),
            "data_source": deepcopy(admin_settings.get("data_source") or {}),
            "paths": deepcopy(admin_settings.get("paths") or {}),
        },
        "tasks": tasks,
        "observability": {
            "review_queue": review_metrics,
            "survey": survey_metrics,
            "deliverables": deliverables,
        },
        "review_entities": {
            "count": len(review_items),
            "source": "review_state" if REVIEW_STATE_PATH.exists() else "legacy_workflow",
        },
        "orchestration": {
            "retry_policies": _default_retry_policies(),
            "work_orders": {},
        },
        "ui": {
            "last_page": "工作台",
        },
    }
    return _reconcile_tasks(state)



def _merge_state_with_blueprint(state: dict[str, Any]) -> dict[str, Any]:
    baseline = bootstrap_system_state()
    merged = deepcopy(baseline)

    merged["created_at"] = str(state.get("created_at") or baseline["created_at"])
    merged["updated_at"] = str(state.get("updated_at") or baseline["updated_at"])

    if isinstance(state.get("batch"), dict):
        merged["batch"].update(state["batch"])

    existing_settings = state.get("settings", {})
    if isinstance(existing_settings, dict):
        for key in ["batch_name", "freeze_threshold", "current_mainline"]:
            if key in existing_settings:
                merged["settings"][key] = existing_settings[key]
        for key in ["role_permissions", "data_source", "paths"]:
            if isinstance(existing_settings.get(key), dict):
                merged["settings"][key] = _normalize_role_permissions(existing_settings[key]) if key == "role_permissions" else deepcopy(existing_settings[key])

    existing_observability = state.get("observability", {})
    if isinstance(existing_observability, dict):
        if isinstance(existing_observability.get("review_queue"), dict):
            merged["observability"]["review_queue"].update(existing_observability["review_queue"])
        if isinstance(existing_observability.get("survey"), dict):
            merged["observability"]["survey"].update(existing_observability["survey"])
        if isinstance(existing_observability.get("deliverables"), dict):
            for key, payload in existing_observability["deliverables"].items():
                if isinstance(payload, dict):
                    current = merged["observability"]["deliverables"].setdefault(key, {})
                    current.update(payload)

    existing_tasks = state.get("tasks", {})
    if isinstance(existing_tasks, dict):
        for blueprint in TASK_BLUEPRINTS:
            task_key = blueprint["task_key"]
            payload = existing_tasks.get(task_key)
            if isinstance(payload, dict):
                merged["tasks"][task_key].update(payload)

    if isinstance(state.get("review_entities"), dict):
        merged["review_entities"].update(state["review_entities"])

    existing_orchestration = state.get("orchestration", {})
    if isinstance(existing_orchestration, dict):
        if isinstance(existing_orchestration.get("retry_policies"), dict):
            for key, payload in existing_orchestration["retry_policies"].items():
                if isinstance(payload, dict):
                    current = merged["orchestration"]["retry_policies"].setdefault(key, {})
                    current.update(payload)
        if isinstance(existing_orchestration.get("work_orders"), dict):
            for key, payload in existing_orchestration["work_orders"].items():
                if isinstance(payload, dict):
                    merged["orchestration"]["work_orders"][key] = deepcopy(payload)

    if isinstance(state.get("ui"), dict):
        merged["ui"].update(state["ui"])
    if isinstance(state.get("pipeline"), dict):
        merged["pipeline"] = deepcopy(state["pipeline"])

    return _reconcile_tasks(merged)



def _refresh_observability_from_sources(state: dict[str, Any]) -> dict[str, Any]:
    freeze_threshold = int(state.get("settings", {}).get("freeze_threshold") or 30)
    review_items, review_metrics = _bootstrap_review_metrics()
    state["observability"]["review_queue"] = review_metrics
    state["observability"]["survey"] = _bootstrap_survey_metrics(freeze_threshold)
    state["review_entities"] = {
        "count": len(review_items),
        "source": "review_state" if REVIEW_STATE_PATH.exists() else "legacy_workflow",
    }

    for key, payload in _build_deliverables_snapshot().items():
        current = state["observability"]["deliverables"].setdefault(key, {})
        current.update(payload)
        current["source"] = "reconciled"
    return state



def ensure_system_state() -> dict[str, Any]:
    state = _load_json(SYSTEM_STATE_PATH)
    if state.get("schema_version") != "control_plane.v1":
        state = bootstrap_system_state()
        _save_json(SYSTEM_STATE_PATH, state)
        return state

    merged = _refresh_observability_from_sources(_merge_state_with_blueprint(state))
    if merged != state:
        _save_json(SYSTEM_STATE_PATH, merged)
    return merged



def load_system_state() -> dict[str, Any]:
    return ensure_system_state()



def save_system_state(state: dict[str, Any]) -> None:
    state["updated_at"] = _now_iso()
    _save_json(SYSTEM_STATE_PATH, _reconcile_tasks(state))



def record_audit_event(
    event_type: str,
    *,
    actor: str,
    target: str,
    status: str,
    detail: dict[str, Any] | None = None,
) -> None:
    _append_jsonl(
        AUDIT_LOG_PATH,
        {
            "recorded_at": _now_iso(),
            "event_type": event_type,
            "actor": actor,
            "target": target,
            "status": status,
            "detail": detail or {},
        },
    )



def load_audit_events(limit: int | None = 100) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not AUDIT_LOG_PATH.exists():
        return rows

    with AUDIT_LOG_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            rows.append(
                {
                    **payload,
                    "time": _format_timestamp(payload.get("recorded_at")),
                }
            )

    rows.sort(key=lambda item: str(item.get("recorded_at", "")), reverse=True)
    if limit is not None:
        return rows[:limit]
    return rows



def apply_review_state(review_items: list[dict[str, Any]]) -> dict[str, Any]:
    state = load_system_state()
    metrics = _review_counts(review_items)
    state["observability"]["review_queue"] = metrics
    state["review_entities"] = {
        "count": len(review_items),
        "source": "review_state",
    }
    save_system_state(state)
    return state



def update_settings(settings: dict[str, Any]) -> dict[str, Any]:
    state = load_system_state()
    state["settings"]["batch_name"] = str(settings.get("batch_name") or state["settings"].get("batch_name", ""))
    state["settings"]["freeze_threshold"] = int(settings.get("freeze_threshold") or state["settings"].get("freeze_threshold", 30))
    state["settings"]["current_mainline"] = str(settings.get("current_mainline") or state["settings"].get("current_mainline", ""))
    state["settings"]["role_permissions"] = _normalize_role_permissions(settings.get("role_permissions") or state["settings"].get("role_permissions", ROLE_PERMISSIONS))
    state["settings"]["data_source"] = deepcopy(settings.get("data_source") or state["settings"].get("data_source", {}))
    state["settings"]["paths"] = deepcopy(settings.get("paths") or state["settings"].get("paths", {}))
    state["batch"]["batch_name"] = state["settings"]["batch_name"]
    state = _refresh_observability_from_sources(state)
    save_system_state(state)
    return state



def update_task_runtime(
    task_key: str,
    *,
    status: str,
    actor: str,
    run_id: str = "",
    message: str = "",
    error: str = "",
    deliverable_updates: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    state = load_system_state()
    task = state["tasks"].setdefault(task_key, {})
    task["status"] = status
    task["latest_run_id"] = run_id
    task["latest_status"] = status
    task["latest_message"] = message
    task["latest_error"] = error
    task["latest_run_at"] = _now_iso()
    task["updated_at"] = _now_iso()

    for key, payload in (deliverable_updates or {}).items():
        current = state["observability"]["deliverables"].setdefault(key, {})
        current.update(payload)

    state = _refresh_observability_from_sources(state)
    save_system_state(state)
    record_audit_event(
        "task_runtime",
        actor=actor,
        target=task_key,
        status=status,
        detail={
            "run_id": run_id,
            "message": message,
            "error": error,
        },
    )
    return state



def mark_deliverables_for_task(task_key: str, paths: list[str]) -> dict[str, dict[str, Any]]:
    updates: dict[str, dict[str, Any]] = {}
    known = set(TASK_TO_DELIVERABLES.get(task_key, []))
    for deliverable_key in known:
        path_value = DELIVERABLE_BLUEPRINTS.get(deliverable_key, {}).get("path")
        path = Path(path_value) if path_value else None
        if path is not None:
            updates[deliverable_key] = {
                "available": path.exists(),
                "updated_at": _file_timestamp(path),
                "source": "task_runtime",
            }
    for path_value in paths:
        path = Path(path_value)
        for key, blueprint in DELIVERABLE_BLUEPRINTS.items():
            if str(path) == blueprint["path"]:
                updates[key] = {
                    "available": path.exists(),
                    "updated_at": _file_timestamp(path),
                    "source": "task_runtime",
                }
    if task_key == "snapshot":
        archive_path = next((Path(value) for value in paths if str(value).endswith(".zip")), None)
        if archive_path is not None:
            updates["snapshot_archive"] = {
                "label": "快照归档",
                "path": str(archive_path),
                "available": archive_path.exists(),
                "updated_at": _file_timestamp(archive_path),
                "source": "task_runtime",
            }
    return updates



def get_role_pages(role: str, state: dict[str, Any] | None = None) -> list[str]:
    current_state = state or load_system_state()
    role_permissions = current_state.get("settings", {}).get("role_permissions", {})
    if isinstance(role_permissions, dict):
        pages = role_permissions.get(role)
        if isinstance(pages, list) and pages:
            return _normalize_role_pages(pages)
    return _normalize_role_pages(ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["管理员"]))



def task_stage_items(state: dict[str, Any]) -> list[dict[str, str]]:
    review_metrics = state["observability"]["review_queue"]
    survey_metrics = state["observability"]["survey"]
    deliverables = state["observability"]["deliverables"]
    items: list[dict[str, str]] = []
    task_index = {task["stage_key"]: state["tasks"][task["task_key"]] for task in TASK_BLUEPRINTS}

    for blueprint in TASK_BLUEPRINTS:
        task = task_index[blueprint["stage_key"]]
        status = task.get("status", "not_started")
        if status == "completed":
            tone = "success"
            status_label = STATUS_LABELS["completed"]
        elif status in {"running", "in_progress", "ready"}:
            tone = "info"
            status_label = STATUS_LABELS.get(status, "当前阶段")
        elif status == "failed":
            tone = "danger"
            status_label = STATUS_LABELS["failed"]
        elif status == "blocked":
            tone = "danger"
            status_label = STATUS_LABELS["blocked"]
        else:
            tone = "neutral"
            status_label = STATUS_LABELS["not_started"]

        note = task.get("summary", "")
        if blueprint["task_key"] == "generation":
            if review_metrics["total"] > 0:
                note = f"已生成并过滤 {review_metrics['total']} 道候选题，等待人工审核。"
            elif deliverables.get("generation_manifest", {}).get("available"):
                note = "本轮已执行生成，但过滤后暂无进入审核队列的候选题。"
        elif blueprint["task_key"] == "review":
            if status == "completed":
                note = f"已定稿入库，共 {review_metrics.get('approved_total', 0)} 道题进入正式题库。"
            elif status == "ready":
                note = f"审核已完成，待定稿入库，共 {review_metrics.get('approved_total', 0)} 道通过题。"
            else:
                note = f"当前待处理 {review_metrics['pending']} 道候选题。"
        elif blueprint["task_key"] == "evaluation" and status == "blocked" and task.get("block_reason"):
            note = task["block_reason"]
        elif blueprint["task_key"] == "survey_collect":
            note = f"当前已提交 {survey_metrics['submitted_count']} 份答卷。"
        elif blueprint["task_key"] == "freeze":
            note = f"冻结阈值 {survey_metrics['freeze_threshold']}，当前已锁定 {survey_metrics['scanned_count']} 人。"
        elif blueprint["task_key"] == "snapshot" and deliverables.get("snapshot_archive", {}).get("available"):
            note = f"最近快照归档时间：{deliverables['snapshot_archive'].get('updated_at', '未记录')}。"
        elif task.get("block_reason"):
            note = task["block_reason"]

        items.append(
            {
                "key": blueprint["stage_key"],
                "label": blueprint["label"],
                "status": status,
                "status_label": status_label,
                "tone": tone,
                "note": note,
            }
        )
    return items

def system_summary(state: dict[str, Any]) -> dict[str, Any]:
    review = state["observability"]["review_queue"]
    survey = state["observability"]["survey"]
    tasks = state["tasks"]
    work_orders = state.get("orchestration", {}).get("work_orders", {})
    failed_tasks = sum(1 for task in tasks.values() if task.get("status") == "failed")
    open_work_orders = sum(1 for row in work_orders.values() if row.get("status") in {"queued", "running"})
    failed_work_orders = sum(1 for row in work_orders.values() if row.get("status") == "failed")
    return {
        "batch_name": state["settings"]["batch_name"],
        "current_mainline": state["settings"]["current_mainline"],
        "pending_review": review["pending"],
        "missing_assets": review.get("approved_missing_assets", review["missing_assets"]),
        "effective_samples": survey["effective_samples"],
        "submitted_count": survey["submitted_count"],
        "failed_tasks": failed_tasks,
        "open_work_orders": open_work_orders,
        "failed_work_orders": failed_work_orders,
        "report_ready": tasks["report"]["status"] == "completed",
        "snapshot_ready": tasks["snapshot"]["status"] == "completed",
        "updated_at": state["updated_at"],
    }


def _default_retry_policies() -> dict[str, dict[str, Any]]:
    policies: dict[str, dict[str, Any]] = {}
    for blueprint in TASK_BLUEPRINTS:
        task_key = blueprint["task_key"]
        defaults = RETRY_POLICY_BLUEPRINTS.get(task_key, {"max_retries": 0, "recovery_actions": ["mark_ready"]})
        policies[task_key] = {
            "max_retries": int(defaults.get("max_retries", 0)),
            "recovery_actions": list(defaults.get("recovery_actions", ["mark_ready"])),
        }
    return policies



def _ensure_orchestration(state: dict[str, Any]) -> dict[str, Any]:
    orchestration = state.setdefault("orchestration", {})
    orchestration.setdefault("retry_policies", _default_retry_policies())
    orchestration.setdefault("work_orders", {})
    for task_key, payload in _default_retry_policies().items():
        current = orchestration["retry_policies"].setdefault(task_key, {})
        current.setdefault("max_retries", int(payload.get("max_retries", 0)))
        current.setdefault("recovery_actions", list(payload.get("recovery_actions", ["mark_ready"])))
    return orchestration



def _task_blueprint(task_key: str) -> dict[str, Any]:
    for blueprint in TASK_BLUEPRINTS:
        if blueprint["task_key"] == task_key:
            return blueprint
    return {}



def _work_order_sort_key(order: dict[str, Any]) -> str:
    return str(order.get("updated_at") or order.get("created_at") or "")



def _new_work_order_id(task_key: str) -> str:
    slug = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"wo-{task_key}-{slug}-{uuid4().hex[:6]}"



def _sync_task_orchestration(state: dict[str, Any]) -> dict[str, Any]:
    orchestration = _ensure_orchestration(state)
    work_orders = orchestration.get("work_orders", {})
    retry_policies = orchestration.get("retry_policies", {})

    for blueprint in TASK_BLUEPRINTS:
        task_key = blueprint["task_key"]
        task = state["tasks"][task_key]
        task_orders = [
            row
            for row in work_orders.values()
            if isinstance(row, dict) and row.get("task_key") == task_key
        ]
        task_orders.sort(key=_work_order_sort_key, reverse=True)

        latest_order = task_orders[0] if task_orders else {}
        active_order = next((row for row in task_orders if row.get("status") in {"queued", "running"}), None)
        execution_orders = [row for row in task_orders if row.get("intent") in {"execution", "retry"}]
        attempt_count = len(
            [row for row in execution_orders if row.get("status") in {"queued", "running", "completed", "failed"}]
        )
        failed_attempts = len([row for row in execution_orders if row.get("status") == "failed"])
        policy = retry_policies.get(task_key, {"max_retries": 0, "recovery_actions": ["mark_ready"]})
        if not isinstance(policy, dict):
            policy = {"max_retries": 0, "recovery_actions": ["mark_ready"]}
        max_retries = int(policy.get("max_retries", 0))
        retry_remaining = 0
        if blueprint.get("action_key"):
            retry_remaining = max(0, max_retries - max(0, attempt_count - 1))
        retry_available = bool(blueprint.get("action_key")) and task.get("status") == "failed" and retry_remaining > 0

        recovery_hint = ""
        if task.get("status") == "failed":
            if retry_available:
                recovery_hint = f"最近工单失败，可立即重试，剩余 {retry_remaining} 次。"
            elif blueprint.get("action_key"):
                recovery_hint = "重试次数已用尽，请人工修复后标记恢复。"
            else:
                recovery_hint = "当前任务需要人工恢复。"
        elif active_order is not None:
            recovery_hint = f"工单 {active_order.get('work_order_id', '')} 正在执行。"

        task["latest_work_order_id"] = str(latest_order.get("work_order_id") or task.get("latest_work_order_id") or "")
        task["active_work_order_id"] = str((active_order or {}).get("work_order_id") or "")
        task["attempt_count"] = attempt_count
        task["failed_attempts"] = failed_attempts
        task["retry_remaining"] = retry_remaining
        task["retry_available"] = retry_available
        task["recovery_hint"] = recovery_hint
        task["retry_policy"] = deepcopy(policy)

    return state


def get_work_order(work_order_id: str) -> dict[str, Any] | None:
    state = load_system_state()
    _ensure_orchestration(state)
    row = state.get("orchestration", {}).get("work_orders", {}).get(work_order_id)
    if not isinstance(row, dict):
        return None
    task = state.get("tasks", {}).get(row.get("task_key", ""), {})
    return {
        **deepcopy(row),
        "time": _format_timestamp(row.get("updated_at") or row.get("created_at")),
        "task_status": task.get("status", "not_started"),
        "task_retry_remaining": task.get("retry_remaining", 0),
        "task_retry_available": task.get("retry_available", False),
        "task_recovery_hint": task.get("recovery_hint", ""),
    }



def get_latest_task_work_order(task_key: str, intents: tuple[str, ...] = ("execution", "retry", "recovery")) -> dict[str, Any] | None:
    state = load_system_state()
    _ensure_orchestration(state)
    rows = [
        row
        for row in state.get("orchestration", {}).get("work_orders", {}).values()
        if row.get("task_key") == task_key and row.get("intent") in intents
    ]
    rows.sort(key=_work_order_sort_key, reverse=True)
    return deepcopy(rows[0]) if rows else None



def list_work_orders(limit: int | None = 100, *, task_key: str = "", statuses: set[str] | None = None) -> list[dict[str, Any]]:
    state = load_system_state()
    _ensure_orchestration(state)
    tasks = state.get("tasks", {})
    rows: list[dict[str, Any]] = []
    for payload in state.get("orchestration", {}).get("work_orders", {}).values():
        if task_key and payload.get("task_key") != task_key:
            continue
        if statuses and payload.get("status") not in statuses:
            continue
        task = tasks.get(payload.get("task_key", ""), {})
        rows.append(
            {
                **deepcopy(payload),
                "time": _format_timestamp(payload.get("updated_at") or payload.get("created_at")),
                "task_status": task.get("status", "not_started"),
                "task_retry_remaining": task.get("retry_remaining", 0),
                "task_retry_available": task.get("retry_available", False),
                "task_recovery_hint": task.get("recovery_hint", ""),
                "status_label": WORK_ORDER_STATUS_LABELS.get(str(payload.get("status") or "").strip(), str(payload.get("status") or "未记录")),
            }
        )
    rows.sort(key=lambda item: _work_order_sort_key(item), reverse=True)
    if limit is not None:
        return rows[:limit]
    return rows



def start_task_work_order(
    task_key: str,
    *,
    actor: str,
    action_key: str = "",
    note: str = "",
    params: dict[str, Any] | None = None,
    intent: str = "execution",
    source_work_order_id: str = "",
) -> dict[str, Any]:
    state = load_system_state()
    orchestration = _ensure_orchestration(state)
    task = state.get("tasks", {}).get(task_key)
    blueprint = _task_blueprint(task_key)
    if not isinstance(task, dict) or not blueprint:
        raise KeyError(f"未找到任务 {task_key}。")

    active_work_order_id = str(task.get("active_work_order_id") or "")
    if active_work_order_id:
        active = orchestration.get("work_orders", {}).get(active_work_order_id, {})
        if active.get("status") in {"queued", "running"}:
            raise RuntimeError("当前任务已有执行中的工单。")

    resolved_action_key = action_key or str(task.get("action_key") or blueprint.get("action_key") or "")
    current_params = deepcopy(params or {})
    policy = orchestration.get("retry_policies", {}).get(task_key, {"max_retries": 0, "recovery_actions": ["mark_ready"]})
    task_orders = [
        row
        for row in orchestration.get("work_orders", {}).values()
        if row.get("task_key") == task_key and row.get("intent") in {"execution", "retry"}
    ]
    task_orders.sort(key=_work_order_sort_key, reverse=True)
    attempt_index = len(task_orders) + 1 if resolved_action_key else 0
    max_retries = int(policy.get("max_retries", 0))
    if intent == "retry" and attempt_index > max_retries + 1:
        raise RuntimeError("当前任务已达到最大重试次数。")

    work_order_id = _new_work_order_id(task_key)
    now = _now_iso()
    work_order = {
        "work_order_id": work_order_id,
        "task_key": task_key,
        "task_label": blueprint.get("label", task_key),
        "owner_role": blueprint.get("owner_role", "管理员"),
        "action_key": resolved_action_key,
        "status": "running",
        "status_label": WORK_ORDER_STATUS_LABELS["running"],
        "intent": intent,
        "attempt_index": attempt_index,
        "max_retries": max_retries,
        "retry_remaining": max(0, max_retries - max(0, attempt_index - 1)) if resolved_action_key else 0,
        "retry_of_work_order_id": source_work_order_id,
        "recovery_actions": list(policy.get("recovery_actions", ["mark_ready"])),
        "created_at": now,
        "updated_at": now,
        "created_by": actor,
        "last_actor": actor,
        "note": note,
        "params": current_params,
        "run_id": "",
        "run_manifest": "",
        "business_manifest": "",
        "outputs": [],
        "logs": [],
        "error": "",
        "message": "",
    }
    orchestration["work_orders"][work_order_id] = work_order
    task["latest_work_order_id"] = work_order_id
    task["active_work_order_id"] = work_order_id
    task["updated_at"] = now
    save_system_state(state)
    record_audit_event(
        "work_order_started",
        actor=actor,
        target=work_order_id,
        status="running",
        detail={
            "task_key": task_key,
            "intent": intent,
            "attempt_index": attempt_index,
            "retry_of": source_work_order_id,
        },
    )
    return get_work_order(work_order_id) or work_order



def complete_task_work_order(
    work_order_id: str,
    *,
    actor: str,
    status: str,
    run_id: str = "",
    message: str = "",
    error: str = "",
    logs: list[str] | None = None,
    outputs: list[str] | None = None,
    run_manifest: str = "",
    business_manifest: str = "",
) -> dict[str, Any] | None:
    state = load_system_state()
    orchestration = _ensure_orchestration(state)
    work_order = orchestration.get("work_orders", {}).get(work_order_id)
    if not isinstance(work_order, dict):
        return None

    now = _now_iso()
    work_order["status"] = status
    work_order["status_label"] = WORK_ORDER_STATUS_LABELS.get(status, status)
    work_order["updated_at"] = now
    work_order["last_actor"] = actor
    work_order["run_id"] = run_id
    work_order["message"] = message
    work_order["error"] = error
    work_order["logs"] = list(logs or [])
    work_order["outputs"] = list(outputs or [])
    work_order["run_manifest"] = run_manifest
    work_order["business_manifest"] = business_manifest

    task = state.get("tasks", {}).get(work_order.get("task_key", ""), {})
    if task.get("active_work_order_id") == work_order_id and status in {"completed", "failed", "recovered", "cancelled"}:
        task["active_work_order_id"] = ""
    task["latest_work_order_id"] = work_order_id
    task["updated_at"] = now

    save_system_state(state)
    record_audit_event(
        "work_order_runtime",
        actor=actor,
        target=work_order_id,
        status=status,
        detail={
            "task_key": work_order.get("task_key", ""),
            "run_id": run_id,
            "message": message,
            "error": error,
        },
    )
    return get_work_order(work_order_id)



def mark_task_recovered(
    task_key: str,
    *,
    actor: str,
    note: str = "",
    source_work_order_id: str = "",
) -> dict[str, Any]:
    state = load_system_state()
    orchestration = _ensure_orchestration(state)
    blueprint = _task_blueprint(task_key)
    task = state.get("tasks", {}).get(task_key)
    if not isinstance(task, dict) or not blueprint:
        raise KeyError(f"未找到任务 {task_key}。")

    work_order_id = _new_work_order_id(task_key)
    now = _now_iso()
    work_order = {
        "work_order_id": work_order_id,
        "task_key": task_key,
        "task_label": blueprint.get("label", task_key),
        "owner_role": blueprint.get("owner_role", "管理员"),
        "action_key": str(task.get("action_key") or blueprint.get("action_key") or ""),
        "status": "recovered",
        "status_label": WORK_ORDER_STATUS_LABELS["recovered"],
        "intent": "recovery",
        "attempt_index": int(task.get("attempt_count") or 0),
        "max_retries": int(orchestration.get("retry_policies", {}).get(task_key, {}).get("max_retries", 0)),
        "retry_remaining": int(task.get("retry_remaining") or 0),
        "retry_of_work_order_id": source_work_order_id,
        "recovery_actions": ["mark_ready"],
        "created_at": now,
        "updated_at": now,
        "created_by": actor,
        "last_actor": actor,
        "note": note or "人工修复后重新开放执行。",
        "params": {"strategy": "mark_ready"},
        "run_id": "",
        "run_manifest": "",
        "business_manifest": "",
        "outputs": [],
        "logs": [],
        "error": "",
        "message": note or "任务已标记恢复。",
    }
    orchestration["work_orders"][work_order_id] = work_order
    task["status"] = "ready"
    task["latest_status"] = "ready"
    task["latest_message"] = work_order["message"]
    task["latest_error"] = ""
    task["latest_work_order_id"] = work_order_id
    task["active_work_order_id"] = ""
    task["updated_at"] = now
    save_system_state(state)
    record_audit_event(
        "task_recovered",
        actor=actor,
        target=task_key,
        status="success",
        detail={
            "work_order_id": work_order_id,
            "source_work_order_id": source_work_order_id,
            "note": work_order["note"],
        },
    )
    return work_order













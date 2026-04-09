from __future__ import annotations

import copy
import io
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from pandas.errors import EmptyDataError

from .actions import get_action
from .generation_pipeline import build_generation_metrics, sync_review_state_from_filtered
from .system_store import (
    apply_review_state,
    get_role_pages as get_role_pages_from_system,
    list_work_orders,
    load_audit_events,
    load_system_state,
    record_audit_event,
    system_summary as build_system_summary,
    task_stage_items,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "results"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
CURATED_DIR = RESULTS_DIR / "curated"
STUDENT_DIR = RESULTS_DIR / "student_subsets"
PACKETS_DIR = CURATED_DIR / "human_eval_packets"
CHAPTER5_DIR = STUDENT_DIR / "chapter5_outputs"
CHAPTER5_TABLES_DIR = CHAPTER5_DIR / "tables"
CHAPTER5_FIGURES_DIR = CHAPTER5_DIR / "figures"
SYSTEM_DIR = OUTPUTS_DIR / "system"

WORKFLOW_STATE_PATH = SYSTEM_DIR / "workflow_state.v1.json"
REPORT_SUMMARY_PATH = SYSTEM_DIR / "report_summary.v1.json"
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
SAMPLE_OVERVIEW_PATH = CHAPTER5_TABLES_DIR / "sample_overview.csv"
ITEM_BY_SOURCE_PATH = CHAPTER5_TABLES_DIR / "item_metrics_by_source.csv"
BATCH_OVERALL_PATH = CHAPTER5_TABLES_DIR / "batch_metrics_overall.csv"
SIGNIFICANCE_ITEM_PATH = CHAPTER5_TABLES_DIR / "significance_ai_vs_expert_item_metrics.csv"
SIGNIFICANCE_TOPIC_PATH = CHAPTER5_TABLES_DIR / "significance_ai_vs_expert_by_topic.csv"
CORRELATION_EXERCISE_PATH = CHAPTER5_TABLES_DIR / "correlation_auto_vs_student.exercise_metrics.v1.csv"
CORRELATION_PAIR_PATH = CHAPTER5_TABLES_DIR / "correlation_auto_vs_student.pair_metrics_ai_only.v1.csv"
RUN_RECORDS_PATH = SYSTEM_DIR / "run_records.v1.jsonl"
TASK_JOURNAL_PATH = SYSTEM_DIR / "task_journal.v1.jsonl"
REVIEW_STATE_PATH = SYSTEM_DIR / "review_state.v1.json"
SNAPSHOTS_DIR = SYSTEM_DIR / "snapshots"
RUNS_DIR = SYSTEM_DIR / "runs"

TOPIC_LABELS = {
    "CNN": "卷积神经网络（CNN）",
    "RNN": "循环神经网络（RNN）",
    "RNN / LSTM": "循环神经网络（RNN）",
    "Transformer": "Transformer 模型（Transformer）",
    "Optimization": "优化训练",
    "优化与训练分析": "优化训练",
}
DIFFICULTY_LABELS = {
    "Beginner": "基础",
    "beginner": "基础",
    "Intermediate": "中级",
    "intermediate": "中级",
    "Advanced": "高级",
    "advanced": "高级",
    "beginner-intermediate": "基础到中级",
    "intermediate-advanced": "中高级",
}
EXERCISE_TYPE_LABELS = {
    "Code Completion": "代码补全",
    "code completion": "代码补全",
    "Model Building": "模型构建",
    "model building": "模型构建",
    "Model Revision": "模型修正",
    "model revision": "模型修正",
    "Training Analysis": "训练分析",
    "training-analysis": "训练分析",
    "概念转代码": "代码补全",
}
ROLE_PERMISSIONS = {
    "管理员": ["流程总览", "题目生成", "当前任务", "审核中心", "问卷管理", "分析报告", "运行记录", "系统设置"],
    "研究员": ["流程总览", "题目生成", "当前任务", "审核中心", "问卷管理", "分析报告", "运行记录"],
}


def _normalize_role_name(role_name: str) -> str:
    normalized = str(role_name or "").strip()
    return "研究员" if normalized == "审核员" else normalized


def _normalize_role_pages(pages: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for page in pages:
        if not isinstance(page, str):
            continue
        candidate = page.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    if "流程总览" not in seen:
        normalized.insert(0, "流程总览")
    return normalized

STAGE_DEFINITIONS = [
    ("generation", "题目生成"),
    ("review", "人工审核"),
    ("evaluation", "自动评测"),
    ("survey_publish", "问卷发放"),
    ("survey_collect", "问卷回收"),
    ("freeze", "冻结样本"),
    ("report", "分析报告"),
    ("snapshot", "快照发布"),
]
STATUS_META = {
    "done": ("已完成", "success"),
    "current": ("当前阶段", "info"),
    "pending": ("未开始", "neutral"),
    "blocked": ("阻塞", "danger"),
}
RUN_STATUS_LABELS = {
    "success": ("成功", "success"),
    "failed": ("失败", "danger"),
    "running": ("执行中", "warning"),
    "queued": ("待执行", "info"),
}
TASK_STATUS_LABELS = {
    "not_started": "未开始",
    "ready": "可执行",
    "blocked": "阻塞",
    "running": "执行中",
    "in_progress": "进行中",
    "completed": "已完成",
    "failed": "失败",
}

def topic_label(value: str) -> str:
    return TOPIC_LABELS.get(str(value or "").strip(), str(value or "").strip())


def difficulty_label(value: str) -> str:
    return DIFFICULTY_LABELS.get(str(value or "").strip(), str(value or "").strip())


def exercise_type_label(value: str) -> str:
    return EXERCISE_TYPE_LABELS.get(str(value or "").strip(), str(value or "").strip())


def prompt_version_label(value: str) -> str:
    text = str(value or "").strip()
    return f"模板版本 {text}" if text else "未设置"


def model_label(value: str) -> str:
    text = str(value or "").strip()
    return f"生成模型 {text}" if text else "未设置"


def identifier_label(field_name: str) -> str:
    return {
        "task_id": "任务编号",
        "candidate_id": "候选编号",
        "review_id": "审核工单编号",
        "reference_id": "参考题编号",
        "batch_id": "批次编号",
        "pair_id": "配对编号",
        "exercise_id": "题目编号",
    }.get(field_name, field_name)


def resolve_path(path_value: str | Path) -> Path:
    if isinstance(path_value, Path):
        return path_value
    text = str(path_value or "").strip()
    if not text:
        return PROJECT_ROOT
    candidate = Path(text)
    if candidate.is_absolute():
        return candidate
    return PROJECT_ROOT / text.replace("\\", "/")


@st.cache_data(show_spinner=False)
def load_csv(path: str | Path) -> pd.DataFrame:
    csv_path = resolve_path(path)
    if not csv_path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(csv_path)
    except EmptyDataError:
        return pd.DataFrame()


@st.cache_data(show_spinner=False)
def load_json_doc(path: str | Path) -> dict[str, Any]:
    json_path = resolve_path(path)
    if not json_path.exists():
        return {}
    try:
        return json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def load_jsonl_docs(path: str | Path) -> list[dict[str, Any]]:
    jsonl_path = resolve_path(path)
    rows: list[dict[str, Any]] = []
    if not jsonl_path.exists():
        return rows
    with jsonl_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def save_json_doc(path: str | Path, doc: dict[str, Any]) -> None:
    json_path = resolve_path(path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl_doc(path: str | Path, row: dict[str, Any]) -> None:
    jsonl_path = resolve_path(path)
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with jsonl_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def format_timestamp(value: Any) -> str:
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


def format_file_timestamp(path: str | Path) -> str:
    file_path = resolve_path(path)
    if not file_path.exists():
        return "未生成"
    modified = datetime.fromtimestamp(file_path.stat().st_mtime)
    return modified.strftime("%Y-%m-%d %H:%M")


def status_badge(status: str) -> tuple[str, str]:
    return STATUS_META.get(status, STATUS_META["pending"])


def run_status_badge(status: str) -> tuple[str, str]:
    return RUN_STATUS_LABELS.get(status, RUN_STATUS_LABELS["queued"])



def task_status_label(status: str) -> str:
    return TASK_STATUS_LABELS.get(str(status or "").strip(), str(status or "未开始"))


def _safe_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _max_timestamp(series: pd.Series) -> str:
    if series.empty:
        return "未记录"
    try:
        parsed = pd.to_datetime(series, utc=True, errors="coerce").dropna()
        if parsed.empty:
            return "未记录"
        return parsed.max().tz_convert("Asia/Shanghai").strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "未记录"


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
    unevaluated = sum(1 for item in items if item.get("eval_status") != "ready")
    high_risk = sum(
        1
        for item in items
        if item.get("code_state") != "valid"
        or str(item.get("difficulty") or "").lower() == "advanced"
        or not item.get("tests_overlay_ready")
    )
    return {
        "pending": pending,
        "approved": approved,
        "rejected": rejected,
        "missing_assets": missing_assets,
        "approved_missing_assets": approved_missing_assets,
        "approved_total": approved,
        "unevaluated": unevaluated,
        "high_risk": high_risk,
    }

def build_survey_metrics(bundle: dict[str, Any]) -> dict[str, Any]:
    participant_meta = bundle["participant_meta"]
    batch_feedback = bundle["batch_feedback"]
    distribution = bundle["distribution_sheet"]
    subset_manifest = bundle["subset_manifest"]
    chapter5_manifest = bundle["chapter5_manifest"]
    workflow_state = bundle["workflow_state"]

    raw_issued_count = int(len(distribution))
    submitted_count = int(len(batch_feedback))
    selected_participants = _safe_int(
        subset_manifest.get("selection_summary", {}).get("selected_participants")
    )
    issued_count = selected_participants or submitted_count or raw_issued_count
    effective_samples = _safe_int(
        chapter5_manifest.get("filter_summary", {}).get("participants_after_filter")
    )
    attention_fail_count = 0
    if not participant_meta.empty and "attention_check_passed" in participant_meta.columns:
        attention_fail_count = int(
            (~participant_meta["attention_check_passed"].astype(str).str.lower().eq("true")).sum()
        )

    latest_submit = (
        _max_timestamp(participant_meta["submitted_at"])
        if not participant_meta.empty and "submitted_at" in participant_meta.columns
        else "未记录"
    )
    freeze_threshold = _safe_int(
        workflow_state.get("admin_settings", {}).get("freeze_threshold") or 30
    )
    threshold_ready = selected_participants >= freeze_threshold or submitted_count >= freeze_threshold

    return {
        "issued_count": issued_count,
        "scanned_count": selected_participants or submitted_count,
        "submitted_count": submitted_count,
        "effective_samples": effective_samples,
        "attention_fail_count": attention_fail_count,
        "latest_submit": latest_submit,
        "freeze_threshold": freeze_threshold,
        "threshold_ready": threshold_ready,
        "data_synced": submitted_count > 0,
        "formal_batch_ready": bool(subset_manifest),
        "qrcode_ready": QRCODE_SHEET_PATH.exists(),
    }


def build_stage_items(bundle: dict[str, Any]) -> list[dict[str, str]]:
    return task_stage_items(bundle["system_state"])


def build_recent_artifacts(system_state: dict[str, Any]) -> list[dict[str, str]]:
    deliverables = system_state.get("observability", {}).get("deliverables", {})
    available: list[dict[str, str]] = []
    for row in deliverables.values():
        if not row.get("available"):
            continue
        available.append(
            {
                "label": str(row.get("label", "系统交付物")),
                "path": str(row.get("path", "")),
                "description": "系统登记的交付物入口。",
                "updated_at": str(row.get("updated_at", "未生成")),
            }
        )
    available.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    return available


def load_review_state_doc() -> dict[str, Any]:
    review_doc = load_json_doc(REVIEW_STATE_PATH)
    if isinstance(review_doc.get("items"), list) and review_doc.get("items"):
        return review_doc
    return sync_review_state_from_filtered(review_doc)

def save_review_state(items: list[dict[str, Any]], history: dict[str, list[dict[str, str]]]) -> None:
    save_json_doc(
        REVIEW_STATE_PATH,
        {
            "updated_at": datetime.now().isoformat(),
            "items": items,
            "history": history,
        },
    )


def set_console_flash(message: str, tone: str = "success") -> None:
    st.session_state["console_flash"] = {"message": message, "tone": tone}


def pop_console_flash() -> dict[str, str] | None:
    flash = st.session_state.get("console_flash")
    if flash is not None:
        del st.session_state["console_flash"]
    return flash


def load_run_records_from_disk() -> list[dict[str, Any]]:
    records = load_jsonl_docs(RUN_RECORDS_PATH)
    enriched: list[dict[str, Any]] = []
    for row in records:
        started_at = row.get("started_at")
        finished_at = row.get("finished_at") or started_at
        duration_seconds = row.get("duration_seconds")
        if duration_seconds in (None, ""):
            duration = row.get("duration") or "未记录"
        else:
            duration = f"{float(duration_seconds):.1f}s"
        enriched.append(
            {
                **row,
                "time": format_timestamp(finished_at),
                "sort_key": str(finished_at or ""),
                "duration": duration,
                "business_manifest": row.get("business_manifest", row.get("manifest", "")),
                "logs": row.get("logs", []),
                "params": row.get("params", {}),
            }
        )
    return enriched


def build_dashboard_bundle() -> dict[str, Any]:
    legacy_workflow = load_json_doc(WORKFLOW_STATE_PATH)
    system_state = load_system_state()
    review_state = load_review_state_doc()
    review_items = review_state.get("items") or []
    review_summary = _review_counts(review_items)
    review_summary["total"] = len(review_items)

    settings = system_state.get("settings", {})
    survey_metrics = copy.deepcopy(system_state.get("observability", {}).get("survey", {}))
    deliverables = copy.deepcopy(system_state.get("observability", {}).get("deliverables", {}))
    tasks = copy.deepcopy(system_state.get("tasks", {}))
    generation_metrics = build_generation_metrics(review_items)
    generation_config = legacy_workflow.get("generation", {}).get("config", {}) if isinstance(legacy_workflow, dict) else {}

    package_manifest = pd.DataFrame([{"registered": True}]) if deliverables.get("packet_manifest", {}).get("available") else pd.DataFrame()
    subset_manifest = {"registered": True} if deliverables.get("subset_manifest", {}).get("available") else {}
    chapter5_manifest = {"registered": True} if deliverables.get("report_manifest", {}).get("available") else {}
    significance_manifest = {"registered": True} if deliverables.get("significance_manifest", {}).get("available") else {}
    correlation_manifest = {"registered": True} if deliverables.get("correlation_manifest", {}).get("available") else {}

    bundle = {
        "system_state": system_state,
        "workflow_state": legacy_workflow or {
            "updated_at": system_state.get("updated_at", "未记录"),
            "current_stage": system_state.get("pipeline", {}).get("current_stage", "generation"),
            "snapshot_locked": tasks.get("snapshot", {}).get("status") == "completed",
        },
        "generation_metrics": generation_metrics,
        "generation_config": {
            "prompt_version": str(generation_config.get("prompt_version") or "MP-v1"),
            "topic": str(generation_config.get("topic") or ""),
            "difficulty": str(generation_config.get("difficulty") or ""),
            "exercise_type": str(generation_config.get("exercise_type") or ""),
            "reference_id": str(generation_config.get("reference_id") or ""),
            "provider": str(generation_config.get("provider") or "bailian"),
            "model": str(generation_config.get("model") or "qwen-plus"),
            "generation_batch": str(generation_config.get("generation_batch") or ""),
            "num_candidates": _safe_int(generation_config.get("count") or generation_config.get("num_candidates") or 2) or 2,
            "temperature": float(generation_config.get("temperature") or 0.7),
            "max_tokens": _safe_int(generation_config.get("max_tokens") or 2200) or 2200,
            "limit": _safe_int(generation_config.get("limit") or 0),
            "strict_filter": bool(generation_config.get("strict_filter") or False),
            "min_instruction_completeness": generation_config.get("min_instruction_completeness") or "",
            "min_structure_completeness": generation_config.get("min_structure_completeness") or "",
            "min_objective_overlap": generation_config.get("min_objective_overlap") or "",
        },
        "report_summary": load_json_doc(REPORT_SUMMARY_PATH) or {
            "report_ready": tasks.get("report", {}).get("status") == "completed",
            "status": tasks.get("report", {}).get("status", "not_started"),
        },
        "curated_analysis_status": load_json_doc(CURATED_ANALYSIS_STATUS_PATH) or {
            "status": "ready" if tasks.get("evaluation", {}).get("status") == "completed" else tasks.get("evaluation", {}).get("status", "blocked"),
        },
        "package_manifest": package_manifest,
        "distribution_sheet": pd.DataFrame(),
        "participant_meta": pd.DataFrame(),
        "item_ratings": pd.DataFrame(),
        "batch_feedback": pd.DataFrame(),
        "subset_manifest": subset_manifest,
        "master_manifest": {"registered": True} if deliverables.get("master_manifest", {}).get("available") else {},
        "chapter5_manifest": chapter5_manifest,
        "significance_manifest": significance_manifest,
        "correlation_manifest": correlation_manifest,
        "sample_overview": pd.DataFrame(),
        "item_by_source": pd.DataFrame(),
        "batch_overall": pd.DataFrame(),
        "significance_item": pd.DataFrame(),
        "significance_topic": pd.DataFrame(),
        "correlation_exercise": pd.DataFrame(),
        "correlation_pair": pd.DataFrame(),
        "review_items": review_items,
        "review_summary": review_summary,
        "settings": {
            "batch_name": str(settings.get("batch_name") or system_state.get("batch", {}).get("batch_name", "2026 春季正式批次")),
            "freeze_threshold": _safe_int(settings.get("freeze_threshold") or 30),
            "current_mainline": str(settings.get("current_mainline") or "学生问卷主线"),
            "role_permissions": settings.get("role_permissions", ROLE_PERMISSIONS),
            "data_source": settings.get("data_source", {}),
            "paths": settings.get("paths", {}),
        },
        "role_options": list(ROLE_PERMISSIONS.keys()),
        "batch_options": [str(settings.get("batch_name") or system_state.get("batch", {}).get("batch_name", "2026 春季正式批次"))],
        "survey_metrics": survey_metrics,
        "stages": task_stage_items(system_state),
        "recent_artifacts": build_recent_artifacts(system_state),
        "tasks": tasks,
        "deliverables": deliverables,
        "work_orders": list_work_orders(200),
        "audit_events": load_audit_events(120),
        "system_summary": build_system_summary(system_state),
    }
    return bundle

def init_session_state(bundle: dict[str, Any]) -> None:
    if "console_batch" not in st.session_state:
        st.session_state["console_batch"] = bundle["batch_options"][0]

    current_role = _normalize_role_name(str(st.session_state.get("console_role") or "管理员"))
    if current_role not in ROLE_PERMISSIONS:
        current_role = "管理员"
    st.session_state["console_role"] = current_role

    if "console_page" not in st.session_state:
        st.session_state["console_page"] = "流程总览"

    review_state = load_review_state_doc()
    review_items = copy.deepcopy(review_state.get("items") or bundle["review_items"])
    review_history = review_state.get("history") or {}
    review_updated_at = str(review_state.get("updated_at") or "")
    if not review_history:
        generated_history: dict[str, list[dict[str, str]]] = {}
        for item in review_items:
            generated_history[item.get("candidate_id", "")] = [
                {
                    "time": format_timestamp(bundle["workflow_state"].get("updated_at")),
                    "operator": "系统",
                    "action": item.get("last_action") or "进入审核队列",
                }
            ]
        review_history = generated_history

    if st.session_state.get("review_state_updated_at") != review_updated_at:
        st.session_state["review_items_state"] = review_items
        st.session_state["review_history_state"] = review_history
        st.session_state["review_state_updated_at"] = review_updated_at
        st.session_state["review_cursor"] = 0
    elif "review_items_state" not in st.session_state:
        st.session_state["review_items_state"] = review_items
        st.session_state["review_history_state"] = review_history
        st.session_state["review_state_updated_at"] = review_updated_at

    if "settings_form_state" not in st.session_state:
        st.session_state["settings_form_state"] = copy.deepcopy(bundle["settings"])
    else:
        st.session_state["settings_form_state"]["role_permissions"] = copy.deepcopy(bundle["settings"].get("role_permissions", ROLE_PERMISSIONS))
    if "snapshot_locked_override" not in st.session_state:
        st.session_state["snapshot_locked_override"] = bundle.get("tasks", {}).get("snapshot", {}).get("status") == "completed"
    if "review_cursor" not in st.session_state:
        st.session_state["review_cursor"] = 0
    if "freeze_confirm_open" not in st.session_state:
        st.session_state["freeze_confirm_open"] = False

def current_review_items() -> list[dict[str, Any]]:
    return st.session_state.get("review_items_state", [])


def current_review_summary() -> dict[str, int]:
    items = current_review_items()
    summary = _review_counts(items)
    summary["total"] = len(items)
    return summary


def append_history(candidate_id: str, action: str, operator: str) -> None:
    history = st.session_state.setdefault("review_history_state", {})
    history.setdefault(candidate_id, []).insert(
        0,
        {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "operator": operator,
            "action": action,
        },
    )
    items = current_review_items()
    save_review_state(items, history)
    apply_review_state(items)
    record_audit_event(
        "review_action",
        actor=operator,
        target=candidate_id or "unknown_candidate",
        status="success",
        detail={"action": action},
    )


def append_run_event(
    action_key: str,
    *,
    status: str = "success",
    operator: str = "管理员",
    note: str = "",
    outputs: list[str] | None = None,
    manifest: str = "",
    business_manifest: str = "",
    scripts: list[str] | None = None,
    inputs: list[str] | None = None,
    logs: list[str] | None = None,
    error: str = "",
    params: dict[str, Any] | None = None,
    work_order_id: str = "",
    run_id: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    duration_seconds: float | None = None,
) -> dict[str, Any]:
    action = get_action(action_key)
    started_at = started_at or datetime.now().isoformat()
    finished_at = finished_at or started_at
    duration_seconds = 0.0 if duration_seconds is None else float(duration_seconds)
    record_id = run_id or f"manual-{action_key}-{datetime.now().timestamp()}"
    event = {
        "id": record_id,
        "action_key": action_key,
        "action_name": action["label"],
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": duration_seconds,
        "operator": operator,
        "note": note,
        "outputs": outputs or [str(path) for path in action["output_paths"]],
        "manifest": manifest or (str(action["manifest_path"]) if action["manifest_path"] else ""),
        "business_manifest": business_manifest or (str(action["manifest_path"]) if action["manifest_path"] else ""),
        "scripts": scripts or [str(path) for path in action["script_paths"]],
        "inputs": inputs or [str(path) for path in action["input_paths"]],
        "logs": logs or [],
        "params": params or {},
        "work_order_id": work_order_id,
        "error": error,
        "time": format_timestamp(finished_at),
        "duration": f"{duration_seconds:.1f}s",
    }
    append_jsonl_doc(RUN_RECORDS_PATH, event)
    append_jsonl_doc(
        TASK_JOURNAL_PATH,
        {
            "recorded_at": finished_at,
            "run_id": record_id,
            "action_key": action_key,
            "action_name": action["label"],
            "status": status,
            "operator": operator,
            "note": note,
            "params": params or {},
            "error": error,
        },
    )
    return event


def _build_base_run_records(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    tasks = bundle.get("tasks", {})
    deliverables = bundle.get("deliverables", {})

    def action_status(task_status: str) -> str:
        return {
            "completed": "success",
            "failed": "failed",
            "running": "running",
            "ready": "queued",
            "in_progress": "running",
        }.get(task_status, "queued")

    def add_task_record(action_key: str, task_key: str, deliverable_key: str, note: str) -> None:
        task = tasks.get(task_key, {})
        task_status = str(task.get("status") or "not_started")
        if task_status in {"not_started", "blocked"}:
            return

        action = get_action(action_key)
        deliverable = deliverables.get(deliverable_key, {}) if deliverable_key else {}
        manifest_path = str(deliverable.get("path") or (action["manifest_path"] if action["manifest_path"] else ""))
        outputs = [manifest_path] if manifest_path else [str(item) for item in action["output_paths"]]
        timestamp = str(task.get("latest_run_at") or deliverable.get("updated_at") or bundle["workflow_state"].get("updated_at"))
        records.append(
            {
                "id": f"base-{action_key}",
                "action_key": action_key,
                "action_name": action["label"],
                "status": action_status(task_status),
                "time": format_timestamp(timestamp),
                "sort_key": str(task.get("latest_run_at") or ""),
                "duration": "系统登记",
                "operator": "系统",
                "note": str(task.get("latest_message") or note),
                "outputs": outputs,
                "manifest": manifest_path,
                "business_manifest": manifest_path,
                "scripts": [str(item) for item in action["script_paths"]],
                "inputs": [str(item) for item in action["input_paths"]],
                "logs": [],
                "params": {},
                "error": str(task.get("latest_error") or ""),
            }
        )

    add_task_record("start_generation", "generation", "generation_manifest", "题目生成批次已登记到系统状态。")
    if bundle.get("review_summary", {}).get("total", 0) > 0:
        add_task_record("finalize_review_batch", "review", "final_pairs", "人工审核定稿链已登记到系统状态。")
    add_task_record("run_auto_evaluation", "evaluation", "evaluation_status", "自动评测链已登记到系统状态。")
    add_task_record("generate_student_packets", "survey_publish", "packet_manifest", "问卷发放链已登记到系统状态。")
    add_task_record("freeze_analysis_input", "freeze", "subset_manifest", "冻结输入已登记到系统状态。")
    add_task_record("generate_analysis_report", "report", "report_summary", "报告链已登记到系统状态。")
    add_task_record("publish_snapshot", "snapshot", "snapshot_archive", "完整快照已登记到系统状态。")
    return records

def list_run_records(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    persisted = load_run_records_from_disk()
    seen_action_keys = {row.get("action_key") for row in persisted}
    base_records = [row for row in _build_base_run_records(bundle) if row.get("action_key") not in seen_action_keys]
    records = persisted + base_records
    records.sort(key=lambda item: item.get("sort_key", item.get("time", "")), reverse=True)
    return records


def get_role_pages(role: str) -> list[str]:
    normalized_role = _normalize_role_name(role)
    settings = st.session_state.get("settings_form_state", {})
    role_permissions = settings.get("role_permissions", {}) if isinstance(settings, dict) else {}
    if isinstance(role_permissions, dict):
        merged_permissions: dict[str, list[str]] = {}
        for raw_role_name, pages in role_permissions.items():
            role_name = _normalize_role_name(raw_role_name)
            if isinstance(pages, list):
                merged_permissions.setdefault(role_name, []).extend(pages)
        pages = merged_permissions.get(normalized_role)
        if isinstance(pages, list) and pages:
            return _normalize_role_pages(pages)
    return _normalize_role_pages(get_role_pages_from_system(normalized_role))

def build_export_zip(paths: list[Path]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            if not path.exists():
                continue
            archive.writestr(path.name, path.read_bytes())
    return buffer.getvalue()


def available_report_export_paths() -> list[Path]:
    paths: list[Path] = []
    for candidate in [
        CHAPTER5_MANIFEST_PATH,
        SAMPLE_OVERVIEW_PATH,
        ITEM_BY_SOURCE_PATH,
        BATCH_OVERALL_PATH,
        SIGNIFICANCE_ITEM_PATH,
        SIGNIFICANCE_TOPIC_PATH,
        CORRELATION_EXERCISE_PATH,
        CORRELATION_PAIR_PATH,
    ]:
        if candidate.exists():
            paths.append(candidate)
    return paths


def available_snapshot_checks(bundle: dict[str, Any]) -> list[dict[str, str]]:
    tasks = bundle.get("tasks", {})
    review_complete = tasks.get("review", {}).get("status") == "completed"
    evaluation_ready = tasks.get("evaluation", {}).get("status") == "completed"
    report_ready = tasks.get("report", {}).get("status") == "completed"
    return [
        {
            "label": "正式配对与审核已完成",
            "note": "候选题审核结束后，才能进入正式快照。",
            "status_label": "通过" if review_complete else "未通过",
            "tone": "success" if review_complete else "danger",
        },
        {
            "label": "自动评测已完成",
            "note": "参考解答、功能正确性与统计状态均可读取。",
            "status_label": "通过" if evaluation_ready else "未通过",
            "tone": "success" if evaluation_ready else "danger",
        },
        {
            "label": "分析报告已生成",
            "note": "Chapter 5 结果与报告摘要可导出。",
            "status_label": "通过" if report_ready else "未通过",
            "tone": "success" if report_ready else "danger",
        },
    ]


def can_publish_snapshot(bundle: dict[str, Any]) -> tuple[bool, str]:
    checks = available_snapshot_checks(bundle)
    blocked = [item for item in checks if item["tone"] != "success"]
    if blocked:
        return False, "；".join(item["label"] for item in blocked)
    return True, ""


def narrative_highlights(bundle: dict[str, Any]) -> list[str]:
    highlights = bundle["report_summary"].get("highlights")
    if isinstance(highlights, list) and highlights:
        return [str(item) for item in highlights]
    survey_metrics = bundle["survey_metrics"]
    return [
        f"本次冻结后纳入 {survey_metrics['effective_samples']} 名有效样本。",
        "显著性检验结果以成对比较表为主，便于论文写作直接引用。",
        "相关性分析优先展示自动指标与学生评分的 Spearman 结果。",
    ]



























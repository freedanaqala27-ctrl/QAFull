from __future__ import annotations

import os
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .actions import get_action
from .generation_pipeline import (
    materialize_review_outcomes,
    sync_finalized_results_to_curated,
    sync_review_state_from_filtered,
)
from .state_store import (
    BATCH_FEEDBACK_PATH,
    CHAPTER5_MANIFEST_PATH,
    CORRELATION_EXERCISE_PATH,
    CORRELATION_MANIFEST_PATH,
    CURATED_ANALYSIS_STATUS_PATH,
    ITEM_RATINGS_PATH,
    MASTER_CSV_PATH,
    MASTER_MANIFEST_PATH,
    PACKAGE_MANIFEST_PATH,
    PARTICIPANT_META_PATH,
    REPORT_SUMMARY_PATH,
    REVIEW_STATE_PATH,
    RUNS_DIR,
    SIGNIFICANCE_ITEM_PATH,
    SIGNIFICANCE_MANIFEST_PATH,
    SNAPSHOTS_DIR,
    SUBSET_MANIFEST_PATH,
    WORKFLOW_STATE_PATH,
    append_run_event,
    available_report_export_paths,
    load_json_doc,
    load_jsonl_docs,
    load_review_state_doc,
    resolve_path,
    save_json_doc,
)
from .system_store import (
    complete_task_work_order,
    get_latest_task_work_order,
    load_system_state,
    mark_deliverables_for_task,
    mark_task_recovered,
    record_audit_event,
    start_task_work_order,
    update_settings as update_system_settings,
    update_task_runtime,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_ROOT = PROJECT_ROOT / ".venv"
PYVENV_CFG = VENV_ROOT / "pyvenv.cfg"
VENV_SCRIPTS = VENV_ROOT / "Scripts"
VENV_SITE_PACKAGES = VENV_ROOT / "Lib" / "site-packages"

ASSET_SCRIPT_MAP = {
    "琛ュ叏浠ｇ爜": "scripts/23_populate_code_completion_overlays.py",
    "妯″瀷淇": "scripts/24_populate_model_revision_overlays.py",
    "概念转代码": "scripts/25_populate_concept_to_code_overlays.py",
    "妯″瀷鏋勫缓": "scripts/26_populate_model_building_overlays.py",
    "璁粌鍒嗘瀽": "scripts/27_populate_training_analysis_overlays.py",
}

SECTION_BY_ACTION = {
    "start_generation": "generation",
    "finalize_review_batch": "review",
    "repair_eval_assets": "evaluation",
    "run_auto_evaluation": "evaluation",
    "generate_student_packets": "survey",
    "freeze_analysis_input": "survey_data",
    "generate_analysis_report": "report",
    "publish_snapshot": "snapshot",
    "request_assets": "review",
}

STAGE_AFTER_SUCCESS = {
    "start_generation": "review",
    "finalize_review_batch": "evaluation",
    "repair_eval_assets": "evaluation",
    "run_auto_evaluation": "survey_publish",
    "generate_student_packets": "survey_collect",
    "freeze_analysis_input": "report",
    "generate_analysis_report": "snapshot",
    "publish_snapshot": "snapshot",
}

SUCCESS_STATUS_BY_ACTION = {
    "start_generation": "completed",
    "finalize_review_batch": "completed",
    "repair_eval_assets": "in_progress",
    "run_auto_evaluation": "completed",
    "generate_student_packets": "completed",
    "freeze_analysis_input": "completed",
    "generate_analysis_report": "completed",
    "publish_snapshot": "locked",
    "request_assets": "in_progress",
}

EXECUTABLE_ACTIONS = {
    "start_generation",
    "finalize_review_batch",
    "repair_eval_assets",
    "run_auto_evaluation",
    "generate_student_packets",
    "freeze_analysis_input",
    "generate_analysis_report",
    "publish_snapshot",
    "request_assets",
}

ACTION_TO_TASK_KEY = {
    "start_generation": "generation",
    "finalize_review_batch": "review",
    "repair_eval_assets": "evaluation",
    "run_auto_evaluation": "evaluation",
    "generate_student_packets": "survey_publish",
    "freeze_analysis_input": "freeze",
    "generate_analysis_report": "report",
    "publish_snapshot": "snapshot",
}
TASK_TO_ACTION_KEY = {task_key: action_key for action_key, task_key in ACTION_TO_TASK_KEY.items()}


def action_is_executable(action_key: str) -> bool:
    return action_key in EXECUTABLE_ACTIONS and bool(get_action(action_key).get("can_execute"))


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _timestamp_slug() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or not path.is_file():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _python_executable() -> Path:
    current = Path(sys.executable)
    if current.exists():
        return current

    venv_python = VENV_SCRIPTS / "python.exe"
    if venv_python.exists():
        return venv_python

    if PYVENV_CFG.exists():
        for line in PYVENV_CFG.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("executable = "):
                candidate = Path(line.split("=", 1)[1].strip())
                if candidate.exists():
                    return candidate

    return current


def _build_runtime_env() -> dict[str, str]:
    env = dict(os.environ)

    pythonpath_parts: list[str] = [str(PROJECT_ROOT)]
    if VENV_SITE_PACKAGES.exists():
        pythonpath_parts.append(str(VENV_SITE_PACKAGES))
    existing_pythonpath = env.get("PYTHONPATH", "").strip()
    if existing_pythonpath:
        pythonpath_parts.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(pythonpath_parts))

    if VENV_SCRIPTS.exists():
        existing_path = env.get("PATH", "")
        env["PATH"] = str(VENV_SCRIPTS) if not existing_path else f"{VENV_SCRIPTS}{os.pathsep}{existing_path}"

    admin_settings = load_json_doc(WORKFLOW_STATE_PATH).get("admin_settings", {})
    data_source = admin_settings.get("data_source", {}) if isinstance(admin_settings, dict) else {}
    supabase_url = str(data_source.get("supabase_url") or "").strip()
    supabase_key = str(data_source.get("supabase_key") or "").strip()

    if supabase_url:
        env["SUPABASE_URL"] = supabase_url
    if supabase_key:
        env["SUPABASE_KEY"] = supabase_key
        env["SUPABASE_SERVICE_ROLE_KEY"] = supabase_key
        env.setdefault("SUPABASE_ANON_KEY", supabase_key)

    return env


def _build_script_steps(action_key: str, params: dict[str, Any], run_id: str) -> list[dict[str, Any]]:
    if action_key == "start_generation":
        prompt_version = str(params.get("prompt_version") or "MP-v1")
        generation_batch = str(params.get("generation_batch") or params.get("run_id") or run_id)
        provider = str(params.get("provider") or "mock")
        model = str(params.get("model") or "mock-model")
        num_candidates = int(params.get("num_candidates") or 1)
        temperature = float(params.get("temperature") or 0.7)
        max_tokens = int(params.get("max_tokens") or 2200)
        limit = int(params.get("limit") or 0)

        prompt_args = ["--prompt-version", prompt_version]
        for flag, value in [
            ("--topic", params.get("topic")),
            ("--difficulty", params.get("difficulty")),
            ("--exercise-type", params.get("exercise_type")),
            ("--reference-id", params.get("reference_id")),
        ]:
            if value not in (None, ""):
                prompt_args.extend([flag, str(value)])

        generation_args = [
            "--provider",
            provider,
            "--model",
            model,
            "--run-id",
            generation_batch,
            "--num-candidates",
            str(num_candidates),
            "--temperature",
            str(temperature),
            "--max-tokens",
            str(max_tokens),
        ]
        for flag, value in [
            ("--topic", params.get("topic")),
            ("--difficulty", params.get("difficulty")),
            ("--exercise-type", params.get("exercise_type")),
        ]:
            if value not in (None, ""):
                generation_args.extend([flag, str(value)])
        if limit > 0:
            generation_args.extend(["--limit", str(limit)])

        filter_args: list[str] = []
        if params.get("strict_filter"):
            filter_args.append("--strict")
        for flag, value in [
            ("--min-instruction-completeness", params.get("min_instruction_completeness")),
            ("--min-structure-completeness", params.get("min_structure_completeness")),
            ("--min-objective-overlap", params.get("min_objective_overlap")),
        ]:
            if value not in (None, ""):
                filter_args.extend([flag, str(value)])

        return [
            {"script": "scripts/01_build_prompts.py", "args": prompt_args},
            {"script": "scripts/02_generate_candidates.py", "args": generation_args},
            {"script": "scripts/04_filter_candidates.py", "args": filter_args},
            {"script": "scripts/03_log_generation_runs.py", "args": []},
        ]

    if action_key == "finalize_review_batch":
        return [
            {"script": "scripts/05_finalize_pairs.py", "args": []},
            {"script": "scripts/28_generate_dynamic_eval_assets.py", "args": []},
            {"script": "scripts/23_populate_code_completion_overlays.py", "args": []},
            {"script": "scripts/24_populate_model_revision_overlays.py", "args": []},
            {"script": "scripts/25_populate_concept_to_code_overlays.py", "args": []},
            {"script": "scripts/26_populate_model_building_overlays.py", "args": []},
            {"script": "scripts/27_populate_training_analysis_overlays.py", "args": []},
        ]

    if action_key == "repair_eval_assets":
        return [
            {"script": "scripts/28_generate_dynamic_eval_assets.py", "args": []},
            {"script": "scripts/23_populate_code_completion_overlays.py", "args": []},
            {"script": "scripts/24_populate_model_revision_overlays.py", "args": []},
            {"script": "scripts/25_populate_concept_to_code_overlays.py", "args": []},
            {"script": "scripts/26_populate_model_building_overlays.py", "args": []},
            {"script": "scripts/27_populate_training_analysis_overlays.py", "args": []},
        ]

    if action_key == "run_auto_evaluation":
        return [
            {"script": "scripts/06c_validate_reference_solutions.py", "args": ["--use-curated"]},
            {"script": "scripts/06d_run_functional_correctness.py", "args": ["--use-curated"]},
            {"script": "scripts/06_compute_auto_metrics.py", "args": ["--use-curated"]},
            {"script": "scripts/07_statistical_analysis.py", "args": ["--use-curated"]},
            {"script": "scripts/10_visualize_results.py", "args": ["--use-curated"]},
        ]
    if action_key == "generate_student_packets":
        return [
            {"script": "scripts/12_prepare_eval_packets.py", "args": []},
            {"script": "scripts/15_prepare_student_distribution_sheet.py", "args": []},
            {"script": "scripts/16_generate_student_qrcodes.py", "args": []},
            {"script": "scripts/17_prepare_student_qrcode_print_sheets.py", "args": []},
        ]
    if action_key == "freeze_analysis_input":
        data_source = load_json_doc(WORKFLOW_STATE_PATH).get("admin_settings", {}).get("data_source", {})
        fetch_from_db = params.get("fetch_from_db")
        if fetch_from_db is None:
            fetch_from_db = data_source.get("pull_mode") == "鐩存帴鎷夊簱"
        params["fetch_from_db"] = bool(fetch_from_db)
        export_args = ["--fetch-from-db"] if params["fetch_from_db"] else []
        return [
            {"script": "scripts/17a_export_student_analysis_inputs.py", "args": export_args},
            {"script": "scripts/18_build_student_analysis_master.py", "args": []},
        ]

    if action_key == "generate_analysis_report":
        return [
            {"script": "scripts/19_generate_student_chapter5_outputs.py", "args": []},
            {"script": "scripts/20_generate_student_significance_tables.py", "args": []},
            {"script": "scripts/21_generate_auto_vs_student_correlations.py", "args": []},
        ]

    if action_key == "request_assets":
        asset_type = str(params.get("asset_type") or "").strip()
        script_path = ASSET_SCRIPT_MAP.get(asset_type)
        if not script_path:
            raise ValueError("缺少可执行的补资产类型。")
        return [{"script": script_path, "args": []}]

    if action_key == "publish_snapshot":
        return []

    raise ValueError(f"动作 {action_key} 暂不支持直接执行。")

def _review_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "review_pending": sum(1 for item in items if item.get("review_status") == "pending_review"),
        "overlay_pending": sum(
            1
            for item in items
            if not item.get("solution_overlay_ready") or not item.get("tests_overlay_ready")
        ),
    }


def _refresh_workflow_queues(workflow_state: dict[str, Any]) -> None:
    review_items = load_review_state_doc().get("items") or workflow_state.get("review", {}).get("items", [])
    if review_items:
        workflow_state.setdefault("review", {})["items"] = review_items
    counts = _review_counts(review_items if isinstance(review_items, list) else [])

    queues = workflow_state.setdefault("queues", {})
    queues["review_pending"] = counts["review_pending"]
    queues["overlay_pending"] = counts["overlay_pending"]
    queues["eval_ready"] = 1 if CURATED_ANALYSIS_STATUS_PATH.exists() else 0
    queues["survey_ready"] = 1 if PACKAGE_MANIFEST_PATH.exists() else 0
    queues["data_import_ready"] = 1 if SUBSET_MANIFEST_PATH.exists() else 0
    queues["report_ready"] = 1 if CHAPTER5_MANIFEST_PATH.exists() else 0
    queues["snapshot_ready"] = 1 if REPORT_SUMMARY_PATH.exists() else 0


def _sync_review_assets_from_curated() -> None:
    review_doc = load_review_state_doc()
    items = review_doc.get("items", []) if isinstance(review_doc, dict) else []
    history = review_doc.get("history", {}) if isinstance(review_doc, dict) else {}
    if not isinstance(items, list):
        return

    final_pairs_path = PROJECT_ROOT / "results" / "curated" / "final_pairs.curated.v1.jsonl"
    reference_solutions_path = PROJECT_ROOT / "results" / "curated" / "reference_solutions.curated.v1.jsonl"
    executable_tests_path = PROJECT_ROOT / "results" / "curated" / "executable_tests.curated.v1.jsonl"

    pair_rows = load_jsonl_docs(final_pairs_path)
    solution_rows = load_jsonl_docs(reference_solutions_path)
    tests_rows = load_jsonl_docs(executable_tests_path)

    pair_by_generation_id = {
        str(row.get("generation_id") or "").strip(): row
        for row in pair_rows
        if str(row.get("generation_id") or "").strip()
    }
    solution_ids = {
        str(row.get("exercise_id") or "").strip()
        for row in solution_rows
        if str(row.get("exercise_id") or "").strip()
    }
    test_ids = {
        str(row.get("exercise_id") or "").strip()
        for row in tests_rows
        if str(row.get("exercise_id") or "").strip()
    }

    updated = False
    stamp = _now_iso()
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("review_status") or "") != "approved":
            continue

        generation_id = str(item.get("generation_id") or "").strip()
        pair_row = pair_by_generation_id.get(generation_id, {})
        reference_exercise_id = str(pair_row.get("reference_exercise_id") or "").strip()
        ai_exercise_id = str(pair_row.get("ai_exercise_id") or "").strip()

        solution_ready = bool(
            reference_exercise_id
            and ai_exercise_id
            and reference_exercise_id in solution_ids
            and ai_exercise_id in solution_ids
        )
        tests_ready = bool(
            reference_exercise_id
            and ai_exercise_id
            and reference_exercise_id in test_ids
            and ai_exercise_id in test_ids
        )
        eval_ready = solution_ready and tests_ready

        changed = (
            bool(item.get("solution_overlay_ready")) != solution_ready
            or bool(item.get("tests_overlay_ready")) != tests_ready
            or str(item.get("eval_status") or "") != ("ready" if eval_ready else "not_ready")
        )

        item["solution_overlay_ready"] = solution_ready
        item["tests_overlay_ready"] = tests_ready
        item["eval_status"] = "ready" if eval_ready else "not_ready"

        action_text = "finalize_assets_synced" if eval_ready else "finalize_assets_incomplete"
        if changed:
            item["last_action"] = action_text
            candidate_id = str(item.get("candidate_id") or "")
            rows = history.get(candidate_id, []) if isinstance(history, dict) else []
            rows = list(rows) if isinstance(rows, list) else []
            if not rows or str(rows[-1].get("action") or "") != action_text:
                rows.append({"time": stamp, "operator": "system", "action": action_text})
                history[candidate_id] = rows
            updated = True

    if updated:
        save_json_doc(
            REVIEW_STATE_PATH,
            {
                "updated_at": stamp,
                "items": items,
                "history": history,
            },
        )


def _update_workflow_state_after_run(
    action_key: str,
    *,
    status: str,
    run_id: str,
    started_at: str,
    finished_at: str,
    note: str,
    manifest_path: str,
    business_manifest: str,
    params: dict[str, Any],
) -> None:
    workflow_state = load_json_doc(WORKFLOW_STATE_PATH)
    workflow_state["updated_at"] = finished_at

    section_name = SECTION_BY_ACTION.get(action_key)
    if section_name:
        section = workflow_state.setdefault(section_name, {})
        section["last_run"] = {
            "run_id": run_id,
            "status": status,
            "started_at": started_at,
            "finished_at": finished_at,
            "note": note,
            "run_manifest": manifest_path,
            "business_manifest": business_manifest,
            "params": params,
        }
        section["status"] = SUCCESS_STATUS_BY_ACTION.get(action_key, "completed") if status == "success" else "failed"

    if action_key == "start_generation":
        generation = workflow_state.setdefault("generation", {})
        generation["config"] = {
            "topic": str(params.get("topic") or ""),
            "difficulty": str(params.get("difficulty") or ""),
            "exercise_type": str(params.get("exercise_type") or ""),
            "prompt_version": str(params.get("prompt_version") or "MP-v1"),
            "count": int(params.get("num_candidates") or 1),
            "reference_id": str(params.get("reference_id") or ""),
            "model": str(params.get("model") or ""),
            "provider": str(params.get("provider") or ""),
            "generation_batch": str(params.get("generation_batch") or run_id),
        }
    workflow_state["snapshot_locked"] = bool(action_key == "publish_snapshot" and status == "success") or bool(
        workflow_state.get("snapshot_locked")
    )

    if status == "success":
        next_stage = STAGE_AFTER_SUCCESS.get(action_key)
        if next_stage:
            workflow_state["current_stage"] = next_stage
        if action_key == "freeze_analysis_input":
            survey_data = workflow_state.setdefault("survey_data", {})
            survey_data["fetch_from_db"] = bool(params.get("fetch_from_db"))
            survey_data["source_mode"] = "db" if params.get("fetch_from_db") else "csv"
            survey_data["inputs_ready"] = SUBSET_MANIFEST_PATH.exists()
        if action_key == "generate_analysis_report":
            report = workflow_state.setdefault("report", {})
            report["summary_ready"] = REPORT_SUMMARY_PATH.exists()
        if action_key == "publish_snapshot":
            snapshot = workflow_state.setdefault("snapshot", {})
            snapshot["status"] = "locked"
            snapshot["label"] = Path(business_manifest).name if business_manifest else run_id
    else:
        if action_key == "publish_snapshot":
            workflow_state["snapshot_locked"] = False

    _refresh_workflow_queues(workflow_state)
    save_json_doc(WORKFLOW_STATE_PATH, workflow_state)

def _build_report_summary() -> dict[str, Any]:
    chapter5_manifest = load_json_doc(CHAPTER5_MANIFEST_PATH)
    significance_manifest = load_json_doc(SIGNIFICANCE_MANIFEST_PATH)
    correlation_manifest = load_json_doc(CORRELATION_MANIFEST_PATH)
    master_df = _safe_read_csv(MASTER_CSV_PATH)
    participant_df = _safe_read_csv(PARTICIPANT_META_PATH)
    significance_df = _safe_read_csv(SIGNIFICANCE_ITEM_PATH)
    correlation_df = _safe_read_csv(CORRELATION_EXERCISE_PATH)

    filter_summary = chapter5_manifest.get("filter_summary", {}) if isinstance(chapter5_manifest, dict) else {}
    participants = int(filter_summary.get("participants_after_filter") or participant_df.get("participant_id", pd.Series(dtype=str)).nunique() or 0)
    exercises = int(filter_summary.get("exercises_after_filter") or master_df.get("exercise_id", pd.Series(dtype=str)).nunique() or 0)

    significant_count = 0
    top_metric = "未记录"
    top_adjusted_p = ""
    if not significance_df.empty and "paired_t_p_adjust_bh" in significance_df.columns:
        p_values = pd.to_numeric(significance_df["paired_t_p_adjust_bh"], errors="coerce")
        significant_count = int((p_values < 0.05).fillna(False).sum())
        if not p_values.dropna().empty:
            top_row = significance_df.loc[p_values.idxmin()]
            top_metric = str(top_row.get("metric_label") or top_row.get("metric") or "未记录")
            top_adjusted_p = f"{float(p_values.min()):.6f}"

    correlation_row_count = int(len(correlation_df))
    top_student_metric = "未记录"
    top_auto_metric = "未记录"
    top_spearman_r = ""
    if not correlation_df.empty and "spearman_r" in correlation_df.columns:
        corr_values = pd.to_numeric(correlation_df["spearman_r"], errors="coerce")
        if not corr_values.dropna().empty:
            top_index = corr_values.abs().idxmax()
            top_row = correlation_df.loc[top_index]
            top_student_metric = str(top_row.get("student_metric") or "未记录")
            top_auto_metric = str(top_row.get("auto_metric") or "未记录")
            top_spearman_r = f"{float(top_row.get('spearman_r')):.4f}"

    highlights = [
        f"过滤后纳入 {participants} 名参与者、{exercises} 道题目进入正式分析。",
        (
            f"显著性检验表已经生成，当前共有 {significant_count} 项指标在多重校正后达到显著。"
            if significance_manifest
            else "显著性检验结果尚未生成。"
        ),
        (
            f"相关性分析中当前绝对值最高的 Spearman 相关为 {top_student_metric} vs {top_auto_metric} ({top_spearman_r})。"
            if correlation_manifest and top_spearman_r
            else "相关性分析结果尚未生成。"
        ),
    ]

    return {
        "updated_at": _now_iso(),
        "report_ready": bool(chapter5_manifest),
        "manifests": {
            "subset": SUBSET_MANIFEST_PATH.exists(),
            "master": MASTER_MANIFEST_PATH.exists(),
            "chapter5": bool(chapter5_manifest),
            "significance": bool(significance_manifest),
            "correlation": bool(correlation_manifest),
        },
        "sample": {
            "participants": participants,
            "item_rows": int(len(master_df)),
            "packages": int(participant_df.get("package_id", pd.Series(dtype=str)).nunique()) if not participant_df.empty else 0,
            "unique_exercises": int(master_df.get("exercise_id", pd.Series(dtype=str)).nunique()) if not master_df.empty else 0,
            "selected_participants": int(load_json_doc(SUBSET_MANIFEST_PATH).get("selection_summary", {}).get("selected_participants") or 0),
            "master_rows": int(len(master_df)),
        },
        "significance": {
            "generated": bool(significance_manifest),
            "significant_count": significant_count,
            "top_metric": top_metric,
            "top_adjusted_p": top_adjusted_p,
        },
        "correlation": {
            "generated": bool(correlation_manifest),
            "row_count": correlation_row_count,
            "top_student_metric": top_student_metric,
            "top_auto_metric": top_auto_metric,
            "top_spearman_r": top_spearman_r,
        },
        "highlights": highlights,
    }


def refresh_report_summary() -> dict[str, Any]:
    report_summary = _build_report_summary()
    save_json_doc(REPORT_SUMMARY_PATH, report_summary)
    return report_summary


def _default_business_manifest(action_key: str) -> str:
    action = get_action(action_key)
    manifest_path = action.get("manifest_path")
    if manifest_path and Path(manifest_path).exists():
        return str(manifest_path)
    return ""


def _collect_existing_outputs(action_key: str, extra_outputs: list[str] | None = None) -> list[str]:
    action = get_action(action_key)
    outputs: list[str] = []
    for path in action.get("output_paths", []):
        if path.exists() and path.is_file():
            outputs.append(str(path))
    for value in extra_outputs or []:
        path = resolve_path(value)
        if path.exists() and path.is_file() and str(path) not in outputs:
            outputs.append(str(path))
    return outputs


def _snapshot_source_paths() -> list[Path]:
    candidates = [
        CURATED_ANALYSIS_STATUS_PATH,
        PACKAGE_MANIFEST_PATH,
        PARTICIPANT_META_PATH,
        ITEM_RATINGS_PATH,
        BATCH_FEEDBACK_PATH,
        SUBSET_MANIFEST_PATH,
        MASTER_CSV_PATH,
        MASTER_MANIFEST_PATH,
        CHAPTER5_MANIFEST_PATH,
        SIGNIFICANCE_MANIFEST_PATH,
        CORRELATION_MANIFEST_PATH,
        REPORT_SUMMARY_PATH,
        WORKFLOW_STATE_PATH,
        *available_report_export_paths(),
    ]
    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        if not path.exists() or not path.is_file():
            continue
        path_key = str(path.resolve())
        if path_key in seen:
            continue
        seen.add(path_key)
        unique.append(path)
    return unique


def _execute_script_chain(
    action_key: str,
    *,
    operator: str,
    note: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    action = get_action(action_key)
    run_id = f"{action_key}-{_timestamp_slug()}"
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    run_manifest_path = run_dir / "run_manifest.json"

    started_at = _now_iso()
    wall_clock = time.perf_counter()
    env = _build_runtime_env()
    python_executable = _python_executable()
    task_key = ACTION_TO_TASK_KEY.get(action_key, "")
    work_order_id = ""
    work_order_intent = str(params.pop("__work_order_intent", "execution") or "execution")
    source_work_order_id = str(params.pop("__source_work_order_id", "") or "")
    work_order_note = str(params.pop("__work_order_note", "") or note)
    steps = _build_script_steps(action_key, params, run_id)
    if task_key:
        work_order = start_task_work_order(
            task_key,
            actor=operator,
            action_key=action_key,
            note=work_order_note,
            params=params,
            intent=work_order_intent,
            source_work_order_id=source_work_order_id,
        )
        work_order_id = str(work_order.get("work_order_id") or "")
        update_task_runtime(task_key, status="running", actor=operator, run_id=run_id, message=note)

    step_records: list[dict[str, Any]] = []
    log_paths: list[str] = []
    status = "success"
    error = ""

    try:
        if action_key == "finalize_review_batch":
            review_doc = load_review_state_doc()
            review_items = review_doc.get("items") if isinstance(review_doc, dict) else []
            review_items = review_items if isinstance(review_items, list) else []
            pending_count = sum(1 for item in review_items if item.get("review_status") == "pending_review")
            approved_count = sum(1 for item in review_items if item.get("review_status") == "approved")
            if pending_count > 0:
                raise RuntimeError(f"仍有 {pending_count} 道候选题待审核，不能定稿入库。")
            if approved_count == 0:
                raise RuntimeError("当前没有已通过候选题，不能定稿入库。")
            materialize_review_outcomes(review_doc)

        for index, step in enumerate(steps, start=1):
            script_path = resolve_path(step["script"])
            args = [str(arg) for arg in step.get("args", [])]
            command = [str(python_executable), str(script_path), *args]
            step_started_at = _now_iso()
            step_clock = time.perf_counter()

            completed = subprocess.run(
                command,
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )

            stdout_path = run_dir / f"{index:02d}_{script_path.stem}.stdout.log"
            stderr_path = run_dir / f"{index:02d}_{script_path.stem}.stderr.log"
            stdout_path.write_text(completed.stdout or "", encoding="utf-8")
            stderr_path.write_text(completed.stderr or "", encoding="utf-8")
            log_paths.extend([str(stdout_path), str(stderr_path)])

            duration_seconds = round(time.perf_counter() - step_clock, 3)
            step_record = {
                "step": index,
                "script": str(script_path),
                "args": args,
                "command": command,
                "started_at": step_started_at,
                "finished_at": _now_iso(),
                "duration_seconds": duration_seconds,
                "return_code": completed.returncode,
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
            }
            step_records.append(step_record)

            if completed.returncode != 0:
                status = "failed"
                stderr_tail = (completed.stderr or completed.stdout or "").strip()
                error = f"{script_path.name} 执行失败（exit {completed.returncode}）。"
                if stderr_tail:
                    error = f"{error} {stderr_tail[-500:]}"
                break
    except Exception as exc:
        status = "failed"
        error = f"执行过程中发生异常：{exc}"
        error_path = run_dir / "runner-error.log"
        error_path.write_text(error, encoding="utf-8")
        log_paths.append(str(error_path))

    finished_at = _now_iso()
    duration_seconds = round(time.perf_counter() - wall_clock, 3)

    extra_outputs: list[str] = []
    business_manifest = _default_business_manifest(action_key)
    if status == "success":
        try:
            if action_key == "start_generation":
                sync_review_state_from_filtered(load_review_state_doc())
                extra_outputs.append(str(REVIEW_STATE_PATH))
            elif action_key == "finalize_review_batch":
                extra_outputs.extend(sync_finalized_results_to_curated())
                _sync_review_assets_from_curated()
                extra_outputs.append(str(REVIEW_STATE_PATH))
            elif action_key == "repair_eval_assets":
                _sync_review_assets_from_curated()
                extra_outputs.append(str(REVIEW_STATE_PATH))
            elif action_key == "generate_analysis_report":
                refresh_report_summary()
                business_manifest = str(REPORT_SUMMARY_PATH)
                extra_outputs.append(str(REPORT_SUMMARY_PATH))
        except Exception as exc:
            status = "failed"
            error = f"执行后处理失败：{exc}"

    run_manifest = {
        "run_id": run_id,
        "action_key": action_key,
        "action_name": action["label"],
        "status": status,
        "operator": operator,
        "note": note,
        "params": params,
        "work_order_id": work_order_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": duration_seconds,
        "python_executable": str(python_executable),
        "steps": step_records,
        "error": error,
        "business_manifest": business_manifest,
    }
    save_json_doc(run_manifest_path, run_manifest)

    outputs = _collect_existing_outputs(action_key, extra_outputs)
    record = append_run_event(
        action_key,
        status=status,
        operator=operator,
        note=note,
        outputs=outputs,
        manifest=str(run_manifest_path),
        business_manifest=business_manifest,
        scripts=[str(resolve_path(step["script"])) for step in steps],
        inputs=[str(path) for path in action.get("input_paths", [])],
        logs=log_paths,
        error=error,
        params=params,
        work_order_id=work_order_id,
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=duration_seconds,
    )

    _update_workflow_state_after_run(
        action_key,
        status=status,
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        note=note,
        manifest_path=str(run_manifest_path),
        business_manifest=business_manifest,
        params=params,
    )
    if work_order_id:
        complete_task_work_order(
            work_order_id,
            actor=operator,
            status="completed" if status == "success" else "failed",
            run_id=run_id,
            message=note or action["label"],
            error=error,
            logs=log_paths,
            outputs=outputs,
            run_manifest=str(run_manifest_path),
            business_manifest=business_manifest,
        )
    if task_key:
        update_task_runtime(
            task_key,
            status="completed" if status == "success" else "failed",
            actor=operator,
            run_id=run_id,
            message=note or action["label"],
            error=error,
            deliverable_updates=mark_deliverables_for_task(task_key, outputs),
        )

    action_label = action["label"]
    if status == "success":
        message = f"{action_label}已执行完成。"
    else:
        message = f"{action_label}执行失败。"

    return {
        "status": status,
        "message": message,
        "error": error,
        "record": record,
        "run_manifest": str(run_manifest_path),
        "business_manifest": business_manifest,
    }

def _publish_snapshot(
    *,
    operator: str,
    note: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    action_key = "publish_snapshot"
    action = get_action(action_key)
    run_id = f"{action_key}-{_timestamp_slug()}"
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    started_at = _now_iso()
    wall_clock = time.perf_counter()
    task_key = ACTION_TO_TASK_KEY.get(action_key, "")
    work_order_id = ""
    work_order_intent = str(params.pop("__work_order_intent", "execution") or "execution")
    source_work_order_id = str(params.pop("__source_work_order_id", "") or "")
    work_order_note = str(params.pop("__work_order_note", "") or note)
    if task_key:
        work_order = start_task_work_order(
            task_key,
            actor=operator,
            action_key=action_key,
            note=work_order_note,
            params=params,
            intent=work_order_intent,
            source_work_order_id=source_work_order_id,
        )
        work_order_id = str(work_order.get("work_order_id") or "")
        update_task_runtime(task_key, status="running", actor=operator, run_id=run_id, message=note)
    snapshot_name = f"console_snapshot_{_timestamp_slug()}"
    snapshot_zip_path = SNAPSHOTS_DIR / f"{snapshot_name}.zip"
    snapshot_manifest_path = SNAPSHOTS_DIR / f"{snapshot_name}.manifest.json"
    run_manifest_path = run_dir / "run_manifest.json"

    included_files: list[dict[str, Any]] = []
    status = "success"
    error = ""

    try:
        snapshot_sources = _snapshot_source_paths()
        if not snapshot_sources:
            raise RuntimeError("当前没有可归档的快照文件。")

        with zipfile.ZipFile(snapshot_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in snapshot_sources:
                relative_path = path.relative_to(PROJECT_ROOT).as_posix()
                archive.write(path, arcname=relative_path)
                included_files.append(
                    {
                        "path": str(path),
                        "archive_path": relative_path,
                        "size_bytes": path.stat().st_size,
                    }
                )
    except Exception as exc:
        status = "failed"
        error = str(exc)

    finished_at = _now_iso()
    duration_seconds = round(time.perf_counter() - wall_clock, 3)

    if status == "success":
        snapshot_manifest = {
            "snapshot_name": snapshot_name,
            "created_at": finished_at,
            "batch_name": load_json_doc(WORKFLOW_STATE_PATH).get("admin_settings", {}).get("batch_name", ""),
            "files": included_files,
            "zip_path": str(snapshot_zip_path),
            "source": "evaluation_system_console",
        }
        save_json_doc(snapshot_manifest_path, snapshot_manifest)
        business_manifest = str(snapshot_manifest_path)
        outputs = [str(snapshot_zip_path), str(snapshot_manifest_path)]
    else:
        business_manifest = ""
        outputs = []

    run_manifest = {
        "run_id": run_id,
        "action_key": action_key,
        "action_name": action["label"],
        "status": status,
        "operator": operator,
        "note": note,
        "params": params,
        "work_order_id": work_order_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": duration_seconds,
        "files": included_files,
        "error": error,
        "business_manifest": business_manifest,
    }
    save_json_doc(run_manifest_path, run_manifest)

    record = append_run_event(
        action_key,
        status=status,
        operator=operator,
        note=note,
        outputs=outputs,
        manifest=str(run_manifest_path),
        business_manifest=business_manifest,
        scripts=[],
        inputs=[str(path) for path in _snapshot_source_paths()],
        logs=[],
        error=error,
        params=params,
        work_order_id=work_order_id,
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=duration_seconds,
    )

    _update_workflow_state_after_run(
        action_key,
        status=status,
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        note=note,
        manifest_path=str(run_manifest_path),
        business_manifest=business_manifest,
        params=params,
    )
    if work_order_id:
        complete_task_work_order(
            work_order_id,
            actor=operator,
            status="completed" if status == "success" else "failed",
            run_id=run_id,
            message=note or action["label"],
            error=error,
            logs=[],
            outputs=outputs,
            run_manifest=str(run_manifest_path),
            business_manifest=business_manifest,
        )
    if task_key:
        update_task_runtime(
            task_key,
            status="completed" if status == "success" else "failed",
            actor=operator,
            run_id=run_id,
            message=note or action["label"],
            error=error,
            deliverable_updates=mark_deliverables_for_task(task_key, outputs),
        )

    if status == "success":
        message = "完整快照已归档。"
    else:
        message = "完整快照发布失败。"

    return {
        "status": status,
        "message": message,
        "error": error,
        "record": record,
        "run_manifest": str(run_manifest_path),
        "business_manifest": business_manifest,
    }


def execute_action(
    action_key: str,
    *,
    operator: str,
    note: str = "",
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_params = dict(params or {})
    action = get_action(action_key)

    if not action_is_executable(action_key):
        return {
            "status": "failed",
            "message": f"{action['label']}暂不支持直接在控制台内执行。",
            "error": "unsupported_action",
            "record": None,
        }

    try:
        if action_key == "publish_snapshot":
            return _publish_snapshot(operator=operator, note=note, params=normalized_params)

        return _execute_script_chain(
            action_key,
            operator=operator,
            note=note,
            params=normalized_params,
        )
    except Exception as exc:
        return {
            "status": "failed",
            "message": f"{action['label']}执行失败。",
            "error": str(exc),
            "record": None,
        }


def recover_task(
    task_key: str,
    *,
    operator: str,
    strategy: str = "retry_now",
    note: str = "",
    source_work_order_id: str = "",
) -> dict[str, Any]:
    state = load_system_state()
    task = state.get("tasks", {}).get(task_key, {})
    task_label = str(task.get("label") or task_key)
    action_key = str(task.get("action_key") or TASK_TO_ACTION_KEY.get(task_key, ""))
    latest_work_order = get_latest_task_work_order(task_key)
    source_id = source_work_order_id or str((latest_work_order or {}).get("work_order_id") or "")

    if strategy == "retry_now":
        if not action_key or not action_is_executable(action_key):
            return {
                "status": "failed",
                "message": f"{task_label}当前不支持直接重试。",
                "error": "retry_not_supported",
                "record": None,
            }
        params = dict((latest_work_order or {}).get("params") or {})
        params["__work_order_intent"] = "retry"
        params["__source_work_order_id"] = source_id
        if note:
            params["__work_order_note"] = note
        retry_note = note or f"失败恢复重试：{task_label}"
        return execute_action(action_key, operator=operator, note=retry_note, params=params)

    if strategy == "mark_ready":
        recovery_note = note or f"人工恢复：{task_label}"
        work_order = mark_task_recovered(
            task_key,
            actor=operator,
            note=recovery_note,
            source_work_order_id=source_id,
        )
        return {
            "status": "success",
            "message": f"{task_label}已标记为恢复，可重新执行。",
            "error": "",
            "record": {"work_order_id": work_order.get("work_order_id", "")},
        }

    return {
        "status": "failed",
        "message": f"{task_label}的恢复策略无效。",
        "error": "invalid_recovery_strategy",
        "record": None,
    }


def save_console_settings(settings: dict[str, Any], *, operator: str, note: str) -> dict[str, Any]:
    update_system_settings(settings)
    workflow_state = load_json_doc(WORKFLOW_STATE_PATH)
    admin_settings = workflow_state.setdefault("admin_settings", {})
    admin_settings["batch_name"] = settings.get("batch_name", admin_settings.get("batch_name", ""))
    admin_settings["freeze_threshold"] = int(settings.get("freeze_threshold") or 30)
    admin_settings["current_mainline"] = settings.get("current_mainline", admin_settings.get("current_mainline", ""))
    admin_settings["role_permissions"] = settings.get("role_permissions", admin_settings.get("role_permissions", {}))
    admin_settings["data_source"] = settings.get("data_source", admin_settings.get("data_source", {}))
    admin_settings["paths"] = settings.get("paths", admin_settings.get("paths", {}))

    survey_data = workflow_state.setdefault("survey_data", {})
    pull_mode = admin_settings.get("data_source", {}).get("pull_mode", "鏈湴 CSV")
    survey_data["fetch_from_db"] = pull_mode == "鐩存帴鎷夊簱"
    survey_data["source_mode"] = "db" if survey_data["fetch_from_db"] else "csv"

    workflow_state.setdefault("ui", {})["last_page"] = "绯荤粺璁剧疆"
    workflow_state["updated_at"] = _now_iso()
    save_json_doc(WORKFLOW_STATE_PATH, workflow_state)

    safe_settings = {
        "batch_name": settings.get("batch_name", ""),
        "freeze_threshold": int(settings.get("freeze_threshold") or 30),
        "current_mainline": settings.get("current_mainline", ""),
        "pull_mode": settings.get("data_source", {}).get("pull_mode", "鏈湴 CSV"),
        "role_permissions": settings.get("role_permissions", {}),
        "paths": settings.get("paths", {}),
    }
    record_audit_event(
        "settings_updated",
        actor=operator,
        target="system_settings",
        status="success",
        detail={"note": note, "settings": safe_settings},
    )

    record = append_run_event(
        "save_settings",
        operator=operator,
        note=note,
        outputs=[str(WORKFLOW_STATE_PATH)],
        manifest=str(WORKFLOW_STATE_PATH),
        business_manifest=str(WORKFLOW_STATE_PATH),
        scripts=[str(WORKFLOW_STATE_PATH)],
        inputs=[str(WORKFLOW_STATE_PATH)],
        logs=[],
        params={"settings_scope": note},
    )
    return {
        "status": "success",
        "message": "系统设置已保存。",
        "error": "",
        "record": record,
    }


















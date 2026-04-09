from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
RESULTS_DIR = PROJECT_ROOT / "results"
SYSTEM_DIR = OUTPUTS_DIR / "system"
CURATED_DIR = RESULTS_DIR / "curated"

RAW_GENERATIONS_PATH = OUTPUTS_DIR / "raw_generations" / "generations.raw.v1.jsonl"
GENERATION_MANIFEST_PATH = OUTPUTS_DIR / "raw_generations" / "generation_manifest.v1.json"
GENERATION_SUMMARY_PATH = PROJECT_ROOT / "prompts" / "logs" / "generation_run_summary.v1.json"
FILTER_ACCEPTED_PATH = OUTPUTS_DIR / "filtered" / "accepted" / "candidates.accepted.v1.jsonl"
FILTER_REJECTED_PATH = OUTPUTS_DIR / "filtered" / "rejected" / "candidates.rejected.v1.jsonl"
FILTER_SUMMARY_PATH = OUTPUTS_DIR / "filtered" / "filter_summary.v1.csv"
FILTER_SUMMARY_BY_REASON_PATH = OUTPUTS_DIR / "filtered" / "filter_summary_by_reason.v1.csv"
FINAL_PAIRS_PATH = RESULTS_DIR / "final_pairs.v1.jsonl"
EXERCISES_ALL_PATH = RESULTS_DIR / "exercises_all.v1.jsonl"
AI_DATASET_PATH = DATA_DIR / "ai_generated" / "accepted" / "ai_exercises.accepted.v1.json"
BLIND_MAPPING_SOURCE_PATH = DATA_DIR / "human_eval" / "blind_mapping.generated.v1.csv"
CURATED_FINAL_PAIRS_PATH = CURATED_DIR / "final_pairs.curated.v1.jsonl"
CURATED_EXERCISES_ALL_PATH = CURATED_DIR / "exercises_all.curated.v1.jsonl"
CURATED_AI_DATASET_PATH = CURATED_DIR / "ai_exercises.curated.v1.json"
CURATED_BLIND_MAPPING_PATH = CURATED_DIR / "blind_mapping.curated.v1.csv"
REVIEW_STATE_PATH = SYSTEM_DIR / "review_state.v1.json"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}



def _write_json(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")



def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows



def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")



def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))



def _file_timestamp(path: Path) -> str:
    if not path.exists():
        return "未生成"
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")



def build_generation_metrics(review_items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    review_rows = list(review_items or [])
    accepted_rows = _read_jsonl(FILTER_ACCEPTED_PATH)
    rejected_rows = _read_jsonl(FILTER_REJECTED_PATH)
    raw_rows = _read_jsonl(RAW_GENERATIONS_PATH)
    manifest = _read_json(GENERATION_MANIFEST_PATH)
    run_summary = _read_json(GENERATION_SUMMARY_PATH)
    filter_summary_rows = _read_csv_rows(FILTER_SUMMARY_PATH)
    filter_summary = {str(row.get("metric") or ""): row for row in filter_summary_rows}

    return {
        "raw_count": len(raw_rows),
        "accepted_count": len(accepted_rows),
        "rejected_count": len(rejected_rows),
        "pending_review_count": sum(1 for item in review_rows if item.get("review_status") == "pending_review"),
        "approved_count": sum(1 for item in review_rows if item.get("review_status") == "approved"),
        "rejected_review_count": sum(1 for item in review_rows if item.get("review_status") == "rejected"),
        "generation_manifest": manifest,
        "generation_run_summary": run_summary,
        "filter_summary": filter_summary,
        "raw_updated_at": _file_timestamp(RAW_GENERATIONS_PATH),
        "filter_updated_at": _file_timestamp(FILTER_ACCEPTED_PATH),
        "finalized_updated_at": _file_timestamp(CURATED_FINAL_PAIRS_PATH),
        "final_pairs_ready": CURATED_FINAL_PAIRS_PATH.exists(),
        "blind_mapping_ready": CURATED_BLIND_MAPPING_PATH.exists(),
        "accepted_path": str(FILTER_ACCEPTED_PATH),
        "rejected_path": str(FILTER_REJECTED_PATH),
        "final_pairs_path": str(CURATED_FINAL_PAIRS_PATH),
        "blind_mapping_path": str(CURATED_BLIND_MAPPING_PATH),
    }



def _item_history(existing_doc: dict[str, Any], candidate_id: str) -> list[dict[str, str]]:
    history = existing_doc.get("history", {}) if isinstance(existing_doc, dict) else {}
    rows = history.get(candidate_id, []) if isinstance(history, dict) else []
    return rows if isinstance(rows, list) else []



def _build_review_item(record: dict[str, Any], existing_item: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    existing = existing_item or {}
    candidate_id = str(record.get("candidate_id") or record.get("generation_id") or payload.get("exercise_id") or "")
    review_status = str(existing.get("review_status") or "pending_review")
    eval_ready = bool(existing.get("solution_overlay_ready") and existing.get("tests_overlay_ready") and review_status == "approved")
    return {
        "candidate_id": candidate_id,
        "review_id": str(existing.get("review_id") or f"REVIEW-{candidate_id}"),
        "reference_id": str(record.get("reference_exercise_id") or payload.get("matched_reference_exercise_id") or ""),
        "prompt_id": str(record.get("prompt_id") or ""),
        "prompt_version": str(record.get("prompt_version") or ""),
        "generation_id": str(record.get("generation_id") or ""),
        "provider": str(record.get("provider") or ""),
        "model_name": str(record.get("model_name") or ""),
        "topic": str(payload.get("topic") or record.get("topic") or ""),
        "difficulty": str(payload.get("difficulty") or record.get("difficulty") or ""),
        "exercise_type": str(payload.get("exercise_type") or record.get("generation_exercise_type") or ""),
        "title": str(payload.get("title") or record.get("title") or ""),
        "instruction": str(payload.get("instruction_text") or record.get("instruction_text") or ""),
        "expected_output": str(payload.get("expected_output") or ""),
        "constraints": list(payload.get("constraints") or []),
        "test_cases": list(payload.get("test_cases") or []),
        "starter_code": str(payload.get("starter_code") or ""),
        "generation_prompt_excerpt": str(record.get("generation_prompt_excerpt") or ""),
        "soft_rank_score": float(record.get("soft_rank_score") or 0.0),
        "review_status": review_status,
        "code_state": str(existing.get("code_state") or ("valid" if payload.get("starter_code") else "missing")),
        "solution_overlay_ready": bool(existing.get("solution_overlay_ready")),
        "tests_overlay_ready": bool(existing.get("tests_overlay_ready")),
        "eval_status": "ready" if eval_ready else "not_ready",
        "survey_status": str(existing.get("survey_status") or "pending"),
        "last_action": str(existing.get("last_action") or "进入人工审核队列"),
        "filter_record": record,
    }



def sync_review_state_from_filtered(existing_doc: dict[str, Any] | None = None) -> dict[str, Any]:
    current_doc = existing_doc or _read_json(REVIEW_STATE_PATH)
    current_items = current_doc.get("items", []) if isinstance(current_doc, dict) else []
    existing_index = {
        str(item.get("candidate_id") or ""): item
        for item in current_items
        if isinstance(item, dict) and str(item.get("candidate_id") or "")
    }

    accepted_rows = _read_jsonl(FILTER_ACCEPTED_PATH)
    items = [_build_review_item(row, existing_index.get(str(row.get("candidate_id") or row.get("generation_id") or ""))) for row in accepted_rows]

    history: dict[str, list[dict[str, str]]] = {}
    for item in items:
        candidate_id = str(item.get("candidate_id") or "")
        existing_history = _item_history(current_doc, candidate_id)
        if existing_history:
            history[candidate_id] = existing_history
        else:
            history[candidate_id] = [
                {
                    "time": _file_timestamp(FILTER_ACCEPTED_PATH),
                    "operator": "系统",
                    "action": str(item.get("last_action") or "进入人工审核队列"),
                }
            ]

    doc = {
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "items": items,
        "history": history,
    }
    _write_json(REVIEW_STATE_PATH, doc)
    return doc



def _manual_rejected_record(item: dict[str, Any], fallback_record: dict[str, Any] | None = None) -> dict[str, Any]:
    record = dict(item.get("filter_record") or fallback_record or {})
    reasons = list(record.get("rejection_reasons") or [])
    if "manual_review_rejected" not in reasons:
        reasons.append("manual_review_rejected")
    categories = list(record.get("rejection_categories") or [])
    if "manual_review" not in categories:
        categories.append("manual_review")
    record["filter_decision"] = "rejected"
    record["decision"] = "rejected"
    record["rejection_reasons"] = sorted(set(reasons))
    record["rejection_categories"] = sorted(set(categories))
    record["hard_filter_failures"] = sorted(set(list(record.get("hard_filter_failures") or []) + ["manual_review_rejected"]))
    return record



def materialize_review_outcomes(review_doc: dict[str, Any] | None = None) -> dict[str, Any]:
    current_doc = review_doc or _read_json(REVIEW_STATE_PATH)
    items = current_doc.get("items", []) if isinstance(current_doc, dict) else []
    auto_accepted_rows = _read_jsonl(FILTER_ACCEPTED_PATH)
    accepted_index = {
        str(row.get("candidate_id") or row.get("generation_id") or ""): row
        for row in auto_accepted_rows
        if str(row.get("candidate_id") or row.get("generation_id") or "")
    }
    auto_rejected_rows = _read_jsonl(FILTER_REJECTED_PATH)

    approved_rows: list[dict[str, Any]] = []
    manual_rejected_rows: list[dict[str, Any]] = []
    approved_count = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        candidate_id = str(item.get("candidate_id") or "")
        fallback_record = accepted_index.get(candidate_id, {})
        review_status = str(item.get("review_status") or "pending_review")
        if review_status == "approved":
            record = dict(item.get("filter_record") or fallback_record)
            if record:
                approved_rows.append(record)
                approved_count += 1
        elif review_status == "rejected":
            manual_record = _manual_rejected_record(item, fallback_record)
            if manual_record:
                manual_rejected_rows.append(manual_record)

    _write_jsonl(FILTER_ACCEPTED_PATH, approved_rows)
    _write_jsonl(FILTER_REJECTED_PATH, auto_rejected_rows + manual_rejected_rows)

    return {
        "approved_count": approved_count,
        "approved_rows": approved_rows,
        "manual_rejected_count": len(manual_rejected_rows),
    }



def sync_finalized_results_to_curated() -> list[str]:
    outputs: list[str] = []
    file_pairs = [
        (FINAL_PAIRS_PATH, CURATED_FINAL_PAIRS_PATH),
        (EXERCISES_ALL_PATH, CURATED_EXERCISES_ALL_PATH),
        (AI_DATASET_PATH, CURATED_AI_DATASET_PATH),
        (BLIND_MAPPING_SOURCE_PATH, CURATED_BLIND_MAPPING_PATH),
    ]
    for source_path, target_path in file_pairs:
        if not source_path.exists():
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        outputs.append(str(target_path))
    return outputs

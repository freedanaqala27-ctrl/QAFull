from __future__ import annotations

import argparse
import ast
import csv
import json
import py_compile
import re
import tempfile
from pathlib import Path
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

PROJECT_ROOT = Path(__file__).resolve().parents[1]

REFERENCE_INDEX = PROJECT_ROOT / "data" / "processed" / "reference_index.v1.jsonl"
RAW_GENERATIONS = PROJECT_ROOT / "outputs" / "raw_generations" / "generations.raw.v1.jsonl"
ACCEPTED_AI_POOL = PROJECT_ROOT / "data" / "ai_generated" / "accepted" / "ai_exercises.accepted.v1.json"
OUT_ACCEPTED = PROJECT_ROOT / "outputs" / "filtered" / "accepted" / "candidates.accepted.v1.jsonl"
OUT_REJECTED = PROJECT_ROOT / "outputs" / "filtered" / "rejected" / "candidates.rejected.v1.jsonl"
OUT_SUMMARY = PROJECT_ROOT / "outputs" / "filtered" / "filter_summary.v1.csv"
OUT_SUMMARY_BY_REASON = PROJECT_ROOT / "outputs" / "filtered" / "filter_summary_by_reason.v1.csv"
OUT_SUMMARY_BY_CATEGORY = PROJECT_ROOT / "outputs" / "filtered" / "filter_summary_by_category.v1.csv"

CORE_FIELDS = ["title", "instruction_text"]
SUPPORT_FIELDS = ["constraints", "expected_output"]
CODE_FIELDS = ["starter_code", "test_cases"]

TITLE_DUP_REF_THRESHOLD = 0.90
INSTR_DUP_REF_THRESHOLD = 0.90
INSTR_DUP_AI_THRESHOLD = 0.92

DEFAULT_MIN_INSTRUCTION_COMPLETENESS = 0.50
DEFAULT_MIN_STRUCTURE_COMPLETENESS = 0.50
DEFAULT_MIN_OBJECTIVE_OVERLAP = 0.05

STRICT_MIN_INSTRUCTION_COMPLETENESS = 0.67
STRICT_MIN_STRUCTURE_COMPLETENESS = 0.70
STRICT_MIN_OBJECTIVE_OVERLAP = 0.20

WARNING_PENALTIES = {
    "instruction_missing_success_criteria": 0.08,
    "instruction_missing_background_knowledge": 0.06,
    "instruction_missing_constraints": 0.08,
    "learning_objective_mismatch_soft": 0.10,
    "code_completion_without_clear_todo": 0.05,
}

REASON_CATEGORY_MAP = {
    "api_error": "parsing",
    "invalid_json": "parsing",
    "json_not_found": "parsing",
    "schema_invalid": "schema",
    "missing_keys": "schema",
    "topic_mismatch": "comparability",
    "difficulty_mismatch": "comparability",
    "exercise_type_mismatch": "comparability",
    "learning_objective_mismatch": "comparability",
    "learning_objective_mismatch_hard": "comparability",
    "instruction_missing_task_goal": "instruction",
    "instruction_missing_io_or_behavior": "instruction",
    "instruction_too_incomplete": "instruction",
    "structure_too_incomplete": "instruction",
    "code_missing_starter_code": "code",
    "code_syntax_error": "code",
    "code_undefined_dependency": "code",
    "near_duplicate_reference": "duplicate",
    "near_duplicate_existing_ai": "duplicate",
    "near_duplicate_current_batch": "duplicate",
    "not_testable": "code",
    "scope_project_like": "scope",
    "scope_time_overflow": "scope",
    "scope_external_dependency": "scope",
    "scope_multi_task": "scope",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_reference_index(path: Path) -> dict[str, dict[str, Any]]:
    rows = read_jsonl(path)
    return {row["exercise_id"]: row for row in rows}


def load_prior_accepted_ai_pool(path: Path) -> list[dict[str, Any]]:
    doc = load_json(path)
    return doc.get("items", []) if isinstance(doc, dict) else []


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def text_nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def list_nonempty(value: Any) -> bool:
    return isinstance(value, list) and len(value) > 0


def jaccard_overlap(a: list[str], b: list[str]) -> float:
    sa = {x.strip().lower() for x in a if isinstance(x, str) and x.strip()}
    sb = {x.strip().lower() for x in b if isinstance(x, str) and x.strip()}
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def categorize_reasons(reasons: list[str]) -> list[str]:
    return sorted({REASON_CATEGORY_MAP.get(reason, "other") for reason in reasons})


def run_structure_validation(payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    required_keys = {
        "title",
        "topic",
        "difficulty",
        "exercise_type",
        "instruction_text",
        "programming_language",
        "framework",
        "has_code",
        "starter_code",
        "constraints",
        "expected_output",
        "test_cases",
        "learning_objectives",
        "prerequisite_concepts",
        "keywords",
        "estimated_time_minutes",
        "target_learner_level",
        "course_context",
        "notes",
    }
    missing = sorted(required_keys - payload.keys())
    if missing:
        failures.append("missing_keys")
    if payload.get("programming_language") != "Python":
        failures.append("programming_language_not_python")
    return failures


def run_scope_control_checks(payload: dict[str, Any], reference_item: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    text = " ".join(
        [
            payload.get("title", ""),
            payload.get("instruction_text", ""),
            payload.get("expected_output", ""),
            " ".join(payload.get("constraints", [])),
        ]
    ).lower()

    project_patterns = [
        r"\bfinal project\b",
        r"\bcapstone\b",
        r"\bend-to-end\b",
        r"\bresearch project\b",
        r"\bbuild a full\b",
        r"\bdeploy\b",
        r"\bmultiple modules\b",
    ]
    if any(re.search(pattern, text) for pattern in project_patterns):
        failures.append("scope_project_like")

    if payload.get("estimated_time_minutes", 0) > max(reference_item.get("estimated_time_minutes", 0) * 1.5, 90):
        failures.append("scope_time_overflow")

    external_dep_patterns = [r"\bdownload\b", r"\bexternal files?\b", r"\bkaggle\b", r"\bhidden dataset\b"]
    if any(re.search(pattern, text) for pattern in external_dep_patterns):
        failures.append("scope_external_dependency")

    multi_task_patterns = [r"\bpart 1\b.*\bpart 2\b", r"\bfirst\b.*\bthen\b.*\bfinally\b"]
    if any(re.search(pattern, text, flags=re.DOTALL) for pattern in multi_task_patterns):
        failures.append("scope_multi_task")

    return failures


def run_comparability_checks(payload: dict[str, Any], reference_item: dict[str, Any]) -> dict[str, Any]:
    topic_match = payload.get("topic") == reference_item.get("topic")
    difficulty_match = payload.get("difficulty") == reference_item.get("difficulty")
    gen_type_match = payload.get("exercise_type") == reference_item.get("generation_exercise_type")
    objective_overlap = jaccard_overlap(
        payload.get("learning_objectives", []),
        reference_item.get("learning_objectives", []),
    )
    return {
        "topic_exact_match": topic_match,
        "difficulty_exact_match": difficulty_match,
        "generation_type_match": gen_type_match,
        "learning_objective_overlap_score": round(objective_overlap, 4),
    }


def run_instruction_completeness_checks(payload: dict[str, Any]) -> dict[str, Any]:
    instruction_text = normalize_space(payload.get("instruction_text", "")).lower()
    expected_output = normalize_space(payload.get("expected_output", "")).lower()
    constraints = payload.get("constraints", [])
    prereq = payload.get("prerequisite_concepts", [])

    artifact_patterns = [r"\bsubmit\b", r"\breturn\b", r"\bprovide\b", r"\bplot\b", r"\btable\b", r"\bexplanation\b"]
    success_patterns = [r"\bsuccess\b", r"\bcorrect\b", r"\bshould\b", r"\bmust\b", r"\bpass\b", r"\bexpected\b"]

    result = {
        "task_goal_present": text_nonempty(payload.get("title")) and text_nonempty(payload.get("instruction_text")),
        "io_or_required_behavior_present": text_nonempty(payload.get("expected_output")) or len(payload.get("test_cases", [])) > 0,
        "constraints_present": list_nonempty(constraints),
        "success_criteria_present": bool(re.search("|".join(success_patterns), instruction_text + " " + expected_output)),
        "background_knowledge_present": list_nonempty(prereq),
        "submission_artifact_present": bool(re.search("|".join(artifact_patterns), instruction_text + " " + expected_output)),
    }
    score = sum(bool(value) for value in result.values())
    result["score"] = score
    result["ratio"] = round(score / 6.0, 4)
    return result


def run_structure_completeness_checks(payload: dict[str, Any]) -> dict[str, Any]:
    exercise_type = payload.get("exercise_type")

    core_present = sum(1 for field in CORE_FIELDS if text_nonempty(payload.get(field)))
    support_present = sum(
        1
        for field in SUPPORT_FIELDS
        if (text_nonempty(payload.get(field)) if field == "expected_output" else list_nonempty(payload.get(field, [])))
    )

    code_applicable_fields = []
    if exercise_type == "code completion":
        code_applicable_fields = CODE_FIELDS
    elif exercise_type in {"model building", "model revision"} and payload.get("has_code", False):
        code_applicable_fields = CODE_FIELDS

    code_present = 0
    if "starter_code" in code_applicable_fields and text_nonempty(payload.get("starter_code")):
        code_present += 1
    if "test_cases" in code_applicable_fields and list_nonempty(payload.get("test_cases", [])):
        code_present += 1

    applicable_total = len(CORE_FIELDS) + len(SUPPORT_FIELDS) + len(code_applicable_fields)
    present_total = core_present + support_present + code_present
    return {
        "core_present": core_present,
        "support_present": support_present,
        "code_present": code_present,
        "structure_completeness_ratio": round(present_total / max(1, applicable_total), 4),
        "structure_score_weighted": round(
            0.45 * (core_present / len(CORE_FIELDS))
            + 0.35 * (support_present / len(SUPPORT_FIELDS))
            + 0.20 * ((code_present / len(code_applicable_fields)) if code_applicable_fields else 1.0),
            4,
        ),
    }


def run_testability_checks(payload: dict[str, Any]) -> dict[str, Any]:
    test_cases = payload.get("test_cases", [])
    expected_output = normalize_space(payload.get("expected_output", ""))
    instruction = normalize_space(payload.get("instruction_text", "")).lower()
    exercise_type = payload.get("exercise_type")

    evidence_patterns = [r"\bplot\b", r"\btable\b", r"\bcompare\b", r"\bexplain\b", r"\bobserve\b", r"\breport\b"]
    has_evidence_requirement = bool(re.search("|".join(evidence_patterns), instruction + " " + expected_output))
    testable = bool(test_cases) or bool(expected_output) or has_evidence_requirement
    if exercise_type == "training-analysis":
        testable = has_evidence_requirement or bool(expected_output) or bool(test_cases)

    return {
        "has_test_cases": bool(test_cases),
        "expected_output_concrete": bool(expected_output),
        "has_evidence_requirement": has_evidence_requirement,
        "testable": testable,
    }


def strip_markdown_fences(code: str) -> str:
    code = code.strip()
    code = re.sub(r"^```python\s*", "", code)
    code = re.sub(r"^```\s*", "", code)
    code = re.sub(r"\s*```$", "", code)
    return code.strip()


def run_code_validity_checks(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload.get("has_code", False):
        return {
            "code_parse_status": "not_applicable",
            "ast_ok": None,
            "py_compile_ok": None,
            "syntax_error_type": "",
            "syntax_error_message": "",
            "todo_region_detected": False,
            "undefined_dependency_flag": False,
        }

    code = strip_markdown_fences(payload.get("starter_code", ""))
    if not code:
        return {
            "code_parse_status": "syntax_error",
            "ast_ok": False,
            "py_compile_ok": False,
            "syntax_error_type": "missing_code",
            "syntax_error_message": "has_code=true but starter_code is empty",
            "todo_region_detected": False,
            "undefined_dependency_flag": False,
        }

    todo_region_detected = "TODO" in code or "YOUR CODE HERE" in code
    undefined_dependency_flag = any(token in code for token in ["undefined_variable", "MISSING_HELPER", "YOUR_CODE_HERE"])

    try:
        ast.parse(code)
        ast_ok = True
        py_compile_ok = None
        with tempfile.NamedTemporaryFile("w", suffix=".py", encoding="utf-8", delete=False) as tmp:
            tmp.write(code)
            tmp_path = tmp.name
        try:
            py_compile.compile(tmp_path, doraise=True)
            py_compile_ok = True
        except py_compile.PyCompileError as exc:
            py_compile_ok = False
            return {
                "code_parse_status": "parsable_fragment" if todo_region_detected else "syntax_error",
                "ast_ok": ast_ok,
                "py_compile_ok": py_compile_ok,
                "syntax_error_type": "py_compile_error",
                "syntax_error_message": str(exc),
                "todo_region_detected": todo_region_detected,
                "undefined_dependency_flag": undefined_dependency_flag,
            }
    except SyntaxError as exc:
        return {
            "code_parse_status": "syntax_error",
            "ast_ok": False,
            "py_compile_ok": False,
            "syntax_error_type": type(exc).__name__,
            "syntax_error_message": str(exc),
            "todo_region_detected": todo_region_detected,
            "undefined_dependency_flag": undefined_dependency_flag,
        }

    return {
        "code_parse_status": "parsable_fragment",
        "ast_ok": True,
        "py_compile_ok": py_compile_ok,
        "syntax_error_type": "",
        "syntax_error_message": "",
        "todo_region_detected": todo_region_detected,
        "undefined_dependency_flag": undefined_dependency_flag,
    }


def cosine_sim(text_a: str, text_b: str) -> float:
    text_a = normalize_space(text_a)
    text_b = normalize_space(text_b)
    if not text_a or not text_b:
        return 0.0
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), lowercase=True)
    matrix = vectorizer.fit_transform([text_a, text_b])
    return float(cosine_similarity(matrix[0:1], matrix[1:2])[0][0])


def run_duplicate_checks(
    payload: dict[str, Any],
    reference_item: dict[str, Any],
    prior_ai_pool: list[dict[str, Any]],
    current_batch_accepted_pool: list[dict[str, Any]],
) -> dict[str, Any]:
    ref_payload = reference_item["reference_payload"]

    title_sim_to_ref = cosine_sim(payload.get("title", ""), ref_payload.get("title", ""))
    instruction_sim_to_ref = cosine_sim(payload.get("instruction_text", ""), ref_payload.get("instruction_text", ""))

    max_instruction_existing = 0.0
    max_title_existing = 0.0
    for item in prior_ai_pool:
        max_instruction_existing = max(max_instruction_existing, cosine_sim(payload.get("instruction_text", ""), item.get("instruction_text", "")))
        max_title_existing = max(max_title_existing, cosine_sim(payload.get("title", ""), item.get("title", "")))

    max_instruction_current = 0.0
    max_title_current = 0.0
    for item in current_batch_accepted_pool:
        max_instruction_current = max(max_instruction_current, cosine_sim(payload.get("instruction_text", ""), item.get("instruction_text", "")))
        max_title_current = max(max_title_current, cosine_sim(payload.get("title", ""), item.get("title", "")))

    return {
        "title_tfidf_cosine_to_reference": round(title_sim_to_ref, 4),
        "instruction_tfidf_cosine_to_reference": round(instruction_sim_to_ref, 4),
        "max_instruction_tfidf_cosine_to_existing_ai": round(max_instruction_existing, 4),
        "max_title_tfidf_cosine_to_existing_ai": round(max_title_existing, 4),
        "max_instruction_tfidf_cosine_to_current_batch": round(max_instruction_current, 4),
        "max_title_tfidf_cosine_to_current_batch": round(max_title_current, 4),
        "near_duplicate_reference_flag": instruction_sim_to_ref >= INSTR_DUP_REF_THRESHOLD or title_sim_to_ref >= TITLE_DUP_REF_THRESHOLD,
        "near_duplicate_existing_ai_flag": max_instruction_existing >= INSTR_DUP_AI_THRESHOLD or max_title_existing >= INSTR_DUP_AI_THRESHOLD,
        "near_duplicate_current_batch_flag": max_instruction_current >= INSTR_DUP_AI_THRESHOLD or max_title_current >= INSTR_DUP_AI_THRESHOLD,
    }


def calculate_soft_rank_score(
    instruction_ratio: float,
    structure_ratio: float,
    objective_overlap: float,
    duplicate_penalty: float,
    penalty_points: float,
) -> float:
    score = (
        0.38 * instruction_ratio
        + 0.34 * structure_ratio
        + 0.18 * objective_overlap
        - 0.10 * duplicate_penalty
        - penalty_points
    )
    return round(max(score, 0.0), 4)


def evaluate_candidate(
    raw_record: dict[str, Any],
    reference_item: dict[str, Any],
    prior_ai_pool: list[dict[str, Any]],
    current_batch_accepted_pool: list[dict[str, Any]],
    strict: bool,
    min_instruction_completeness: float,
    min_structure_completeness: float,
    min_objective_overlap: float,
) -> dict[str, Any]:
    payload = raw_record.get("payload") or {}
    failures: list[str] = []
    warning_flags: list[str] = []
    penalty_points = 0.0

    if raw_record.get("api_status") == "error":
        failures.append("api_error")
    if raw_record.get("parse_status") in {"json_not_found", "invalid_json", "api_error"}:
        failures.append(raw_record.get("parse_status", "invalid_json"))
    if not raw_record.get("schema_valid", False):
        failures.append("schema_invalid")
    failures.extend(run_structure_validation(payload))

    comparability = run_comparability_checks(payload, reference_item)
    instruction = run_instruction_completeness_checks(payload)
    structure = run_structure_completeness_checks(payload)
    code_validity = run_code_validity_checks(payload)
    testability = run_testability_checks(payload)
    duplicate = run_duplicate_checks(payload, reference_item, prior_ai_pool, current_batch_accepted_pool)
    failures.extend(run_scope_control_checks(payload, reference_item))

    if not comparability["topic_exact_match"]:
        failures.append("topic_mismatch")
    if not comparability["difficulty_exact_match"]:
        failures.append("difficulty_mismatch")
    if not comparability["generation_type_match"]:
        failures.append("exercise_type_mismatch")

    if instruction["task_goal_present"] is False:
        failures.append("instruction_missing_task_goal")
    if instruction["io_or_required_behavior_present"] is False:
        failures.append("instruction_missing_io_or_behavior")
    if instruction["success_criteria_present"] is False:
        warning_flags.append("instruction_missing_success_criteria")
        penalty_points += WARNING_PENALTIES["instruction_missing_success_criteria"]
    if instruction["background_knowledge_present"] is False:
        warning_flags.append("instruction_missing_background_knowledge")
        penalty_points += WARNING_PENALTIES["instruction_missing_background_knowledge"]
    if instruction["constraints_present"] is False:
        warning_flags.append("instruction_missing_constraints")
        penalty_points += WARNING_PENALTIES["instruction_missing_constraints"]

    if instruction["ratio"] < min_instruction_completeness:
        failures.append("instruction_too_incomplete")
    if structure["structure_completeness_ratio"] < min_structure_completeness:
        failures.append("structure_too_incomplete")

    objective_overlap = comparability["learning_objective_overlap_score"]
    if objective_overlap < min_objective_overlap:
        if strict or objective_overlap <= max(min_objective_overlap / 2.0, 0.01):
            failures.append("learning_objective_mismatch_hard")
        else:
            warning_flags.append("learning_objective_mismatch_soft")
            penalty_points += WARNING_PENALTIES["learning_objective_mismatch_soft"]

    if payload.get("has_code") and not text_nonempty(payload.get("starter_code")):
        failures.append("code_missing_starter_code")
    if payload.get("has_code") and not code_validity["ast_ok"]:
        failures.append("code_syntax_error")
    if payload.get("has_code") and code_validity["undefined_dependency_flag"]:
        failures.append("code_undefined_dependency")
    if payload.get("exercise_type") == "code completion" and not code_validity["todo_region_detected"]:
        warning_flags.append("code_completion_without_clear_todo")
        penalty_points += WARNING_PENALTIES["code_completion_without_clear_todo"]

    if not testability["testable"]:
        failures.append("not_testable")

    if duplicate["near_duplicate_reference_flag"]:
        failures.append("near_duplicate_reference")
    if duplicate["near_duplicate_existing_ai_flag"]:
        failures.append("near_duplicate_existing_ai")
    if duplicate["near_duplicate_current_batch_flag"]:
        failures.append("near_duplicate_current_batch")

    duplicate_penalty = round(
        max(
            duplicate["instruction_tfidf_cosine_to_reference"],
            duplicate["max_instruction_tfidf_cosine_to_existing_ai"],
            duplicate["max_instruction_tfidf_cosine_to_current_batch"],
        ),
        4,
    )
    soft_rank_score = calculate_soft_rank_score(
        instruction_ratio=instruction["ratio"],
        structure_ratio=structure["structure_completeness_ratio"],
        objective_overlap=objective_overlap,
        duplicate_penalty=duplicate_penalty,
        penalty_points=penalty_points,
    )

    rejection_reasons = sorted(set(failures))
    rejection_categories = categorize_reasons(rejection_reasons)
    filter_decision = "accepted" if not rejection_reasons else "rejected"

    return {
        "candidate_id": raw_record.get("candidate_id", raw_record.get("generation_id", "")),
        "generation_id": raw_record.get("generation_id", ""),
        "run_id": raw_record.get("run_id", ""),
        "prompt_id": raw_record.get("prompt_id", ""),
        "prompt_version": raw_record.get("prompt_version", ""),
        "reference_exercise_id": raw_record.get("reference_exercise_id", ""),
        "reference_exercise_type_original": raw_record.get("reference_exercise_type_original", reference_item.get("reference_exercise_type_original", "")),
        "generation_exercise_type": raw_record.get("generation_exercise_type", reference_item.get("generation_exercise_type", "")),
        "topic": payload.get("topic") or reference_item.get("topic"),
        "difficulty": payload.get("difficulty") or reference_item.get("difficulty"),
        "provider": raw_record.get("provider", ""),
        "model_name": raw_record.get("model_name", ""),
        "temperature": raw_record.get("temperature"),
        "max_tokens": raw_record.get("max_tokens"),
        "generation_started_at": raw_record.get("generation_started_at", ""),
        "generation_finished_at": raw_record.get("generation_finished_at", ""),
        "generation_prompt_hash": raw_record.get("generation_prompt_hash", ""),
        "generation_prompt_excerpt": raw_record.get("generation_prompt_excerpt", ""),
        "api_status": raw_record.get("api_status", ""),
        "json_extract_status": raw_record.get("json_extract_status", ""),
        "schema_status": raw_record.get("schema_status", ""),
        "error_stage": raw_record.get("error_stage", ""),
        "error_message_short": raw_record.get("error_message_short", ""),
        "parse_status": raw_record.get("parse_status", ""),
        "schema_valid": bool(raw_record.get("schema_valid")),
        "validation_errors": raw_record.get("validation_errors", []),
        "filter_decision": filter_decision,
        "decision": filter_decision,
        "rejection_reasons": rejection_reasons,
        "rejection_categories": rejection_categories,
        "hard_filter_failures": rejection_reasons,
        "hard_filter_pass": not rejection_reasons,
        "warning_flags": sorted(set(warning_flags)),
        "penalty_points": round(penalty_points, 4),
        "soft_rank_score": soft_rank_score,
        "instruction_ratio": instruction["ratio"],
        "structure_ratio": structure["structure_completeness_ratio"],
        "objective_overlap": objective_overlap,
        "duplicate_penalty": duplicate_penalty,
        "code_parse_ok": code_validity["ast_ok"],
        "testability_ok": testability["testable"],
        "comparability": comparability,
        "instruction_completeness": instruction,
        "structure_completeness": structure,
        "code_validity": code_validity,
        "testability": testability,
        "duplicate_check": duplicate,
        "quick_scores": {
            "instruction_ratio": instruction["ratio"],
            "structure_ratio": structure["structure_completeness_ratio"],
            "objective_overlap": objective_overlap,
            "duplicate_penalty": duplicate_penalty,
            "code_parse_ok": code_validity["ast_ok"],
            "testability_ok": testability["testable"],
        },
        "payload": payload,
    }


def split_filter_results(decisions: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted = [row for row in decisions if row["filter_decision"] == "accepted"]
    rejected = [row for row in decisions if row["filter_decision"] == "rejected"]
    return accepted, rejected


def build_filter_summary(decisions: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    total = len(decisions)
    accepted_count = sum(row["filter_decision"] == "accepted" for row in decisions)
    rejected_count = total - accepted_count

    overall_rows = [
        {"metric": "total", "count": total, "rate": 1.0 if total else 0.0},
        {"metric": "accepted", "count": accepted_count, "rate": round(accepted_count / total, 4) if total else 0.0},
        {"metric": "rejected", "count": rejected_count, "rate": round(rejected_count / total, 4) if total else 0.0},
        {"metric": "acceptance_rate", "count": accepted_count, "rate": round(accepted_count / total, 4) if total else 0.0},
    ]

    reason_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    for row in decisions:
        if row["filter_decision"] != "rejected":
            continue
        for reason in row.get("rejection_reasons", []):
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        for category in row.get("rejection_categories", []):
            category_counts[category] = category_counts.get(category, 0) + 1

    by_reason_rows = [
        {"reason": reason, "count": count, "rate": round(count / total, 4) if total else 0.0}
        for reason, count in sorted(reason_counts.items())
    ]
    by_category_rows = [
        {"category": category, "count": count, "rate": round(count / total, 4) if total else 0.0}
        for category, count in sorted(category_counts.items())
    ]
    return overall_rows, by_reason_rows, by_category_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-index", default=str(REFERENCE_INDEX))
    parser.add_argument("--raw-jsonl", default=str(RAW_GENERATIONS))
    parser.add_argument("--accepted-pool", default=str(ACCEPTED_AI_POOL))
    parser.add_argument("--accepted-out", default=str(OUT_ACCEPTED))
    parser.add_argument("--rejected-out", default=str(OUT_REJECTED))
    parser.add_argument("--summary-out", default=str(OUT_SUMMARY))
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--min-instruction-completeness", type=float)
    parser.add_argument("--min-structure-completeness", type=float)
    parser.add_argument("--min-objective-overlap", type=float)
    args = parser.parse_args()

    min_instruction_completeness = args.min_instruction_completeness
    min_structure_completeness = args.min_structure_completeness
    min_objective_overlap = args.min_objective_overlap
    if args.strict:
        if min_instruction_completeness is None:
            min_instruction_completeness = STRICT_MIN_INSTRUCTION_COMPLETENESS
        if min_structure_completeness is None:
            min_structure_completeness = STRICT_MIN_STRUCTURE_COMPLETENESS
        if min_objective_overlap is None:
            min_objective_overlap = STRICT_MIN_OBJECTIVE_OVERLAP
    else:
        if min_instruction_completeness is None:
            min_instruction_completeness = DEFAULT_MIN_INSTRUCTION_COMPLETENESS
        if min_structure_completeness is None:
            min_structure_completeness = DEFAULT_MIN_STRUCTURE_COMPLETENESS
        if min_objective_overlap is None:
            min_objective_overlap = DEFAULT_MIN_OBJECTIVE_OVERLAP

    reference_index = load_reference_index(Path(args.reference_index))
    raw_records = read_jsonl(Path(args.raw_jsonl))
    prior_ai_pool = load_prior_accepted_ai_pool(Path(args.accepted_pool))
    current_batch_accepted_pool: list[dict[str, Any]] = []

    decisions: list[dict[str, Any]] = []
    for raw_record in raw_records:
        reference_item = reference_index[raw_record["reference_exercise_id"]]
        decision = evaluate_candidate(
            raw_record=raw_record,
            reference_item=reference_item,
            prior_ai_pool=prior_ai_pool,
            current_batch_accepted_pool=current_batch_accepted_pool,
            strict=args.strict,
            min_instruction_completeness=min_instruction_completeness,
            min_structure_completeness=min_structure_completeness,
            min_objective_overlap=min_objective_overlap,
        )
        decisions.append(decision)
        if decision["filter_decision"] == "accepted" and isinstance(decision.get("payload"), dict):
            current_batch_accepted_pool.append(decision["payload"])

    accepted, rejected = split_filter_results(decisions)
    overall_rows, reason_rows, category_rows = build_filter_summary(decisions)

    write_jsonl(accepted, Path(args.accepted_out))
    write_jsonl(rejected, Path(args.rejected_out))
    write_csv(overall_rows, Path(args.summary_out))
    write_csv(reason_rows, OUT_SUMMARY_BY_REASON)
    write_csv(category_rows, OUT_SUMMARY_BY_CATEGORY)

    print(f"Accepted: {len(accepted)} -> {args.accepted_out}")
    print(f"Rejected: {len(rejected)} -> {args.rejected_out}")
    print(f"Wrote filter summary -> {args.summary_out}")
    print(f"Wrote reason summary -> {OUT_SUMMARY_BY_REASON}")
    print(f"Wrote category summary -> {OUT_SUMMARY_BY_CATEGORY}")


if __name__ == "__main__":
    main()

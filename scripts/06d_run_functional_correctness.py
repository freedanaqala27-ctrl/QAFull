from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from _shared_execution_eval import (
    DEFAULT_MAX_MEMORY_BYTES,
    EVAL_RESULT_BEGIN,
    EVAL_RESULT_END,
    assemble_solution_code,
    build_test_harness,
    ensure_string_list,
    ensure_surface_checks,
    required_packages_status,
    run_subprocess_code,
)
from _shared_io import index_rows_by_key, read_jsonl_rows, write_csv_rows, write_json_doc, write_jsonl_rows

PROJECT_ROOT = Path(__file__).resolve().parents[1]

FINAL_PAIRS = PROJECT_ROOT / "results" / "final_pairs.v1.jsonl"
VALIDATION_JSONL = PROJECT_ROOT / "results" / "reference_solution_validation.v1.jsonl"
OUT_JSONL = PROJECT_ROOT / "results" / "exercise_correctness_metrics.v1.jsonl"
OUT_CSV = PROJECT_ROOT / "results" / "exercise_correctness_metrics.v1.csv"
OUT_MANIFEST = PROJECT_ROOT / "results" / "exercise_correctness_manifest.v1.json"
REFERENCE_SOLUTIONS = PROJECT_ROOT / "results" / "reference_solutions.v1.jsonl"
EXECUTABLE_TESTS = PROJECT_ROOT / "results" / "executable_tests.v1.jsonl"

CURATED_DIR = PROJECT_ROOT / "results" / "curated"
CURATED_FINAL_PAIRS = CURATED_DIR / "final_pairs.curated.v1.jsonl"
CURATED_VALIDATION_JSONL = CURATED_DIR / "reference_solution_validation.curated.v1.jsonl"
CURATED_OUT_JSONL = CURATED_DIR / "exercise_correctness_metrics.curated.v1.jsonl"
CURATED_OUT_CSV = CURATED_DIR / "exercise_correctness_metrics.curated.v1.csv"
CURATED_OUT_MANIFEST = CURATED_DIR / "exercise_correctness_manifest.curated.v1.json"
CURATED_REFERENCE_SOLUTIONS = CURATED_DIR / "reference_solutions.curated.v1.jsonl"
CURATED_EXECUTABLE_TESTS = CURATED_DIR / "executable_tests.curated.v1.jsonl"


def safe_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def merge_overlay(
    payload: dict[str, Any],
    exercise_id: str,
    solution_index: dict[str, dict[str, Any]],
    tests_index: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], bool, bool]:
    merged = dict(payload or {})
    solution_overlay = solution_index.get(exercise_id, {})
    tests_overlay = tests_index.get(exercise_id, {})
    solution_hit = bool(solution_overlay)
    tests_hit = bool(tests_overlay)
    if solution_hit:
        for key, value in solution_overlay.items():
            if key != "exercise_id":
                merged[key] = value
    if tests_hit:
        for key, value in tests_overlay.items():
            if key != "exercise_id":
                merged[key] = value
    return merged, solution_hit, tests_hit


def parse_json_from_output(text: str) -> dict[str, Any]:
    pattern = re.compile(
        rf"{re.escape(EVAL_RESULT_BEGIN)}\s*(\{{.*?\}})\s*{re.escape(EVAL_RESULT_END)}",
        flags=re.DOTALL,
    )
    matches = pattern.findall(text)
    if not matches:
        return {}
    try:
        return json.loads(matches[-1])
    except json.JSONDecodeError:
        return {}


def summarize_surface_results(surface_results: list[dict[str, Any]]) -> tuple[int, int, int, int]:
    total = len(surface_results)
    passed = sum(1 for item in surface_results if item.get("passed"))
    shape_passed = sum(1 for item in surface_results if item.get("passed") and "shape" in str(item.get("type", "")).lower())
    behavior_passed = sum(
        1
        for item in surface_results
        if item.get("passed") and any(token in str(item.get("type", "")).lower() for token in ["behavior", "forward", "backward", "api"])
    )
    return total, passed, shape_passed, behavior_passed


def build_row(
    payload: dict[str, Any],
    *,
    validation_row: dict[str, Any] | None,
    pair_id: str,
    source_type: str,
    exercise_id: str,
    default_timeout_seconds: int,
    solution_overlay_hit: bool,
    tests_overlay_hit: bool,
    default_max_memory_bytes: int,
) -> dict[str, Any]:
    packages_ok, missing_packages = required_packages_status(payload)
    assembled = assemble_solution_code(payload)
    timeout_seconds = max(safe_int(payload.get("timeout_seconds"), default_timeout_seconds), default_timeout_seconds)
    max_memory_bytes = safe_int(payload.get("max_memory_bytes"), default_max_memory_bytes)

    row = {
        "pair_id": pair_id,
        "exercise_id": exercise_id,
        "source_type": source_type,
        "topic": payload.get("topic", ""),
        "difficulty": payload.get("difficulty", ""),
        "exercise_type": payload.get("exercise_type", ""),
        "entry_point": payload.get("entry_point", ""),
        "evaluation_mode": payload.get("evaluation_mode", ""),
        "public_tests_total": 0,
        "public_tests_passed": 0,
        "hidden_tests_total": 0,
        "hidden_tests_passed": 0,
        "public_pass_rate": 0.0,
        "hidden_pass_rate": 0.0,
        "surface_checks_total": 0,
        "surface_checks_passed": 0,
        "shape_checks_passed": 0,
        "behavior_checks_passed": 0,
        "correctness_status": "",
        "reference_solution_fully_valid": False,
        "required_packages_satisfied": packages_ok,
        "missing_packages": "|".join(missing_packages),
        "exec_prereq_status": (validation_row or {}).get("reference_solution_status", ""),
        "timeout_seconds": timeout_seconds,
        "max_memory_bytes": max_memory_bytes,
        "failure_message": "",
        "solution_overlay_hit": solution_overlay_hit,
        "tests_overlay_hit": tests_overlay_hit,
    }

    if assembled["assembly_status"] != "ok":
        row["correctness_status"] = "not_evaluable"
        row["failure_message"] = assembled["assembly_status"]
        return row
    if not packages_ok:
        row["correctness_status"] = "not_evaluable"
        row["failure_message"] = "missing_packages"
        return row
    if validation_row and validation_row.get("reference_solution_status") != "exec_ok":
        row["correctness_status"] = "not_evaluable"
        row["failure_message"] = validation_row.get("reference_solution_status", "")
        return row

    public_tests = ensure_string_list(payload.get("public_tests_py", []))
    hidden_tests = ensure_string_list(payload.get("hidden_tests_py", []))
    surface_checks = ensure_surface_checks(payload.get("surface_checks", []))
    all_tests = public_tests + hidden_tests

    row["public_tests_total"] = len(public_tests)
    row["hidden_tests_total"] = len(hidden_tests)

    if not all_tests and not surface_checks:
        row["correctness_status"] = "not_evaluable"
        row["failure_message"] = "missing_executable_tests"
        return row

    harness = build_test_harness(assembled["assembled_code"], all_tests, surface_checks)
    run_result = run_subprocess_code(harness, timeout_seconds, max_memory_bytes=max_memory_bytes)
    if run_result["timed_out"]:
        row["correctness_status"] = "timeout"
        row["failure_message"] = "functional correctness harness timed out"
        return row

    payload_out = parse_json_from_output((run_result["stdout"] or "") + "\n" + (run_result["stderr"] or ""))
    if not payload_out:
        row["correctness_status"] = "fail"
        row["failure_message"] = "missing_harness_output"
        return row
    if not payload_out.get("exec_ok"):
        row["correctness_status"] = "fail"
        row["failure_message"] = f"{payload_out.get('exec_error_type', '')}: {payload_out.get('exec_error_message', '')}".strip()
        return row

    test_results = payload_out.get("test_results", [])
    public_results = test_results[: len(public_tests)]
    hidden_results = test_results[len(public_tests) :]

    row["public_tests_passed"] = sum(1 for item in public_results if item.get("passed"))
    row["hidden_tests_passed"] = sum(1 for item in hidden_results if item.get("passed"))
    if public_tests:
        row["public_pass_rate"] = round(row["public_tests_passed"] / len(public_tests), 4)
    if hidden_tests:
        row["hidden_pass_rate"] = round(row["hidden_tests_passed"] / len(hidden_tests), 4)

    surface_total, surface_passed, shape_passed, behavior_passed = summarize_surface_results(
        payload_out.get("surface_results", [])
    )
    row["surface_checks_total"] = surface_total
    row["surface_checks_passed"] = surface_passed
    row["shape_checks_passed"] = shape_passed
    row["behavior_checks_passed"] = behavior_passed

    total_checks = row["public_tests_total"] + row["hidden_tests_total"] + row["surface_checks_total"]
    passed_checks = row["public_tests_passed"] + row["hidden_tests_passed"] + row["surface_checks_passed"]
    if total_checks == 0:
        row["correctness_status"] = "not_evaluable"
    elif passed_checks == total_checks:
        row["correctness_status"] = "pass"
        row["reference_solution_fully_valid"] = True
    elif passed_checks > 0:
        row["correctness_status"] = "partial_pass"
    else:
        row["correctness_status"] = "fail"

    if row["correctness_status"] != "pass":
        failing_records = [
            item for item in test_results + payload_out.get("surface_results", []) if not item.get("passed", False)
        ]
        if failing_records:
            first_fail = failing_records[0]
            row["failure_message"] = f"{first_fail.get('error_type', '')}: {first_fail.get('error_message', '')}".strip()
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Run functional correctness checks for exercise reference solutions.")
    parser.add_argument("--pairs-jsonl", default=str(FINAL_PAIRS))
    parser.add_argument("--validation-jsonl", default=str(VALIDATION_JSONL))
    parser.add_argument("--output-jsonl", default=str(OUT_JSONL))
    parser.add_argument("--output-csv", default=str(OUT_CSV))
    parser.add_argument("--manifest-output", default=str(OUT_MANIFEST))
    parser.add_argument("--reference-solutions-jsonl", default=str(REFERENCE_SOLUTIONS))
    parser.add_argument("--executable-tests-jsonl", default=str(EXECUTABLE_TESTS))
    parser.add_argument("--default-timeout-seconds", type=int, default=10)
    parser.add_argument("--default-max-memory-bytes", type=int, default=DEFAULT_MAX_MEMORY_BYTES)
    parser.add_argument("--use-curated", action="store_true")
    args = parser.parse_args()

    if args.use_curated:
        args.pairs_jsonl = str(CURATED_FINAL_PAIRS)
        args.validation_jsonl = str(CURATED_VALIDATION_JSONL)
        args.output_jsonl = str(CURATED_OUT_JSONL)
        args.output_csv = str(CURATED_OUT_CSV)
        args.manifest_output = str(CURATED_OUT_MANIFEST)
        args.reference_solutions_jsonl = str(CURATED_REFERENCE_SOLUTIONS)
        args.executable_tests_jsonl = str(CURATED_EXECUTABLE_TESTS)

    pair_rows = read_jsonl_rows(Path(args.pairs_jsonl))
    validation_rows = read_jsonl_rows(Path(args.validation_jsonl))
    validation_index = {(row.get("pair_id", ""), row.get("exercise_id", "")): row for row in validation_rows}
    solution_index = index_rows_by_key(read_jsonl_rows(Path(args.reference_solutions_jsonl)), "exercise_id")
    tests_index = index_rows_by_key(read_jsonl_rows(Path(args.executable_tests_jsonl)), "exercise_id")

    output_rows: list[dict[str, Any]] = []
    for pair in pair_rows:
        ref_payload, ref_solution_hit, ref_tests_hit = merge_overlay(
            pair.get("reference_payload", {}),
            pair.get("reference_exercise_id", ""),
            solution_index,
            tests_index,
        )
        output_rows.append(
            build_row(
                ref_payload,
                validation_row=validation_index.get((pair.get("pair_id", ""), pair.get("reference_exercise_id", ""))),
                pair_id=pair.get("pair_id", ""),
                source_type="Expert",
                exercise_id=pair.get("reference_exercise_id", ""),
                default_timeout_seconds=args.default_timeout_seconds,
                solution_overlay_hit=ref_solution_hit,
                tests_overlay_hit=ref_tests_hit,
                default_max_memory_bytes=args.default_max_memory_bytes,
            )
        )
        ai_payload, ai_solution_hit, ai_tests_hit = merge_overlay(
            pair.get("ai_payload", {}),
            pair.get("ai_exercise_id", ""),
            solution_index,
            tests_index,
        )
        output_rows.append(
            build_row(
                ai_payload,
                validation_row=validation_index.get((pair.get("pair_id", ""), pair.get("ai_exercise_id", ""))),
                pair_id=pair.get("pair_id", ""),
                source_type="AI",
                exercise_id=pair.get("ai_exercise_id", ""),
                default_timeout_seconds=args.default_timeout_seconds,
                solution_overlay_hit=ai_solution_hit,
                tests_overlay_hit=ai_tests_hit,
                default_max_memory_bytes=args.default_max_memory_bytes,
            )
        )

    manifest = {
        "num_pairs": len(pair_rows),
        "num_exercises": len(output_rows),
        "correctness_status_counts": {},
        "fully_valid_reference_solutions": sum(1 for row in output_rows if row["reference_solution_fully_valid"]),
        "overlay_coverage": {
            "solution_overlay_hits": sum(1 for row in output_rows if row["solution_overlay_hit"]),
            "tests_overlay_hits": sum(1 for row in output_rows if row["tests_overlay_hit"]),
        },
    }
    status_counts: dict[str, int] = {}
    for row in output_rows:
        status = row["correctness_status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    manifest["correctness_status_counts"] = status_counts

    write_jsonl_rows(output_rows, Path(args.output_jsonl))
    write_csv_rows(output_rows, Path(args.output_csv))
    write_json_doc(manifest, Path(args.manifest_output))

    print(f"Wrote {len(output_rows)} correctness rows -> {args.output_jsonl}")
    print(f"Wrote correctness CSV -> {args.output_csv}")
    print(f"Wrote correctness manifest -> {args.manifest_output}")


if __name__ == "__main__":
    main()

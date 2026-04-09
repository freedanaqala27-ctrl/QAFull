from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from _shared_execution_eval import (
    DEFAULT_MAX_MEMORY_BYTES,
    assemble_solution_code,
    required_packages_status,
    run_subprocess_code,
    validate_code_artifact,
)
from _shared_io import index_rows_by_key, read_jsonl_rows, write_csv_rows, write_json_doc, write_jsonl_rows

PROJECT_ROOT = Path(__file__).resolve().parents[1]

FINAL_PAIRS = PROJECT_ROOT / "results" / "final_pairs.v1.jsonl"
OUT_JSONL = PROJECT_ROOT / "results" / "reference_solution_validation.v1.jsonl"
OUT_CSV = PROJECT_ROOT / "results" / "reference_solution_validation.v1.csv"
OUT_MANIFEST = PROJECT_ROOT / "results" / "reference_solution_validation_manifest.v1.json"
REFERENCE_SOLUTIONS = PROJECT_ROOT / "results" / "reference_solutions.v1.jsonl"
EXECUTABLE_TESTS = PROJECT_ROOT / "results" / "executable_tests.v1.jsonl"

CURATED_DIR = PROJECT_ROOT / "results" / "curated"
CURATED_FINAL_PAIRS = CURATED_DIR / "final_pairs.curated.v1.jsonl"
CURATED_OUT_JSONL = CURATED_DIR / "reference_solution_validation.curated.v1.jsonl"
CURATED_OUT_CSV = CURATED_DIR / "reference_solution_validation.curated.v1.csv"
CURATED_OUT_MANIFEST = CURATED_DIR / "reference_solution_validation_manifest.curated.v1.json"
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


def validate_payload(
    payload: dict[str, Any],
    *,
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
        "solution_present": bool(str(payload.get("solution", "") or "").strip()),
        "required_packages_satisfied": packages_ok,
        "missing_packages": "|".join(missing_packages),
        "solution_format": assembled["solution_format"],
        "assembly_status": assembled["assembly_status"],
        "assembly_strategy": assembled["assembly_strategy"],
        "assembly_message": assembled["assembly_message"],
        "syntax_parse_ok": False,
        "compile_ok": False,
        "exec_ok": False,
        "timed_out": False,
        "runtime_error_type": "",
        "runtime_error_message": "",
        "timeout_seconds": timeout_seconds,
        "max_memory_bytes": max_memory_bytes,
        "reference_solution_status": "",
        "solution_overlay_hit": solution_overlay_hit,
        "tests_overlay_hit": tests_overlay_hit,
    }

    if assembled["assembly_status"] != "ok":
        row["reference_solution_status"] = assembled["assembly_status"]
        return row

    syntax_result = validate_code_artifact(assembled["assembled_code"])
    row["syntax_parse_ok"] = syntax_result["syntax_parse_ok"]
    row["compile_ok"] = syntax_result["compile_ok"]

    if not row["syntax_parse_ok"]:
        row["runtime_error_type"] = syntax_result["syntax_error_type"]
        row["runtime_error_message"] = syntax_result["syntax_error_message"]
        row["reference_solution_status"] = "parse_error"
        return row
    if not row["compile_ok"]:
        row["runtime_error_type"] = syntax_result["syntax_error_type"]
        row["runtime_error_message"] = syntax_result["syntax_error_message"]
        row["reference_solution_status"] = "compile_error"
        return row
    if not packages_ok:
        row["reference_solution_status"] = "missing_packages"
        return row

    run_result = run_subprocess_code(assembled["assembled_code"], timeout_seconds, max_memory_bytes=max_memory_bytes)
    row["timed_out"] = run_result["timed_out"]
    if run_result["timed_out"]:
        row["reference_solution_status"] = "timeout"
        return row

    row["exec_ok"] = run_result["returncode"] == 0
    if row["exec_ok"]:
        row["reference_solution_status"] = "exec_ok"
    else:
        row["runtime_error_type"] = "RuntimeError"
        row["runtime_error_message"] = (run_result["stderr"] or run_result["stdout"]).strip()[-1000:]
        row["reference_solution_status"] = "runtime_error"
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate reference and AI solutions for executability.")
    parser.add_argument("--pairs-jsonl", default=str(FINAL_PAIRS))
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
        args.output_jsonl = str(CURATED_OUT_JSONL)
        args.output_csv = str(CURATED_OUT_CSV)
        args.manifest_output = str(CURATED_OUT_MANIFEST)
        args.reference_solutions_jsonl = str(CURATED_REFERENCE_SOLUTIONS)
        args.executable_tests_jsonl = str(CURATED_EXECUTABLE_TESTS)

    pair_rows = read_jsonl_rows(Path(args.pairs_jsonl))
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
            validate_payload(
                ref_payload,
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
            validate_payload(
                ai_payload,
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
        "status_counts": {},
        "solution_present_counts": {
            "present": sum(1 for row in output_rows if row["solution_present"]),
            "missing": sum(1 for row in output_rows if not row["solution_present"]),
        },
        "overlay_coverage": {
            "solution_overlay_hits": sum(1 for row in output_rows if row["solution_overlay_hit"]),
            "tests_overlay_hits": sum(1 for row in output_rows if row["tests_overlay_hit"]),
        },
    }
    status_counts: dict[str, int] = {}
    for row in output_rows:
        status = row["reference_solution_status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    manifest["status_counts"] = status_counts

    write_jsonl_rows(output_rows, Path(args.output_jsonl))
    write_csv_rows(output_rows, Path(args.output_csv))
    write_json_doc(manifest, Path(args.manifest_output))

    print(f"Wrote {len(output_rows)} validation rows -> {args.output_jsonl}")
    print(f"Wrote validation CSV -> {args.output_csv}")
    print(f"Wrote validation manifest -> {args.manifest_output}")


if __name__ == "__main__":
    main()

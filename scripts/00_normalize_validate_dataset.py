from __future__ import annotations

import argparse
import ast
import csv
import json
import re
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_DATASET = PROJECT_ROOT / "data" / "frozen" / "expert_exercises.main_frozen.v1.json"
OUTPUT_JSONL = PROJECT_ROOT / "data" / "processed" / "exercises.normalized.v1.jsonl"
REPORT_CSV = PROJECT_ROOT / "data" / "processed" / "data_validation_report.v1.csv"
SUMMARY_CSV = PROJECT_ROOT / "data" / "processed" / "data_validation_summary.v1.csv"

TOPIC_NORMALIZATION = {
    "cnn": "CNN",
    "rnn": "RNN",
    "transformer": "Transformer",
    "optimization": "Optimization",
}

DIFFICULTY_NORMALIZATION = {
    "basic": "beginner",
    "easy": "beginner",
    "beginner": "beginner",
    "beginner-intermediate": "beginner-intermediate",
    "intermediate": "intermediate",
    "mid": "intermediate",
    "intermediate-advanced": "intermediate-advanced",
    "advanced": "advanced",
    "hard": "advanced",
}

EXERCISE_TYPE_NORMALIZATION = {
    "code completion": "code completion",
    "concept-to-code": "concept-to-code",
    "model building": "model building",
    "model revision": "model revision",
    "training-analysis": "training-analysis",
    "model_implementation": "model building",
    "debugging": "model revision",
}

REQUIRED_FIELDS = [
    "exercise_id",
    "title",
    "topic",
    "difficulty",
    "exercise_type",
    "instruction_text",
]

LIST_FIELDS = [
    "constraints",
    "test_cases",
    "public_tests_py",
    "hidden_tests_py",
    "surface_checks",
    "required_packages",
    "learning_objectives",
    "prerequisite_concepts",
    "keywords",
]

TEXT_FIELDS = [
    "title",
    "instruction_text",
    "starter_code",
    "expected_output",
    "solution",
    "evaluation_mode",
    "entry_point",
    "solution_format",
    "todo_start_marker",
    "todo_end_marker",
    "setup_code",
    "reference_solution_authority",
]

MOJIBAKE_PATTERNS = [
    "Ã",
    "Â",
    "ðŸ",
    "ï¿½",
    "璇",
    "浠",
    "闂",
    "锟",
]


def load_dataset(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


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


def normalize_value(value: str, mapping: dict[str, str]) -> str:
    key = str(value or "").strip().lower()
    return mapping.get(key, str(value or "").strip())


def ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item)
    normalized["topic"] = normalize_value(item.get("topic", ""), TOPIC_NORMALIZATION)
    normalized["difficulty"] = normalize_value(item.get("difficulty", ""), DIFFICULTY_NORMALIZATION)
    normalized["exercise_type"] = normalize_value(item.get("exercise_type", ""), EXERCISE_TYPE_NORMALIZATION)
    normalized["starter_code"] = str(item.get("starter_code", "") or "")
    normalized["expected_output"] = str(item.get("expected_output", "") or "")
    normalized["solution"] = str(item.get("solution", "") or "")
    normalized["evaluation_mode"] = str(item.get("evaluation_mode", "") or "")
    normalized["entry_point"] = str(item.get("entry_point", "") or "")
    normalized["solution_format"] = str(item.get("solution_format", "") or "")
    normalized["todo_start_marker"] = str(item.get("todo_start_marker", "") or "")
    normalized["todo_end_marker"] = str(item.get("todo_end_marker", "") or "")
    normalized["setup_code"] = str(item.get("setup_code", "") or "")
    normalized["reference_solution_authority"] = str(item.get("reference_solution_authority", "") or "")
    normalized["has_code"] = bool(item.get("has_code", bool(normalized["starter_code"].strip())))
    for field in LIST_FIELDS:
        normalized[field] = ensure_list(item.get(field, []))

    estimated_time = item.get("estimated_time_minutes")
    if estimated_time in {"", None}:
        normalized["estimated_time_minutes"] = None
    else:
        try:
            normalized["estimated_time_minutes"] = int(estimated_time)
        except (TypeError, ValueError):
            normalized["estimated_time_minutes"] = estimated_time
    return normalized


def detect_text_issues(text: str) -> list[str]:
    issues: list[str] = []
    if not isinstance(text, str) or not text:
        return issues

    if "\ufffd" in text:
        issues.append("replacement_char")

    if any(ord(char) < 32 and char not in "\n\r\t" for char in text):
        issues.append("control_char")

    for marker in MOJIBAKE_PATTERNS:
        if marker in text:
            issues.append("mojibake_pattern")
            break

    return sorted(set(issues))


def add_finding(
    findings: list[dict[str, Any]],
    exercise_id: str,
    check_name: str,
    status: str,
    details: str,
    field: str = "",
) -> None:
    findings.append(
        {
            "exercise_id": exercise_id,
            "field": field,
            "check_name": check_name,
            "status": status,
            "details": details,
        }
    )


def validate_item(item: dict[str, Any], seen_keys: set[str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    exercise_id = str(item.get("exercise_id", "") or "")

    for field in REQUIRED_FIELDS:
        if not str(item.get(field, "")).strip():
            add_finding(findings, exercise_id, "required_field", "fail", "missing required value", field)

    for field in TEXT_FIELDS:
        value = str(item.get(field, "") or "")
        issues = detect_text_issues(value)
        if not issues:
            continue
        for issue in issues:
            add_finding(findings, exercise_id, "text_quality", "fail", issue, field)

    for field in LIST_FIELDS:
        if not isinstance(item.get(field), list):
            add_finding(findings, exercise_id, "field_type", "fail", "expected list", field)
        else:
            add_finding(findings, exercise_id, "field_type", "pass", "list", field)

    estimated_time = item.get("estimated_time_minutes")
    if estimated_time is not None and not isinstance(estimated_time, int):
        add_finding(
            findings,
            exercise_id,
            "field_type",
            "fail",
            f"expected int or None, got {type(estimated_time).__name__}",
            "estimated_time_minutes",
        )
    else:
        add_finding(findings, exercise_id, "field_type", "pass", "int_or_none", "estimated_time_minutes")

    title = str(item.get("title", "")).strip().lower()
    instruction = str(item.get("instruction_text", "")).strip().lower()
    if title and instruction.startswith(title):
        add_finding(
            findings,
            exercise_id,
            "title_instruction_separation",
            "warn",
            "instruction_text starts with title",
        )
    else:
        add_finding(findings, exercise_id, "title_instruction_separation", "pass", "separated")

    starter_code = str(item.get("starter_code", "") or "").strip()
    if starter_code:
        try:
            ast.parse(starter_code)
            add_finding(findings, exercise_id, "starter_code_parse", "pass", "ok", "starter_code")
        except SyntaxError as exc:
            add_finding(findings, exercise_id, "starter_code_parse", "fail", str(exc), "starter_code")
    else:
        add_finding(findings, exercise_id, "starter_code_parse", "warn", "empty starter_code", "starter_code")

    dedupe_key = f"{title}||{instruction}"
    if dedupe_key in seen_keys:
        add_finding(findings, exercise_id, "duplicate_check", "fail", "duplicate title+instruction")
    else:
        seen_keys.add(dedupe_key)
        add_finding(findings, exercise_id, "duplicate_check", "pass", "unique title+instruction")

    return findings


def build_summary_rows(report_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: dict[tuple[str, str], int] = {}
    for row in report_rows:
        key = (row["check_name"], row["status"])
        summary[key] = summary.get(key, 0) + 1

    return [
        {"check_name": check_name, "status": status, "count": count}
        for (check_name, status), count in sorted(summary.items())
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(INPUT_DATASET))
    parser.add_argument("--output-jsonl", default=str(OUTPUT_JSONL))
    parser.add_argument("--report-csv", default=str(REPORT_CSV))
    parser.add_argument("--summary-csv", default=str(SUMMARY_CSV))
    args = parser.parse_args()

    dataset = load_dataset(Path(args.input))
    items = dataset.get("items", [])

    normalized_items: list[dict[str, Any]] = []
    report_rows: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for item in items:
        normalized = normalize_item(item)
        normalized_items.append(normalized)
        report_rows.extend(validate_item(normalized, seen_keys))

    summary_rows = build_summary_rows(report_rows)

    write_jsonl(normalized_items, Path(args.output_jsonl))
    write_csv(report_rows, Path(args.report_csv))
    write_csv(summary_rows, Path(args.summary_csv))

    print(f"Wrote {len(normalized_items)} normalized exercises -> {args.output_jsonl}")
    print(f"Wrote validation report -> {args.report_csv}")
    print(f"Wrote validation summary -> {args.summary_csv}")


if __name__ == "__main__":
    main()

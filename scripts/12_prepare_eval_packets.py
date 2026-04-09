from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import shutil
from typing import Any

from _shared_io import read_csv_rows, read_jsonl_rows, write_csv_rows
from survey.human_eval_paths import build_human_eval_paths

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CURATED_DIR = PROJECT_ROOT / "results" / "curated"
HUMAN_EVAL_PATHS = build_human_eval_paths(PROJECT_ROOT)

DEFAULT_BLIND_MAPPING = CURATED_DIR / "blind_mapping.curated.v1.csv"
DEFAULT_EXERCISES_ALL = CURATED_DIR / "exercises_all.curated.v1.jsonl"
DEFAULT_FINAL_PAIRS = CURATED_DIR / "final_pairs.curated.v1.jsonl"
DEFAULT_OUTPUT_DIR = HUMAN_EVAL_PATHS.human_eval_packets_dir

EXPERT_RATING_COLUMNS = [
    "instruction_clarity",
    "information_completeness",
    "content_accuracy",
    "structure_completeness",
    "difficulty_appropriateness",
    "pedagogical_effectiveness",
    "course_suitability",
    "practical_value",
    "code_quality",
    "overall_score",
    "needs_improvement",
    "issue_flags",
]

STUDENT_RATING_COLUMNS = [
    "goal_orientation",
    "support_sufficiency",
    "course_relevance",
    "learning_helpfulness",
    "intrinsic_load",
    "extraneous_load",
    "active_engagement",
    "mental_effort",
]

EXPERT_BATCH_COLUMNS = [
    "evaluator_id",
    "consent",
    "current_role",
    "teaching_related_experience",
    "teaching_experience_years",
    "framework_familiarity",
    "exercise_review_frequency",
    "attention_check_1",
    "overall_batch_quality",
    "important_features_top3",
    "questionnaire_suggestions",
    "rating_time_seconds",
]

STUDENT_BATCH_COLUMNS = [
    "student_id",
    "consent",
    "study_stage",
    "learning_background",
    "python_familiarity",
    "dl_framework_familiarity",
    "has_taken_dl_course",
    "familiar_topics",
    "tam_usefulness",
    "tam_ease_of_use",
    "tam_behavioral_intention",
    "overall_batch_quality",
    "questionnaire_suggestions",
    "rating_time_seconds",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build blind evaluation packets for curated expert/student human review."
    )
    parser.add_argument("--blind-mapping", type=Path, default=DEFAULT_BLIND_MAPPING)
    parser.add_argument("--exercises-all", type=Path, default=DEFAULT_EXERCISES_ALL)
    parser.add_argument("--final-pairs", type=Path, default=DEFAULT_FINAL_PAIRS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-missing-format-fields", type=int, default=1)
    parser.add_argument("--include-sparse", action="store_true")
    parser.add_argument("--expert-package-size", type=int, default=12)
    parser.add_argument("--student-package-size", type=int, default=6)
    parser.add_argument("--random-seed", type=int, default=42)
    return parser.parse_args()


def write_json(doc: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def format_list(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, list):
        return "\n".join(f"- {item}" for item in value if str(item).strip())
    return str(value)


def format_test_cases(value: Any) -> str:
    if not value:
        return ""
    if not isinstance(value, list):
        return str(value)

    chunks: list[str] = []
    for index, item in enumerate(value, start=1):
        if isinstance(item, dict):
            description = str(item.get("description", "")).strip()
            input_text = str(item.get("input", "")).strip()
            expected_output = str(item.get("expected_output", "")).strip()
            notes = str(item.get("notes", "")).strip()
            lines = [f"Test {index}"]
            if description:
                lines.append(f"Description: {description}")
            if input_text:
                lines.append(f"Input: {input_text}")
            if expected_output:
                lines.append(f"Expected: {expected_output}")
            if notes:
                lines.append(f"Notes: {notes}")
            chunks.append("\n".join(lines))
        else:
            chunks.append(f"Test {index}\n{item}")
    return "\n\n".join(chunks)


def build_visible_packet_row(
    mapping_row: dict[str, Any],
    exercise_row: dict[str, Any],
) -> dict[str, Any]:
    return {
        "blind_exercise_id": mapping_row.get("blind_exercise_id", ""),
        "title": exercise_row.get("title", ""),
        "topic": mapping_row.get("topic", "") or exercise_row.get("topic", ""),
        "difficulty": mapping_row.get("difficulty", "") or exercise_row.get("difficulty", ""),
        "exercise_type": mapping_row.get("exercise_type", "") or exercise_row.get("exercise_type", ""),
        "instruction_text": exercise_row.get("instruction_text", ""),
        "starter_code": exercise_row.get("starter_code", ""),
        "expected_output": exercise_row.get("expected_output", ""),
        "constraints_text": format_list(exercise_row.get("constraints", [])),
        "test_cases_text": format_test_cases(exercise_row.get("test_cases", [])),
        "programming_language": exercise_row.get("programming_language", ""),
        "framework": exercise_row.get("framework", ""),
        "estimated_time_minutes": exercise_row.get("estimated_time_minutes", ""),
        "target_learner_level": exercise_row.get("target_learner_level", ""),
        "notes_for_evaluator": "",
        "dataset_split": "formal",
    }


def build_expert_packet_row(base_row: dict[str, Any]) -> dict[str, Any]:
    row = dict(base_row)
    row["rating_id"] = ""
    row["evaluator_id"] = ""
    for column in EXPERT_RATING_COLUMNS:
        row[column] = ""
    row["notes"] = ""
    return row


def build_student_packet_row(base_row: dict[str, Any]) -> dict[str, Any]:
    row = dict(base_row)
    row["rating_id"] = ""
    row["student_id"] = ""
    for column in STUDENT_RATING_COLUMNS:
        row[column] = ""
    row["notes"] = ""
    return row


def build_batch_template(fieldnames: list[str]) -> list[dict[str, Any]]:
    return [{field: "" for field in fieldnames}]


def is_blank_text(value: Any) -> bool:
    return not str(value or "").strip()


def compute_format_audit(exercise_row: dict[str, Any]) -> dict[str, Any]:
    missing_starter_code = is_blank_text(exercise_row.get("starter_code"))
    missing_expected_output = is_blank_text(exercise_row.get("expected_output"))
    missing_constraints = not bool(exercise_row.get("constraints"))
    missing_test_cases = not bool(exercise_row.get("test_cases"))
    missing_count = sum(
        [
            missing_starter_code,
            missing_expected_output,
            missing_constraints,
            missing_test_cases,
        ]
    )
    return {
        "missing_starter_code": missing_starter_code,
        "missing_expected_output": missing_expected_output,
        "missing_constraints": missing_constraints,
        "missing_test_cases": missing_test_cases,
        "missing_format_field_count": missing_count,
    }


def build_fairness_audit_rows(
    pair_rows: list[dict[str, Any]],
    exercise_index: dict[str, dict[str, Any]],
    max_missing_format_fields: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pair_row in pair_rows:
        reference_id = pair_row.get("reference_exercise_id", "")
        ai_id = pair_row.get("ai_exercise_id", "")
        ref_ex = exercise_index.get(reference_id, {})
        ai_ex = exercise_index.get(ai_id, {})
        ref_audit = compute_format_audit(ref_ex)
        ai_audit = compute_format_audit(ai_ex)
        pair_eligible = (
            ref_audit["missing_format_field_count"] <= max_missing_format_fields
            and ai_audit["missing_format_field_count"] <= max_missing_format_fields
        )
        rows.append(
            {
                "pair_id": pair_row.get("pair_id", ""),
                "reference_exercise_id": reference_id,
                "ai_exercise_id": ai_id,
                "topic": pair_row.get("topic", ""),
                "difficulty": pair_row.get("difficulty", ""),
                "exercise_type": pair_row.get("generation_exercise_type", ""),
                "reference_missing_format_field_count": ref_audit["missing_format_field_count"],
                "ai_missing_format_field_count": ai_audit["missing_format_field_count"],
                "reference_missing_starter_code": ref_audit["missing_starter_code"],
                "reference_missing_expected_output": ref_audit["missing_expected_output"],
                "reference_missing_constraints": ref_audit["missing_constraints"],
                "reference_missing_test_cases": ref_audit["missing_test_cases"],
                "ai_missing_starter_code": ai_audit["missing_starter_code"],
                "ai_missing_expected_output": ai_audit["missing_expected_output"],
                "ai_missing_constraints": ai_audit["missing_constraints"],
                "ai_missing_test_cases": ai_audit["missing_test_cases"],
                "human_eval_eligible": pair_eligible,
                "exclude_reason": (
                    "pair_has_sparse_format_fields"
                    if not pair_eligible
                    else ""
                ),
            }
        )
    return rows


def build_source_balance_rows(
    mapping_rows: list[dict[str, Any]],
    eligible_exercise_ids: set[str],
) -> list[dict[str, Any]]:
    summary: dict[tuple[str, str], int] = {}
    for row in mapping_rows:
        if row.get("exercise_id", "") not in eligible_exercise_ids:
            continue
        key = (row.get("source_type", ""), row.get("topic", ""))
        summary[key] = summary.get(key, 0) + 1
    return [
        {"source_type": source_type, "topic": topic, "exercise_count": count}
        for (source_type, topic), count in sorted(summary.items())
    ]


def interleave_pairs_by_topic(pair_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in pair_rows:
        grouped.setdefault(row.get("topic", "UNKNOWN"), []).append(row)

    ordered_topics = sorted(grouped)
    output: list[dict[str, Any]] = []
    still_has_rows = True
    while still_has_rows:
        still_has_rows = False
        for topic in ordered_topics:
            topic_rows = grouped[topic]
            if topic_rows:
                output.append(topic_rows.pop(0))
                still_has_rows = True
    return output


def chunk_rows(rows: list[dict[str, Any]], chunk_size: int) -> list[list[dict[str, Any]]]:
    if chunk_size <= 0:
        return [rows]
    return [rows[index : index + chunk_size] for index in range(0, len(rows), chunk_size)]


def build_package_rows(
    pair_rows: list[dict[str, Any]],
    mapping_index: dict[str, dict[str, Any]],
    exercise_index: dict[str, dict[str, Any]],
    packet_builder,
    package_prefix: str,
    package_size: int,
) -> list[tuple[str, list[dict[str, Any]]]]:
    ordered_pairs = interleave_pairs_by_topic(pair_rows)
    packages: list[tuple[str, list[dict[str, Any]]]] = []
    pair_chunks = chunk_rows(ordered_pairs, max(1, package_size // 2))
    for package_index, pair_chunk in enumerate(pair_chunks, start=1):
        package_id = f"{package_prefix}{package_index:02d}"
        package_rows: list[dict[str, Any]] = []
        display_order = 1
        for pair_row in pair_chunk:
            for exercise_id in [pair_row.get("reference_exercise_id", ""), pair_row.get("ai_exercise_id", "")]:
                mapping_row = mapping_index.get(exercise_id, {})
                exercise_row = exercise_index.get(exercise_id, {})
                visible_row = build_visible_packet_row(mapping_row, exercise_row)
                packet_row = packet_builder(visible_row)
                packet_row["package_id"] = package_id
                packet_row["display_order"] = display_order
                display_order += 1
                package_rows.append(packet_row)
        packages.append((package_id, package_rows))
    return packages


def assign_student_row_to_package(
    package_states: list[dict[str, Any]],
    row: dict[str, Any],
    package_size: int,
) -> int:
    pair_id = row.get("_pair_id", "")
    topic = row.get("topic", "")
    exercise_type = row.get("exercise_type", "")
    source_type = row.get("_source_type", "")
    candidates: list[tuple[tuple[int, int, int], int]] = []

    for index, state in enumerate(package_states):
        if package_size > 0 and len(state["rows"]) >= package_size:
            continue
        if pair_id and pair_id in state["pair_ids"]:
            continue
        score = (
            len(state["rows"]),
            state["topic_exercise_type_counts"].get((topic, exercise_type), 0),
            state["topic_counts"].get(topic, 0),
            state["source_counts"].get(source_type, 0),
        )
        candidates.append((score, index))

    if not candidates:
        for index, state in enumerate(package_states):
            if pair_id and pair_id in state["pair_ids"]:
                continue
            score = (
                len(state["rows"]),
                state["topic_exercise_type_counts"].get((topic, exercise_type), 0),
                state["topic_counts"].get(topic, 0),
                state["source_counts"].get(source_type, 0),
            )
            candidates.append((score, index))

    if not candidates:
        raise RuntimeError("Unable to assign student exercise row to a package without pair collision.")

    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def build_student_package_rows(
    pair_rows: list[dict[str, Any]],
    mapping_index: dict[str, dict[str, Any]],
    exercise_index: dict[str, dict[str, Any]],
    packet_builder,
    package_prefix: str,
    package_size: int,
) -> list[tuple[str, list[dict[str, Any]], int]]:
    ordered_pairs = interleave_pairs_by_topic(pair_rows)
    total_exercises = len(ordered_pairs) * 2
    topic_exercise_type_counts: dict[tuple[str, str], int] = {}
    for pair_row in ordered_pairs:
        for exercise_id in [pair_row.get("reference_exercise_id", ""), pair_row.get("ai_exercise_id", "")]:
            mapping_row = mapping_index.get(exercise_id, {})
            combo_key = (
                mapping_row.get("topic", "") or exercise_index.get(exercise_id, {}).get("topic", ""),
                mapping_row.get("exercise_type", "") or exercise_index.get(exercise_id, {}).get("exercise_type", ""),
            )
            topic_exercise_type_counts[combo_key] = topic_exercise_type_counts.get(combo_key, 0) + 1

    min_packages = 2 if ordered_pairs else 1
    max_combo_frequency = max(topic_exercise_type_counts.values(), default=1)
    num_packages = max(
        min_packages,
        math.ceil(total_exercises / max(1, package_size)),
        max_combo_frequency,
    )

    package_states: list[dict[str, Any]] = []
    for package_index in range(1, num_packages + 1):
        package_states.append(
            {
                "package_id": f"{package_prefix}{package_index:02d}",
                "rows": [],
                "pair_ids": set(),
                "topic_counts": {},
                "topic_exercise_type_counts": {},
                "source_counts": {},
            }
        )

    for pair_row in ordered_pairs:
        pair_id = pair_row.get("pair_id", "")
        candidate_rows: list[dict[str, Any]] = []
        for exercise_id in [pair_row.get("reference_exercise_id", ""), pair_row.get("ai_exercise_id", "")]:
            mapping_row = mapping_index.get(exercise_id, {})
            exercise_row = exercise_index.get(exercise_id, {})
            visible_row = build_visible_packet_row(mapping_row, exercise_row)
            packet_row = packet_builder(visible_row)
            packet_row["_pair_id"] = pair_id
            packet_row["_source_type"] = mapping_row.get("source_type", "")
            candidate_rows.append(packet_row)

        for packet_row in sorted(candidate_rows, key=lambda row: row.get("_source_type", "")):
            package_index = assign_student_row_to_package(package_states, packet_row, package_size)
            package_state = package_states[package_index]
            packet_row["package_id"] = package_state["package_id"]
            package_state["rows"].append(packet_row)
            package_state["pair_ids"].add(pair_id)
            topic = packet_row.get("topic", "")
            exercise_type = packet_row.get("exercise_type", "")
            source_type = packet_row.get("_source_type", "")
            package_state["topic_counts"][topic] = package_state["topic_counts"].get(topic, 0) + 1
            topic_ex_type_key = (topic, exercise_type)
            package_state["topic_exercise_type_counts"][topic_ex_type_key] = (
                package_state["topic_exercise_type_counts"].get(topic_ex_type_key, 0) + 1
            )
            package_state["source_counts"][source_type] = package_state["source_counts"].get(source_type, 0) + 1

    packages: list[tuple[str, list[dict[str, Any]], int]] = []
    for state in package_states:
        rows = state["rows"]
        rows.sort(key=lambda row: (row.get("topic", ""), row.get("blind_exercise_id", "")))
        for display_order, row in enumerate(rows, start=1):
            row["display_order"] = display_order
            row.pop("_pair_id", None)
            row.pop("_source_type", None)
        packages.append((state["package_id"], rows, len(state["pair_ids"])))
    return packages


def main() -> None:
    args = parse_args()

    mapping_rows = read_csv_rows(args.blind_mapping)
    exercise_rows = read_jsonl_rows(args.exercises_all)
    pair_rows = read_jsonl_rows(args.final_pairs)
    exercise_index = {row.get("exercise_id", ""): row for row in exercise_rows}
    mapping_index = {row.get("exercise_id", ""): row for row in mapping_rows}

    fairness_audit_rows = build_fairness_audit_rows(
        pair_rows,
        exercise_index,
        args.max_missing_format_fields,
    )
    eligible_pair_rows = [
        pair_row
        for pair_row in pair_rows
        if args.include_sparse
        or next(
            (
                audit_row["human_eval_eligible"]
                for audit_row in fairness_audit_rows
                if audit_row["pair_id"] == pair_row.get("pair_id", "")
            ),
            False,
        )
    ]
    eligible_exercise_ids = {
        exercise_id
        for pair_row in eligible_pair_rows
        for exercise_id in [pair_row.get("reference_exercise_id", ""), pair_row.get("ai_exercise_id", "")]
        if exercise_id
    }

    expert_packet_rows: list[dict[str, Any]] = []
    student_packet_rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []

    for mapping_row in mapping_rows:
        exercise_id = mapping_row.get("exercise_id", "")
        if exercise_id not in eligible_exercise_ids:
            continue
        exercise_row = exercise_index.get(exercise_id)
        if not exercise_row:
            missing_rows.append(
                {
                    "blind_exercise_id": mapping_row.get("blind_exercise_id", ""),
                    "exercise_id": exercise_id,
                    "issue": "exercise_not_found_in_exercises_all",
                }
            )
            continue

        visible_row = build_visible_packet_row(mapping_row, exercise_row)
        expert_packet_rows.append(build_expert_packet_row(visible_row))
        student_packet_rows.append(build_student_packet_row(visible_row))

    output_dir = args.output_dir
    packets_dir = output_dir / "packets"
    templates_dir = output_dir / "templates"
    audit_dir = output_dir / "audit"
    audit_build_dir = audit_dir / "build"
    audit_quality_dir = audit_dir / "quality"
    write_csv_rows(expert_packet_rows, packets_dir / "expert_eval_packet.curated.v1.csv")
    write_csv_rows(student_packet_rows, packets_dir / "student_eval_packet.curated.v1.csv")
    write_csv_rows(
        build_batch_template(EXPERT_BATCH_COLUMNS),
        templates_dir / "expert_batch_template.curated.v1.csv",
    )
    write_csv_rows(
        build_batch_template(STUDENT_BATCH_COLUMNS),
        templates_dir / "student_batch_template.curated.v1.csv",
    )
    write_csv_rows(missing_rows, audit_build_dir / "eval_packet_build_issues.v1.csv")
    write_csv_rows(
        fairness_audit_rows,
        audit_quality_dir / "human_eval_fairness_audit.curated.v1.csv",
    )
    write_csv_rows(
        build_source_balance_rows(mapping_rows, eligible_exercise_ids),
        audit_quality_dir / "human_eval_source_balance.curated.v1.csv",
    )

    expert_packages = build_package_rows(
        eligible_pair_rows,
        mapping_index,
        exercise_index,
        build_expert_packet_row,
        package_prefix="EXPERT-P",
        package_size=args.expert_package_size,
    )
    student_packages = build_student_package_rows(
        eligible_pair_rows,
        mapping_index,
        exercise_index,
        build_student_packet_row,
        package_prefix="STUDENT-P",
        package_size=args.student_package_size,
    )

    shutil.rmtree(packets_dir / "expert_packages", ignore_errors=True)
    shutil.rmtree(packets_dir / "student_packages", ignore_errors=True)

    expert_package_manifest_rows: list[dict[str, Any]] = []
    for package_id, rows in expert_packages:
        package_dir = packets_dir / "expert_packages" / package_id
        write_csv_rows(rows, package_dir / "expert_eval_packet.curated.v1.csv")
        expert_package_manifest_rows.append(
            {"package_id": package_id, "exercise_count": len(rows), "pair_count": len(rows) // 2}
        )
    student_package_manifest_rows: list[dict[str, Any]] = []
    for package_id, rows, pair_count in student_packages:
        package_dir = packets_dir / "student_packages" / package_id
        write_csv_rows(rows, package_dir / "student_eval_packet.curated.v1.csv")
        student_package_manifest_rows.append(
            {"package_id": package_id, "exercise_count": len(rows), "pair_count": pair_count}
        )

    write_csv_rows(
        expert_package_manifest_rows,
        packets_dir / "expert_package_manifest.curated.v1.csv",
    )
    write_csv_rows(
        student_package_manifest_rows,
        packets_dir / "student_package_manifest.curated.v1.csv",
    )

    manifest = {
        "blind_mapping": str(args.blind_mapping),
        "exercises_all": str(args.exercises_all),
        "final_pairs": str(args.final_pairs),
        "expert_packet_rows": len(expert_packet_rows),
        "student_packet_rows": len(student_packet_rows),
        "missing_row_count": len(missing_rows),
        "eligible_pair_count": len(eligible_pair_rows),
        "eligible_exercise_count": len(eligible_exercise_ids),
        "include_sparse": args.include_sparse,
        "max_missing_format_fields": args.max_missing_format_fields,
        "expert_package_size": args.expert_package_size,
        "student_package_size": args.student_package_size,
        "outputs": {
            "expert_eval_packet": str(packets_dir / "expert_eval_packet.curated.v1.csv"),
            "student_eval_packet": str(packets_dir / "student_eval_packet.curated.v1.csv"),
            "expert_batch_template": str(
                templates_dir / "expert_batch_template.curated.v1.csv"
            ),
            "student_batch_template": str(
                templates_dir / "student_batch_template.curated.v1.csv"
            ),
            "fairness_audit": str(
                audit_quality_dir / "human_eval_fairness_audit.curated.v1.csv"
            ),
            "source_balance": str(
                audit_quality_dir / "human_eval_source_balance.curated.v1.csv"
            ),
            "expert_package_manifest": str(
                packets_dir / "expert_package_manifest.curated.v1.csv"
            ),
            "student_package_manifest": str(
                packets_dir / "student_package_manifest.curated.v1.csv"
            ),
            "build_issues": str(audit_build_dir / "eval_packet_build_issues.v1.csv"),
        },
    }
    write_json(manifest, audit_build_dir / "eval_packet_manifest.v1.json")

    print(f"Wrote expert evaluation packet -> {packets_dir / 'expert_eval_packet.curated.v1.csv'}")
    print(f"Wrote student evaluation packet -> {packets_dir / 'student_eval_packet.curated.v1.csv'}")
    print(f"Wrote packet manifest -> {audit_build_dir / 'eval_packet_manifest.v1.json'}")


if __name__ == "__main__":
    main()

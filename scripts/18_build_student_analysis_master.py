from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from statistics import mean

from _shared_io import read_csv_rows, write_csv_rows

ITEM_SCORE_FIELDS = [
    "task_goal_clarity",
    "key_support",
    "course_relevance",
    "learning_help",
    "info_load",
    "search_effort",
    "active_engagement",
    "mental_effort",
]

POSITIVE_ITEM_FIELDS = [
    "task_goal_clarity",
    "key_support",
    "course_relevance",
    "learning_help",
    "active_engagement",
]

NEGATIVE_ITEM_FIELDS = [
    "info_load",
    "search_effort",
    "mental_effort",
]

USABILITY_FIELDS = [
    "task_goal_clarity",
    "key_support",
    "course_relevance",
    "learning_help",
]

COGNITIVE_LOAD_FIELDS = [
    "info_load",
    "search_effort",
    "mental_effort",
]

BATCH_SCORE_FIELDS = [
    "overall_usefulness",
    "overall_ease",
    "continued_use_intention",
    "overall_quality",
]

SELECTED_EXERCISE_METRICS = {
    "instruction_metrics.flesch_reading_ease": "auto_flesch_reading_ease",
    "instruction_metrics.flesch_kincaid_grade": "auto_flesch_kincaid_grade",
    "instruction_metrics.instruction_completeness_ratio": "auto_instruction_completeness_ratio",
    "instruction_metrics.technical_term_density_instruction": "auto_technical_term_density_instruction",
    "instruction_metrics.avg_sentence_length": "auto_avg_sentence_length",
    "structure_metrics.structure_completeness_ratio": "auto_structure_completeness_ratio",
    "structure_metrics.structure_score_weighted": "auto_structure_score_weighted",
    "code_quality_metrics.starter_code_mccabe_max": "auto_starter_code_mccabe_max",
    "code_quality_metrics.starter_code_mi": "auto_starter_code_mi",
}

SELECTED_PAIR_METRICS = {
    "pair_id": "pair_id",
    "tfidf_cosine_full_text": "pair_tfidf_cosine_full_text",
    "tfidf_cosine_instruction_only": "pair_tfidf_cosine_instruction_only",
    "bertscore_f1_instruction_only": "pair_bertscore_f1_instruction_only",
    "rougeL_f1_instruction_only": "pair_rougeL_f1_instruction_only",
    "meteor_instruction_only": "pair_meteor_instruction_only",
    "topic_coherence_score_ai": "pair_topic_coherence_score_ai",
    "topic_coherence_score_reference": "pair_topic_coherence_score_reference",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build cleaned student analysis master table.")
    parser.add_argument(
        "--participant-meta",
        type=Path,
        default=Path("results/student_subsets/participant_meta_30.csv"),
    )
    parser.add_argument(
        "--item-ratings",
        type=Path,
        default=Path("results/student_subsets/item_ratings_30.csv"),
    )
    parser.add_argument(
        "--batch-feedback",
        type=Path,
        default=Path("results/student_subsets/batch_feedback_30.csv"),
    )
    parser.add_argument(
        "--blind-mapping",
        type=Path,
        default=Path("results/curated/blind_mapping.curated.v1.csv"),
    )
    parser.add_argument(
        "--exercise-metrics",
        type=Path,
        default=Path("results/curated/exercise_metrics.curated.v1.csv"),
    )
    parser.add_argument(
        "--pair-metrics",
        type=Path,
        default=Path("results/curated/pair_similarity_metrics.curated.v1.csv"),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("results/student_subsets/student_analysis_master_30.csv"),
    )
    parser.add_argument(
        "--output-manifest",
        type=Path,
        default=Path("results/student_subsets/student_analysis_master_30.manifest.json"),
    )
    return parser.parse_args()


def normalize_bool(value: str) -> str:
    text = (value or "").strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return "True"
    if text in {"false", "0", "no", "n"}:
        return "False"
    return ""


def normalize_number(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    try:
        number = float(text)
    except ValueError:
        return text
    if number.is_integer():
        return str(int(number))
    return f"{number:.4f}".rstrip("0").rstrip(".")


def parse_iso_datetime(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    return datetime.fromisoformat(text)


def safe_mean(values: list[float]) -> str:
    if not values:
        return ""
    score = mean(values)
    return f"{score:.4f}".rstrip("0").rstrip(".")


def to_float(value: str) -> float | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def reverse_likert_5(value: str) -> float | None:
    numeric = to_float(value)
    if numeric is None:
        return None
    return 6.0 - numeric


def split_topics(text: str) -> list[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    return [part.strip() for part in raw.split(";") if part.strip()]


def to_float_list(row: dict[str, str], fields: list[str]) -> list[float]:
    values: list[float] = []
    for field in fields:
        text = (row.get(field) or "").strip()
        if not text:
            continue
        try:
            values.append(float(text))
        except ValueError:
            continue
    return values


def build_overall_item_scores(row: dict[str, str]) -> list[float]:
    values: list[float] = []
    for field in POSITIVE_ITEM_FIELDS:
        numeric = to_float(row.get(field, ""))
        if numeric is not None:
            values.append(numeric)
    for field in NEGATIVE_ITEM_FIELDS:
        numeric = reverse_likert_5(row.get(field, ""))
        if numeric is not None:
            values.append(numeric)
    return values


def build_meta_lookup(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for row in rows:
        participant_id = row["participant_id"]
        started_at = parse_iso_datetime(row.get("started_at", ""))
        submitted_at = parse_iso_datetime(row.get("submitted_at", ""))
        duration_seconds = ""
        if started_at and submitted_at:
            duration_seconds = normalize_number(str((submitted_at - started_at).total_seconds()))
        familiar_topics = split_topics(row.get("familiar_topics", ""))
        lookup[participant_id] = {
            "participant_id": participant_id,
            "package_id": row.get("package_id", ""),
            "consent": row.get("consent", ""),
            "study_stage": row.get("study_stage", ""),
            "programming_background": row.get("programming_background", ""),
            "python_familiarity": row.get("python_familiarity", ""),
            "framework_familiarity": row.get("framework_familiarity", ""),
            "dl_course_taken": row.get("dl_course_taken", ""),
            "familiar_topics": row.get("familiar_topics", ""),
            "familiar_topics_count": normalize_number(str(len(familiar_topics))),
            "started_at": row.get("started_at", ""),
            "submitted_at": row.get("submitted_at", ""),
            "response_duration_seconds": duration_seconds,
            "attention_check_score": normalize_number(row.get("attention_check_score", "")),
            "attention_check_passed": normalize_bool(row.get("attention_check_passed", "")),
        }
    return lookup


def build_batch_lookup(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for row in rows:
        participant_id = row["participant_id"]
        batch_values = to_float_list(row, BATCH_SCORE_FIELDS)
        lookup[participant_id] = {
            "overall_usefulness": normalize_number(row.get("overall_usefulness", "")),
            "overall_ease": normalize_number(row.get("overall_ease", "")),
            "continued_use_intention": normalize_number(row.get("continued_use_intention", "")),
            "overall_quality": normalize_number(row.get("overall_quality", "")),
            "batch_acceptance_mean": safe_mean(batch_values),
            "final_comment": row.get("final_comment", "").strip(),
            "final_comment_present": normalize_bool("true" if row.get("final_comment", "").strip() else "false"),
            "rating_time_seconds": normalize_number(row.get("rating_time_seconds", "")),
            "batch_saved_at": row.get("saved_at", ""),
        }
    return lookup


def build_blind_lookup(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["blind_exercise_id"]: row for row in rows}


def build_exercise_metrics_lookup(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for row in rows:
        exercise_id = row["exercise_id"]
        selected = {}
        for source_key, target_key in SELECTED_EXERCISE_METRICS.items():
            selected[target_key] = normalize_number(row.get(source_key, ""))
        lookup[exercise_id] = selected
    return lookup


def build_pair_metrics_lookup(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for row in rows:
        pair_id = normalize_number(row.get("pair_id", ""))
        ai_selected = {"pair_id": pair_id}
        for source_key, target_key in SELECTED_PAIR_METRICS.items():
            if source_key == "pair_id":
                continue
            ai_selected[target_key] = normalize_number(row.get(source_key, ""))
        ai_exercise_id = row.get("ai_exercise_id", "")
        reference_exercise_id = row.get("reference_exercise_id", "")
        if ai_exercise_id:
            lookup[ai_exercise_id] = ai_selected
        if reference_exercise_id:
            lookup[reference_exercise_id] = {"pair_id": pair_id}
    return lookup


def build_straightline_lookup(item_rows: list[dict[str, str]]) -> dict[str, str]:
    grouped: dict[str, list[str]] = {}
    for row in item_rows:
        participant_id = row["participant_id"]
        grouped.setdefault(participant_id, [])
        for field in ITEM_SCORE_FIELDS:
            value = (row.get(field) or "").strip()
            if value:
                grouped[participant_id].append(value)
    result: dict[str, str] = {}
    for participant_id, values in grouped.items():
        result[participant_id] = normalize_bool("true" if len(set(values)) == 1 and values else "false")
    return result


def build_master_rows(
    item_rows: list[dict[str, str]],
    meta_lookup: dict[str, dict[str, str]],
    batch_lookup: dict[str, dict[str, str]],
    blind_lookup: dict[str, dict[str, str]],
    exercise_metrics_lookup: dict[str, dict[str, str]],
    pair_metrics_lookup: dict[str, dict[str, str]],
    straightline_lookup: dict[str, str],
) -> list[dict[str, str]]:
    master_rows: list[dict[str, str]] = []
    for row in item_rows:
        participant_id = row["participant_id"]
        blind_exercise_id = row["blind_exercise_id"]
        meta = meta_lookup.get(participant_id, {})
        batch = batch_lookup.get(participant_id, {})
        blind = blind_lookup.get(blind_exercise_id, {})
        exercise_id = blind.get("exercise_id", "")
        exercise_metrics = exercise_metrics_lookup.get(exercise_id, {})
        pair_metrics = pair_metrics_lookup.get(exercise_id, {})

        item_scores = build_overall_item_scores(row)
        usability_scores = to_float_list(row, USABILITY_FIELDS)
        cognitive_load_scores = to_float_list(row, COGNITIVE_LOAD_FIELDS)

        master_row = {
            "participant_id": participant_id,
            "package_id": row.get("package_id", meta.get("package_id", "")),
            "blind_exercise_id": blind_exercise_id,
            "exercise_id": exercise_id,
            "source_type": blind.get("source_type", ""),
            "topic": blind.get("topic", ""),
            "difficulty": blind.get("difficulty", ""),
            "exercise_type": blind.get("exercise_type", ""),
            "item_order": normalize_number(row.get("item_order", "")),
            "task_goal_clarity": normalize_number(row.get("task_goal_clarity", "")),
            "key_support": normalize_number(row.get("key_support", "")),
            "course_relevance": normalize_number(row.get("course_relevance", "")),
            "learning_help": normalize_number(row.get("learning_help", "")),
            "info_load": normalize_number(row.get("info_load", "")),
            "search_effort": normalize_number(row.get("search_effort", "")),
            "active_engagement": normalize_number(row.get("active_engagement", "")),
            "mental_effort": normalize_number(row.get("mental_effort", "")),
            "item_mean_score": safe_mean(item_scores),
            "usability_mean_score": safe_mean(usability_scores),
            "cognitive_load_mean_score": safe_mean(cognitive_load_scores),
            "engagement_score": normalize_number(row.get("active_engagement", "")),
            "open_comment": row.get("open_comment", "").strip(),
            "open_comment_present": normalize_bool("true" if row.get("open_comment", "").strip() else "false"),
            "item_saved_at": row.get("saved_at", ""),
            "overall_usefulness": batch.get("overall_usefulness", ""),
            "overall_ease": batch.get("overall_ease", ""),
            "continued_use_intention": batch.get("continued_use_intention", ""),
            "overall_quality": batch.get("overall_quality", ""),
            "batch_acceptance_mean": batch.get("batch_acceptance_mean", ""),
            "final_comment": batch.get("final_comment", ""),
            "final_comment_present": batch.get("final_comment_present", ""),
            "rating_time_seconds": batch.get("rating_time_seconds", ""),
            "batch_saved_at": batch.get("batch_saved_at", ""),
            "consent": meta.get("consent", ""),
            "study_stage": meta.get("study_stage", ""),
            "programming_background": meta.get("programming_background", ""),
            "python_familiarity": meta.get("python_familiarity", ""),
            "framework_familiarity": meta.get("framework_familiarity", ""),
            "dl_course_taken": meta.get("dl_course_taken", ""),
            "familiar_topics": meta.get("familiar_topics", ""),
            "familiar_topics_count": meta.get("familiar_topics_count", ""),
            "started_at": meta.get("started_at", ""),
            "submitted_at": meta.get("submitted_at", ""),
            "response_duration_seconds": meta.get("response_duration_seconds", ""),
            "attention_check_score": meta.get("attention_check_score", ""),
            "attention_check_passed": meta.get("attention_check_passed", ""),
            "participant_straightline_flag": straightline_lookup.get(participant_id, ""),
            "participant_fast_flag_under_180s": normalize_bool(
                "true"
                if batch.get("rating_time_seconds", "")
                and float(batch["rating_time_seconds"]) < 180
                else "false"
            ),
        }
        master_row.update(exercise_metrics)
        master_row.update(pair_metrics)
        master_rows.append(master_row)
    return master_rows


def main() -> None:
    args = parse_args()
    meta_rows = read_csv_rows(args.participant_meta)
    item_rows = read_csv_rows(args.item_ratings)
    batch_rows = read_csv_rows(args.batch_feedback)
    blind_rows = read_csv_rows(args.blind_mapping)
    exercise_metric_rows = read_csv_rows(args.exercise_metrics)
    pair_metric_rows = read_csv_rows(args.pair_metrics)

    meta_lookup = build_meta_lookup(meta_rows)
    batch_lookup = build_batch_lookup(batch_rows)
    blind_lookup = build_blind_lookup(blind_rows)
    exercise_metrics_lookup = build_exercise_metrics_lookup(exercise_metric_rows)
    pair_metrics_lookup = build_pair_metrics_lookup(pair_metric_rows)
    straightline_lookup = build_straightline_lookup(item_rows)

    master_rows = build_master_rows(
        item_rows=item_rows,
        meta_lookup=meta_lookup,
        batch_lookup=batch_lookup,
        blind_lookup=blind_lookup,
        exercise_metrics_lookup=exercise_metrics_lookup,
        pair_metrics_lookup=pair_metrics_lookup,
        straightline_lookup=straightline_lookup,
    )
    write_csv_rows(master_rows, args.output_csv, encoding="utf-8-sig")

    manifest = {
        "participant_meta_rows": len(meta_rows),
        "item_rating_rows": len(item_rows),
        "batch_feedback_rows": len(batch_rows),
        "master_rows": len(master_rows),
        "unique_participants": len({row["participant_id"] for row in master_rows}),
        "unique_exercises": len({row["blind_exercise_id"] for row in master_rows}),
        "unique_packages": len({row["package_id"] for row in master_rows}),
        "item_mean_score_definition": {
            "positive_fields": POSITIVE_ITEM_FIELDS,
            "reverse_coded_fields": NEGATIVE_ITEM_FIELDS,
            "scale": "5-point Likert",
        },
        "pair_metric_attachment": {
            "pair_id_on_both_sources": True,
            "pair_similarity_metrics_on_ai_rows_only": True,
        },
        "output_csv": str(args.output_csv.resolve()),
    }
    args.output_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

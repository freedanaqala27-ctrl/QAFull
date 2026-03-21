from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CURATED_DIR = PROJECT_ROOT / "results" / "curated"
VALIDATION_REPORT_NAME = "merge_validation_report.v1.csv"

DEFAULT_AUTO_METRIC_SUMMARY_COLUMNS = [
    "instruction_metrics.flesch_reading_ease",
    "instruction_metrics.flesch_kincaid_grade",
    "instruction_metrics.instruction_completeness_ratio",
    "instruction_metrics.technical_term_density_instruction",
    "structure_metrics.structure_completeness_ratio",
    "structure_metrics.structure_score_weighted",
    "code_quality_metrics.mccabe_complexity",
    "code_quality_metrics.maintainability_index",
    "code_quality_metrics.ruff_error_count",
    "code_quality_metrics.pylint_warning_count",
]

DIMENSION_MAPPING = {
    "instruction_clarity": "instruction_clarity",
    "information_completeness": "information_completeness",
    "content_accuracy": "content_accuracy",
    "structure_completeness": "structure_completeness",
    "difficulty_appropriateness": "difficulty_alignment",
    "pedagogical_effectiveness": "pedagogical_effectiveness",
    "practical_value": "practical_value",
    "course_suitability": "course_suitability",
    "code_quality": "code_quality",
    "overall_score": "overall_quality",
    "goal_orientation": "pmlq_goal_orientation",
    "support_sufficiency": "pmlq_support_sufficiency",
    "course_relevance": "pmlq_applicability",
    "learning_helpfulness": "pmlq_added_value",
    "intrinsic_load": "intrinsic_cognitive_load",
    "extraneous_load": "extraneous_cognitive_load",
    "active_engagement": "germane_cognitive_load",
    "mental_effort": "mental_effort",
    "tam_usefulness": "tam_perceived_usefulness",
    "tam_ease_of_use": "tam_perceived_ease_of_use",
    "tam_behavioral_intention": "tam_behavioral_intention",
    "overall_batch_quality": "overall_batch_quality",
}

EXPERT_SCORE_COLS = [
    "instruction_clarity",
    "information_completeness",
    "content_accuracy",
    "structure_completeness",
    "difficulty_appropriateness",
    "pedagogical_effectiveness",
    "code_quality",
    "practical_value",
    "course_suitability",
    "overall_score",
]

STUDENT_SCORE_COLS = [
    "goal_orientation",
    "support_sufficiency",
    "course_relevance",
    "learning_helpfulness",
    "intrinsic_load",
    "extraneous_load",
    "active_engagement",
    "mental_effort",
]

EXPERT_BATCH_SCORE_COLS = ["overall_batch_quality"]
STUDENT_BATCH_SCORE_COLS = [
    "tam_usefulness",
    "tam_ease_of_use",
    "tam_behavioral_intention",
    "overall_batch_quality",
]

COLUMN_ALIAS_EXACT = {
    "您是否知情同意参与本研究?": "consent",
    "您是否知情同意参与本研究？": "consent",
    "您目前所处的学习阶段是?": "study_stage",
    "您目前所处的学习阶段是？": "study_stage",
    "您的编程学习背景如何?": "learning_background",
    "您的编程学习背景如何？": "learning_background",
    "您对 Python 的熟悉程度如何?": "python_familiarity",
    "您对 Python 的熟悉程度如何？": "python_familiarity",
    "您对深度学习框架（如 PyTorch、TensorFlow）的熟悉程度如何?": "dl_framework_familiarity",
    "您对深度学习框架（如 PyTorch、TensorFlow）的熟悉程度如何？": "dl_framework_familiarity",
    "您是否学习过深度学习相关课程?": "has_taken_dl_course",
    "您是否学习过深度学习相关课程？": "has_taken_dl_course",
    "您对以下哪些主题相对更熟悉？（可多选）": "familiar_topics",
}

COLUMN_ALIAS_PATTERNS = [
    ("清楚说明了我需要完成的任务目标", "goal_orientation"),
    ("提供了开始作答所需的关键信息与支持", "support_sufficiency"),
    ("与深度学习课程内容或实际编程任务相关", "course_relevance"),
    ("对我的学习有明显帮助", "learning_helpfulness"),
    ("需要同时处理很多信息", "intrinsic_load"),
    ("需要额外花力气去找出最重要的信息", "extraneous_load"),
    ("会主动投入思考和理解", "active_engagement"),
    ("需要我投入较高的心理努力", "mental_effort"),
    ("有助于提高我对深度学习知识的理解", "tam_usefulness"),
    ("整体上，这批练习题比较容易上手", "tam_ease_of_use"),
    ("如果后续课程继续使用这类练习题，我愿意继续使用", "tam_behavioral_intention"),
    ("总体而言，这批练习题的质量较高", "overall_batch_quality"),
    ("清楚说明了学习者需要完成的任务", "instruction_clarity"),
    ("提供了完成任务所需的关键信息", "information_completeness"),
    ("最需要改进的地方", "needs_improvement"),
    ("存在歧义、信息缺失或错误", "issue_flags"),
    ("对本问卷或本批练习题还有什么建议", "questionnaire_suggestions"),
]


def load_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() == ".jsonl":
        rows = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        return pd.json_normalize(rows)
    if path.suffix.lower() == ".json":
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return pd.json_normalize(data["items"])
        return pd.json_normalize(data if isinstance(data, list) else [data])
    raise ValueError(f"Unsupported file type: {path}")


def normalize_string_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().replace({"": np.nan, "nan": np.nan, "None": np.nan})


def infer_column_name(raw_name: str) -> str:
    cleaned = str(raw_name).strip()
    if cleaned in COLUMN_ALIAS_EXACT:
        return COLUMN_ALIAS_EXACT[cleaned]
    for pattern, alias in COLUMN_ALIAS_PATTERNS:
        if pattern in cleaned:
            return alias
    return cleaned


def normalize_rating_value(value: Any, allow_not_applicable: bool = False) -> float | None:
    if pd.isna(value):
        return np.nan
    text = str(value).strip()
    if not text:
        return np.nan
    lowered = text.lower()
    if allow_not_applicable and ("不适用" in text or "无法判断" in text or lowered in {"na", "n/a", "not applicable"}):
        return np.nan
    match = re.search(r"\b([1-6])\b", text)
    return float(match.group(1)) if match else np.nan


def normalize_common_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    df = df.copy().rename(columns={col: infer_column_name(col) for col in df.columns})
    for col in [
        "exercise_id",
        "blind_exercise_id",
        "source_type",
        "topic",
        "difficulty",
        "exercise_type",
        "evaluator_id",
        "student_id",
        "rating_id",
        "dataset_split",
    ]:
        if col in df.columns:
            df[col] = normalize_string_series(df[col])
    if "source_type" in df.columns:
        df["source_type"] = df["source_type"].replace({"ai": "AI", "expert": "Expert", "AI-generated": "AI", "human": "Expert"})
    return df


def ensure_dataset_split(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "dataset_split" not in df.columns:
        df["dataset_split"] = "formal"
    df["dataset_split"] = normalize_string_series(df["dataset_split"]).fillna("formal")
    return df


def load_blind_mapping(path: Path) -> pd.DataFrame:
    mapping = normalize_common_columns(load_table(path))
    if mapping.empty:
        return mapping
    cols = [c for c in ["blind_exercise_id", "exercise_id", "source_type", "topic", "difficulty", "exercise_type"] if c in mapping.columns]
    return mapping[cols].drop_duplicates()


def backfill_from_mapping(df: pd.DataFrame, mapping_df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or mapping_df.empty or "blind_exercise_id" not in df.columns:
        return df
    merged = df.merge(mapping_df, on="blind_exercise_id", how="left", suffixes=("", "__map"))
    for col in ["exercise_id", "source_type", "topic", "difficulty", "exercise_type"]:
        map_col = f"{col}__map"
        if map_col in merged.columns:
            if col in merged.columns:
                merged[col] = merged[col].fillna(merged[map_col])
            else:
                merged[col] = merged[map_col]
            merged = merged.drop(columns=[map_col])
    return merged


def validate_rows(
    df: pd.DataFrame,
    score_cols: list[str],
    id_cols: list[str],
    table_name: str,
    allow_na_cols: set[str] | None = None,
    require_mapping: bool = False,
    mapping_ids: set[str] | None = None,
) -> tuple[pd.DataFrame, list[dict[str, Any]], dict[str, int]]:
    if df.empty:
        return df.copy(), [], {"rows_input": 0, "rows_unmatched_to_mapping": 0, "rows_invalid_score": 0, "formal_rows_used": 0, "sample_rows_used": 0}
    working = ensure_dataset_split(df)
    allow_na_cols = allow_na_cols or set()
    valid_mask = pd.Series(True, index=working.index)
    report_rows: list[dict[str, Any]] = []

    if require_mapping and mapping_ids is not None and "blind_exercise_id" in working.columns:
        missing_mapping = ~working["blind_exercise_id"].isin(mapping_ids)
        for _, row in working[missing_mapping].iterrows():
            report_rows.append({"table": table_name, "row_id": row.get("rating_id", ""), "exercise_id": row.get("exercise_id", ""), "blind_exercise_id": row.get("blind_exercise_id", ""), "check_name": "blind_id_exists_in_mapping", "status": "fail", "details": "blind_exercise_id not found in mapping"})
        valid_mask &= ~missing_mapping

    if id_cols and all(col in working.columns for col in id_cols):
        duplicate_mask = working.duplicated(subset=id_cols, keep=False)
        for _, row in working[duplicate_mask].iterrows():
            report_rows.append({"table": table_name, "row_id": row.get("rating_id", ""), "exercise_id": row.get("exercise_id", ""), "blind_exercise_id": row.get("blind_exercise_id", ""), "check_name": "duplicate_rating", "status": "fail", "details": "+".join(id_cols)})
        valid_mask &= ~duplicate_mask

    for score_col in score_cols:
        if score_col not in working.columns:
            continue
        allow_not_applicable = score_col in allow_na_cols
        working[score_col] = working[score_col].apply(lambda value: normalize_rating_value(value, allow_not_applicable=allow_not_applicable))
        values = pd.to_numeric(working[score_col], errors="coerce")
        max_score = 6 if allow_not_applicable else 5
        invalid_mask = values.notna() & ~values.between(1, max_score)
        for _, row in working[invalid_mask].iterrows():
            report_rows.append({"table": table_name, "row_id": row.get("rating_id", ""), "exercise_id": row.get("exercise_id", ""), "blind_exercise_id": row.get("blind_exercise_id", ""), "check_name": "score_range_1_5", "status": "fail", "details": f"{score_col}={row.get(score_col)}"})
        valid_mask &= ~invalid_mask
        if score_col not in allow_na_cols:
            missing_mask = working[score_col].isna()
            for _, row in working[missing_mask].iterrows():
                report_rows.append({"table": table_name, "row_id": row.get("rating_id", ""), "exercise_id": row.get("exercise_id", ""), "blind_exercise_id": row.get("blind_exercise_id", ""), "check_name": "required_dimension_present", "status": "fail", "details": score_col})
            valid_mask &= ~missing_mask

    if require_mapping and "exercise_id" in working.columns:
        missing_exercise = working["exercise_id"].isna()
        for _, row in working[missing_exercise].iterrows():
            report_rows.append({"table": table_name, "row_id": row.get("rating_id", ""), "exercise_id": row.get("exercise_id", ""), "blind_exercise_id": row.get("blind_exercise_id", ""), "check_name": "mapping_backfill", "status": "fail", "details": "exercise_id missing after mapping backfill"})
        valid_mask &= ~missing_exercise

    validated = working[valid_mask].copy()
    for col in allow_na_cols:
        if col in validated.columns:
            validated.loc[pd.to_numeric(validated[col], errors="coerce") == 6, col] = np.nan

    stats = {
        "rows_input": int(len(working)),
        "rows_unmatched_to_mapping": int(len([r for r in report_rows if r["check_name"] in {"blind_id_exists_in_mapping", "mapping_backfill"}])),
        "rows_invalid_score": int(len([r for r in report_rows if r["check_name"] == "score_range_1_5"])),
        "formal_rows_used": int((validated["dataset_split"] == "formal").sum()) if "dataset_split" in validated.columns else 0,
        "sample_rows_used": int((validated["dataset_split"] == "sample").sum()) if "dataset_split" in validated.columns else 0,
    }
    return validated, report_rows, stats


def load_auto_metrics(path: Path) -> pd.DataFrame:
    auto_df = normalize_common_columns(load_table(path))
    if auto_df.empty:
        return auto_df
    if "exercise_id" not in auto_df.columns:
        raise ValueError("Auto metrics file must contain exercise_id.")
    return auto_df.drop_duplicates(subset=["exercise_id"], keep="first")


def build_auto_metric_subset(auto_df: pd.DataFrame) -> pd.DataFrame:
    if auto_df.empty:
        return auto_df.copy()
    keep_cols = [c for c in ["exercise_id", "source_type", "topic", "difficulty", "exercise_type"] if c in auto_df.columns]
    keep_cols.extend([c for c in DEFAULT_AUTO_METRIC_SUMMARY_COLUMNS if c in auto_df.columns])
    return auto_df[list(dict.fromkeys(keep_cols))].copy()


def merge_human_with_auto(human_df: pd.DataFrame, auto_df: pd.DataFrame) -> pd.DataFrame:
    if human_df.empty or auto_df.empty or "exercise_id" not in auto_df.columns:
        return human_df.copy()
    merged = human_df.merge(auto_df, on="exercise_id", how="left", suffixes=("", "__auto"))
    for col in ["source_type", "topic", "difficulty", "exercise_type"]:
        auto_col = f"{col}__auto"
        if auto_col in merged.columns:
            if col in merged.columns:
                merged[col] = merged[col].fillna(merged[auto_col])
            else:
                merged[col] = merged[auto_col]
            merged = merged.drop(columns=[auto_col])
    return merged


def build_long_ratings(df: pd.DataFrame, evaluator_type: str, id_col: str, score_cols: list[str]) -> pd.DataFrame:
    if df.empty or not score_cols:
        return pd.DataFrame()
    base_cols = ["rating_id", id_col, "exercise_id", "blind_exercise_id", "source_type", "topic", "difficulty", "exercise_type", "rated_at", "notes"]
    base_cols.extend([c for c in DEFAULT_AUTO_METRIC_SUMMARY_COLUMNS if c in df.columns])
    base_cols = [c for c in base_cols if c in df.columns]
    melted = df[base_cols + score_cols].copy().rename(columns={id_col: "respondent_id"})
    melted["evaluator_type"] = evaluator_type
    melted = melted.melt(id_vars=[c for c in melted.columns if c not in score_cols], value_vars=score_cols, var_name="rating_dimension", value_name="rating_value")
    melted["normalized_dimension"] = melted["rating_dimension"].map(DIMENSION_MAPPING).fillna(melted["rating_dimension"])
    return melted


def aggregate_ratings(df: pd.DataFrame, score_cols: list[str]) -> pd.DataFrame:
    if df.empty or not score_cols:
        return pd.DataFrame()
    group_cols = [c for c in ["exercise_id", "source_type", "topic", "difficulty", "exercise_type"] if c in df.columns]
    rows = []
    for keys, group_df in df.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_cols, keys))
        row["rating_count"] = int(len(group_df))
        for col in score_cols:
            values = pd.to_numeric(group_df[col], errors="coerce").dropna()
            row[f"{col}_mean"] = float(values.mean()) if not values.empty else np.nan
            row[f"{col}_std"] = float(values.std(ddof=1)) if len(values) > 1 else np.nan
            row[f"{col}_count"] = int(values.count())
        rows.append(row)
    return pd.DataFrame(rows)


def build_dimension_mapping_table() -> pd.DataFrame:
    return pd.DataFrame([{"original_dimension": src, "normalized_dimension": dst} for src, dst in sorted(DIMENSION_MAPPING.items())])


def build_rating_balance_by_source(long_df: pd.DataFrame) -> pd.DataFrame:
    if long_df.empty:
        return pd.DataFrame()
    return long_df.groupby(["evaluator_type", "source_type"], dropna=False).agg(rating_rows=("rating_value", "count"), unique_exercises=("exercise_id", pd.Series.nunique), unique_respondents=("respondent_id", pd.Series.nunique)).reset_index()


def build_exercise_rating_coverage(expert_df: pd.DataFrame, student_df: pd.DataFrame, auto_subset: pd.DataFrame) -> pd.DataFrame:
    if auto_subset.empty or "exercise_id" not in auto_subset.columns:
        coverage = pd.DataFrame(columns=["exercise_id", "source_type", "topic", "difficulty", "exercise_type"])
    else:
        coverage = auto_subset[[c for c in ["exercise_id", "source_type", "topic", "difficulty", "exercise_type"] if c in auto_subset.columns]].drop_duplicates(subset=["exercise_id"], keep="first")
    if not expert_df.empty:
        coverage = coverage.merge(expert_df.groupby("exercise_id").size().rename("expert_rating_count").reset_index(), on="exercise_id", how="left")
    if not student_df.empty:
        coverage = coverage.merge(student_df.groupby("exercise_id").size().rename("student_rating_count").reset_index(), on="exercise_id", how="left")
    return coverage


def build_batch_summary(batch_frames: dict[str, pd.DataFrame], score_cols_map: dict[str, list[str]]) -> pd.DataFrame:
    rows = []
    for respondent_type, df in batch_frames.items():
        if df.empty:
            continue
        for score_col in score_cols_map.get(respondent_type, []):
            if score_col not in df.columns:
                continue
            values = pd.to_numeric(df[score_col], errors="coerce").dropna()
            if values.empty:
                continue
            rows.append({"respondent_type": respondent_type, "metric": score_col, "sample_size": int(values.count()), "mean": float(values.mean()), "std": float(values.std(ddof=1)) if len(values) > 1 else np.nan, "median": float(values.median()), "min": float(values.min()), "max": float(values.max())})
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge human evaluation tables with exercise-level automatic metrics.")
    parser.add_argument("--use-curated", action="store_true")
    parser.add_argument("--auto-metrics", default="results/exercise_metrics.v1.csv")
    parser.add_argument("--expert-ratings", default="data/human_eval/expert_ratings.csv")
    parser.add_argument("--student-ratings", default="data/human_eval/student_ratings.csv")
    parser.add_argument("--expert-batch", default="data/human_eval/expert_batch.csv")
    parser.add_argument("--student-batch", default="data/human_eval/student_batch.csv")
    parser.add_argument("--open-feedback", default="data/human_eval/open_feedback.csv")
    parser.add_argument("--blind-mapping", default="data/human_eval/blind_mapping.generated.v1.csv")
    parser.add_argument("--output-dir", default="results/human_eval_merged")
    args = parser.parse_args()

    if args.use_curated:
        args.auto_metrics = str(CURATED_DIR / "exercise_metrics.curated.v1.csv")
        args.blind_mapping = str(CURATED_DIR / "blind_mapping.curated.v1.csv")
        args.output_dir = str(CURATED_DIR / "human_eval_merged")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    auto_df = build_auto_metric_subset(load_auto_metrics(Path(args.auto_metrics)))
    mapping_df = load_blind_mapping(Path(args.blind_mapping))
    mapping_ids = set(mapping_df["blind_exercise_id"].dropna().tolist()) if not mapping_df.empty else set()

    expert_df = ensure_dataset_split(backfill_from_mapping(normalize_common_columns(load_table(Path(args.expert_ratings))), mapping_df))
    student_df = ensure_dataset_split(backfill_from_mapping(normalize_common_columns(load_table(Path(args.student_ratings))), mapping_df))
    feedback_df = ensure_dataset_split(backfill_from_mapping(normalize_common_columns(load_table(Path(args.open_feedback))), mapping_df))
    expert_batch_df = ensure_dataset_split(normalize_common_columns(load_table(Path(args.expert_batch))))
    student_batch_df = ensure_dataset_split(normalize_common_columns(load_table(Path(args.student_batch))))

    expert_df, expert_validation_rows, expert_stats = validate_rows(expert_df, [c for c in EXPERT_SCORE_COLS if c in expert_df.columns], ["evaluator_id", "blind_exercise_id"], "expert", allow_na_cols={"code_quality"}, require_mapping=True, mapping_ids=mapping_ids)
    student_df, student_validation_rows, student_stats = validate_rows(student_df, [c for c in STUDENT_SCORE_COLS if c in student_df.columns], ["student_id", "blind_exercise_id"], "student", require_mapping=True, mapping_ids=mapping_ids)
    expert_batch_df, expert_batch_validation_rows, expert_batch_stats = validate_rows(expert_batch_df, [c for c in EXPERT_BATCH_SCORE_COLS if c in expert_batch_df.columns], ["evaluator_id"], "expert_batch")
    student_batch_df, student_batch_validation_rows, student_batch_stats = validate_rows(student_batch_df, [c for c in STUDENT_BATCH_SCORE_COLS if c in student_batch_df.columns], ["student_id"], "student_batch")

    expert_merged_all = merge_human_with_auto(expert_df, auto_df)
    student_merged_all = merge_human_with_auto(student_df, auto_df)
    feedback_merged_all = merge_human_with_auto(feedback_df, auto_df)
    expert_merged = expert_merged_all[expert_merged_all["dataset_split"] == "formal"].copy() if "dataset_split" in expert_merged_all.columns else expert_merged_all
    student_merged = student_merged_all[student_merged_all["dataset_split"] == "formal"].copy() if "dataset_split" in student_merged_all.columns else student_merged_all
    feedback_merged = feedback_merged_all[feedback_merged_all["dataset_split"] == "formal"].copy() if "dataset_split" in feedback_merged_all.columns else feedback_merged_all

    expert_score_cols = [c for c in EXPERT_SCORE_COLS if c in expert_merged.columns]
    student_score_cols = [c for c in STUDENT_SCORE_COLS if c in student_merged.columns]
    expert_by_exercise = aggregate_ratings(expert_merged, expert_score_cols)
    student_by_exercise = aggregate_ratings(student_merged, student_score_cols)
    human_ratings_long = pd.concat([build_long_ratings(expert_merged, "expert", "evaluator_id", expert_score_cols), build_long_ratings(student_merged, "student", "student_id", student_score_cols)], ignore_index=True)

    if not expert_merged.empty:
        expert_merged.to_csv(output_dir / "expert_ratings_merged.v1.csv", index=False)
    if not student_merged.empty:
        student_merged.to_csv(output_dir / "student_ratings_merged.v1.csv", index=False)
    if not feedback_merged.empty:
        feedback_merged.to_csv(output_dir / "open_feedback_merged.v1.csv", index=False)
    if not expert_by_exercise.empty:
        expert_by_exercise.to_csv(output_dir / "expert_ratings_by_exercise.v1.csv", index=False)
    if not student_by_exercise.empty:
        student_by_exercise.to_csv(output_dir / "student_ratings_by_exercise.v1.csv", index=False)
    if not human_ratings_long.empty:
        human_ratings_long.to_csv(output_dir / "human_ratings_long.v1.csv", index=False)
    if not expert_batch_df.empty:
        expert_batch_df.to_csv(output_dir / "expert_batch_responses.v1.csv", index=False)
    if not student_batch_df.empty:
        student_batch_df.to_csv(output_dir / "student_batch_responses.v1.csv", index=False)

    batch_summary = build_batch_summary({"expert": expert_batch_df, "student": student_batch_df}, {"expert": [c for c in EXPERT_BATCH_SCORE_COLS if c in expert_batch_df.columns], "student": [c for c in STUDENT_BATCH_SCORE_COLS if c in student_batch_df.columns]})
    if not batch_summary.empty:
        batch_summary.to_csv(output_dir / "batch_response_summary.v1.csv", index=False)

    build_dimension_mapping_table().to_csv(output_dir / "dimension_mapping.v1.csv", index=False)
    build_rating_balance_by_source(human_ratings_long).to_csv(output_dir / "rating_balance_by_source.v1.csv", index=False)
    build_exercise_rating_coverage(expert_merged, student_merged, auto_df).to_csv(output_dir / "exercise_rating_coverage.v1.csv", index=False)
    pd.DataFrame(expert_validation_rows + student_validation_rows + expert_batch_validation_rows + student_batch_validation_rows).to_csv(output_dir / VALIDATION_REPORT_NAME, index=False)

    manifest = {
        "inputs": {
            "auto_metrics": args.auto_metrics,
            "expert_ratings": args.expert_ratings,
            "student_ratings": args.student_ratings,
            "expert_batch": args.expert_batch,
            "student_batch": args.student_batch,
            "open_feedback": args.open_feedback,
            "blind_mapping": args.blind_mapping,
        },
        "outputs": {
            "expert_ratings_merged": str(output_dir / "expert_ratings_merged.v1.csv"),
            "student_ratings_merged": str(output_dir / "student_ratings_merged.v1.csv"),
            "open_feedback_merged": str(output_dir / "open_feedback_merged.v1.csv"),
            "expert_ratings_by_exercise": str(output_dir / "expert_ratings_by_exercise.v1.csv"),
            "student_ratings_by_exercise": str(output_dir / "student_ratings_by_exercise.v1.csv"),
            "human_ratings_long": str(output_dir / "human_ratings_long.v1.csv"),
            "expert_batch_responses": str(output_dir / "expert_batch_responses.v1.csv"),
            "student_batch_responses": str(output_dir / "student_batch_responses.v1.csv"),
            "batch_response_summary": str(output_dir / "batch_response_summary.v1.csv"),
            "dimension_mapping": str(output_dir / "dimension_mapping.v1.csv"),
            "rating_balance_by_source": str(output_dir / "rating_balance_by_source.v1.csv"),
            "exercise_rating_coverage": str(output_dir / "exercise_rating_coverage.v1.csv"),
            "merge_validation_report": str(output_dir / VALIDATION_REPORT_NAME),
        },
    }
    with (output_dir / "merge_manifest.v1.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"Outputs written to: {output_dir}")


if __name__ == "__main__":
    main()

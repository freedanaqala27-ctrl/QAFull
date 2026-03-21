from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd
from scipy import stats

try:
    from statsmodels.stats.multitest import multipletests
except Exception:
    multipletests = None


STUDENT_ITEM_METRICS = [
    "task_goal_clarity",
    "key_support",
    "course_relevance",
    "learning_help",
    "info_load",
    "search_effort",
    "active_engagement",
    "mental_effort",
    "item_mean_score",
    "usability_mean_score",
    "cognitive_load_mean_score",
    "engagement_score",
]

EXERCISE_AUTO_METRICS = [
    "auto_flesch_reading_ease",
    "auto_flesch_kincaid_grade",
    "auto_instruction_completeness_ratio",
    "auto_technical_term_density_instruction",
    "auto_avg_sentence_length",
    "auto_structure_completeness_ratio",
    "auto_structure_score_weighted",
    "auto_starter_code_mccabe_max",
    "auto_starter_code_mi",
]

PAIR_AUTO_METRICS = [
    "pair_tfidf_cosine_full_text",
    "pair_tfidf_cosine_instruction_only",
    "pair_bertscore_f1_instruction_only",
    "pair_rougeL_f1_instruction_only",
    "pair_meteor_instruction_only",
    "pair_topic_coherence_score_ai",
]

AGGREGATION_KEYS = [
    "exercise_id",
    "source_type",
    "topic",
    "difficulty",
    "exercise_type",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate auto-vs-student correlation tables.")
    parser.add_argument(
        "--master-csv",
        type=Path,
        default=Path("results/student_subsets/student_analysis_master_30.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/student_subsets/chapter5_outputs/tables"),
    )
    parser.add_argument(
        "--exclude-attention-fail",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Exclude participants who failed the attention check. Use --no-exclude-attention-fail to keep them.",
    )
    parser.add_argument(
        "--exclude-fast-flag",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Exclude participants flagged as very fast responders. Use --no-exclude-fast-flag to keep them.",
    )
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def adjust_pvalues(values: list[float]) -> list[float]:
    if not values:
        return []
    if multipletests is not None:
        return list(multipletests(values, method="fdr_bh")[1])

    indexed = sorted(enumerate(values), key=lambda item: item[1])
    total = len(values)
    adjusted = [0.0] * total
    running_min = 1.0
    for reverse_rank, (idx, value) in enumerate(reversed(indexed), start=1):
        rank = total - reverse_rank + 1
        candidate = min(1.0, value * total / rank)
        running_min = min(running_min, candidate)
        adjusted[idx] = running_min
    return adjusted


def significance_label(p_value: float) -> str:
    if pd.isna(p_value):
        return ""
    if p_value < 0.001:
        return "***"
    if p_value < 0.01:
        return "**"
    if p_value < 0.05:
        return "*"
    return "ns"


def coerce_bool(series: pd.Series) -> pd.Series:
    normalized = series.astype(str).str.strip().str.lower()
    return normalized.map({"true": True, "false": False}).fillna(False)


def load_master(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def filter_master(
    df: pd.DataFrame,
    *,
    exclude_attention_fail: bool,
    exclude_fast_flag: bool,
) -> tuple[pd.DataFrame, dict[str, int]]:
    working = df.copy()
    summary = {
        "rows_before_filter": int(len(working)),
        "participants_before_filter": int(working["participant_id"].nunique()),
    }

    if exclude_attention_fail and "attention_check_passed" in working.columns:
        attention_mask = coerce_bool(working["attention_check_passed"])
        working = working[attention_mask].copy()

    if exclude_fast_flag and "participant_fast_flag_under_180s" in working.columns:
        fast_mask = ~coerce_bool(working["participant_fast_flag_under_180s"])
        working = working[fast_mask].copy()

    summary["rows_after_filter"] = int(len(working))
    summary["participants_after_filter"] = int(working["participant_id"].nunique())
    summary["exercises_after_filter"] = int(working["exercise_id"].nunique())
    return working, summary


def build_exercise_level_table(df: pd.DataFrame) -> pd.DataFrame:
    agg_spec: dict[str, Any] = {
        "participant_id": pd.NamedAgg(column="participant_id", aggfunc="nunique"),
    }
    for metric in STUDENT_ITEM_METRICS:
        agg_spec[f"{metric}_mean"] = pd.NamedAgg(column=metric, aggfunc="mean")
        agg_spec[f"{metric}_std"] = pd.NamedAgg(column=metric, aggfunc="std")

    for metric in EXERCISE_AUTO_METRICS + PAIR_AUTO_METRICS:
        if metric in df.columns:
            agg_spec[metric] = pd.NamedAgg(column=metric, aggfunc="first")

    grouped = (
        df.groupby(AGGREGATION_KEYS, dropna=False)
        .agg(**agg_spec)
        .reset_index()
        .rename(columns={"participant_id": "student_rating_count"})
    )
    return grouped


def correlation_rows(df: pd.DataFrame, human_metrics: list[str], auto_metrics: list[str], scope: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for human_metric in human_metrics:
        for auto_metric in auto_metrics:
            if human_metric not in df.columns or auto_metric not in df.columns:
                continue
            subset = df[[human_metric, auto_metric]].apply(pd.to_numeric, errors="coerce").dropna()
            if len(subset) < 3:
                continue
            pearson_r, pearson_p = stats.pearsonr(subset[human_metric], subset[auto_metric])
            spearman_r, spearman_p = stats.spearmanr(subset[human_metric], subset[auto_metric], nan_policy="omit")
            rows.append(
                {
                    "analysis_scope": scope,
                    "student_metric": human_metric,
                    "auto_metric": auto_metric,
                    "sample_size": int(len(subset)),
                    "pearson_r": float(pearson_r),
                    "pearson_p_value": float(pearson_p),
                    "spearman_r": float(spearman_r),
                    "spearman_p_value": float(spearman_p),
                    "direction": "positive" if spearman_r > 0 else "negative" if spearman_r < 0 else "zero",
                }
            )

    if rows:
        pearson_adjusted = adjust_pvalues([float(row["pearson_p_value"]) for row in rows])
        spearman_adjusted = adjust_pvalues([float(row["spearman_p_value"]) for row in rows])
        for row, pearson_adj, spearman_adj in zip(rows, pearson_adjusted, spearman_adjusted):
            row["pearson_p_adjust_bh"] = pearson_adj
            row["spearman_p_adjust_bh"] = spearman_adj
            row["spearman_significance"] = significance_label(spearman_adj)
    return pd.DataFrame(rows)


def write_dataframe(df: pd.DataFrame, path: Path) -> None:
    ensure_dir(path.parent)
    df.to_csv(path, index=False)


def write_json(doc: dict[str, Any], path: Path) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    ensure_dir(args.output_dir)

    master_df = load_master(args.master_csv)
    filtered_df, filter_summary = filter_master(
        master_df,
        exclude_attention_fail=args.exclude_attention_fail,
        exclude_fast_flag=args.exclude_fast_flag,
    )

    exercise_level_df = build_exercise_level_table(filtered_df)
    exercise_level_path = args.output_dir / "student_exercise_level_aggregates_30.csv"
    write_dataframe(exercise_level_df, exercise_level_path)

    student_mean_metrics = [f"{metric}_mean" for metric in STUDENT_ITEM_METRICS]
    exercise_corr_df = correlation_rows(
        exercise_level_df,
        student_mean_metrics,
        EXERCISE_AUTO_METRICS,
        scope="exercise_level_all_exercises",
    ).sort_values(["student_metric", "spearman_p_adjust_bh", "auto_metric"], na_position="last")

    ai_only_df = exercise_level_df[exercise_level_df["source_type"] == "AI"].copy()
    pair_corr_df = correlation_rows(
        ai_only_df,
        student_mean_metrics,
        PAIR_AUTO_METRICS,
        scope="exercise_level_ai_only_pair_metrics",
    ).sort_values(["student_metric", "spearman_p_adjust_bh", "auto_metric"], na_position="last")

    write_dataframe(
        exercise_corr_df,
        args.output_dir / "correlation_auto_vs_student.exercise_metrics.v1.csv",
    )
    write_dataframe(
        pair_corr_df,
        args.output_dir / "correlation_auto_vs_student.pair_metrics_ai_only.v1.csv",
    )

    manifest = {
        "master_csv": str(args.master_csv),
        "output_dir": str(args.output_dir),
        "filters": {
            "exclude_attention_fail": args.exclude_attention_fail,
            "exclude_fast_flag": args.exclude_fast_flag,
        },
        "filter_summary": filter_summary,
        "exercise_level_rows": int(len(exercise_level_df)),
        "ai_only_exercise_rows": int(len(ai_only_df)),
        "exercise_metric_correlation_rows": int(len(exercise_corr_df)),
        "pair_metric_correlation_rows": int(len(pair_corr_df)),
        "exercise_auto_metrics_included": sorted(exercise_corr_df["auto_metric"].dropna().unique().tolist()),
        "pair_auto_metrics_included": sorted(pair_corr_df["auto_metric"].dropna().unique().tolist()),
        "outputs": {
            "exercise_level_aggregates": str(exercise_level_path),
            "exercise_metric_correlations": str(args.output_dir / "correlation_auto_vs_student.exercise_metrics.v1.csv"),
            "pair_metric_correlations": str(args.output_dir / "correlation_auto_vs_student.pair_metrics_ai_only.v1.csv"),
        },
    }
    write_json(manifest, args.output_dir / "correlation_auto_vs_student.manifest.json")

    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

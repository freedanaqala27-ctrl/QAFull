from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

try:
    from statsmodels.stats.multitest import multipletests
except Exception:
    multipletests = None

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CURATED_DIR = PROJECT_ROOT / "results" / "curated"
CURATED_FAIRNESS_AUDIT = CURATED_DIR / "human_eval_packets" / "audit" / "quality" / "human_eval_fairness_audit.curated.v1.csv"
CURATED_CORRECTNESS_METRICS = CURATED_DIR / "exercise_correctness_metrics.curated.v1.csv"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)

    if path.suffix.lower() == ".jsonl":
        records: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        return pd.json_normalize(records)

    raise ValueError(f"Unsupported input file: {path}")


def load_exercise_metrics(path: Path) -> pd.DataFrame:
    return load_table(path)


def load_pair_metrics(path: Path) -> pd.DataFrame:
    return load_table(path)


def load_correctness_metrics(path: Path) -> pd.DataFrame:
    return load_table(path)


def write_json(doc: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)


def write_dataframe(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if df.empty:
        path.write_text("", encoding="utf-8")
        return
    df.to_csv(path, index=False)


def get_numeric_metric_columns(df: pd.DataFrame, exclude: list[str] | None = None) -> list[str]:
    excluded = set(exclude or [])
    return [col for col in df.select_dtypes(include=[np.number]).columns if col not in excluded]


def summarize_group(df: pd.DataFrame, group_cols: list[str], metric_cols: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    grouped = [((), df)] if not group_cols else df.groupby(group_cols, dropna=False)

    for group_key, group_df in grouped:
        if not isinstance(group_key, tuple):
            group_key = (group_key,)
        group_meta = dict(zip(group_cols, group_key))
        for metric in metric_cols:
            values = pd.to_numeric(group_df[metric], errors="coerce").dropna()
            if values.empty:
                continue
            rows.append(
                {
                    **group_meta,
                    "metric": metric,
                    "sample_size": int(values.count()),
                    "mean": float(values.mean()),
                    "std": float(values.std(ddof=1)) if len(values) > 1 else np.nan,
                    "median": float(values.median()),
                    "min": float(values.min()),
                    "max": float(values.max()),
                }
            )
    return pd.DataFrame(rows)


def build_sample_size_summary(
    raw_exercise_df: pd.DataFrame,
    pair_df: pd.DataFrame,
    analysis_exercise_df: pd.DataFrame | None = None,
    correctness_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if not raw_exercise_df.empty and "source_type" in raw_exercise_df.columns:
        for source_type, group_df in raw_exercise_df.groupby("source_type", dropna=False):
            rows.append(
                {
                    "dataset": "exercise_metrics_raw",
                    "group": str(source_type),
                    "sample_size": int(group_df["exercise_id"].nunique()) if "exercise_id" in group_df.columns else int(len(group_df)),
                }
            )

    if not raw_exercise_df.empty and {"topic", "source_type"}.issubset(raw_exercise_df.columns):
        grouped = raw_exercise_df.groupby(["topic", "source_type"], dropna=False)
        for (topic, source_type), group_df in grouped:
            rows.append(
                {
                    "dataset": "exercise_metrics_by_topic_raw",
                    "group": f"{topic}|{source_type}",
                    "sample_size": int(group_df["exercise_id"].nunique()) if "exercise_id" in group_df.columns else int(len(group_df)),
                }
            )

    if analysis_exercise_df is not None and not analysis_exercise_df.empty and "source_type" in analysis_exercise_df.columns:
        for source_type, group_df in analysis_exercise_df.groupby("source_type", dropna=False):
            rows.append(
                {
                    "dataset": "exercise_metrics_analysis",
                    "group": str(source_type),
                    "sample_size": int(group_df["exercise_id"].nunique()) if "exercise_id" in group_df.columns else int(len(group_df)),
                }
            )
        if "pair_id" in analysis_exercise_df.columns:
            rows.append(
                {
                    "dataset": "exercise_pairs_analysis",
                    "group": "overall",
                    "sample_size": int(analysis_exercise_df["pair_id"].dropna().nunique()),
                }
            )

    if correctness_df is not None and not correctness_df.empty and "source_type" in correctness_df.columns:
        for source_type, group_df in correctness_df.groupby("source_type", dropna=False):
            rows.append(
                {
                    "dataset": "correctness_metrics_analysis",
                    "group": str(source_type),
                    "sample_size": int(group_df["exercise_id"].nunique()) if "exercise_id" in group_df.columns else int(len(group_df)),
                }
            )
        if "pair_id" in correctness_df.columns:
            rows.append(
                {
                    "dataset": "correctness_pairs_analysis",
                    "group": "overall",
                    "sample_size": int(correctness_df["pair_id"].dropna().nunique()),
                }
            )

    if not pair_df.empty:
        rows.append(
            {
                "dataset": "pair_metrics",
                "group": "overall",
                "sample_size": int(pair_df["pair_id"].nunique()) if "pair_id" in pair_df.columns else int(len(pair_df)),
            }
        )
        if "topic" in pair_df.columns:
            for topic, group_df in pair_df.groupby("topic", dropna=False):
                rows.append(
                    {
                        "dataset": "pair_metrics_by_topic",
                        "group": str(topic),
                        "sample_size": int(group_df["pair_id"].nunique()) if "pair_id" in group_df.columns else int(len(group_df)),
                    }
                )
    return pd.DataFrame(rows)


def normalize_boolean_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().map({"true": 1.0, "false": 0.0})


def prepare_correctness_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    prepared = df.copy()
    for col in ["reference_solution_fully_valid", "required_packages_satisfied", "solution_overlay_hit", "tests_overlay_hit"]:
        if col in prepared.columns:
            prepared[col] = normalize_boolean_series(prepared[col])

    if "correctness_status" in prepared.columns:
        prepared["correctness_status_binary_pass"] = (
            prepared["correctness_status"].astype(str).str.strip().str.lower().eq("pass").astype(float)
        )
        prepared["correctness_status_binary_evaluable"] = (
            prepared["correctness_status"].astype(str).str.strip().str.lower().isin(["pass", "partial_pass", "fail"]).astype(float)
        )
    return prepared


def filter_evaluable_correctness(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "correctness_status" not in df.columns:
        return df.copy()
    return df[df["correctness_status"].astype(str).str.strip().str.lower().isin(["pass", "partial_pass", "fail"])].copy()


def correctness_status_summary(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if df.empty or "correctness_status" not in df.columns:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    grouped = [((), df)] if not group_cols else df.groupby(group_cols, dropna=False)
    for group_key, group_df in grouped:
        if not isinstance(group_key, tuple):
            group_key = (group_key,)
        group_meta = dict(zip(group_cols, group_key))
        counts = (
            group_df["correctness_status"]
            .astype(str)
            .str.strip()
            .str.lower()
            .value_counts(dropna=False)
            .to_dict()
        )
        total = int(len(group_df))
        row = {**group_meta, "sample_size": total}
        for status_name, count in counts.items():
            row[f"status_{status_name}"] = int(count)
            row[f"rate_{status_name}"] = float(count / total) if total else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


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


def cohens_d(ai_values: pd.Series, expert_values: pd.Series) -> float:
    ai = ai_values.dropna().astype(float)
    expert = expert_values.dropna().astype(float)
    if len(ai) < 2 or len(expert) < 2:
        return np.nan
    ai_var = ai.var(ddof=1)
    expert_var = expert.var(ddof=1)
    pooled = np.sqrt(((len(ai) - 1) * ai_var + (len(expert) - 1) * expert_var) / (len(ai) + len(expert) - 2))
    if pooled == 0:
        return np.nan
    return float((ai.mean() - expert.mean()) / pooled)


def cohens_dz(diff_values: pd.Series) -> float:
    diff = diff_values.dropna().astype(float)
    if len(diff) < 2:
        return np.nan
    diff_sd = diff.std(ddof=1)
    if diff_sd == 0 or pd.isna(diff_sd):
        return np.nan
    return float(diff.mean() / diff_sd)


def run_paired_group_comparison(df: pd.DataFrame, metric_cols: list[str]) -> pd.DataFrame:
    if df.empty or "source_type" not in df.columns or "pair_id" not in df.columns:
        return pd.DataFrame()

    comparison_rows: list[dict[str, Any]] = []
    for metric in metric_cols:
        wide = (
            df[["pair_id", "source_type", metric]]
            .copy()
            .assign(**{metric: lambda frame: pd.to_numeric(frame[metric], errors="coerce")})
            .pivot(index="pair_id", columns="source_type", values=metric)
        )
        if not {"AI", "Expert"}.issubset(wide.columns):
            continue

        wide = wide.dropna(subset=["AI", "Expert"])
        if len(wide) < 2:
            continue

        ai_values = pd.to_numeric(wide["AI"], errors="coerce")
        expert_values = pd.to_numeric(wide["Expert"], errors="coerce")
        diff = ai_values - expert_values
        nonzero_diff = diff[diff != 0]

        t_stat, t_p = stats.ttest_rel(ai_values, expert_values, nan_policy="omit")

        wilcoxon_stat = np.nan
        wilcoxon_p = np.nan
        if len(nonzero_diff) >= 3:
            try:
                wilcoxon_stat, wilcoxon_p = stats.wilcoxon(nonzero_diff)
            except ValueError:
                wilcoxon_stat, wilcoxon_p = np.nan, np.nan

        comparison_rows.append(
            {
                "metric": metric,
                "n_pairs": int(len(wide)),
                "ai_mean": float(ai_values.mean()),
                "expert_mean": float(expert_values.mean()),
                "mean_diff_ai_minus_expert": float(diff.mean()),
                "paired_t_statistic": float(t_stat) if not pd.isna(t_stat) else np.nan,
                "paired_t_raw_p_value": float(t_p) if not pd.isna(t_p) else np.nan,
                "wilcoxon_statistic": float(wilcoxon_stat) if not pd.isna(wilcoxon_stat) else np.nan,
                "wilcoxon_raw_p_value": float(wilcoxon_p) if not pd.isna(wilcoxon_p) else np.nan,
                "cohens_dz": cohens_dz(diff),
            }
        )

    if comparison_rows:
        t_adjusted = adjust_pvalues(
            [float(row["paired_t_raw_p_value"]) for row in comparison_rows if not pd.isna(row["paired_t_raw_p_value"])]
        )
        wilcoxon_adjusted = adjust_pvalues(
            [float(row["wilcoxon_raw_p_value"]) for row in comparison_rows if not pd.isna(row["wilcoxon_raw_p_value"])]
        )

        t_index = 0
        wilcoxon_index = 0
        for row in comparison_rows:
            if not pd.isna(row["paired_t_raw_p_value"]):
                row["paired_t_p_adjust_bh"] = t_adjusted[t_index]
                t_index += 1
            else:
                row["paired_t_p_adjust_bh"] = np.nan

            if not pd.isna(row["wilcoxon_raw_p_value"]):
                row["wilcoxon_p_adjust_bh"] = wilcoxon_adjusted[wilcoxon_index]
                wilcoxon_index += 1
            else:
                row["wilcoxon_p_adjust_bh"] = np.nan

    return pd.DataFrame(comparison_rows)


DIMENSION_MAP = {
    "instruction_clarity_mean": "instruction_clarity_mean",
    "information_completeness_mean": "information_completeness_mean",
    "information_sufficiency_mean": "information_sufficiency_mean",
    "content_accuracy_mean": "content_accuracy_mean",
    "structure_completeness_mean": "structure_completeness_mean",
    "easy_to_understand_mean": "easy_to_understand_mean",
    "goal_orientation_mean": "goal_orientation_mean",
    "course_relevance_mean": "course_relevance_mean",
    "support_sufficiency_mean": "support_sufficiency_mean",
    "learning_helpfulness_mean": "learning_helpfulness_mean",
    "intrinsic_load_mean": "intrinsic_load_mean",
    "extraneous_load_mean": "extraneous_load_mean",
    "active_engagement_mean": "active_engagement_mean",
    "mental_effort_mean": "mental_effort_mean",
    "pedagogical_effectiveness_mean": "pedagogical_effectiveness_mean",
    "helpful_for_learning_mean": "helpful_for_learning_mean",
    "practical_value_mean": "practical_value_mean",
    "course_suitability_mean": "course_suitability_mean",
    "code_quality_mean": "code_quality_mean",
    "overall_score_mean": "overall_score_mean",
    "overall_satisfaction_mean": "overall_satisfaction_mean",
    "tam_usefulness_mean": "tam_usefulness_mean",
    "tam_ease_of_use_mean": "tam_ease_of_use_mean",
    "tam_behavioral_intention_mean": "tam_behavioral_intention_mean",
    "overall_batch_quality_mean": "overall_batch_quality_mean",
}


def correlation_frame(auto_df: pd.DataFrame, human_df: pd.DataFrame, evaluator_type: str) -> pd.DataFrame:
    if auto_df.empty or human_df.empty or "exercise_id" not in auto_df.columns or "exercise_id" not in human_df.columns:
        return pd.DataFrame()

    merged = human_df.merge(auto_df, on="exercise_id", how="inner")
    if merged.empty:
        return pd.DataFrame()

    human_cols = [col for col in DIMENSION_MAP if col in merged.columns]
    auto_cols = [
        col
        for col in auto_df.columns
        if col in merged.columns and pd.api.types.is_numeric_dtype(merged[col]) and col not in human_cols
    ]

    rows: list[dict[str, Any]] = []
    for auto_metric in auto_cols:
        for human_metric in human_cols:
            subset = merged[[auto_metric, human_metric]].apply(pd.to_numeric, errors="coerce").dropna()
            if len(subset) < 3:
                continue
            pearson_r, pearson_p = stats.pearsonr(subset[auto_metric], subset[human_metric])
            spearman_r, spearman_p = stats.spearmanr(subset[auto_metric], subset[human_metric], nan_policy="omit")
            rows.append(
                {
                    "evaluator_type": evaluator_type,
                    "auto_metric": auto_metric,
                    "human_metric": human_metric,
                    "sample_size": int(len(subset)),
                    "pearson_r": float(pearson_r),
                    "pearson_p_value": float(pearson_p),
                    "spearman_r": float(spearman_r),
                    "spearman_p_value": float(spearman_p),
                }
            )

    if rows:
        adjusted = adjust_pvalues([float(row["spearman_p_value"]) for row in rows])
        for row, adjusted_value in zip(rows, adjusted):
            row["spearman_p_adjust_bh"] = adjusted_value
    return pd.DataFrame(rows)


def build_analysis_status(exercise_df: pd.DataFrame, min_group_size: int) -> dict[str, Any]:
    status = {
        "status": "ready",
        "min_group_size": min_group_size,
        "has_ai_group": False,
        "has_expert_group": False,
        "ai_n": 0,
        "expert_n": 0,
        "reason": "",
    }

    if exercise_df.empty or "source_type" not in exercise_df.columns:
        status["status"] = "insufficient_data"
        status["reason"] = "no_exercise_metrics"
        return status

    counts = exercise_df.groupby("source_type")["exercise_id"].nunique() if "exercise_id" in exercise_df.columns else exercise_df["source_type"].value_counts()
    ai_n = int(counts.get("AI", 0))
    expert_n = int(counts.get("Expert", 0))
    status["has_ai_group"] = ai_n > 0
    status["has_expert_group"] = expert_n > 0
    status["ai_n"] = ai_n
    status["expert_n"] = expert_n

    if ai_n == 0 or expert_n == 0:
        status["status"] = "insufficient_data"
        status["reason"] = "missing_source_group"
    elif ai_n < min_group_size or expert_n < min_group_size:
        status["status"] = "insufficient_data"
        status["reason"] = "group_below_min_sample_size"

    return status


def attach_pair_metadata(exercise_df: pd.DataFrame, pair_df: pd.DataFrame) -> pd.DataFrame:
    if exercise_df.empty or pair_df.empty:
        return exercise_df.copy()

    mapping_rows: list[dict[str, Any]] = []
    for _, row in pair_df.iterrows():
        pair_id = row.get("pair_id", "")
        ai_exercise_id = row.get("ai_exercise_id", "")
        reference_exercise_id = row.get("reference_exercise_id", "")
        if ai_exercise_id:
            mapping_rows.append({"exercise_id": ai_exercise_id, "pair_id": pair_id})
        if reference_exercise_id:
            mapping_rows.append({"exercise_id": reference_exercise_id, "pair_id": pair_id})

    mapping_df = pd.DataFrame(mapping_rows).drop_duplicates(subset=["exercise_id"])
    if mapping_df.empty:
        return exercise_df.copy()
    return exercise_df.merge(mapping_df, on="exercise_id", how="left")


def apply_fairness_filter(
    exercise_df: pd.DataFrame,
    fairness_df: pd.DataFrame,
    *,
    eligible_only: bool,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    summary = {
        "eligible_only": eligible_only,
        "fairness_audit_loaded": False,
        "eligible_pair_count": 0,
        "ineligible_pair_count": 0,
        "rows_before_filter": int(len(exercise_df)),
        "rows_after_filter": int(len(exercise_df)),
    }

    if exercise_df.empty or fairness_df.empty or "pair_id" not in exercise_df.columns or "pair_id" not in fairness_df.columns:
        summary["filter_applied"] = False
        summary["reason"] = "fairness_audit_missing_or_unmergeable"
        return exercise_df.copy(), summary

    fairness_cols = ["pair_id", "human_eval_eligible", "exclude_reason"]
    fairness = fairness_df[fairness_cols].drop_duplicates(subset=["pair_id"]).copy()
    merged = exercise_df.merge(fairness, on="pair_id", how="left")
    merged["human_eval_eligible"] = (
        merged["human_eval_eligible"].astype(str).str.strip().str.lower().map({"true": True, "false": False})
    )

    summary["fairness_audit_loaded"] = True
    summary["eligible_pair_count"] = int(fairness["human_eval_eligible"].astype(str).str.strip().str.lower().eq("true").sum())
    summary["ineligible_pair_count"] = int(fairness["human_eval_eligible"].astype(str).str.strip().str.lower().eq("false").sum())

    if eligible_only:
        merged = merged[merged["human_eval_eligible"] == True].copy()  # noqa: E712
        summary["filter_applied"] = True
        summary["reason"] = "eligible_pairs_only"
    else:
        summary["filter_applied"] = False
        summary["reason"] = "all_pairs_included"

    summary["rows_after_filter"] = int(len(merged))
    summary["pair_count_after_filter"] = int(merged["pair_id"].dropna().nunique()) if "pair_id" in merged.columns else 0
    return merged, summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--use-curated", action="store_true")
    parser.add_argument("--exercise-metrics", default="results/exercise_metrics.v1.csv")
    parser.add_argument("--correctness-metrics", default="results/exercise_correctness_metrics.v1.csv")
    parser.add_argument("--pair-metrics", default="results/pair_similarity_metrics.v1.csv")
    parser.add_argument("--fairness-audit", default=str(CURATED_FAIRNESS_AUDIT))
    parser.add_argument("--human-merged-dir", default="results/human_eval_merged")
    parser.add_argument("--output-dir", default="results/statistics")
    parser.add_argument("--min-group-size", type=int, default=2)
    parser.add_argument(
        "--eligible-only",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use only fairness-eligible matched pairs for the main AI vs Expert comparison.",
    )
    parser.add_argument(
        "--enable-legacy-human-correlations",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Enable legacy auto-vs-human correlation outputs from archived human_eval_merged tables.",
    )
    args = parser.parse_args()

    if args.use_curated:
        args.exercise_metrics = str(CURATED_DIR / "exercise_metrics.curated.v1.csv")
        args.correctness_metrics = str(CURATED_CORRECTNESS_METRICS)
        args.pair_metrics = str(CURATED_DIR / "pair_similarity_metrics.curated.v1.csv")
        args.fairness_audit = str(CURATED_FAIRNESS_AUDIT)
        args.human_merged_dir = str(CURATED_DIR / "human_eval_merged")
        args.output_dir = str(CURATED_DIR / "statistics")

    output_dir = Path(args.output_dir)
    ensure_dir(output_dir)

    exercise_df_raw = load_exercise_metrics(Path(args.exercise_metrics))
    correctness_df_raw = prepare_correctness_df(load_correctness_metrics(Path(args.correctness_metrics)))
    pair_df = load_pair_metrics(Path(args.pair_metrics))
    fairness_df = load_table(Path(args.fairness_audit))
    human_dir = Path(args.human_merged_dir)

    exercise_df_with_pairs = attach_pair_metadata(exercise_df_raw, pair_df)
    exercise_df, fairness_summary = apply_fairness_filter(
        exercise_df_with_pairs,
        fairness_df,
        eligible_only=args.eligible_only,
    )
    correctness_df, correctness_fairness_summary = apply_fairness_filter(
        correctness_df_raw,
        fairness_df,
        eligible_only=args.eligible_only,
    )
    evaluable_correctness_df = filter_evaluable_correctness(correctness_df)

    write_dataframe(
        build_sample_size_summary(
            exercise_df_raw,
            pair_df,
            analysis_exercise_df=exercise_df,
            correctness_df=evaluable_correctness_df,
        ),
        output_dir / "sample_size_summary.v1.csv",
    )

    status_doc = build_analysis_status(exercise_df, args.min_group_size)
    status_doc["eligible_only"] = args.eligible_only
    status_doc["fairness_summary"] = fairness_summary
    status_doc["correctness_fairness_summary"] = correctness_fairness_summary
    status_doc["correctness_rows_raw"] = int(len(correctness_df_raw))
    status_doc["correctness_rows_analysis"] = int(len(correctness_df))
    status_doc["correctness_rows_evaluable"] = int(len(evaluable_correctness_df))
    if not evaluable_correctness_df.empty and "correctness_status" in evaluable_correctness_df.columns:
        status_doc["correctness_status_counts"] = (
            evaluable_correctness_df["correctness_status"].astype(str).str.strip().str.lower().value_counts().to_dict()
        )
    else:
        status_doc["correctness_status_counts"] = {}
    status_doc["legacy_human_correlations_enabled"] = args.enable_legacy_human_correlations
    write_json(status_doc, output_dir / "analysis_status.v1.json")

    if not exercise_df.empty:
        exercise_metric_cols = get_numeric_metric_columns(exercise_df, exclude=["human_eval_eligible"])
        write_dataframe(
            summarize_group(exercise_df, ["source_type"], exercise_metric_cols),
            output_dir / "descriptive_stats.by_source.v1.csv",
        )
        write_dataframe(
            summarize_group(exercise_df, ["topic", "source_type"], exercise_metric_cols),
            output_dir / "descriptive_stats.by_topic_and_source.v1.csv",
        )
        write_dataframe(
            summarize_group(exercise_df, ["difficulty", "source_type"], exercise_metric_cols),
            output_dir / "descriptive_stats.by_difficulty_and_source.v1.csv",
        )

        if status_doc["status"] == "ready":
            comparison_df = run_paired_group_comparison(exercise_df, exercise_metric_cols)
            write_dataframe(comparison_df, output_dir / "ttest.ai_vs_expert.v1.csv")
            chi_square_path = output_dir / "chi_square.ai_vs_expert.v1.csv"
            if chi_square_path.exists():
                chi_square_path.unlink()

    write_dataframe(
        correctness_status_summary(correctness_df, ["source_type"]),
        output_dir / "correctness_status.by_source.v1.csv",
    )
    write_dataframe(
        correctness_status_summary(correctness_df, ["topic", "source_type"]),
        output_dir / "correctness_status.by_topic_and_source.v1.csv",
    )

    if not evaluable_correctness_df.empty:
        correctness_metric_cols = [
            col
            for col in [
                "public_tests_passed",
                "public_tests_total",
                "hidden_tests_passed",
                "hidden_tests_total",
                "public_pass_rate",
                "hidden_pass_rate",
                "surface_checks_passed",
                "surface_checks_total",
                "shape_checks_passed",
                "behavior_checks_passed",
                "correctness_status_binary_pass",
                "correctness_status_binary_evaluable",
                "reference_solution_fully_valid",
                "required_packages_satisfied",
            ]
            if col in evaluable_correctness_df.columns
        ]

        write_dataframe(
            evaluable_correctness_df,
            output_dir / "exercise_correctness.evaluable_subset.v1.csv",
        )
        write_dataframe(
            summarize_group(evaluable_correctness_df, ["source_type"], correctness_metric_cols),
            output_dir / "correctness.descriptive_stats.by_source.v1.csv",
        )
        write_dataframe(
            summarize_group(evaluable_correctness_df, ["topic", "source_type"], correctness_metric_cols),
            output_dir / "correctness.descriptive_stats.by_topic_and_source.v1.csv",
        )
        write_dataframe(
            run_paired_group_comparison(evaluable_correctness_df, correctness_metric_cols),
            output_dir / "correctness.ttest.ai_vs_expert.v1.csv",
        )

    if not pair_df.empty:
        pair_metric_cols = get_numeric_metric_columns(pair_df)
        write_dataframe(
            summarize_group(pair_df, [], pair_metric_cols),
            output_dir / "pair_similarity.overall.v1.csv",
        )
        write_dataframe(
            summarize_group(pair_df, ["topic"], pair_metric_cols),
            output_dir / "pair_similarity.by_topic.v1.csv",
        )
        write_dataframe(
            summarize_group(pair_df, ["difficulty"], pair_metric_cols),
            output_dir / "pair_similarity.by_difficulty.v1.csv",
        )

    expert_corr_path = output_dir / "correlation.auto_vs_human.expert.v1.csv"
    student_corr_path = output_dir / "correlation.auto_vs_human.student.v1.csv"
    if args.enable_legacy_human_correlations and not exercise_df.empty and human_dir.exists():
        expert_by_exercise = load_table(human_dir / "expert_ratings_by_exercise.v1.csv")
        student_by_exercise = load_table(human_dir / "student_ratings_by_exercise.v1.csv")
        expert_corr_df = correlation_frame(exercise_df, expert_by_exercise, "expert")
        student_corr_df = correlation_frame(exercise_df, student_by_exercise, "student")
        if not expert_corr_df.empty:
            write_dataframe(expert_corr_df, expert_corr_path)
        elif expert_corr_path.exists():
            expert_corr_path.unlink()
        if not student_corr_df.empty:
            write_dataframe(student_corr_df, student_corr_path)
        elif student_corr_path.exists():
            student_corr_path.unlink()
    else:
        if expert_corr_path.exists():
            expert_corr_path.unlink()
        if student_corr_path.exists():
            student_corr_path.unlink()

    print(f"Analysis complete. Results saved to {output_dir}")


if __name__ == "__main__":
    main()

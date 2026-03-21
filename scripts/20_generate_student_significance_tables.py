from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

try:
    from statsmodels.stats.multitest import multipletests
except Exception:
    multipletests = None


ITEM_METRICS = [
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
]

AGGREGATION_KEYS = [
    "pair_id",
    "exercise_id",
    "source_type",
    "topic",
    "difficulty",
    "exercise_type",
]

DISPLAY_LABELS = {
    "task_goal_clarity": "Task Goal Clarity",
    "key_support": "Key Support",
    "course_relevance": "Course Relevance",
    "learning_help": "Learning Help",
    "info_load": "Information Load",
    "search_effort": "Search Effort",
    "active_engagement": "Active Engagement",
    "mental_effort": "Mental Effort",
    "item_mean_score": "Overall Item Score",
    "usability_mean_score": "Usability Mean",
    "cognitive_load_mean_score": "Cognitive Load Mean",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate significance test tables for student survey analysis.")
    parser.add_argument(
        "--input-csv",
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


def cohen_d(x: pd.Series, y: pd.Series) -> float | None:
    if len(x) < 2 or len(y) < 2:
        return None
    var_x = x.var(ddof=1)
    var_y = y.var(ddof=1)
    pooled_num = ((len(x) - 1) * var_x) + ((len(y) - 1) * var_y)
    pooled_den = len(x) + len(y) - 2
    if pooled_den <= 0:
        return None
    pooled_sd = math.sqrt(pooled_num / pooled_den) if pooled_num > 0 else 0.0
    if pooled_sd == 0:
        return None
    return (x.mean() - y.mean()) / pooled_sd


def cohen_dz(diff: pd.Series) -> float | None:
    values = diff.dropna().astype(float)
    if len(values) < 2:
        return None
    sd = values.std(ddof=1)
    if pd.isna(sd) or sd == 0:
        return None
    return float(values.mean() / sd)


def p_label(p_value: float | None) -> str:
    if p_value is None or math.isnan(p_value):
        return ""
    if p_value < 0.001:
        return "***"
    if p_value < 0.01:
        return "**"
    if p_value < 0.05:
        return "*"
    return "ns"


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


def coerce_bool(series: pd.Series) -> pd.Series:
    normalized = series.astype(str).str.strip().str.lower()
    return normalized.map({"true": True, "false": False}).fillna(False)


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
        working = working[coerce_bool(working["attention_check_passed"])].copy()

    if exclude_fast_flag and "participant_fast_flag_under_180s" in working.columns:
        working = working[~coerce_bool(working["participant_fast_flag_under_180s"])].copy()

    summary["rows_after_filter"] = int(len(working))
    summary["participants_after_filter"] = int(working["participant_id"].nunique())
    summary["exercises_after_filter"] = int(working["exercise_id"].nunique())
    return working, summary


def build_exercise_level_table(df: pd.DataFrame) -> pd.DataFrame:
    agg_spec: dict[str, object] = {
        "participant_id": pd.NamedAgg(column="participant_id", aggfunc="nunique"),
    }
    for metric in ITEM_METRICS:
        agg_spec[metric] = pd.NamedAgg(column=metric, aggfunc="mean")

    grouped = (
        df.groupby(AGGREGATION_KEYS, dropna=False)
        .agg(**agg_spec)
        .reset_index()
        .rename(columns={"participant_id": "student_rating_count"})
    )
    return grouped


def test_paired_groups(df: pd.DataFrame, metric: str, *, min_pairs: int = 2, min_pairs_topic: int | None = None) -> dict[str, object]:
    wide = (
        df[["pair_id", "source_type", metric]]
        .copy()
        .assign(**{metric: lambda frame: pd.to_numeric(frame[metric], errors="coerce")})
        .pivot(index="pair_id", columns="source_type", values=metric)
    )

    result: dict[str, object] = {
        "metric": metric,
        "metric_label": DISPLAY_LABELS.get(metric, metric),
        "n_pairs": 0,
        "mean_ai": None,
        "sd_ai": None,
        "mean_expert": None,
        "sd_expert": None,
        "mean_diff_ai_minus_expert": None,
        "paired_t_stat": None,
        "paired_t_p": None,
        "paired_t_sig": "",
        "wilcoxon_stat": None,
        "wilcoxon_p": None,
        "wilcoxon_sig": "",
        "cohen_dz_ai_minus_expert": None,
        "not_tested_small_n": False,
    }

    if not {"AI", "Expert"}.issubset(wide.columns):
        return result

    wide = wide.dropna(subset=["AI", "Expert"])
    if wide.empty:
        return result

    ai = pd.to_numeric(wide["AI"], errors="coerce").dropna()
    expert = pd.to_numeric(wide["Expert"], errors="coerce").dropna()
    if ai.empty or expert.empty:
        return result

    diff = ai - expert
    nonzero_diff = diff[diff != 0]

    result.update(
        {
            "n_pairs": int(len(wide)),
            "mean_ai": round(float(ai.mean()), 4),
            "sd_ai": round(float(ai.std(ddof=1)), 4) if ai.count() > 1 else None,
            "mean_expert": round(float(expert.mean()), 4),
            "sd_expert": round(float(expert.std(ddof=1)), 4) if expert.count() > 1 else None,
            "mean_diff_ai_minus_expert": round(float(diff.mean()), 4),
            "cohen_dz_ai_minus_expert": round(float(cohen_dz(diff)), 4) if cohen_dz(diff) is not None else None,
        }
    )

    required_pairs = min_pairs_topic if min_pairs_topic is not None else min_pairs
    if len(wide) < required_pairs:
        result["not_tested_small_n"] = True
        return result

    if len(wide) >= min_pairs:
        t_stat, t_p = stats.ttest_rel(ai, expert, nan_policy="omit")
        if not pd.isna(t_p):
            result["paired_t_stat"] = round(float(t_stat), 4)
            result["paired_t_p"] = round(float(t_p), 6)
            result["paired_t_sig"] = p_label(float(t_p))

    if len(nonzero_diff) >= 3:
        try:
            wilcoxon_stat, wilcoxon_p = stats.wilcoxon(nonzero_diff)
            if not pd.isna(wilcoxon_p):
                result["wilcoxon_stat"] = round(float(wilcoxon_stat), 4)
                result["wilcoxon_p"] = round(float(wilcoxon_p), 6)
                result["wilcoxon_sig"] = p_label(float(wilcoxon_p))
        except ValueError:
            pass

    return result


def build_overall_tests(df: pd.DataFrame) -> pd.DataFrame:
    rows = [test_paired_groups(df, metric) for metric in ITEM_METRICS]
    result = pd.DataFrame(rows)
    if result.empty:
        return result

    paired_mask = result["paired_t_p"].notna()
    if paired_mask.any():
        adjusted = adjust_pvalues(result.loc[paired_mask, "paired_t_p"].astype(float).tolist())
        result.loc[paired_mask, "paired_t_p_adjust_bh"] = adjusted
        result.loc[paired_mask, "paired_t_sig"] = [p_label(value) for value in adjusted]
    else:
        result["paired_t_p_adjust_bh"] = np.nan

    wilcoxon_mask = result["wilcoxon_p"].notna()
    if wilcoxon_mask.any():
        adjusted = adjust_pvalues(result.loc[wilcoxon_mask, "wilcoxon_p"].astype(float).tolist())
        result.loc[wilcoxon_mask, "wilcoxon_p_adjust_bh"] = adjusted
        result.loc[wilcoxon_mask, "wilcoxon_sig"] = [p_label(value) for value in adjusted]
    else:
        result["wilcoxon_p_adjust_bh"] = np.nan
    return result


def build_topic_tests(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for topic, group in sorted(df.groupby("topic", dropna=False), key=lambda x: str(x[0])):
        for metric in ITEM_METRICS:
            row = test_paired_groups(group, metric, min_pairs_topic=3)
            row["topic"] = topic
            rows.append(row)
    if not rows:
        return pd.DataFrame()

    result = pd.DataFrame(rows)
    result["paired_t_p_adjust_bh_topic"] = np.nan
    result["wilcoxon_p_adjust_bh_topic"] = np.nan

    for topic, topic_index in result.groupby("topic", dropna=False).groups.items():
        topic_rows = result.loc[topic_index]
        paired_mask = topic_rows["paired_t_p"].notna()
        if paired_mask.any():
            adjusted = adjust_pvalues(topic_rows.loc[paired_mask, "paired_t_p"].astype(float).tolist())
            result.loc[topic_rows.loc[paired_mask].index, "paired_t_p_adjust_bh_topic"] = adjusted

        wilcoxon_mask = topic_rows["wilcoxon_p"].notna()
        if wilcoxon_mask.any():
            adjusted = adjust_pvalues(topic_rows.loc[wilcoxon_mask, "wilcoxon_p"].astype(float).tolist())
            result.loc[topic_rows.loc[wilcoxon_mask].index, "wilcoxon_p_adjust_bh_topic"] = adjusted

    result.loc[result["paired_t_p_adjust_bh_topic"].notna(), "paired_t_sig"] = result.loc[
        result["paired_t_p_adjust_bh_topic"].notna(), "paired_t_p_adjust_bh_topic"
    ].map(p_label)
    result.loc[result["wilcoxon_p_adjust_bh_topic"].notna(), "wilcoxon_sig"] = result.loc[
        result["wilcoxon_p_adjust_bh_topic"].notna(), "wilcoxon_p_adjust_bh_topic"
    ].map(p_label)

    column_order = ["topic"] + [col for col in result.columns if col != "topic"]
    return result[column_order]


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    raw_df = pd.read_csv(args.input_csv)
    filtered_df, filter_summary = filter_master(
        raw_df,
        exclude_attention_fail=args.exclude_attention_fail,
        exclude_fast_flag=args.exclude_fast_flag,
    )
    df = build_exercise_level_table(filtered_df)

    exercise_level_path = args.output_dir / "significance_exercise_level_aggregates.csv"
    df.to_csv(exercise_level_path, index=False, encoding="utf-8-sig")

    overall_df = build_overall_tests(df)
    overall_path = args.output_dir / "significance_ai_vs_expert_item_metrics.csv"
    overall_df.to_csv(overall_path, index=False, encoding="utf-8-sig")

    topic_df = build_topic_tests(df)
    topic_path = args.output_dir / "significance_ai_vs_expert_by_topic.csv"
    topic_df.to_csv(topic_path, index=False, encoding="utf-8-sig")

    manifest = {
        "input_csv": str(args.input_csv.resolve()),
        "output_dir": str(args.output_dir.resolve()),
        "analysis_unit": "pair_level_exercise_mean",
        "filters": {
            "exclude_attention_fail": args.exclude_attention_fail,
            "exclude_fast_flag": args.exclude_fast_flag,
        },
        "topic_level_min_pairs": 3,
        "filter_summary": filter_summary,
        "generated_tables": [
            exercise_level_path.name,
            overall_path.name,
            topic_path.name,
        ],
    }
    (args.output_dir / "significance_outputs_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

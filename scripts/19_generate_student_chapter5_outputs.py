from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from thesis_plot import AI_COLOR, AUX_COLOR, EXPERT_COLOR, apply_axis_style, heatmap, save_figure, set_tick_fonts, setup_thesis_style


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

BATCH_METRICS = [
    "overall_usefulness",
    "overall_ease",
    "continued_use_intention",
    "overall_quality",
    "batch_acceptance_mean",
    "rating_time_seconds",
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
    "overall_usefulness": "Overall Usefulness",
    "overall_ease": "Overall Ease",
    "continued_use_intention": "Continued Use",
    "overall_quality": "Overall Quality",
    "batch_acceptance_mean": "Batch Acceptance Mean",
    "rating_time_seconds": "Completion Time (s)",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Chapter 5 descriptive tables and figures from student master table.")
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=Path("results/student_subsets/student_analysis_master_30.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/student_subsets/chapter5_outputs"),
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


def summarise(df: pd.DataFrame, group_cols: list[str], metric_cols: list[str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    grouped = df.groupby(group_cols, dropna=False)
    for keys, group in grouped:
        if not isinstance(keys, tuple):
            keys = (keys,)
        base = dict(zip(group_cols, keys))
        for metric in metric_cols:
            series = pd.to_numeric(group[metric], errors="coerce").dropna()
            rows.append(
                {
                    **base,
                    "metric": metric,
                    "metric_label": DISPLAY_LABELS.get(metric, metric),
                    "n": int(series.count()),
                    "mean": round(float(series.mean()), 4) if not series.empty else None,
                    "std": round(float(series.std(ddof=1)), 4) if series.count() > 1 else None,
                    "median": round(float(series.median()), 4) if not series.empty else None,
                    "min": round(float(series.min()), 4) if not series.empty else None,
                    "max": round(float(series.max()), 4) if not series.empty else None,
                }
            )
    return pd.DataFrame(rows)


def save_table(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def prepare_item_plot_df(df: pd.DataFrame) -> pd.DataFrame:
    plot_df = df.melt(
        id_vars=["participant_id", "source_type", "topic", "exercise_type"],
        value_vars=[
            "task_goal_clarity",
            "key_support",
            "course_relevance",
            "learning_help",
            "active_engagement",
            "mental_effort",
        ],
        var_name="metric",
        value_name="score",
    )
    plot_df["score"] = pd.to_numeric(plot_df["score"], errors="coerce")
    plot_df["metric_label"] = plot_df["metric"].map(DISPLAY_LABELS)
    return plot_df.dropna(subset=["score"])


def plot_source_metric_bars(df: pd.DataFrame, path: Path) -> None:
    order = [
        "Task Goal Clarity",
        "Key Support",
        "Course Relevance",
        "Learning Help",
        "Active Engagement",
        "Mental Effort",
    ]
    fig, ax = plt.subplots(figsize=(6.8, 4.4))
    sns.barplot(
        data=df,
        x="metric_label",
        y="score",
        hue="source_type",
        estimator="mean",
        errorbar="sd",
        order=order,
        palette={"AI": AI_COLOR, "Expert": EXPERT_COLOR},
        edgecolor="black",
        linewidth=0.5,
        ax=ax,
    )
    ax.legend(frameon=False, prop={"family": "Times New Roman", "size": 9})
    set_tick_fonts(ax, rotation=20, ha="right")
    apply_axis_style(ax, ylabel="Mean Score")
    fig.tight_layout()
    save_figure(fig, path)
    plt.close(fig)


def plot_item_mean_box(df: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(5.8, 4.2))
    sns.boxplot(
        data=df,
        x="source_type",
        y="item_mean_score",
        hue="source_type",
        palette={"AI": AI_COLOR, "Expert": EXPERT_COLOR},
        linewidth=1.0,
        dodge=False,
        ax=ax,
    )
    sns.stripplot(
        data=df,
        x="source_type",
        y="item_mean_score",
        color=AUX_COLOR,
        alpha=0.35,
        jitter=0.18,
        size=3,
        ax=ax,
    )
    if ax.legend_ is not None:
        ax.legend_.remove()
    set_tick_fonts(ax)
    apply_axis_style(ax, ylabel="Overall Item Score")
    fig.tight_layout()
    save_figure(fig, path)
    plt.close(fig)


def plot_topic_source_heatmap(df: pd.DataFrame, path: Path) -> None:
    heat_df = (
        df.groupby(["topic", "source_type"], dropna=False)["item_mean_score"]
        .mean()
        .reset_index()
        .pivot(index="topic", columns="source_type", values="item_mean_score")
        .sort_index()
    )
    fig, ax = plt.subplots(figsize=(5.8, 4.8))
    im = heatmap(
        ax,
        heat_df.to_numpy(),
        row_labels=list(heat_df.index),
        col_labels=list(heat_df.columns),
        cmap="Blues",
        value_decimals=2,
        vmin=1,
        vmax=5,
    )
    cbar = fig.colorbar(im)
    cbar.ax.tick_params(labelsize=9, width=0.8)
    fig.tight_layout()
    save_figure(fig, path)
    plt.close(fig)


def plot_batch_metrics(df: pd.DataFrame, path: Path) -> None:
    batch_plot = df.melt(
        id_vars=["participant_id", "package_id"],
        value_vars=["overall_usefulness", "overall_ease", "continued_use_intention", "overall_quality"],
        var_name="metric",
        value_name="score",
    )
    batch_plot["score"] = pd.to_numeric(batch_plot["score"], errors="coerce")
    batch_plot = batch_plot.dropna(subset=["score"])
    batch_plot["metric_label"] = batch_plot["metric"].map(DISPLAY_LABELS)
    order = ["Overall Usefulness", "Overall Ease", "Continued Use", "Overall Quality"]
    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    sns.barplot(
        data=batch_plot,
        x="metric_label",
        y="score",
        estimator="mean",
        errorbar="sd",
        color=AI_COLOR,
        order=order,
        edgecolor="black",
        linewidth=0.5,
        ax=ax,
    )
    set_tick_fonts(ax, rotation=15, ha="right")
    apply_axis_style(ax, ylabel="Mean Score")
    fig.tight_layout()
    save_figure(fig, path)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir
    tables_dir = output_dir / "tables"
    figures_dir = output_dir / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    setup_thesis_style()

    raw_df = pd.read_csv(args.input_csv)
    df, filter_summary = filter_master(
        raw_df,
        exclude_attention_fail=args.exclude_attention_fail,
        exclude_fast_flag=args.exclude_fast_flag,
    )

    for col in ITEM_METRICS + BATCH_METRICS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    item_df = df.copy()
    participant_df = df.drop_duplicates(subset=["participant_id"]).copy()

    sample_overview = pd.DataFrame(
        [
            {"section": "participants", "value": participant_df["participant_id"].nunique()},
            {"section": "item_rows", "value": len(item_df)},
            {"section": "packages", "value": participant_df["package_id"].nunique()},
            {"section": "unique_exercises", "value": item_df["blind_exercise_id"].nunique()},
            {"section": "ai_item_rows", "value": int((item_df["source_type"] == "AI").sum())},
            {"section": "expert_item_rows", "value": int((item_df["source_type"] == "Expert").sum())},
        ]
    )
    save_table(sample_overview, tables_dir / "sample_overview.csv")

    item_by_source = summarise(item_df, ["source_type"], ITEM_METRICS)
    save_table(item_by_source, tables_dir / "item_metrics_by_source.csv")

    item_by_topic_source = summarise(item_df, ["topic", "source_type"], ITEM_METRICS)
    save_table(item_by_topic_source, tables_dir / "item_metrics_by_topic_and_source.csv")

    item_by_exercise_type_source = summarise(item_df, ["exercise_type", "source_type"], ITEM_METRICS)
    save_table(item_by_exercise_type_source, tables_dir / "item_metrics_by_exercise_type_and_source.csv")

    batch_summary = summarise(participant_df, ["package_id"], BATCH_METRICS)
    save_table(batch_summary, tables_dir / "batch_metrics_by_package.csv")

    batch_overall = summarise(participant_df.assign(group="All"), ["group"], BATCH_METRICS)
    save_table(batch_overall, tables_dir / "batch_metrics_overall.csv")

    plot_df = prepare_item_plot_df(item_df)
    plot_source_metric_bars(plot_df, figures_dir / "bar_student_metrics_ai_vs_expert.png")
    plot_item_mean_box(item_df, figures_dir / "box_item_mean_by_source.png")
    plot_topic_source_heatmap(item_df, figures_dir / "heatmap_item_mean_by_topic_and_source.png")
    plot_batch_metrics(participant_df, figures_dir / "bar_batch_metrics_overall.png")

    manifest = {
        "input_csv": str(args.input_csv.resolve()),
        "tables_dir": str(tables_dir.resolve()),
        "figures_dir": str(figures_dir.resolve()),
        "filters": {
            "exclude_attention_fail": args.exclude_attention_fail,
            "exclude_fast_flag": args.exclude_fast_flag,
        },
        "filter_summary": filter_summary,
        "generated_tables": [
            "sample_overview.csv",
            "item_metrics_by_source.csv",
            "item_metrics_by_topic_and_source.csv",
            "item_metrics_by_exercise_type_and_source.csv",
            "batch_metrics_by_package.csv",
            "batch_metrics_overall.csv",
        ],
        "generated_figures": [
            "bar_student_metrics_ai_vs_expert.png",
            "box_item_mean_by_source.png",
            "heatmap_item_mean_by_topic_and_source.png",
            "bar_batch_metrics_overall.png",
        ],
    }
    (output_dir / "chapter5_outputs_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

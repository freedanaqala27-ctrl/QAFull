from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    import seaborn as sns
except Exception:
    sns = None

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from thesis_plot import AI_COLOR, AUX_COLOR, EXPERT_COLOR, apply_axis_style, heatmap, save_figure, set_tick_fonts, setup_thesis_style

CURATED_DIR = PROJECT_ROOT / "results" / "curated"
CURATED_STATS_DIR = CURATED_DIR / "statistics"

DISPLAY_NAME_MAP = {
    "instruction_metrics.instruction_completeness_ratio": "Instruction Completeness",
    "instruction_metrics.flesch_reading_ease": "Reading Ease",
    "instruction_metrics.flesch_kincaid_grade": "FK Grade",
    "structure_metrics.structure_completeness_ratio": "Structure Completeness",
    "structure_metrics.structure_score_weighted": "Weighted Structure Score",
    "code_quality_metrics.starter_code_mi": "Starter Code Maintainability",
    "code_quality_metrics.solution_code_mi": "Solution Code Maintainability",
    "code_quality_metrics.starter_code_mccabe_max": "Starter Code Complexity",
    "code_quality_metrics.solution_code_mccabe_max": "Solution Code Complexity",
    "tfidf_cosine_instruction_only": "Instruction TF-IDF Cosine",
    "tfidf_cosine_full_text": "Full-Text TF-IDF Cosine",
    "rougeL_f1_instruction_only": "ROUGE-L F1",
    "meteor_instruction_only": "METEOR",
    "bertscore_f1_instruction_only": "BERTScore F1",
}

EXERCISE_METRICS = [
    "instruction_metrics.instruction_completeness_ratio",
    "instruction_metrics.flesch_reading_ease",
    "instruction_metrics.flesch_kincaid_grade",
    "structure_metrics.structure_completeness_ratio",
    "structure_metrics.structure_score_weighted",
    "code_quality_metrics.starter_code_mi",
    "code_quality_metrics.solution_code_mi",
    "code_quality_metrics.starter_code_mccabe_max",
    "code_quality_metrics.solution_code_mccabe_max",
]

BAR_METRIC_GROUPS = {
    "bar_ai_vs_expert": {
        "metrics": [
            "instruction_metrics.instruction_completeness_ratio",
            "structure_metrics.structure_completeness_ratio",
            "structure_metrics.structure_score_weighted",
        ],
        "ylabel": "Mean Ratio / Score",
    },
    "bar_ai_vs_expert_readability": {
        "metrics": [
            "instruction_metrics.flesch_reading_ease",
            "instruction_metrics.flesch_kincaid_grade",
        ],
        "ylabel": "Mean Readability Value",
    },
    "bar_ai_vs_expert_code_quality": {
        "metrics": [
            "code_quality_metrics.starter_code_mi",
            "code_quality_metrics.starter_code_mccabe_max",
        ],
        "ylabel": "Mean Code Metric Value",
    },
}

PAIR_METRICS = [
    "tfidf_cosine_instruction_only",
    "tfidf_cosine_full_text",
    "rougeL_f1_instruction_only",
    "meteor_instruction_only",
    "bertscore_f1_instruction_only",
]

CORRECTNESS_RATE_LABELS = {
    "rate_pass": "Pass Rate",
    "rate_not_evaluable": "Not-Evaluable Rate",
}


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def load_json_doc(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def pretty_name(metric: str) -> str:
    return DISPLAY_NAME_MAP.get(metric, metric)


def select_metrics(df: pd.DataFrame, candidates: list[str]) -> list[str]:
    selected: list[str] = []
    for metric in candidates:
        if metric not in df.columns:
            continue
        series = pd.to_numeric(df[metric], errors="coerce")
        if series.notna().any():
            selected.append(metric)
    return selected


def set_style() -> None:
    setup_thesis_style()


def save_bar_ai_vs_expert(
    df: pd.DataFrame,
    figures_dir: Path,
    tables_dir: Path,
    *,
    filename_base: str,
    metric_candidates: list[str],
    ylabel: str,
) -> None:
    metrics = select_metrics(df, metric_candidates)
    if df.empty or not metrics or "source_type" not in df.columns:
        return

    summary = (
        df.groupby("source_type")[metrics]
        .mean(numeric_only=True)
        .reset_index()
        .melt(id_vars="source_type", var_name="metric", value_name="mean_value")
    )
    summary["metric_label"] = summary["metric"].map(pretty_name)
    summary.to_csv(tables_dir / f"{filename_base}.source_means.csv", index=False)

    fig, ax = plt.subplots(figsize=(6.8, 4.4))
    if sns is not None:
        sns.barplot(
            data=summary,
            x="metric_label",
            y="mean_value",
            hue="source_type",
            palette={"AI": AI_COLOR, "Expert": EXPERT_COLOR},
            edgecolor="black",
            linewidth=0.5,
            ax=ax,
        )
    else:
        pivoted = summary.pivot(index="metric_label", columns="source_type", values="mean_value").fillna(0)
        pivoted.plot(kind="bar", ax=ax, color=[AI_COLOR, EXPERT_COLOR], edgecolor="black", linewidth=0.5)
    ax.legend(frameon=False, prop={"family": "Times New Roman", "size": 9})
    set_tick_fonts(ax, rotation=25, ha="right")
    apply_axis_style(ax, ylabel=ylabel)
    fig.tight_layout()
    save_figure(fig, figures_dir / f"{filename_base}.png")
    plt.close(fig)


def save_boxplot_metrics(df: pd.DataFrame, figures_dir: Path, tables_dir: Path) -> None:
    metrics = select_metrics(df, EXERCISE_METRICS)
    if df.empty or not metrics or "source_type" not in df.columns:
        return

    melted = df[["source_type"] + metrics].melt(id_vars="source_type", var_name="metric", value_name="value")
    melted["metric_label"] = melted["metric"].map(pretty_name)
    melted.to_csv(tables_dir / "boxplot_metrics.data.csv", index=False)

    fig, ax = plt.subplots(figsize=(6.8, 4.4))
    if sns is not None:
        sns.boxplot(
            data=melted,
            x="metric_label",
            y="value",
            hue="source_type",
            palette={"AI": AI_COLOR, "Expert": EXPERT_COLOR},
            linewidth=1.0,
            ax=ax,
        )
    else:
        melted.boxplot(column="value", by="metric_label", ax=ax, rot=25)
        fig.suptitle("")
    ax.legend(frameon=False, prop={"family": "Times New Roman", "size": 9})
    set_tick_fonts(ax, rotation=25, ha="right")
    apply_axis_style(ax, ylabel="Metric Value")
    fig.tight_layout()
    save_figure(fig, figures_dir / "boxplot_metrics.png")
    plt.close(fig)


def save_heatmap(df: pd.DataFrame, figures_dir: Path, tables_dir: Path) -> None:
    metrics = select_metrics(df, EXERCISE_METRICS)
    if df.empty or len(metrics) < 2:
        return

    corr = df[metrics].corr(method="spearman", numeric_only=True)
    corr.index = [pretty_name(metric) for metric in corr.index]
    corr.columns = [pretty_name(metric) for metric in corr.columns]
    corr.to_csv(tables_dir / "heatmap_correlations.matrix.csv")

    fig, ax = plt.subplots(figsize=(6.4, 5.2))
    im = heatmap(
        ax,
        corr.to_numpy(),
        row_labels=list(corr.index),
        col_labels=list(corr.columns),
        cmap="Blues",
        value_decimals=2,
        vmin=-1,
        vmax=1,
    )
    cbar = fig.colorbar(im)
    cbar.ax.tick_params(labelsize=9, width=0.8)
    fig.tight_layout()
    save_figure(fig, figures_dir / "heatmap_correlations.png")
    plt.close(fig)


def save_topic_comparison(df: pd.DataFrame, figures_dir: Path, tables_dir: Path) -> None:
    metric = "instruction_metrics.instruction_completeness_ratio"
    if df.empty or metric not in df.columns or "topic" not in df.columns or "source_type" not in df.columns:
        return

    summary = (
        df.groupby(["topic", "source_type"])[metric]
        .mean()
        .reset_index()
        .rename(columns={metric: "mean_value"})
    )
    summary["metric_label"] = pretty_name(metric)
    summary.to_csv(tables_dir / "topic_comparison.data.csv", index=False)

    fig, ax = plt.subplots(figsize=(6.0, 4.2))
    if sns is not None:
        sns.barplot(
            data=summary,
            x="topic",
            y="mean_value",
            hue="source_type",
            palette={"AI": AI_COLOR, "Expert": EXPERT_COLOR},
            edgecolor="black",
            linewidth=0.5,
            ax=ax,
        )
    else:
        summary.pivot(index="topic", columns="source_type", values="mean_value").plot(
            kind="bar",
            ax=ax,
            color=[AI_COLOR, EXPERT_COLOR],
            edgecolor="black",
            linewidth=0.5,
        )
    ax.legend(frameon=False, prop={"family": "Times New Roman", "size": 9})
    set_tick_fonts(ax)
    apply_axis_style(ax, ylabel=pretty_name(metric))
    fig.tight_layout()
    save_figure(fig, figures_dir / "topic_comparison.png")
    plt.close(fig)


def save_difficulty_comparison(df: pd.DataFrame, figures_dir: Path, tables_dir: Path) -> None:
    metric = "instruction_metrics.instruction_completeness_ratio"
    if df.empty or metric not in df.columns or "difficulty" not in df.columns or "source_type" not in df.columns:
        return

    summary = (
        df.groupby(["difficulty", "source_type"])[metric]
        .mean()
        .reset_index()
        .rename(columns={metric: "mean_value"})
    )
    summary["metric_label"] = pretty_name(metric)
    summary.to_csv(tables_dir / "difficulty_comparison.data.csv", index=False)

    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    if sns is not None:
        sns.barplot(
            data=summary,
            x="difficulty",
            y="mean_value",
            hue="source_type",
            palette={"AI": AI_COLOR, "Expert": EXPERT_COLOR},
            edgecolor="black",
            linewidth=0.5,
            ax=ax,
        )
    else:
        summary.pivot(index="difficulty", columns="source_type", values="mean_value").plot(
            kind="bar",
            ax=ax,
            color=[AI_COLOR, EXPERT_COLOR],
            edgecolor="black",
            linewidth=0.5,
        )
    ax.legend(frameon=False, prop={"family": "Times New Roman", "size": 9})
    set_tick_fonts(ax, rotation=20, ha="right")
    apply_axis_style(ax, ylabel=pretty_name(metric))
    fig.tight_layout()
    save_figure(fig, figures_dir / "difficulty_comparison.png")
    plt.close(fig)


def save_pair_similarity_boxplot(df: pd.DataFrame, figures_dir: Path, tables_dir: Path) -> None:
    metrics = select_metrics(df, PAIR_METRICS)
    if df.empty or not metrics:
        return

    melted = df[metrics].melt(var_name="metric", value_name="value").dropna()
    if melted.empty:
        return
    melted["metric_label"] = melted["metric"].map(pretty_name)
    melted.to_csv(tables_dir / "pair_similarity_boxplot.data.csv", index=False)

    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    if sns is not None:
        sns.boxplot(
            data=melted,
            x="metric_label",
            y="value",
            color=AI_COLOR,
            linewidth=1.0,
            ax=ax,
        )
    else:
        melted.boxplot(column="value", by="metric_label", ax=ax, rot=25)
        fig.suptitle("")
    set_tick_fonts(ax, rotation=25, ha="right")
    apply_axis_style(ax, ylabel="Similarity Score")
    fig.tight_layout()
    save_figure(fig, figures_dir / "pair_similarity_boxplot.png")
    plt.close(fig)


def save_pair_similarity_by_topic(df: pd.DataFrame, figures_dir: Path, tables_dir: Path) -> None:
    metric = "tfidf_cosine_instruction_only"
    if df.empty or metric not in df.columns or "topic" not in df.columns:
        return

    summary = df.groupby("topic")[metric].mean().reset_index().rename(columns={metric: "mean_value"})
    if summary.empty:
        return
    summary["topic"] = summary["topic"].astype(str)
    summary["metric_label"] = pretty_name(metric)
    summary.to_csv(tables_dir / "pair_similarity_by_topic.data.csv", index=False)

    fig, ax = plt.subplots(figsize=(5.8, 4.0))
    if sns is not None:
        sns.barplot(
            data=summary,
            x="topic",
            y="mean_value",
            color=AI_COLOR,
            edgecolor="black",
            linewidth=0.5,
            ax=ax,
        )
    else:
        ax.bar(summary["topic"], summary["mean_value"], color=AI_COLOR, edgecolor="black", linewidth=0.5)
    set_tick_fonts(ax)
    apply_axis_style(ax, ylabel=pretty_name(metric))
    fig.tight_layout()
    save_figure(fig, figures_dir / "pair_similarity_by_topic.png")
    plt.close(fig)


def save_correctness_pass_rate(df: pd.DataFrame, figures_dir: Path, tables_dir: Path) -> None:
    required = {"source_type", "correctness_status"}
    if df.empty or not required.issubset(df.columns):
        return

    grouped = (
        df.groupby("source_type")
        .agg(
            sample_size=("exercise_id", "count"),
            status_pass=("correctness_status", lambda s: int((s == "pass").sum())),
        )
        .reset_index()
    )
    grouped["status_not_evaluable"] = 0
    grouped["rate_pass"] = grouped["status_pass"] / grouped["sample_size"]
    grouped["rate_not_evaluable"] = 0.0
    grouped.to_csv(tables_dir / "correctness_pass_rate.summary.csv", index=False)

    summary = grouped[["source_type", "rate_pass", "rate_not_evaluable"]].copy()
    summary = summary.melt(id_vars="source_type", var_name="metric", value_name="rate")
    summary["metric_label"] = summary["metric"].map(CORRECTNESS_RATE_LABELS)
    summary.to_csv(tables_dir / "correctness_pass_rate.data.csv", index=False)

    fig, ax = plt.subplots(figsize=(5.8, 4.0))
    if sns is not None:
        sns.barplot(
            data=summary,
            x="metric_label",
            y="rate",
            hue="source_type",
            palette={"AI": AI_COLOR, "Expert": EXPERT_COLOR},
            edgecolor="black",
            linewidth=0.5,
            ax=ax,
        )
    else:
        pivoted = summary.pivot(index="metric_label", columns="source_type", values="rate").fillna(0)
        pivoted.plot(kind="bar", ax=ax, color=[AI_COLOR, EXPERT_COLOR], edgecolor="black", linewidth=0.5)
    ax.set_ylim(0, 1.0)
    ax.legend(frameon=False, prop={"family": "Times New Roman", "size": 9})
    set_tick_fonts(ax, rotation=0, ha="center")
    apply_axis_style(ax, ylabel="Rate")
    for patch in ax.patches:
        height = patch.get_height()
        ax.text(
            patch.get_x() + patch.get_width() / 2,
            height + 0.02,
            f"{height:.2f}",
            ha="center",
            va="bottom",
            fontsize=8,
            fontname="Times New Roman",
        )
    fig.tight_layout()
    save_figure(fig, figures_dir / "correctness_pass_rate.png")
    plt.close(fig)


def save_correctness_evaluable_subset(df: pd.DataFrame, figures_dir: Path, tables_dir: Path) -> None:
    required = {"pair_id", "topic", "exercise_type"}
    if df.empty or not required.issubset(df.columns):
        return

    pair_df = df.drop_duplicates(subset=["pair_id"])[["pair_id", "topic", "exercise_type"]].copy()
    if pair_df.empty:
        return

    summary = (
        pair_df.groupby(["topic", "exercise_type"])
        .size()
        .reset_index(name="pair_count")
        .sort_values(["topic", "exercise_type"])
    )
    summary.to_csv(tables_dir / "correctness_evaluable_subset.data.csv", index=False)

    summary["topic_label"] = summary.apply(lambda row: f"{row['topic']} ({row['exercise_type']})", axis=1)

    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    if sns is not None:
        sns.barplot(
            data=summary,
            x="topic_label",
            y="pair_count",
            color=AI_COLOR,
            edgecolor="black",
            linewidth=0.5,
            ax=ax,
        )
    else:
        ax.bar(summary["topic_label"], summary["pair_count"], color=AI_COLOR, edgecolor="black", linewidth=0.5)
    set_tick_fonts(ax, rotation=25, ha="right")
    apply_axis_style(ax, ylabel="Number of Evaluable Pairs")
    for idx, value in enumerate(summary["pair_count"].tolist()):
        ax.text(idx, value, str(int(value)), ha="center", va="bottom", fontsize=8, fontname="Times New Roman")
    fig.tight_layout()
    save_figure(fig, figures_dir / "correctness_evaluable_subset.png")
    plt.close(fig)


def save_correctness_full_coverage_overview(
    validation_manifest: dict[str, Any],
    correctness_manifest: dict[str, Any],
    analysis_status: dict[str, Any],
    figures_dir: Path,
    tables_dir: Path,
) -> None:
    if not validation_manifest or not correctness_manifest or not analysis_status:
        return

    num_exercises = int(correctness_manifest.get("num_exercises", 0) or 0)
    exec_ok = int(validation_manifest.get("status_counts", {}).get("exec_ok", 0) or 0)
    pass_count = int(correctness_manifest.get("correctness_status_counts", {}).get("pass", 0) or 0)
    solution_hits = int(correctness_manifest.get("overlay_coverage", {}).get("solution_overlay_hits", 0) or 0)

    eligible_pairs = int(analysis_status.get("correctness_fairness_summary", {}).get("eligible_pair_count", 0) or 0)
    pair_count_after_filter = int(
        analysis_status.get("correctness_fairness_summary", {}).get("pair_count_after_filter", 0) or 0
    )
    evaluable_rows = int(analysis_status.get("correctness_rows_evaluable", 0) or 0)
    evaluable_pairs = evaluable_rows // 2 if evaluable_rows else 0

    if num_exercises <= 0:
        return

    exercise_summary = pd.DataFrame(
        [
            {"stage": "Overlay Coverage", "count": solution_hits, "total": num_exercises},
            {"stage": "Executable References", "count": exec_ok, "total": num_exercises},
            {"stage": "Correctness Pass", "count": pass_count, "total": num_exercises},
        ]
    )
    exercise_summary["rate"] = exercise_summary["count"] / exercise_summary["total"]

    pair_total = eligible_pairs or pair_count_after_filter
    if pair_total <= 0:
        pair_total = 1
    pair_summary = pd.DataFrame(
        [
            {"stage": "Eligible Pairs", "count": pair_count_after_filter, "total": pair_total},
            {"stage": "Evaluable Pairs", "count": evaluable_pairs, "total": pair_total},
        ]
    )
    pair_summary["rate"] = pair_summary["count"] / pair_summary["total"]

    overview_table = pd.concat(
        [
            exercise_summary.assign(scope="exercise_level"),
            pair_summary.assign(scope="pair_level"),
        ],
        ignore_index=True,
    )
    overview_table.to_csv(tables_dir / "correctness_full_coverage_overview.data.csv", index=False)

    fig, axes = plt.subplots(1, 2, figsize=(8.8, 4.1), gridspec_kw={"width_ratios": [3, 2]})

    left = axes[0]
    left.bar(
        exercise_summary["stage"],
        exercise_summary["rate"],
        color=AUX_COLOR,
        edgecolor="black",
        linewidth=0.5,
    )
    left.set_ylim(0, 1.05)
    set_tick_fonts(left, rotation=20, ha="right")
    apply_axis_style(left, ylabel="Coverage Rate")
    left.set_title("Exercise-Level Coverage", fontname="Times New Roman", fontsize=10)
    for idx, row in exercise_summary.reset_index(drop=True).iterrows():
        left.text(
            idx,
            float(row["rate"]) + 0.02,
            f"{int(row['count'])}/{int(row['total'])}",
            ha="center",
            va="bottom",
            fontsize=8,
            fontname="Times New Roman",
        )

    right = axes[1]
    right.bar(
        pair_summary["stage"],
        pair_summary["rate"],
        color=AUX_COLOR,
        edgecolor="black",
        linewidth=0.5,
    )
    right.set_ylim(0, 1.05)
    set_tick_fonts(right, rotation=20, ha="right")
    apply_axis_style(right, ylabel="Coverage Rate")
    right.set_title("Pair-Level Fairness Subset", fontname="Times New Roman", fontsize=10)
    for idx, row in pair_summary.reset_index(drop=True).iterrows():
        right.text(
            idx,
            float(row["rate"]) + 0.02,
            f"{int(row['count'])}/{int(row['total'])}",
            ha="center",
            va="bottom",
            fontsize=8,
            fontname="Times New Roman",
        )

    fig.tight_layout()
    save_figure(fig, figures_dir / "correctness_full_coverage_overview.png")
    plt.close(fig)


def build_case_study_candidates(pair_df: pd.DataFrame, pair_records: list[dict[str, Any]]) -> pd.DataFrame:
    if pair_df.empty or "pair_id" not in pair_df.columns:
        return pd.DataFrame()

    metric = "tfidf_cosine_instruction_only" if "tfidf_cosine_instruction_only" in pair_df.columns else None
    if metric is None:
        numeric_cols = pair_df.select_dtypes(include="number").columns.tolist()
        if not numeric_cols:
            return pd.DataFrame()
        metric = numeric_cols[0]

    scored = pair_df[["pair_id", metric]].copy()
    scored[metric] = pd.to_numeric(scored[metric], errors="coerce")
    scored = scored.dropna().sort_values(metric).reset_index(drop=True)
    if scored.empty:
        return pd.DataFrame()

    candidate_indices = sorted(set([0, len(scored) // 2, len(scored) - 1]))
    selected = scored.iloc[candidate_indices].copy()

    record_index = {row["pair_id"]: row for row in pair_records if "pair_id" in row}
    rows: list[dict[str, Any]] = []
    for _, row in selected.iterrows():
        pair_record = record_index.get(row["pair_id"], {})
        reference_payload = pair_record.get("reference_payload", {})
        ai_payload = pair_record.get("ai_payload", {})
        band = "low"
        if row[metric] >= scored[metric].quantile(0.67):
            band = "high"
        elif row[metric] >= scored[metric].quantile(0.33):
            band = "medium"
        rows.append(
            {
                "pair_id": row["pair_id"],
                "similarity_band": band,
                "metric_name": metric,
                "metric_display_name": pretty_name(metric),
                "metric_value": float(row[metric]),
                "reference_exercise_id": pair_record.get("reference_exercise_id", ""),
                "ai_exercise_id": pair_record.get("ai_exercise_id", ""),
                "topic": pair_record.get("topic", ""),
                "difficulty": pair_record.get("difficulty", ""),
                "reference_title": reference_payload.get("title", ""),
                "ai_title": ai_payload.get("title", ""),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--use-curated", action="store_true")
    parser.add_argument("--exercise-metrics", default="results/exercise_metrics.v1.csv")
    parser.add_argument("--pair-metrics", default="results/pair_similarity_metrics.v1.csv")
    parser.add_argument("--final-pairs", default="results/final_pairs.v1.jsonl")
    parser.add_argument("--figures-dir", default="results/figures")
    parser.add_argument("--tables-dir", default="results/tables")
    parser.add_argument("--correctness-status-by-source", default="results/statistics/correctness_status.by_source.v1.csv")
    parser.add_argument("--correctness-evaluable-subset", default="results/statistics/exercise_correctness.evaluable_subset.v1.csv")
    parser.add_argument("--reference-validation-manifest", default="results/reference_solution_validation_manifest.v1.json")
    parser.add_argument("--correctness-manifest", default="results/exercise_correctness_manifest.v1.json")
    parser.add_argument("--analysis-status", default="results/statistics/analysis_status.v1.json")
    args = parser.parse_args()

    if args.use_curated:
        args.exercise_metrics = str(CURATED_DIR / "exercise_metrics.curated.v1.csv")
        args.pair_metrics = str(CURATED_DIR / "pair_similarity_metrics.curated.v1.csv")
        args.final_pairs = str(CURATED_DIR / "final_pairs.curated.v1.jsonl")
        args.figures_dir = str(CURATED_DIR / "figures")
        args.tables_dir = str(CURATED_DIR / "tables")
        args.correctness_status_by_source = str(CURATED_STATS_DIR / "correctness_status.by_source.v1.csv")
        args.correctness_evaluable_subset = str(CURATED_STATS_DIR / "exercise_correctness.evaluable_subset.v1.csv")
        args.reference_validation_manifest = str(CURATED_DIR / "reference_solution_validation_manifest.curated.v1.json")
        args.correctness_manifest = str(CURATED_DIR / "exercise_correctness_manifest.curated.v1.json")
        args.analysis_status = str(CURATED_STATS_DIR / "analysis_status.v1.json")

    figures_dir = Path(args.figures_dir)
    tables_dir = Path(args.tables_dir)
    ensure_dir(figures_dir)
    ensure_dir(tables_dir)
    set_style()

    exercise_df = load_csv(Path(args.exercise_metrics))
    pair_df = load_csv(Path(args.pair_metrics))
    pair_records = load_jsonl(Path(args.final_pairs))
    correctness_status_by_source_df = load_csv(Path(args.correctness_status_by_source))
    correctness_evaluable_subset_df = load_csv(Path(args.correctness_evaluable_subset))
    validation_manifest = load_json_doc(Path(args.reference_validation_manifest))
    correctness_manifest = load_json_doc(Path(args.correctness_manifest))
    analysis_status = load_json_doc(Path(args.analysis_status))

    for filename_base, config in BAR_METRIC_GROUPS.items():
        save_bar_ai_vs_expert(
            exercise_df,
            figures_dir,
            tables_dir,
            filename_base=filename_base,
            metric_candidates=config["metrics"],
            ylabel=config["ylabel"],
        )
    save_boxplot_metrics(exercise_df, figures_dir, tables_dir)
    save_heatmap(exercise_df, figures_dir, tables_dir)
    save_topic_comparison(exercise_df, figures_dir, tables_dir)
    save_difficulty_comparison(exercise_df, figures_dir, tables_dir)
    save_pair_similarity_boxplot(pair_df, figures_dir, tables_dir)
    save_pair_similarity_by_topic(pair_df, figures_dir, tables_dir)
    save_correctness_pass_rate(correctness_evaluable_subset_df, figures_dir, tables_dir)
    save_correctness_evaluable_subset(correctness_evaluable_subset_df, figures_dir, tables_dir)
    save_correctness_full_coverage_overview(
        validation_manifest,
        correctness_manifest,
        analysis_status,
        figures_dir,
        tables_dir,
    )

    case_study_df = build_case_study_candidates(pair_df, pair_records)
    if not case_study_df.empty:
        case_study_df.to_csv(tables_dir / "case_study_candidates.v1.csv", index=False)

    print(f"Figures written to {figures_dir}")
    print(f"Tables written to {tables_dir}")


if __name__ == "__main__":
    main()

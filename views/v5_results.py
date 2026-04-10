from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from evaluation_system.components import (
    render_empty_state,
    render_page_header,
    render_primary_action_panel,
    render_summary_band,
)
from evaluation_system.runner import execute_action
from evaluation_system.state_store import CURATED_ANALYSIS_STATUS_PATH, load_csv, load_json_doc, set_console_flash, task_status_label

CURATED_ROOT = CURATED_ANALYSIS_STATUS_PATH.parent.parent
STATS_DIR = CURATED_ROOT / "statistics"
TABLES_DIR = CURATED_ROOT / "tables"
FIGURES_DIR = CURATED_ROOT / "figures"

DESCRIPTIVE_BY_SOURCE = STATS_DIR / "descriptive_stats.by_source.v1.csv"
TTEST_PATH = STATS_DIR / "ttest.ai_vs_expert.v1.csv"
CORRECTNESS_TTEST_PATH = STATS_DIR / "correctness.ttest.ai_vs_expert.v1.csv"
CORRECTNESS_BY_SOURCE_PATH = STATS_DIR / "correctness.descriptive_stats.by_source.v1.csv"
PAIR_OVERALL_PATH = STATS_DIR / "pair_similarity.overall.v1.csv"
PAIR_BY_TOPIC_PATH = STATS_DIR / "pair_similarity.by_topic.v1.csv"

CATEGORY_CONFIG = {
    "Code Correctness": {
        "tables": [
            ("AI vs Expert significance", CORRECTNESS_TTEST_PATH, None),
            ("Descriptive stats by source", CORRECTNESS_BY_SOURCE_PATH, None),
        ],
        "figures": [
            ("Pass rate", FIGURES_DIR / "correctness_pass_rate.png"),
            ("Evaluable subset", FIGURES_DIR / "correctness_evaluable_subset.png"),
            ("Coverage overview", FIGURES_DIR / "correctness_full_coverage_overview.png"),
        ],
    },
    "Instruction Quality": {
        "tables": [
            ("AI vs Expert significance", TTEST_PATH, "instruction_metrics."),
            ("Descriptive stats by source", DESCRIPTIVE_BY_SOURCE, "instruction_metrics."),
        ],
        "figures": [
            ("Readability comparison", FIGURES_DIR / "bar_ai_vs_expert_readability.png"),
            ("Topic comparison", FIGURES_DIR / "topic_comparison.png"),
            ("Difficulty comparison", FIGURES_DIR / "difficulty_comparison.png"),
        ],
    },
    "Structure Completeness": {
        "tables": [
            ("AI vs Expert significance", TTEST_PATH, "structure_metrics."),
            ("Descriptive stats by source", DESCRIPTIVE_BY_SOURCE, "structure_metrics."),
        ],
        "figures": [
            ("Structure comparison", FIGURES_DIR / "bar_ai_vs_expert.png"),
        ],
    },
    "Static Code Quality": {
        "tables": [
            ("AI vs Expert significance", TTEST_PATH, "code_quality_metrics."),
            ("Descriptive stats by source", DESCRIPTIVE_BY_SOURCE, "code_quality_metrics."),
        ],
        "figures": [
            ("Code quality comparison", FIGURES_DIR / "bar_ai_vs_expert_code_quality.png"),
            ("Code metric distribution", FIGURES_DIR / "boxplot_metrics.png"),
            ("Metric correlation", FIGURES_DIR / "heatmap_correlations.png"),
        ],
    },
    "AI-Expert Pair Similarity": {
        "tables": [
            ("Overall descriptive stats", PAIR_OVERALL_PATH, None),
            ("Descriptive stats by topic", PAIR_BY_TOPIC_PATH, None),
        ],
        "figures": [
            ("Similarity distribution", FIGURES_DIR / "pair_similarity_boxplot.png"),
            ("Similarity by topic", FIGURES_DIR / "pair_similarity_by_topic.png"),
        ],
    },
}


def _run_action(action_key: str, note: str) -> None:
    with st.spinner("Running automatic evaluation and result generation..."):
        result = execute_action(
            action_key,
            operator=st.session_state["console_role"],
            note=note,
        )
    set_console_flash(result["message"], "success" if result["status"] == "success" else "danger")
    st.cache_data.clear()
    st.rerun()


def _load_dataframe(path: Path) -> pd.DataFrame:
    try:
        return load_csv(path)
    except Exception:
        return pd.DataFrame()


def _filter_metrics(df: pd.DataFrame, prefix: str | None) -> pd.DataFrame:
    if df.empty or not prefix:
        return df
    metric_col = None
    for candidate in ["metric", "metric_name"]:
        if candidate in df.columns:
            metric_col = candidate
            break
    if metric_col is None:
        return df
    filtered = df[df[metric_col].astype(str).str.startswith(prefix)].copy()
    return filtered if not filtered.empty else df


def _render_table_block(title: str, path: Path, prefix: str | None) -> None:
    df = _filter_metrics(_load_dataframe(path), prefix)
    st.markdown(f"**{title}**")
    if df.empty:
        st.caption("This table has not been generated yet.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_figure_block(title: str, path: Path) -> None:
    st.markdown(f"**{title}**")
    if not path.exists():
        st.caption("This figure has not been generated yet.")
        return
    st.image(str(path), use_container_width=True)


def _render_category_tab(config: dict[str, list[tuple[str, Path, str | None]]]) -> None:
    for title, path, prefix in config.get("tables", []):
        _render_table_block(title, path, prefix)
    for title, path in config.get("figures", []):
        _render_figure_block(title, path)


def _render_pending_state(bundle: dict) -> None:
    tasks = bundle.get("tasks", {})
    evaluation_task = tasks.get("evaluation", {})
    disabled_reason = evaluation_task.get("block_reason", "") if evaluation_task.get("status") == "blocked" else ""

    clicked = render_primary_action_panel(
        title="Run automatic evaluation",
        description="This will execute reference validation, functional correctness, automatic metrics, statistical analysis, and thesis figures.",
        primary_label="Run automatic evaluation",
        primary_key="results-run-auto-evaluation",
        primary_disabled=bool(disabled_reason),
        disabled_reason=disabled_reason,
        secondary_actions=[
            {"label": "Go to Generation", "key": "results-go-generation"},
            {"label": "Go to Review", "key": "results-go-review"},
        ],
    )
    if clicked.get("primary"):
        _run_action("run_auto_evaluation", "Run automatic evaluation from results page")
    if clicked.get("results-go-generation"):
        st.session_state["console_page"] = "\u751f\u6210"
        st.rerun()
    if clicked.get("results-go-review"):
        st.session_state["console_page"] = "\u5ba1\u6838"
        st.rerun()

    render_empty_state(
        "Automatic evaluation results are not ready yet",
        "Once the run finishes, this page will show the five automatic-evaluation categories used by the thesis: correctness, instruction quality, structure completeness, static code quality, and AI-expert similarity.",
    )


def _render_ready_state(bundle: dict) -> None:
    tasks = bundle.get("tasks", {})
    status_doc = load_json_doc(CURATED_ANALYSIS_STATUS_PATH) or {}
    figure_count = len(list(FIGURES_DIR.glob("*.png"))) if FIGURES_DIR.exists() else 0
    table_count = len(list(TABLES_DIR.glob("*.csv"))) + len(list(STATS_DIR.glob("*.csv")))

    render_summary_band(
        [
            {
                "label": "Evaluation",
                "value": task_status_label(tasks.get("evaluation", {}).get("status", "not_started")),
                "note": "automatic evaluation task",
            },
            {
                "label": "AI n",
                "value": str(status_doc.get("ai_n", 0)),
                "note": "AI exercises in analysis",
            },
            {
                "label": "Expert n",
                "value": str(status_doc.get("expert_n", 0)),
                "note": "expert exercises in analysis",
            },
            {
                "label": "Artifacts",
                "value": f"{table_count} tables / {figure_count} figures",
                "note": "generated automatic-evaluation outputs",
            },
        ]
    )

    if st.button("Re-run automatic evaluation", key="results-rerun-auto-evaluation", use_container_width=True):
        _run_action("run_auto_evaluation", "Re-run automatic evaluation from results page")

    tabs = st.tabs(list(CATEGORY_CONFIG.keys()))
    for tab, (_, config) in zip(tabs, CATEGORY_CONFIG.items()):
        with tab:
            _render_category_tab(config)


def render(bundle: dict) -> None:
    render_page_header("Results", "Show only automatic-evaluation outputs used by the thesis.")

    if not CURATED_ANALYSIS_STATUS_PATH.exists():
        _render_pending_state(bundle)
        return

    _render_ready_state(bundle)
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from .common import (
    CURATED_DIR,
    STUDENT_SUBSETS_DIR,
    load_csv,
    render_kpi_cards,
    render_panel,
)


CURATED_STATISTICS_DIR = CURATED_DIR / "statistics"
CURATED_FIGURES_DIR = CURATED_DIR / "figures"
STUDENT_TABLES_DIR = STUDENT_SUBSETS_DIR / "chapter5_outputs" / "tables"
STUDENT_FIGURES_DIR = STUDENT_SUBSETS_DIR / "chapter5_outputs" / "figures"


def _read_overview_value(df: pd.DataFrame, section: str, default: str = "0") -> str:
    if df.empty or "section" not in df.columns or "value" not in df.columns:
        return default
    match = df.loc[df["section"] == section, "value"]
    return str(match.iloc[0]) if not match.empty else default


def _figure_picker(base_dir: Path, label: str, key: str) -> None:
    figure_files = sorted(base_dir.glob("*.png"))
    if not figure_files:
        st.info(f"{label} 当前没有可展示的图表。")
        return
    selected_name = st.selectbox(label, [path.name for path in figure_files], key=key)
    st.image(str(base_dir / selected_name), use_container_width=True)


def _table_picker(base_dir: Path, label: str, key: str) -> None:
    table_files = sorted(base_dir.glob("*.csv"))
    if not table_files:
        st.info(f"{label} 当前没有可展示的表格。")
        return
    selected_name = st.selectbox(label, [path.name for path in table_files], key=key)
    st.dataframe(load_csv(base_dir / selected_name), use_container_width=True, hide_index=True)


def render_analysis_tab() -> None:
    st.subheader("Analysis Dashboard")
    render_panel(
        "Results overview",
        "把 curated 自动分析结果和学生问卷结果放在同一页查看，适合快速展示样本规模、统计表和关键图形。",
        eyebrow="Analysis",
    )

    curated_sample = load_csv(CURATED_STATISTICS_DIR / "sample_size_summary.v1.csv")
    student_overview = load_csv(STUDENT_TABLES_DIR / "sample_overview.csv")

    curated_pairs = "0"
    if not curated_sample.empty and {"group", "n"}.issubset(curated_sample.columns):
        pair_match = curated_sample.loc[curated_sample["group"].astype(str) == "pairs", "n"]
        if not pair_match.empty:
            curated_pairs = str(pair_match.iloc[0])

    render_kpi_cards(
        [
            ("Curated pairs", curated_pairs),
            ("Student participants", _read_overview_value(student_overview, "participants")),
            ("Student item rows", _read_overview_value(student_overview, "item_rows")),
            ("Unique exercises", _read_overview_value(student_overview, "unique_exercises")),
        ]
    )

    st.markdown("**Student analysis filters**")
    item_metrics = load_csv(STUDENT_TABLES_DIR / "item_metrics_by_topic_and_source.csv")
    if not item_metrics.empty and {"topic", "source_type"}.issubset(item_metrics.columns):
        col1, col2 = st.columns(2)
        topic_options = sorted(item_metrics["topic"].dropna().astype(str).unique().tolist())
        source_options = sorted(
            item_metrics["source_type"].dropna().astype(str).unique().tolist()
        )
        selected_topics = col1.multiselect(
            "Topic",
            topic_options,
            default=topic_options,
            key="analysis_topic_filter",
        )
        selected_sources = col2.multiselect(
            "Source type",
            source_options,
            default=source_options,
            key="analysis_source_filter",
        )
        filtered = item_metrics.loc[
            item_metrics["topic"].astype(str).isin(selected_topics)
            & item_metrics["source_type"].astype(str).isin(selected_sources)
        ]
        st.dataframe(filtered, use_container_width=True, hide_index=True)

    st.markdown("**Curated outputs**")
    curated_col1, curated_col2 = st.columns(2)
    with curated_col1:
        _table_picker(CURATED_STATISTICS_DIR, "Curated statistics table", "curated_table")
    with curated_col2:
        _figure_picker(CURATED_FIGURES_DIR, "Curated figure", "curated_figure")

    st.markdown("**Student outputs**")
    student_col1, student_col2 = st.columns(2)
    with student_col1:
        _table_picker(STUDENT_TABLES_DIR, "Student analysis table", "student_table")
    with student_col2:
        _figure_picker(STUDENT_FIGURES_DIR, "Student analysis figure", "student_figure")

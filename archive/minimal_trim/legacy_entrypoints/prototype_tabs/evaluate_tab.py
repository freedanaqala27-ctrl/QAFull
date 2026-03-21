from __future__ import annotations

import streamlit as st

from .common import CURATED_DIR, load_csv, render_kpi_cards, render_panel


def _metric_family_columns(df: pd.DataFrame, prefix: str) -> list[str]:
    return [column for column in df.columns if column.startswith(prefix)]


def render_evaluate_tab() -> None:
    st.subheader("Automatic Metrics")
    render_panel(
        "Metric inventory",
        "集中展示当前自动指标，包括可读性、结构完整性、代码复杂度和 pair-level 语义相似度。",
        eyebrow="Evaluate",
    )
    exercise_metrics = load_csv(CURATED_DIR / "exercise_metrics.curated.v1.csv")
    pair_metrics = load_csv(CURATED_DIR / "pair_similarity_metrics.curated.v1.csv")

    if exercise_metrics.empty and pair_metrics.empty:
        st.info("当前没有可展示的自动评估结果。")
        return

    render_kpi_cards(
        [
            ("Exercise metric rows", str(len(exercise_metrics))),
            ("Pair metric rows", str(len(pair_metrics))),
            (
                "Instruction metrics",
                str(len(_metric_family_columns(exercise_metrics, "instruction_metrics."))),
            ),
            (
                "Pair similarity metrics",
                str(
                    len(
                        [
                            column
                            for column in pair_metrics.columns
                            if column.startswith("pair_")
                            or column.endswith("_instruction_only")
                        ]
                    )
                ),
            ),
        ]
    )

    if not exercise_metrics.empty:
        st.markdown("**Exercise metrics**")
        exercise_view_columns = [
            "exercise_id",
            "source_type",
            "topic",
            "difficulty",
            "exercise_type",
            "instruction_metrics.flesch_reading_ease",
            "instruction_metrics.instruction_completeness_ratio",
            "structure_metrics.structure_completeness_ratio",
            "code_quality_metrics.starter_code_mccabe_max",
            "code_quality_metrics.starter_code_mi",
        ]
        available_columns = [
            column for column in exercise_view_columns if column in exercise_metrics.columns
        ]
        st.dataframe(
            exercise_metrics[available_columns],
            use_container_width=True,
            hide_index=True,
        )

    if not pair_metrics.empty:
        st.markdown("**Pair similarity metrics**")
        pair_view_columns = [
            "pair_id",
            "topic",
            "difficulty",
            "pair_tfidf_cosine_instruction_only",
            "pair_rougeL_f1_instruction_only",
            "meteor_instruction_only",
            "bertscore_f1_instruction_only",
        ]
        available_pair_columns = [
            column for column in pair_view_columns if column in pair_metrics.columns
        ]
        pair_filtered = pair_metrics.copy()
        if "topic" in pair_filtered.columns:
            topics = sorted(pair_filtered["topic"].dropna().astype(str).unique().tolist())
            selected_topics = st.multiselect("按主题筛选 pair", topics, default=topics)
            pair_filtered = pair_filtered.loc[
                pair_filtered["topic"].astype(str).isin(selected_topics)
            ]
        st.dataframe(
            pair_filtered[available_pair_columns],
            use_container_width=True,
            hide_index=True,
        )

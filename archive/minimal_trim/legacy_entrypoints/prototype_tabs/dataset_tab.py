from __future__ import annotations

import pandas as pd
import streamlit as st

from .common import (
    CURATED_DIR,
    load_jsonl,
    normalize_text,
    render_kpi_cards,
    render_panel,
    sorted_unique,
)


def render_dataset_tab() -> None:
    st.subheader("Dataset Explorer")
    render_panel(
        "Curated exercise browser",
        "按来源、主题、难度和题型浏览当前用于分析的 exercise 集合，并查看单题详情。",
        eyebrow="Dataset",
    )
    rows = load_jsonl(CURATED_DIR / "exercises_all.curated.v1.jsonl")
    if not rows:
        st.info("当前没有可展示的 curated exercise 数据。")
        return

    df = pd.DataFrame(rows)
    render_kpi_cards(
        [
            ("Exercises", str(len(df))),
            ("AI items", str((df.get("source_type") == "AI").sum())),
            ("Expert items", str((df.get("source_type") == "Expert").sum())),
            ("Topics", str(df.get("topic").nunique())),
        ]
    )

    st.markdown("**Filters**")
    col1, col2, col3, col4 = st.columns(4)
    selected_sources = col1.multiselect(
        "Source type",
        sorted_unique(df["source_type"]),
        default=sorted_unique(df["source_type"]),
        key="dataset_source_filter",
    )
    selected_topics = col2.multiselect(
        "Topic",
        sorted_unique(df["topic"]),
        default=sorted_unique(df["topic"]),
        key="dataset_topic_filter",
    )
    selected_difficulties = col3.multiselect(
        "Difficulty",
        sorted_unique(df["difficulty"]),
        default=sorted_unique(df["difficulty"]),
        key="dataset_difficulty_filter",
    )
    selected_types = col4.multiselect(
        "Exercise type",
        sorted_unique(df["exercise_type"]),
        default=sorted_unique(df["exercise_type"]),
        key="dataset_type_filter",
    )

    filtered_df = df.loc[
        df["source_type"].astype(str).isin(selected_sources)
        & df["topic"].astype(str).isin(selected_topics)
        & df["difficulty"].astype(str).isin(selected_difficulties)
        & df["exercise_type"].astype(str).isin(selected_types)
    ].copy()

    st.caption(f"Filtered exercises: {len(filtered_df)}")
    visible_columns = [
        column
        for column in [
            "exercise_id",
            "source_type",
            "topic",
            "difficulty",
            "exercise_type",
            "title",
        ]
        if column in filtered_df.columns
    ]
    st.dataframe(filtered_df[visible_columns], use_container_width=True, hide_index=True)

    if filtered_df.empty:
        return

    selected_id = st.selectbox(
        "查看题目详情",
        options=filtered_df["exercise_id"].astype(str).tolist(),
    )
    selected_row = filtered_df.loc[filtered_df["exercise_id"] == selected_id].iloc[0]
    st.markdown(f"**标题：** {normalize_text(selected_row.get('title'), '无标题')}")
    st.markdown(f"**来源：** {normalize_text(selected_row.get('source_type'), '未标注')}")
    st.markdown(f"**主题：** {normalize_text(selected_row.get('topic'), '未标注')}")
    st.markdown(f"**难度：** {normalize_text(selected_row.get('difficulty'), '未标注')}")
    st.markdown(
        f"**题型：** {normalize_text(selected_row.get('exercise_type'), '未标注')}"
    )
    st.markdown("**题目描述**")
    st.write(normalize_text(selected_row.get("instruction_text"), "无"))
    starter_code = normalize_text(selected_row.get("starter_code"))
    if starter_code.strip():
        st.markdown("**起始代码**")
        st.code(starter_code, language="python")

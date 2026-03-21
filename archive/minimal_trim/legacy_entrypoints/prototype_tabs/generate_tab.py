from __future__ import annotations

import pandas as pd
import streamlit as st

from .common import (
    CURATED_DIR,
    PROMPTS_DIR,
    load_csv,
    load_text,
    render_kpi_cards,
    render_panel,
)


def render_generate_tab() -> None:
    st.subheader("Generation Workflow")
    render_panel(
        "Prompt-driven generation view",
        "展示题目生成原型的提示词资产、约束结构和当前 curated 数据分布，适合答辩时讲解生成来源与控制变量。",
        eyebrow="Generate",
    )

    distribution_df = load_csv(CURATED_DIR / "distribution_summary.v1.csv")
    if not distribution_df.empty:
        render_kpi_cards(
            [
                ("Distribution rows", str(len(distribution_df))),
                (
                    "Topics covered",
                    str(
                        distribution_df.loc[
                            distribution_df["dimension"] == "topic", "value"
                        ].nunique()
                    ),
                ),
                (
                    "Exercise types",
                    str(
                        distribution_df.loc[
                            distribution_df["dimension"] == "exercise_type", "value"
                        ].nunique()
                    ),
                ),
            ]
        )

    st.markdown("**Prompt assets**")
    prompt_files = {
        "Master prompt": PROMPTS_DIR / "master" / "MP-v1.md",
        "Code completion": PROMPTS_DIR / "subtemplates" / "CC-v1.md",
        "Model building": PROMPTS_DIR / "subtemplates" / "MB-v1.md",
        "Model revision": PROMPTS_DIR / "subtemplates" / "MR-v1.md",
        "Training analysis": PROMPTS_DIR / "subtemplates" / "TA-v1.md",
    }
    selected_label = st.selectbox("查看提示词文件", list(prompt_files.keys()))
    selected_path = prompt_files[selected_label]
    st.caption(str(selected_path))
    st.code(load_text(selected_path)[:6000], language="markdown")

    if distribution_df.empty:
        st.info("当前没有可展示的生成分布汇总。")
        return

    st.markdown("**Curated distribution summary**")
    dimension = st.selectbox(
        "选择汇总维度",
        sorted(distribution_df["dimension"].dropna().unique().tolist()),
    )
    filtered_df = distribution_df.loc[distribution_df["dimension"] == dimension].copy()
    if "count" in filtered_df.columns:
        filtered_df["count"] = pd.to_numeric(filtered_df["count"], errors="coerce")
        filtered_df = filtered_df.sort_values("count", ascending=False)
    st.dataframe(filtered_df, use_container_width=True, hide_index=True)

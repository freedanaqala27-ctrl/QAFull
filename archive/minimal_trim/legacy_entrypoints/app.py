from __future__ import annotations

import streamlit as st

from prototype_tabs.analysis_tab import render_analysis_tab
from prototype_tabs.common import apply_claude_warm_theme
from prototype_tabs.dataset_tab import render_dataset_tab
from prototype_tabs.evaluate_tab import render_evaluate_tab
from prototype_tabs.generate_tab import render_generate_tab
from prototype_tabs.survey_tab import render_survey_tab


def main() -> None:
    st.set_page_config(
        page_title="Deep Learning Exercise Evaluation Prototype",
        page_icon=":bar_chart:",
        layout="wide",
    )
    apply_claude_warm_theme()

    st.title("Deep Learning Exercise Evaluation Prototype")
    st.markdown(
        """
        <div class="prototype-hero">
            <div class="prototype-eyebrow">Presentation Prototype</div>
            <p>
                用于展示深度学习编程练习题质量评估流程、核心数据资产，以及当前
                Chapter 5 风格的分析结果。
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tabs = st.tabs(["Generate", "Dataset", "Evaluate", "Analysis", "Student Survey"])
    with tabs[0]:
        render_generate_tab()
    with tabs[1]:
        render_dataset_tab()
    with tabs[2]:
        render_evaluate_tab()
    with tabs[3]:
        render_analysis_tab()
    with tabs[4]:
        render_survey_tab()


if __name__ == "__main__":
    main()

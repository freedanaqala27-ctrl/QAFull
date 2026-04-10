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
    "代码正确性": {
        "tables": [
            ("AI vs Expert 显著性", CORRECTNESS_TTEST_PATH, None),
            ("来源分组描述统计", CORRECTNESS_BY_SOURCE_PATH, None),
        ],
        "figures": [
            ("通过率图", FIGURES_DIR / "correctness_pass_rate.png"),
            ("可评测子集分布", FIGURES_DIR / "correctness_evaluable_subset.png"),
            ("全覆盖概览", FIGURES_DIR / "correctness_full_coverage_overview.png"),
        ],
    },
    "题面说明质量": {
        "tables": [
            ("AI vs Expert 显著性", TTEST_PATH, "instruction_metrics."),
            ("来源分组描述统计", DESCRIPTIVE_BY_SOURCE, "instruction_metrics."),
        ],
        "figures": [
            ("可读性对比", FIGURES_DIR / "bar_ai_vs_expert_readability.png"),
            ("主题对比", FIGURES_DIR / "topic_comparison.png"),
            ("难度对比", FIGURES_DIR / "difficulty_comparison.png"),
        ],
    },
    "结构完整性": {
        "tables": [
            ("AI vs Expert 显著性", TTEST_PATH, "structure_metrics."),
            ("来源分组描述统计", DESCRIPTIVE_BY_SOURCE, "structure_metrics."),
        ],
        "figures": [
            ("结构指标对比", FIGURES_DIR / "bar_ai_vs_expert.png"),
        ],
    },
    "代码静态质量": {
        "tables": [
            ("AI vs Expert 显著性", TTEST_PATH, "code_quality_metrics."),
            ("来源分组描述统计", DESCRIPTIVE_BY_SOURCE, "code_quality_metrics."),
        ],
        "figures": [
            ("代码质量均值对比", FIGURES_DIR / "bar_ai_vs_expert_code_quality.png"),
            ("代码指标分布", FIGURES_DIR / "boxplot_metrics.png"),
            ("代码指标相关性", FIGURES_DIR / "heatmap_correlations.png"),
        ],
    },
    "AI-专家配对相似性": {
        "tables": [
            ("总体描述统计", PAIR_OVERALL_PATH, None),
            ("按主题描述统计", PAIR_BY_TOPIC_PATH, None),
        ],
        "figures": [
            ("相似性分布", FIGURES_DIR / "pair_similarity_boxplot.png"),
            ("按主题相似性", FIGURES_DIR / "pair_similarity_by_topic.png"),
        ],
    },
}


def _run_action(action_key: str, note: str) -> None:
    with st.spinner("正在执行自动评测与结果生成..."):
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
        st.caption("该表尚未生成。")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_figure_block(title: str, path: Path) -> None:
    st.markdown(f"**{title}**")
    if not path.exists():
        st.caption("该图尚未生成。")
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
        title="开始自动评测",
        description="运行参考解验证、功能正确性、自动指标、统计分析和论文图表生成。",
        primary_label="开始自动评测",
        primary_key="results-run-auto-evaluation",
        primary_disabled=bool(disabled_reason),
        disabled_reason=disabled_reason,
        secondary_actions=[
            {"label": "去生成页", "key": "results-go-generation"},
            {"label": "去审核页", "key": "results-go-review"},
        ],
    )
    if clicked.get("primary"):
        _run_action("run_auto_evaluation", "从结果页发起自动评测")
    if clicked.get("results-go-generation"):
        st.session_state["console_page"] = "生成"
        st.rerun()
    if clicked.get("results-go-review"):
        st.session_state["console_page"] = "审核"
        st.rerun()

    render_empty_state(
        "自动评价结果尚未生成",
        "完成自动评测后，这里会展示代码正确性、题面说明质量、结构完整性、代码静态质量和 AI-专家配对相似性的表与图。",
    )


def _render_ready_state(bundle: dict) -> None:
    tasks = bundle.get("tasks", {})
    status_doc = load_json_doc(CURATED_ANALYSIS_STATUS_PATH) or {}
    figure_count = len(list(FIGURES_DIR.glob("*.png"))) if FIGURES_DIR.exists() else 0
    table_count = len(list(TABLES_DIR.glob("*.csv"))) + len(list(STATS_DIR.glob("*.csv")))

    render_summary_band(
        [
            {
                "label": "自动评测",
                "value": task_status_label(tasks.get("evaluation", {}).get("status", "not_started")),
                "note": "自动评测任务状态",
            },
            {
                "label": "AI 样本数",
                "value": str(status_doc.get("ai_n", 0)),
                "note": "进入统计分析的 AI 题数",
            },
            {
                "label": "Expert 样本数",
                "value": str(status_doc.get("expert_n", 0)),
                "note": "进入统计分析的专家题数",
            },
            {
                "label": "结果产物",
                "value": f"{table_count} 表 / {figure_count} 图",
                "note": "当前已生成的自动评价产物",
            },
        ]
    )

    if st.button("重新执行自动评测", key="results-rerun-auto-evaluation", use_container_width=True):
        _run_action("run_auto_evaluation", "从结果页重新执行自动评测")

    tabs = st.tabs(list(CATEGORY_CONFIG.keys()))
    for tab, (_, config) in zip(tabs, CATEGORY_CONFIG.items()):
        with tab:
            _render_category_tab(config)


def render(bundle: dict) -> None:
    render_page_header("结果", "只展示论文中的自动评价结果，不展示问卷或人评结果。")

    if not CURATED_ANALYSIS_STATUS_PATH.exists():
        _render_pending_state(bundle)
        return

    _render_ready_state(bundle)
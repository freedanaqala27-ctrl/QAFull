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
DYNAMIC_ASSET_MANIFEST_PATH = CURATED_ROOT / "dynamic_eval_assets.manifest.v1.json"
REFERENCE_VALIDATION_MANIFEST_PATH = CURATED_ROOT / "reference_solution_validation_manifest.curated.v1.json"
CORRECTNESS_MANIFEST_PATH = CURATED_ROOT / "exercise_correctness_manifest.curated.v1.json"

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
        "empty_hint": "当前这批题目还没有形成完整的代码正确性结果。通常意味着部分题目的参考解或可执行测试仍需补齐。",
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
        "figures": [("结构指标对比", FIGURES_DIR / "bar_ai_vs_expert.png")],
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


def _run_action(action_key: str, note: str, spinner_text: str) -> None:
    with st.spinner(spinner_text):
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
    return filtered if not filtered.empty else pd.DataFrame()


def _render_table_block(title: str, path: Path, prefix: str | None) -> bool:
    df = _filter_metrics(_load_dataframe(path), prefix)
    st.markdown(f"**{title}**")
    if df.empty:
        st.caption("该表尚未生成。")
        return False
    st.dataframe(df, use_container_width=True, hide_index=True)
    return True


def _render_figure_block(title: str, path: Path) -> bool:
    st.markdown(f"**{title}**")
    if not path.exists():
        st.caption("该图尚未生成。")
        return False
    st.image(str(path), use_container_width=True)
    return True


def _render_category_tab(config: dict[str, object]) -> None:
    rendered_any = False
    for title, path, prefix in config.get("tables", []):
        rendered_any = _render_table_block(title, path, prefix) or rendered_any
    for title, path in config.get("figures", []):
        rendered_any = _render_figure_block(title, path) or rendered_any
    if not rendered_any:
        st.info(str(config.get("empty_hint") or "当前分类结果尚未生成。"))


def _asset_summary() -> dict[str, object]:
    dynamic_doc = load_json_doc(DYNAMIC_ASSET_MANIFEST_PATH) if DYNAMIC_ASSET_MANIFEST_PATH.exists() else {}
    validation_doc = load_json_doc(REFERENCE_VALIDATION_MANIFEST_PATH) if REFERENCE_VALIDATION_MANIFEST_PATH.exists() else {}
    correctness_doc = load_json_doc(CORRECTNESS_MANIFEST_PATH) if CORRECTNESS_MANIFEST_PATH.exists() else {}

    solution_counts = validation_doc.get("solution_present_counts", {}) if isinstance(validation_doc, dict) else {}
    correctness_counts = correctness_doc.get("correctness_status_counts", {}) if isinstance(correctness_doc, dict) else {}
    failed_rows = dynamic_doc.get("failed_exercises", []) if isinstance(dynamic_doc, dict) else []

    return {
        "total": int(dynamic_doc.get("num_exercises_seen") or validation_doc.get("num_exercises") or 0),
        "solution_ready": int(solution_counts.get("present") or 0),
        "solution_missing": int(solution_counts.get("missing") or 0),
        "failed_count": int(dynamic_doc.get("failed_exercise_count") or 0),
        "failed_rows": failed_rows if isinstance(failed_rows, list) else [],
        "correctness_ready": int(correctness_counts.get("pass") or 0),
        "correctness_not_evaluable": int(correctness_counts.get("not_evaluable") or 0),
    }


def _render_asset_repair_panel() -> None:
    summary = _asset_summary()
    render_summary_band(
        [
            {"label": "题目总数", "value": str(summary["total"]), "note": "进入资产构建的题目数"},
            {"label": "参考解已补齐", "value": str(summary["solution_ready"]), "note": "当前已有参考解的题目数"},
            {"label": "补齐失败", "value": str(summary["failed_count"]), "note": "本轮自动补齐失败的题目数"},
            {"label": "可评测题目", "value": str(summary["correctness_ready"]), "note": "已进入代码正确性评测的题目数"},
        ]
    )

    if st.button("补齐失败资产", key="results-repair-assets", use_container_width=True):
        _run_action("repair_eval_assets", "从结果页补齐失败的评测资产", "正在补齐失败资产...")

    if summary["failed_rows"]:
        with st.expander(f"查看失败题目清单（{summary['failed_count']}）", expanded=False):
            st.dataframe(pd.DataFrame(summary["failed_rows"]), use_container_width=True, hide_index=True)
    elif summary["total"] > 0:
        st.caption("当前没有记录到失败题目，或失败题目已被补齐。")


def _render_pending_state(bundle: dict) -> None:
    tasks = bundle.get("tasks", {})
    evaluation_task = tasks.get("evaluation", {})
    disabled_reason = evaluation_task.get("block_reason", "") if evaluation_task.get("status") == "blocked" else ""

    _render_asset_repair_panel()

    clicked = render_primary_action_panel(
        title="开始自动评测",
        description="运行参考解验证、功能正确性、自动指标、统计分析和论文图表生成。",
        primary_label="开始自动评测",
        primary_key="results-run-auto-evaluation",
        primary_disabled=bool(disabled_reason),
        disabled_reason=disabled_reason,
        secondary_actions=[],
    )
    if clicked.get("primary"):
        _run_action("run_auto_evaluation", "从结果页发起自动评测", "正在执行自动评测与结果生成...")

    render_empty_state(
        "自动评价结果尚未生成",
        "先补齐评测资产，再执行自动评测。完成后这里会展示代码正确性、题面说明质量、结构完整性、代码静态质量和 AI-专家配对相似性的表与图。",
    )


def _render_ready_state(bundle: dict) -> None:
    tasks = bundle.get("tasks", {})
    status_doc = load_json_doc(CURATED_ANALYSIS_STATUS_PATH) or {}
    figure_count = len(list(FIGURES_DIR.glob("*.png"))) if FIGURES_DIR.exists() else 0
    table_count = len(list(TABLES_DIR.glob("*.csv"))) + len(list(STATS_DIR.glob("*.csv")))

    render_summary_band(
        [
            {"label": "自动评测", "value": task_status_label(tasks.get("evaluation", {}).get("status", "not_started")), "note": "自动评测任务状态"},
            {"label": "AI 样本数", "value": str(status_doc.get("ai_n", 0)), "note": "进入统计分析的 AI 题数"},
            {"label": "Expert 样本数", "value": str(status_doc.get("expert_n", 0)), "note": "进入统计分析的专家题数"},
            {"label": "结果产物", "value": f"{table_count} 表 / {figure_count} 图", "note": "当前已生成的自动评价产物"},
        ]
    )

    _render_asset_repair_panel()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("重新执行自动评测", key="results-rerun-auto-evaluation", use_container_width=True):
            _run_action("run_auto_evaluation", "从结果页重新执行自动评测", "正在重新执行自动评测...")
    with col2:
        if st.button("补齐后再评测", key="results-repair-and-rerun", use_container_width=True):
            _run_action("repair_eval_assets", "从结果页补齐评测资产", "正在补齐失败资产...")

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

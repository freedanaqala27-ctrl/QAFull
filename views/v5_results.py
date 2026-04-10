from __future__ import annotations

from evaluation_system.components import render_page_header
from views import v7_report


def render(bundle: dict) -> None:
    render_page_header("结果", "集中展示自动指标、学生问卷和最终结果摘要。")
    v7_report.render(bundle, show_header=False)
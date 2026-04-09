from __future__ import annotations

from pathlib import Path
from typing import Iterable

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.font_manager import FontProperties, fontManager


def _find_font(candidates: list[str]) -> str | None:
    available = {font.name for font in fontManager.ttflist}
    for name in candidates:
        if name in available:
            return name
    return None


def get_font_config() -> tuple[str, str]:
    en_font = _find_font(
        [
            "Times New Roman",
            "Times",
            "Nimbus Roman",
            "Nimbus Roman No9 L",
            "TeX Gyre Termes",
            "DejaVu Serif",
        ]
    )
    zh_font = _find_font(
        [
            "SimSun",
            "Songti SC",
            "STSong",
            "Noto Serif CJK SC",
            "Source Han Serif SC",
            "AR PL UMing CN",
        ]
    )
    return en_font or "DejaVu Serif", zh_font or "DejaVu Sans"


EN_FONT, ZH_FONT = get_font_config()
ZH_FONT_10 = FontProperties(family=ZH_FONT, size=10)
ZH_FONT_9 = FontProperties(family=ZH_FONT, size=9)

AI_COLOR = "#4C72B0"
EXPERT_COLOR = "#DD8452"
AUX_COLOR = "#7F7F7F"


def setup_thesis_style() -> None:
    mpl.rcParams["figure.dpi"] = 300
    mpl.rcParams["savefig.dpi"] = 300
    mpl.rcParams["savefig.bbox"] = "tight"
    mpl.rcParams["font.family"] = "serif"
    mpl.rcParams["font.serif"] = [EN_FONT]
    mpl.rcParams["axes.unicode_minus"] = False
    mpl.rcParams["axes.linewidth"] = 0.8
    mpl.rcParams["lines.linewidth"] = 1.2
    mpl.rcParams["grid.linewidth"] = 0.4
    mpl.rcParams["font.size"] = 10
    mpl.rcParams["axes.labelsize"] = 10
    mpl.rcParams["xtick.labelsize"] = 9
    mpl.rcParams["ytick.labelsize"] = 9
    mpl.rcParams["legend.fontsize"] = 9
    mpl.rcParams["pdf.fonttype"] = 42
    mpl.rcParams["ps.fonttype"] = 42
    mpl.rcParams["svg.fonttype"] = "none"


def apply_axis_style(ax: plt.Axes, xlabel: str | None = None, ylabel: str | None = None, *, grid_y: bool = True) -> None:
    if xlabel:
        ax.set_xlabel(xlabel, fontname=EN_FONT, fontsize=10)
    if ylabel:
        ax.set_ylabel(ylabel, fontname=EN_FONT, fontsize=10)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.tick_params(axis="both", labelsize=9, width=0.8)

    if grid_y:
        ax.grid(axis="y", linestyle="--", linewidth=0.4, alpha=0.3)
    else:
        ax.grid(False)


def set_tick_fonts(ax: plt.Axes, *, rotation: float = 0, ha: str = "center") -> None:
    for label in ax.get_xticklabels():
        label.set_fontname(EN_FONT)
        label.set_fontsize(9)
        label.set_rotation(rotation)
        label.set_ha(ha)
    for label in ax.get_yticklabels():
        label.set_fontname(EN_FONT)
        label.set_fontsize(9)


def save_figure(fig: plt.Figure, output_path: Path) -> None:
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=300, bbox_inches="tight")
    fig.savefig(str(output_path.with_suffix(".pdf")), bbox_inches="tight")


def format_p_value(p_value: float) -> str:
    if p_value < 0.001:
        return "p < 0.001"
    return f"p = {p_value:.3f}"


def add_significance(ax: plt.Axes, x1: float, x2: float, y: float, h: float, p_value: float, *, fontsize: int = 9) -> None:
    ax.plot([x1, x1, x2, x2], [y, y + h, y + h, y], color="black", linewidth=0.8)
    if p_value < 0.001:
        text = "***"
    elif p_value < 0.01:
        text = "**"
    elif p_value < 0.05:
        text = "*"
    else:
        text = "ns"
    ax.text((x1 + x2) / 2, y + h, text, ha="center", va="bottom", fontname=EN_FONT, fontsize=fontsize)


def grouped_bar(
    ax: plt.Axes,
    categories: list[str],
    left_values: Iterable[float],
    right_values: Iterable[float],
    *,
    left_label: str = "AI-generated",
    right_label: str = "Expert-created",
    width: float = 0.36,
    colors: tuple[str, str] = (AI_COLOR, EXPERT_COLOR),
    show_values: bool = False,
) -> None:
    x = np.arange(len(categories))
    bars1 = ax.bar(
        x - width / 2,
        list(left_values),
        width,
        label=left_label,
        color=colors[0],
        edgecolor="black",
        linewidth=0.5,
    )
    bars2 = ax.bar(
        x + width / 2,
        list(right_values),
        width,
        label=right_label,
        color=colors[1],
        edgecolor="black",
        linewidth=0.5,
    )
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    set_tick_fonts(ax, rotation=25, ha="right")
    ax.legend(frameon=False, prop={"family": EN_FONT, "size": 9})

    if show_values:
        for bars in (bars1, bars2):
            for bar in bars:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height(),
                    f"{bar.get_height():.2f}",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    fontname=EN_FONT,
                )


def boxplot(
    ax: plt.Axes,
    data_groups: list[Iterable[float]],
    labels: list[str],
    *,
    colors: list[str] | None = None,
) -> None:
    palette = colors or [AI_COLOR, EXPERT_COLOR]
    bp = ax.boxplot(
        data_groups,
        labels=labels,
        widths=0.5,
        patch_artist=True,
        boxprops=dict(linewidth=1.0, edgecolor="black"),
        whiskerprops=dict(linewidth=1.0, color="black"),
        capprops=dict(linewidth=1.0, color="black"),
        medianprops=dict(linewidth=1.2, color="black"),
        flierprops=dict(marker="o", markersize=4, markerfacecolor="white", markeredgecolor="black", linewidth=0.6),
    )
    for patch, color in zip(bp["boxes"], palette[: len(bp["boxes"])]):
        patch.set_facecolor(color)
        patch.set_alpha(0.5)
    set_tick_fonts(ax)


def line_plot(
    ax: plt.Axes,
    x: Iterable[float],
    left_values: Iterable[float],
    right_values: Iterable[float],
    *,
    left_label: str = "AI-generated",
    right_label: str = "Expert-created",
    colors: tuple[str, str] = (AI_COLOR, EXPERT_COLOR),
) -> None:
    ax.plot(list(x), list(left_values), marker="o", markersize=5, color=colors[0], label=left_label)
    ax.plot(list(x), list(right_values), marker="s", markersize=5, color=colors[1], label=right_label)
    ax.legend(frameon=False, prop={"family": EN_FONT, "size": 9})
    set_tick_fonts(ax)


def heatmap(
    ax: plt.Axes,
    matrix: np.ndarray,
    row_labels: list[str],
    col_labels: list[str],
    *,
    cmap: str = "Blues",
    value_decimals: int = 2,
    vmin: float | None = None,
    vmax: float | None = None,
) -> mpl.image.AxesImage:
    im = ax.imshow(matrix, cmap=cmap, aspect="auto", vmin=vmin, vmax=vmax)
    ax.set_xticks(np.arange(len(col_labels)))
    ax.set_yticks(np.arange(len(row_labels)))
    ax.set_xticklabels(col_labels)
    ax.set_yticklabels(row_labels)
    set_tick_fonts(ax, rotation=45, ha="right")

    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            value = matrix[i, j]
            if np.isnan(value):
                text = ""
            else:
                text = f"{value:.{value_decimals}f}"
            ax.text(j, i, text, ha="center", va="center", fontsize=8, fontname=EN_FONT)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return im


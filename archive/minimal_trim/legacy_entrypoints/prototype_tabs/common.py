from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from pandas.errors import EmptyDataError


PROJECT_ROOT = Path(__file__).resolve().parents[4]
RESULTS_DIR = PROJECT_ROOT / "results"
CURATED_DIR = RESULTS_DIR / "curated"
STUDENT_SUBSETS_DIR = RESULTS_DIR / "student_subsets"
PROMPTS_DIR = PROJECT_ROOT / "prompts" / "v1"
HUMAN_EVAL_PACKETS_DIR = CURATED_DIR / "human_eval_packets"
PACKETS_DIR = HUMAN_EVAL_PACKETS_DIR / "packets"
DISTRIBUTION_DIR = HUMAN_EVAL_PACKETS_DIR / "distribution"


def apply_claude_warm_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --page-bg: #F7F5F2;
            --card-bg: #FCFBF8;
            --subtle-bg: #F1EEE8;
            --text-main: #26231E;
            --text-muted: #6B645C;
            --border-soft: #E6E0D8;
            --accent: #D97757;
            --accent-strong: #C97B63;
            --shadow-soft: 0 2px 10px rgba(38, 35, 30, 0.04);
        }

        .stApp {
            background: var(--page-bg);
            color: var(--text-main);
        }

        [data-testid="stAppViewContainer"] {
            background: var(--page-bg);
        }

        [data-testid="stHeader"] {
            background: transparent;
        }

        [data-testid="stSidebar"] {
            background: var(--subtle-bg);
        }

        .block-container {
            max-width: 840px;
            padding-top: 2.2rem;
            padding-bottom: 4rem;
        }

        html, body, [class*="css"] {
            color: var(--text-main);
        }

        p, li, label, .stMarkdown, .stCaption {
            font-size: 15.5px;
            line-height: 1.72;
        }

        h1, h2, h3 {
            color: var(--text-main);
            letter-spacing: -0.01em;
            font-weight: 600;
        }

        h1 {
            font-size: 2.1rem;
            margin-bottom: 0.35rem;
        }

        h2, h3 {
            font-weight: 560;
        }

        .prototype-hero {
            background: var(--card-bg);
            border: 1px solid var(--border-soft);
            border-radius: 22px;
            padding: 1.25rem 1.35rem;
            margin: 0.4rem 0 1.25rem 0;
            box-shadow: var(--shadow-soft);
        }

        .prototype-hero p {
            margin: 0.35rem 0 0 0;
            color: var(--text-muted);
        }

        .prototype-eyebrow {
            color: var(--accent-strong);
            font-size: 0.82rem;
            font-weight: 600;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }

        .prototype-section {
            background: var(--card-bg);
            border: 1px solid var(--border-soft);
            border-radius: 18px;
            padding: 0.95rem 1.05rem;
            margin: 0.75rem 0 1rem 0;
            box-shadow: var(--shadow-soft);
        }

        .prototype-section-title {
            font-size: 1rem;
            font-weight: 600;
            color: var(--text-main);
            margin-bottom: 0.25rem;
        }

        .prototype-section-body {
            color: var(--text-muted);
            margin: 0;
        }

        [data-testid="stMetric"] {
            background: var(--card-bg);
            border: 1px solid var(--border-soft);
            border-radius: 18px;
            padding: 0.95rem 1rem;
            box-shadow: var(--shadow-soft);
        }

        [data-testid="stMetricLabel"] {
            color: var(--text-muted);
            font-weight: 500;
        }

        [data-testid="stMetricValue"] {
            color: var(--text-main);
            font-weight: 650;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 0.5rem;
            background: transparent;
            padding: 0.2rem 0 0.8rem 0;
        }

        .stTabs [data-baseweb="tab"] {
            background: var(--subtle-bg);
            border: 1px solid var(--border-soft);
            border-radius: 16px;
            color: var(--text-muted);
            padding: 0.55rem 0.9rem;
            height: auto;
        }

        .stTabs [aria-selected="true"] {
            background: #F4E6DF;
            border-color: #E2C4B8;
            color: var(--text-main);
        }

        .stButton > button,
        .stDownloadButton > button {
            background: #F4E6DF;
            color: var(--text-main);
            border: 1px solid #E2C4B8;
            border-radius: 16px;
            padding: 0.55rem 1rem;
            box-shadow: none;
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover {
            background: #EFD8CF;
            border-color: #D8B3A3;
            color: var(--text-main);
        }

        .stSelectbox [data-baseweb="select"],
        .stMultiSelect [data-baseweb="select"],
        .stTextArea textarea,
        .stTextInput input {
            background: var(--card-bg);
            border-radius: 20px !important;
            border: 1px solid var(--border-soft) !important;
            color: var(--text-main) !important;
        }

        .stCodeBlock,
        pre {
            background: #F3EFE8 !important;
            border: 1px solid var(--border-soft);
            border-radius: 14px !important;
        }

        [data-testid="stDataFrame"],
        [data-testid="stTable"] {
            border: 1px solid var(--border-soft);
            border-radius: 18px;
            overflow: hidden;
            background: var(--card-bg);
        }

        .stAlert {
            border-radius: 16px;
            border: 1px solid var(--border-soft);
        }

        hr {
            border-color: var(--border-soft);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_panel(title: str, body: str, eyebrow: str | None = None) -> None:
    eyebrow_html = (
        f'<div class="prototype-eyebrow">{eyebrow}</div>' if eyebrow else ""
    )
    st.markdown(
        f"""
        <div class="prototype-section">
            {eyebrow_html}
            <div class="prototype-section-title">{title}</div>
            <p class="prototype-section-body">{body}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except EmptyDataError:
        return pd.DataFrame()


@st.cache_data(show_spinner=False)
def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


@st.cache_data(show_spinner=False)
def load_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def render_kpi_cards(items: list[tuple[str, str]]) -> None:
    if not items:
        return
    columns = st.columns(len(items))
    for column, (label, value) in zip(columns, items):
        column.metric(label, value)


def normalize_text(value: Any, default: str = "") -> str:
    if value is None or pd.isna(value):
        return default
    return str(value)


def sorted_unique(series: pd.Series) -> list[str]:
    return sorted(
        {str(value) for value in series.tolist() if pd.notna(value) and str(value).strip()}
    )

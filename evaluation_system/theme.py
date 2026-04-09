from __future__ import annotations

import streamlit as st


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --wb-bg: #f4f6fb;
            --wb-surface: #ffffff;
            --wb-surface-soft: #f8faff;
            --wb-border: #d8e0ef;
            --wb-text: #111827;
            --wb-text-muted: #52607a;
            --wb-primary: #1f5ad1;
            --wb-primary-soft: #eaf1ff;
            --wb-success: #1f8f5f;
            --wb-success-soft: #e8f8ef;
            --wb-warning: #bd7a00;
            --wb-warning-soft: #fff5db;
            --wb-danger: #c13b32;
            --wb-danger-soft: #fdebea;
            --wb-shadow: 0 8px 24px rgba(16, 24, 40, 0.05);
        }

        html, body, [class*="css"], .stApp {
            font-family: "Microsoft YaHei UI", "PingFang SC", "Segoe UI", sans-serif;
            color: var(--wb-text);
        }

        .stApp, [data-testid="stAppViewContainer"] {
            background: var(--wb-bg);
        }

        [data-testid="stHeader"] {
            background: rgba(244, 246, 251, 0.92);
            border-bottom: 1px solid rgba(216, 224, 239, 0.75);
        }

        [data-testid="stSidebar"] {
            background: #ffffff;
            border-right: 1px solid var(--wb-border);
        }

        [data-testid="stSidebarNav"] {
            display: none;
        }

        .block-container {
            max-width: 1420px;
            padding-top: 1.35rem;
            padding-bottom: 3rem;
        }

        h1, h2, h3, h4 {
            color: var(--wb-text);
            letter-spacing: -0.02em;
        }

        .wb-page-header {
            padding: 0.2rem 0 1rem 0;
        }

        .wb-page-title {
            font-size: 2.1rem;
            font-weight: 700;
            margin: 0;
        }

        .wb-page-subtitle {
            color: var(--wb-text-muted);
            margin-top: 0.35rem;
            font-size: 1rem;
        }

        .wb-stage-strip {
            display: grid;
            grid-template-columns: repeat(8, minmax(0, 1fr));
            gap: 0.6rem;
            margin-top: 0.75rem;
        }

        .wb-stage {
            background: var(--wb-surface);
            border: 1px solid var(--wb-border);
            border-radius: 16px;
            padding: 0.8rem 0.75rem;
            min-height: 96px;
            box-shadow: var(--wb-shadow);
        }

        .wb-stage[data-status="done"] {
            border-color: rgba(31, 143, 95, 0.35);
            background: linear-gradient(180deg, #ffffff 0%, #f3fbf6 100%);
        }

        .wb-stage[data-status="current"] {
            border-color: rgba(31, 90, 209, 0.35);
            background: linear-gradient(180deg, #ffffff 0%, #f3f7ff 100%);
        }

        .wb-stage[data-status="blocked"] {
            border-color: rgba(193, 59, 50, 0.35);
            background: linear-gradient(180deg, #ffffff 0%, #fff7f7 100%);
        }

        .wb-stage-index {
            font-size: 0.76rem;
            color: var(--wb-text-muted);
            text-transform: uppercase;
            letter-spacing: 0.06em;
        }

        .wb-stage-title {
            margin-top: 0.25rem;
            font-weight: 700;
            font-size: 0.95rem;
        }

        .wb-stage-note {
            margin-top: 0.35rem;
            font-size: 0.82rem;
            color: var(--wb-text-muted);
            line-height: 1.45;
        }

        .wb-summary-band {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.75rem;
            margin-top: 0.85rem;
        }

        .wb-summary-card {
            background: var(--wb-surface);
            border: 1px solid var(--wb-border);
            border-radius: 16px;
            padding: 0.9rem 1rem;
            box-shadow: var(--wb-shadow);
        }

        .wb-summary-label {
            color: var(--wb-text-muted);
            font-size: 0.84rem;
        }

        .wb-summary-value {
            font-size: 1.35rem;
            font-weight: 700;
            margin-top: 0.25rem;
        }

        .wb-section-card {
            background: var(--wb-surface);
            border: 1px solid var(--wb-border);
            border-radius: 20px;
            padding: 1.15rem 1.2rem;
            box-shadow: var(--wb-shadow);
        }

        .wb-section-title {
            font-size: 1.25rem;
            font-weight: 700;
            margin-bottom: 0.2rem;
        }

        .wb-section-subtitle {
            color: var(--wb-text-muted);
            font-size: 0.94rem;
            margin-bottom: 0.9rem;
        }

        .wb-badge {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 0.26rem 0.62rem;
            font-size: 0.82rem;
            font-weight: 600;
            margin-right: 0.35rem;
            margin-bottom: 0.35rem;
        }

        .wb-badge--neutral {
            color: var(--wb-text-muted);
            background: #eef2fa;
        }

        .wb-badge--info {
            color: var(--wb-primary);
            background: var(--wb-primary-soft);
        }

        .wb-badge--success {
            color: var(--wb-success);
            background: var(--wb-success-soft);
        }

        .wb-badge--warning {
            color: var(--wb-warning);
            background: var(--wb-warning-soft);
        }

        .wb-badge--danger {
            color: var(--wb-danger);
            background: var(--wb-danger-soft);
        }

        .wb-checklist {
            display: grid;
            gap: 0.55rem;
        }

        .wb-check-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 1rem;
            background: var(--wb-surface-soft);
            border: 1px solid var(--wb-border);
            border-radius: 14px;
            padding: 0.7rem 0.85rem;
        }

        .wb-check-label {
            font-weight: 600;
        }

        .wb-check-note {
            color: var(--wb-text-muted);
            font-size: 0.86rem;
            margin-top: 0.15rem;
        }

        .wb-empty {
            background: var(--wb-surface);
            border: 1px dashed var(--wb-border);
            border-radius: 20px;
            padding: 1.3rem 1.4rem;
            color: var(--wb-text-muted);
        }

        .wb-empty strong {
            color: var(--wb-text);
            display: block;
            margin-bottom: 0.35rem;
        }

        .stButton > button,
        .stDownloadButton > button {
            border-radius: 14px;
            border: 1px solid var(--wb-border);
            min-height: 42px;
        }

        .stButton > button[kind="primary"] {
            background: var(--wb-primary);
            color: #ffffff;
            border-color: var(--wb-primary);
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover {
            border-color: #9fb5e6;
            color: var(--wb-text);
        }

        .stButton > button[kind="primary"]:hover {
            background: #1849ae;
            color: #ffffff;
            border-color: #1849ae;
        }

        .stTextInput input,
        .stTextArea textarea,
        .stSelectbox [data-baseweb="select"],
        .stMultiSelect [data-baseweb="select"] {
            border-radius: 14px !important;
            border-color: var(--wb-border) !important;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 0.5rem;
            padding-top: 0.2rem;
            padding-bottom: 0.8rem;
        }

        .stTabs [data-baseweb="tab"] {
            background: var(--wb-surface);
            border: 1px solid var(--wb-border);
            border-radius: 14px;
            padding: 0.55rem 0.9rem;
        }

        .stTabs [aria-selected="true"] {
            background: var(--wb-primary-soft);
            border-color: rgba(31, 90, 209, 0.3);
            color: var(--wb-primary);
        }

        [data-testid="stDataFrame"] {
            border: 1px solid var(--wb-border);
            border-radius: 18px;
            overflow: hidden;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

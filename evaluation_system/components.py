from __future__ import annotations

import html
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


def _escape(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def badge_html(text: str, tone: str = "neutral") -> str:
    return f'<span class="wb-badge wb-badge--{_escape(tone)}">{_escape(text)}</span>'


def render_page_header(title: str, subtitle: str) -> None:
    st.markdown(
        (
            f'<div class="wb-page-header">'
            f'<div class="wb-page-title">{_escape(title)}</div>'
            f'<div class="wb-page-subtitle">{_escape(subtitle)}</div>'
            f'</div>'
        ),
        unsafe_allow_html=True,
    )



def render_stage_strip(stages: list[dict[str, str]]) -> None:
    parts: list[str] = ['<div class="wb-stage-strip">']
    for index, stage in enumerate(stages, start=1):
        parts.append(
            (
                f'<div class="wb-stage" data-status="{_escape(stage.get("status", "pending"))}">'
                f'<div class="wb-stage-index">阶段 {index}</div>'
                f'<div class="wb-stage-title">{_escape(stage.get("label", ""))}</div>'
                f'<div>{badge_html(stage.get("status_label", "未开始"), stage.get("tone", "neutral"))}</div>'
                f'<div class="wb-stage-note">{_escape(stage.get("note", ""))}</div>'
                f'</div>'
            )
        )
    parts.append('</div>')
    st.markdown(''.join(parts), unsafe_allow_html=True)



def render_summary_band(items: list[dict[str, str]]) -> None:
    blocks: list[str] = ['<div class="wb-summary-band">']
    for item in items:
        blocks.append(
            (
                f'<div class="wb-summary-card">'
                f'<div class="wb-summary-label">{_escape(item.get("label", ""))}</div>'
                f'<div class="wb-summary-value">{_escape(item.get("value", ""))}</div>'
                f'<div class="wb-section-subtitle" style="margin:0.2rem 0 0 0;">{_escape(item.get("note", ""))}</div>'
                f'</div>'
            )
        )
    blocks.append('</div>')
    st.markdown(''.join(blocks), unsafe_allow_html=True)



def render_empty_state(title: str, body: str) -> None:
    st.markdown(
        (
            f'<div class="wb-empty">'
            f'<strong>{_escape(title)}</strong>'
            f'<div>{_escape(body)}</div>'
            f'</div>'
        ),
        unsafe_allow_html=True,
    )



def render_error_state(title: str, body: str) -> None:
    st.error(f"{title}\n\n{body}")



def render_checklist(items: list[dict[str, str]]) -> None:
    rows: list[str] = ['<div class="wb-checklist">']
    for item in items:
        rows.append(
            (
                f'<div class="wb-check-item">'
                f'<div><div class="wb-check-label">{_escape(item.get("label", ""))}</div>'
                f'<div class="wb-check-note">{_escape(item.get("note", ""))}</div></div>'
                f'<div>{badge_html(item.get("status_label", ""), item.get("tone", "neutral"))}</div>'
                f'</div>'
            )
        )
    rows.append('</div>')
    st.markdown(''.join(rows), unsafe_allow_html=True)



def render_key_value_table(rows: list[tuple[str, str]], columns: int = 2) -> None:
    if not rows:
        return
    grid_columns = st.columns(columns)
    for index, (label, value) in enumerate(rows):
        with grid_columns[index % columns]:
            st.caption(label)
            st.markdown(f"**{value}**")



def render_primary_action_panel(
    *,
    title: str,
    description: str,
    primary_label: str,
    primary_key: str,
    secondary_actions: list[dict[str, str]] | None = None,
    primary_disabled: bool = False,
    disabled_reason: str = "",
) -> dict[str, bool]:
    st.markdown(
        (
            f'<div class="wb-section-card">'
            f'<div class="wb-section-title">{_escape(title)}</div>'
            f'<div class="wb-section-subtitle">{_escape(description)}</div>'
            f'</div>'
        ),
        unsafe_allow_html=True,
    )
    if primary_disabled and disabled_reason:
        st.caption(f"当前无法执行：{disabled_reason}")

    clicked: dict[str, bool] = {}
    button_columns = st.columns(1 + len(secondary_actions or []))
    clicked["primary"] = button_columns[0].button(
        primary_label,
        key=primary_key,
        type="primary",
        disabled=primary_disabled,
        use_container_width=True,
    )
    for offset, action in enumerate(secondary_actions or [], start=1):
        clicked[action["key"]] = button_columns[offset].button(
            action["label"],
            key=action["key"],
            use_container_width=True,
        )
    return clicked



def download_file_button(path: Path, label: str, key: str, *, use_container_width: bool = True) -> None:
    if not path.exists():
        st.button(label, key=key, disabled=True, use_container_width=use_container_width)
        return
    st.download_button(
        label,
        data=path.read_bytes(),
        file_name=path.name,
        key=key,
        use_container_width=use_container_width,
    )



def render_artifact_table(records: list[dict[str, Any]], key_prefix: str) -> None:
    if not records:
        render_empty_state("当前没有可展示的产物", "等产物生成后，这里会集中提供查看和下载入口。")
        return

    header_cols = st.columns([2.2, 1.3, 1.1, 1.1])
    header_cols[0].caption("产物")
    header_cols[1].caption("说明")
    header_cols[2].caption("更新时间")
    header_cols[3].caption("操作")

    for index, record in enumerate(records):
        cols = st.columns([2.2, 1.3, 1.1, 1.1])
        cols[0].markdown(f"**{record.get('label', '')}**\n\n`{record.get('path', '')}`")
        cols[1].markdown(record.get("description", ""))
        cols[2].markdown(record.get("updated_at", "未生成"))
        with cols[3]:
            download_file_button(
                Path(record["path"]),
                "下载",
                key=f"{key_prefix}-download-{index}",
            )
        st.divider()



def render_dataframe(df: pd.DataFrame, *, height: int | None = None) -> None:
    st.dataframe(df, use_container_width=True, hide_index=True, height=height)

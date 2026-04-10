from __future__ import annotations

import io
import zipfile
from pathlib import Path

import streamlit as st

from evaluation_system.components import render_key_value_table, render_page_header
from evaluation_system.runner import execute_action
from evaluation_system.state_store import set_console_flash, task_status_label


def _deliverable(bundle: dict, key: str) -> dict:
    return bundle.get("deliverables", {}).get(key, {})


def _run_student_packet_generation() -> None:
    with st.spinner("正在生成学生题包和问卷材料..."):
        result = execute_action(
            "generate_student_packets",
            operator=st.session_state["console_role"],
            note="答辩模式 / 问卷发放",
        )
    set_console_flash(result["message"], "success" if result["status"] == "success" else "danger")
    st.cache_data.clear()
    st.rerun()


def _run_freeze(bundle: dict) -> None:
    pull_mode = bundle["settings"].get("data_source", {}).get("pull_mode", "本地 CSV")
    with st.spinner("正在冻结正式分析样本..."):
        result = execute_action(
            "freeze_analysis_input",
            operator=st.session_state["console_role"],
            note="答辩模式 / 冻结分析样本",
            params={
                "pull_mode": pull_mode,
                "fetch_from_db": pull_mode == "直接拉库",
            },
        )
    set_console_flash(result["message"], "success" if result["status"] == "success" else "danger")
    st.session_state["freeze_confirm_open"] = False
    st.cache_data.clear()
    st.rerun()


def _survey_export_paths(packet_manifest: Path, distribution_sheet: Path, qrcode_sheet: Path) -> list[Path]:
    paths: list[Path] = []
    for candidate in [packet_manifest, distribution_sheet, qrcode_sheet]:
        if candidate.exists():
            paths.append(candidate)

    if distribution_sheet.exists():
        with_qr_csv = distribution_sheet.parent / "student_distribution_with_qrcodes.curated.v1.csv"
        if with_qr_csv.exists():
            paths.append(with_qr_csv)
        qrcode_dir = distribution_sheet.parent / "student_qrcodes"
        if qrcode_dir.exists():
            paths.append(qrcode_dir)

    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _build_survey_export_zip(paths: list[Path]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            if not path.exists():
                continue
            if path.is_dir():
                for child in sorted(path.rglob("*")):
                    if child.is_dir():
                        continue
                    archive.write(child, arcname=f"{path.name}/{child.relative_to(path).as_posix()}")
            else:
                archive.write(path, arcname=path.name)
    return buffer.getvalue()


def render(bundle: dict, *, show_header: bool = True) -> None:
    if show_header:
        render_page_header("问卷", "发放材料、查看回收、冻结正式样本。")

    survey_metrics = bundle["survey_metrics"]
    tasks = bundle.get("tasks", {})
    packet_manifest = Path(str(_deliverable(bundle, "packet_manifest").get("path") or ""))
    qrcode_sheet = Path(str(_deliverable(bundle, "qrcode_sheet").get("path") or ""))
    distribution_sheet = Path(str(_deliverable(bundle, "distribution_sheet").get("path") or ""))

    render_key_value_table(
        [
            ("发放状态", task_status_label(tasks.get("survey_publish", {}).get("status", "not_started"))),
            ("已发放", str(survey_metrics.get("issued_count", 0))),
            ("已提交", str(survey_metrics.get("submitted_count", 0))),
            ("有效样本", str(survey_metrics.get("effective_samples", 0))),
            ("冻结阈值", str(survey_metrics.get("freeze_threshold", 0))),
            ("样本冻结", task_status_label(tasks.get("freeze", {}).get("status", "not_started"))),
        ],
        columns=3,
    )

    action_cols = st.columns(3)
    if action_cols[0].button("生成问卷材料", type="primary", use_container_width=True):
        _run_student_packet_generation()
    if action_cols[1].button(
        "冻结分析样本",
        use_container_width=True,
        disabled=str(tasks.get("freeze", {}).get("status") or "") == "blocked",
    ):
        st.session_state["freeze_confirm_open"] = True
    if action_cols[2].button("去结果页", use_container_width=True):
        st.session_state["console_page"] = "结果"
        st.rerun()

    with st.expander("下载材料", expanded=False):
        export_paths = _survey_export_paths(packet_manifest, distribution_sheet, qrcode_sheet)
        ready = bool(export_paths)
        st.download_button(
            "下载完整发放包 ZIP",
            data=_build_survey_export_zip(export_paths) if ready else b"",
            file_name="survey_materials_bundle.zip",
            key="survey-materials-zip",
            disabled=not ready,
            use_container_width=True,
        )
        if ready:
            st.caption("ZIP 内包含题包清单、分发清单、二维码页、带二维码路径的分发表，以及 student_qrcodes 图片目录。")
        else:
            st.caption("先生成问卷材料，之后这里会提供完整发放包下载。")

    if tasks.get("freeze", {}).get("block_reason"):
        st.caption(f"当前限制：{tasks['freeze']['block_reason']}")

    if st.session_state.get("freeze_confirm_open"):
        st.info("确认后系统会导出问卷输入并锁定正式分析样本。")
        confirm_cols = st.columns(2)
        if confirm_cols[0].button("确认", type="primary", use_container_width=True):
            _run_freeze(bundle)
        if confirm_cols[1].button("取消", use_container_width=True):
            st.session_state["freeze_confirm_open"] = False
            st.rerun()
from __future__ import annotations

import streamlit as st

from evaluation_system.components import render_checklist, render_empty_state, render_key_value_table, render_page_header
from evaluation_system.runner import execute_action
from evaluation_system.state_store import available_snapshot_checks, can_publish_snapshot, list_run_records, set_console_flash, task_status_label



def render(bundle: dict, *, show_header: bool = True) -> None:
    if show_header:
        render_page_header("快照发布", "归档并发布当前批次快照。")
    if st.session_state.get("console_role") != "管理员":
        render_empty_state("当前角色不可发布快照", "快照发布只保留给管理员，用于最终归档与交付。")
        return

    tasks = bundle.get("tasks", {})
    report_summary = bundle.get("deliverables", {}).get("report_summary", {})
    snapshot_archive = bundle.get("deliverables", {}).get("snapshot_archive", {})
    snapshot_status = str(tasks.get("snapshot", {}).get("status") or "not_started")

    can_publish, disabled_reason = can_publish_snapshot(bundle)
    render_key_value_table(
        [
            ("当前批次", bundle["settings"]["batch_name"]),
            ("最近报告登记", str(report_summary.get("updated_at", "未生成"))),
            ("快照任务", task_status_label(snapshot_status)),
        ],
        columns=3,
    )

    st.markdown("### 快照前检查")
    render_checklist(available_snapshot_checks(bundle))
    st.markdown("### 快照包含内容")
    st.write("- 自动评测任务状态与登记 manifest")
    st.write("- 冻结后的分析输入与主分析表 manifest")
    st.write("- 报告链交付物与最终归档包")

    if snapshot_archive.get("available"):
        st.caption(f"最近归档：{snapshot_archive.get('updated_at', '未记录')}")

    if st.button("发布完整快照", type="primary", disabled=not can_publish, use_container_width=True):
        with st.spinner("正在发布完整快照..."):
            result = execute_action(
                "publish_snapshot",
                operator=st.session_state["console_role"],
                note="从快照发布页发起",
            )
        if result["status"] == "success":
            st.session_state["snapshot_locked_override"] = True
        set_console_flash(result["message"], "success" if result["status"] == "success" else "danger")
        st.cache_data.clear()
        st.rerun()
    if not can_publish and disabled_reason:
        st.caption(f"当前不可发布：{disabled_reason}")

    st.markdown("### 最近快照记录")
    snapshot_runs = [row for row in list_run_records(bundle) if row.get("action_key") == "publish_snapshot"]
    if not snapshot_runs:
        st.info("当前还没有快照发布记录。")
    else:
        for row in snapshot_runs[:5]:
            st.write(f"{row.get('time', '未记录')} | {row.get('operator', '系统')} | {row.get('note', '') or '发布完整快照'}")



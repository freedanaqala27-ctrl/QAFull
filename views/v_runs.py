from __future__ import annotations

from pathlib import Path

import streamlit as st

from evaluation_system.actions import get_action
from evaluation_system.components import badge_html, download_file_button, render_empty_state, render_page_header
from evaluation_system.runner import action_is_executable, execute_action, recover_task
from evaluation_system.state_store import load_csv, load_json_doc, load_jsonl_docs, list_run_records, run_status_badge, set_console_flash


RUN_FILTER_MAP = {
    "全部": None,
    "成功": "success",
    "失败": "failed",
    "执行中": "running",
    "待执行": "queued",
}

WORK_ORDER_FILTERS = {
    "全部": None,
    "异常中": {"failed"},
    "执行中": {"running", "queued"},
    "已完成": {"completed"},
    "已恢复": {"recovered"},
}

WORK_ORDER_TONES = {
    "queued": "info",
    "running": "warning",
    "completed": "success",
    "failed": "danger",
    "recovered": "success",
    "cancelled": "neutral",
}

ACTION_LABELS = {
    "start_generation": "生成候选题",
    "finalize_review_batch": "更新正式题库",
    "run_auto_evaluation": "准备测评结果",
    "generate_student_packets": "准备发放材料",
    "freeze_analysis_input": "确认分析样本",
    "generate_analysis_report": "生成报告",
    "publish_snapshot": "发布结果快照",
    "request_assets": "补充评测材料",
    "approve_candidate": "审核通过",
    "reject_candidate": "审核驳回",
    "regenerate_candidate": "打回重生成",
}

EVENT_LABELS = {
    "task.state_changed": "更新处理状态",
    "task.recovered": "恢复处理",
    "task.started": "开始处理",
    "task.completed": "完成处理",
    "task.failed": "处理未完成",
    "run.recorded": "登记处理记录",
    "review.approved": "审核通过",
    "review.rejected": "审核驳回",
    "review.regenerated": "打回重生成",
    "settings.updated": "更新系统设置",
    "snapshot.published": "发布结果快照",
}

STATUS_TEXT = {
    "queued": "待执行",
    "running": "执行中",
    "completed": "已完成",
    "failed": "未完成",
    "recovered": "已恢复",
    "cancelled": "已取消",
    "success": "已完成",
}


def _preview_file(path_value: str) -> None:
    path = Path(path_value)
    if not path.exists():
        st.caption("文件不存在。")
        return
    if path.is_dir():
        st.caption("当前路径是目录，请改为查看具体文件。")
        return
    suffix = path.suffix.lower()
    if suffix == ".csv":
        render = load_csv(path)
        st.dataframe(render.head(30), use_container_width=True, hide_index=True)
        return
    if suffix == ".json":
        st.json(load_json_doc(path))
        return
    if suffix == ".jsonl":
        st.json(load_jsonl_docs(path)[:20])
        return
    st.code(path.read_text(encoding="utf-8", errors="ignore")[:4000])


def _friendly_action_label(action_key: str, fallback: str = "") -> str:
    clean_key = str(action_key or "").strip()
    if clean_key in ACTION_LABELS:
        return ACTION_LABELS[clean_key]
    return fallback or clean_key or "未命名事项"


def _friendly_status_text(status: str, fallback: str = "") -> str:
    clean_status = str(status or "").strip()
    return fallback or STATUS_TEXT.get(clean_status, clean_status or "未记录")


def _friendly_work_order_title(row: dict) -> str:
    return str(row.get("task_label") or _friendly_action_label(row.get("action_key", ""), row.get("task_key", "")))


def _friendly_event_label(row: dict) -> str:
    event_type = str(row.get("event_type") or "").strip()
    if event_type in EVENT_LABELS:
        return EVENT_LABELS[event_type]
    if "review" in event_type and "approve" in event_type:
        return "审核通过"
    if "review" in event_type and "reject" in event_type:
        return "审核驳回"
    if "recover" in event_type:
        return "恢复处理"
    if "settings" in event_type:
        return "更新系统设置"
    if "snapshot" in event_type:
        return "发布结果快照"
    if "task" in event_type:
        return "更新处理状态"
    if "run" in event_type or "action" in event_type:
        return "执行处理"
    return event_type.replace(".", " / ") if event_type else "系统处理"


def _friendly_event_note(row: dict) -> str:
    detail = row.get("detail") or {}
    if isinstance(detail, dict):
        for key in ["message", "note", "summary", "reason"]:
            value = detail.get(key)
            if value:
                return str(value)
        status_from = detail.get("from")
        status_to = detail.get("to")
        if status_from or status_to:
            return f"{status_from or '未记录'} -> {status_to or '未记录'}"
    target = str(row.get("target") or "").strip()
    return target or "已记录关键操作。"


def _work_order_badge(row: dict) -> str:
    status = str(row.get("status") or "queued")
    label = _friendly_status_text(status, str(row.get("status_label") or ""))
    return badge_html(label, WORK_ORDER_TONES.get(status, "neutral"))


def _render_work_orders(bundle: dict) -> None:
    filter_name = st.radio("查看范围", list(WORK_ORDER_FILTERS.keys()), horizontal=True, key="work-order-filter")
    statuses = WORK_ORDER_FILTERS[filter_name]
    work_orders = bundle.get("work_orders", [])
    if statuses is not None:
        work_orders = [row for row in work_orders if row.get("status") in statuses]

    if not work_orders:
        render_empty_state("当前没有需要跟进的处理事项", "处理开始执行后，这里会集中显示需要关注的事项和恢复入口。")
        return

    labels = []
    for row in work_orders:
        labels.append(
            f"{row.get('time', '未记录')} | {_friendly_work_order_title(row)} | {_friendly_status_text(row.get('status', ''), str(row.get('status_label') or ''))}"
        )

    left, right = st.columns([0.96, 1.24], gap="large")
    with left:
        selected_label = st.radio("处理事项列表", labels, label_visibility="collapsed")
        selected = work_orders[labels.index(selected_label)]
        st.markdown(_work_order_badge(selected), unsafe_allow_html=True)
        st.caption(f"发起人：{selected.get('created_by', '系统')}")
        if selected.get("note"):
            st.write(selected["note"])
        if selected.get("task_recovery_hint"):
            st.info(selected["task_recovery_hint"])

    with right:
        selected = work_orders[labels.index(selected_label)]
        preview_targets = [*(selected.get("outputs") or []), *(selected.get("logs") or [])]
        st.markdown("### 处理详情")
        st.text_input("事项", value=_friendly_work_order_title(selected), disabled=True)
        st.text_input("处理进度", value=_friendly_status_text(selected.get("status", ""), str(selected.get("status_label") or "")), disabled=True)
        st.text_input("关联记录", value=selected.get("run_id", "") or "未生成", disabled=True)
        st.text_input("已尝试次数", value=str(selected.get("attempt_index", "") or "1"), disabled=True)
        st.text_input("可继续重试", value=str(selected.get("task_retry_remaining", 0)), disabled=True)
        if selected.get("outputs"):
            st.text_area("相关文件", value="\n".join(selected.get("outputs") or []), height=90, disabled=True)
        if selected.get("logs"):
            st.text_area("处理日志", value="\n".join(selected.get("logs") or []), height=90, disabled=True)
        if selected.get("error"):
            st.error(f"本次处理未完成\n\n{selected['error']}")

        action_cols = st.columns(3)
        can_retry = bool(selected.get("task_retry_available")) and selected.get("status") == "failed"
        if action_cols[0].button("立即重试", use_container_width=True, disabled=not can_retry):
            with st.spinner("正在重新发起处理..."):
                result = recover_task(
                    selected.get("task_key", ""),
                    operator=st.session_state["console_role"],
                    strategy="retry_now",
                    note=f"从处理事项页重试：{selected.get('work_order_id', '')}",
                    source_work_order_id=selected.get("work_order_id", ""),
                )
            if result["status"] == "success" and selected.get("action_key") == "publish_snapshot":
                st.session_state["snapshot_locked_override"] = True
            set_console_flash(result["message"], "success" if result["status"] == "success" else "danger")
            st.cache_data.clear()
            st.rerun()
        can_mark_ready = selected.get("status") == "failed" or selected.get("task_status") == "failed"
        if action_cols[1].button("标记可继续", use_container_width=True, disabled=not can_mark_ready):
            result = recover_task(
                selected.get("task_key", ""),
                operator=st.session_state["console_role"],
                strategy="mark_ready",
                note=f"从处理事项页人工恢复：{selected.get('work_order_id', '')}",
                source_work_order_id=selected.get("work_order_id", ""),
            )
            set_console_flash(result["message"], "success" if result["status"] == "success" else "danger")
            st.cache_data.clear()
            st.rerun()
        with action_cols[2]:
            with st.popover("查看相关文件", use_container_width=True):
                if not preview_targets:
                    st.caption("当前还没有可查看的文件。")
                else:
                    preview_name = st.selectbox("选择文件", preview_targets, key=f"work-order-preview-{selected.get('work_order_id', '')}")
                    _preview_file(preview_name)


def _render_run_records(bundle: dict) -> None:
    filter_name = st.radio("查看状态", list(RUN_FILTER_MAP.keys()), horizontal=True, key="run-filter")
    records = list_run_records(bundle)
    if RUN_FILTER_MAP[filter_name] is not None:
        records = [item for item in records if item.get("status") == RUN_FILTER_MAP[filter_name]]

    if not records:
        render_empty_state("当前还没有处理记录", "业务动作执行后，这里会保留处理结果和相关文件入口。")
        return

    labels = []
    for item in records:
        status_label, _ = run_status_badge(item.get("status", "queued"))
        labels.append(f"{item.get('time', '未记录')} | {_friendly_action_label(item.get('action_key', ''), item.get('action_name', ''))} | {status_label}")

    left, right = st.columns([0.92, 1.28], gap="large")
    with left:
        selected_label = st.radio("处理记录列表", labels, label_visibility="collapsed")
        selected_index = labels.index(selected_label)
        selected = records[selected_index]
        selected_status_label, selected_tone = run_status_badge(selected.get("status", "queued"))
        st.markdown(badge_html(selected_status_label, selected_tone), unsafe_allow_html=True)
        st.caption(f"处理人：{selected.get('operator', '系统')}  |  用时：{selected.get('duration', '未记录')}")
        if selected.get("note"):
            st.write(selected["note"])
    with right:
        selected = records[labels.index(selected_label)]
        action_meta = get_action(selected.get("action_key", ""))
        run_manifest = selected.get("manifest", "")
        preview_targets = []
        for value in [*(selected.get("outputs") or []), *(selected.get("logs") or [])]:
            if value and value not in preview_targets:
                preview_targets.append(value)

        st.markdown("### 记录详情")
        st.text_input("处理事项", value=_friendly_action_label(selected.get("action_key", ""), selected.get("action_name", "")), disabled=True)
        st.text_input("处理进度", value=run_status_badge(selected.get("status", "queued"))[0], disabled=True)
        st.text_input("关联处理单", value=selected.get("work_order_id", "") or "未关联", disabled=True)
        if selected.get("outputs") or action_meta.get("output_paths"):
            st.text_area(
                "结果文件",
                value="\n".join(selected.get("outputs") or [str(path) for path in action_meta.get("output_paths", [])]),
                height=120,
                disabled=True,
            )
        if selected.get("logs"):
            st.text_area("处理日志", value="\n".join(selected.get("logs") or []), height=120, disabled=True)
        if selected.get("error"):
            st.error(f"本次处理未完成\n\n{selected['error']}")
        action_cols = st.columns(3)
        can_rerun = action_is_executable(selected.get("action_key", ""))
        if action_cols[0].button("再次执行", use_container_width=True, disabled=not can_rerun):
            with st.spinner(f"正在重新执行：{_friendly_action_label(selected.get('action_key', ''), selected.get('action_name', ''))}..."):
                result = execute_action(
                    selected.get("action_key", ""),
                    operator=st.session_state["console_role"],
                    note=f"从处理记录页重试：{selected.get('id', '')}",
                    params=selected.get("params") or {},
                )
            if result["status"] == "success" and selected.get("action_key") == "publish_snapshot":
                st.session_state["snapshot_locked_override"] = True
            set_console_flash(result["message"], "success" if result["status"] == "success" else "danger")
            st.cache_data.clear()
            st.rerun()
        with action_cols[1]:
            if run_manifest:
                download_file_button(Path(run_manifest), "下载处理日志", "run-download-manifest")
            else:
                st.button("下载处理日志", disabled=True, use_container_width=True)
        with action_cols[2]:
            with st.popover("查看结果文件", use_container_width=True):
                if not preview_targets:
                    st.caption("当前没有可查看的结果文件。")
                else:
                    preview_name = st.selectbox("选择文件", preview_targets, key=f"run-preview-{selected.get('id', '')}")
                    _preview_file(preview_name)


def _render_audit_events(bundle: dict) -> None:
    audit_rows = bundle.get("audit_events", [])
    if not audit_rows:
        render_empty_state("当前还没有操作记录", "关键操作发生后，这里会记录谁在什么时候完成了什么处理。")
        return

    st.caption("这里保留关键操作，方便回看处理过程。")
    for row in audit_rows[:40]:
        cols = st.columns([1.2, 1.0, 1.1, 2.7])
        cols[0].write(row.get("time", "未记录"))
        cols[1].write(row.get("actor", "系统"))
        cols[2].write(_friendly_event_label(row))
        cols[3].write(_friendly_event_note(row))


def render(bundle: dict) -> None:
    render_page_header("运行记录", "查看各项处理进度、结果文件和关键操作记录。")
    work_order_tab, run_tab, audit_tab = st.tabs(["处理事项", "处理记录", "操作记录"])
    with work_order_tab:
        _render_work_orders(bundle)
    with run_tab:
        _render_run_records(bundle)
    with audit_tab:
        _render_audit_events(bundle)

from __future__ import annotations

import streamlit as st

from .common import PACKETS_DIR, load_csv, normalize_text, render_kpi_cards, render_panel


def render_survey_tab() -> None:
    st.subheader("Student Survey Materials")
    render_panel(
        "Student packet showcase",
        "这里聚焦展示学生问卷所使用的题包结构、每包题量和单题预览，不再展示发放和运营层面的材料。",
        eyebrow="Survey",
    )

    package_manifest = load_csv(PACKETS_DIR / "student_package_manifest.curated.v1.csv")
    if package_manifest.empty:
        st.info("当前没有可展示的学生题包数据。")
        return

    exercise_count_series = package_manifest.get("exercise_count")
    total_exercises = (
        int(exercise_count_series.astype(int).sum())
        if exercise_count_series is not None
        else 0
    )
    avg_exercises = (
        f"{exercise_count_series.astype(float).mean():.1f}"
        if exercise_count_series is not None
        else "0.0"
    )

    render_kpi_cards(
        [
            ("Student packages", str(len(package_manifest))),
            ("Total packaged exercises", str(total_exercises)),
            ("Average items per package", avg_exercises),
        ]
    )

    st.markdown("**Package overview**")
    overview_columns = [
        column
        for column in ["package_id", "exercise_count", "pair_count"]
        if column in package_manifest.columns
    ]
    st.dataframe(
        package_manifest[overview_columns],
        use_container_width=True,
        hide_index=True,
    )

    package_id = st.selectbox(
        "Preview a student packet",
        package_manifest["package_id"].astype(str).tolist(),
        key="survey_package_preview",
    )
    packet_path = (
        PACKETS_DIR
        / "student_packages"
        / package_id
        / "student_eval_packet.zh-CN.curated.v1.csv"
    )
    packet_df = load_csv(packet_path)
    if packet_df.empty:
        packet_df = load_csv(
            PACKETS_DIR
            / "student_packages"
            / package_id
            / "student_eval_packet.curated.v1.csv"
        )

    if packet_df.empty:
        st.info("当前题包没有可展示的题目内容。")
        return

    st.markdown("**Packet contents**")
    preview_columns = [
        column
        for column in [
            "display_order",
            "blind_exercise_id",
            "topic",
            "difficulty",
            "exercise_type",
            "title",
        ]
        if column in packet_df.columns
    ]
    st.dataframe(packet_df[preview_columns], use_container_width=True, hide_index=True)

    selected_item = st.selectbox(
        "Preview a specific exercise",
        packet_df["blind_exercise_id"].astype(str).tolist(),
        key="survey_item_preview",
    )
    row = packet_df.loc[
        packet_df["blind_exercise_id"].astype(str) == str(selected_item)
    ].iloc[0]

    render_panel(
        normalize_text(row.get("title"), "Untitled exercise"),
        (
            f"Topic: {normalize_text(row.get('topic'), 'Unlabeled')} | "
            f"Difficulty: {normalize_text(row.get('difficulty'), 'Unlabeled')} | "
            f"Type: {normalize_text(row.get('exercise_type'), 'Unlabeled')}"
        ),
        eyebrow="Exercise Preview",
    )
    st.markdown("**Instruction**")
    st.write(normalize_text(row.get("instruction_text"), "无"))

    starter_code = normalize_text(row.get("starter_code"))
    if starter_code.strip():
        st.markdown("**Starter code**")
        st.code(starter_code, language="python")

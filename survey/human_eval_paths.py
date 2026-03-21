from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    from .curated_paths import CuratedPaths, build_curated_paths
    from .export_paths import ExportPaths, build_export_paths
    from .survey_paths import SurveyPaths, build_survey_paths
except ImportError:
    from curated_paths import CuratedPaths, build_curated_paths
    from export_paths import ExportPaths, build_export_paths
    from survey_paths import SurveyPaths, build_survey_paths


@dataclass(frozen=True)
class HumanEvalPaths:
    project_root: Path
    results_dir: Path
    curated_dir: Path
    human_eval_packets_dir: Path
    packets_dir: Path
    materials_dir: Path
    templates_dir: Path
    distribution_dir: Path
    audit_dir: Path
    audit_build_dir: Path
    audit_quality_dir: Path
    audit_materials_dir: Path
    expert_packages_dir: Path
    student_packages_dir: Path
    expert_packet: Path
    student_packet: Path
    student_packet_zh: Path
    expert_package_manifest: Path
    student_package_manifest: Path
    expert_batch_template: Path
    student_batch_template: Path
    expert_response_template: Path
    student_response_template: Path
    blind_review_booklet_md: Path
    blind_review_booklet_html: Path
    package_materials_manifest: Path
    human_eval_materials_manifest: Path
    wjx_expert_question_bank: Path
    wjx_student_question_bank: Path
    wjx_expert_question_outline: Path
    wjx_student_question_outline: Path
    wjx_package_manifest: Path
    wjx_question_bank_manifest: Path
    student_distribution_sheet: Path
    student_distribution_with_qrcodes: Path
    student_qrcodes_dir: Path
    student_qrcode_print_sheets: Path
    student_packets_zh_manifest: Path
    eval_packet_manifest: Path
    eval_packet_build_issues: Path
    human_eval_fairness_audit: Path
    human_eval_source_balance: Path
    export_dir: Path
    student_meta_export: Path
    student_ratings_export: Path
    student_batch_export: Path


def _combine_paths(
    curated_paths: CuratedPaths,
    survey_paths: SurveyPaths,
    export_paths: ExportPaths,
) -> HumanEvalPaths:
    return HumanEvalPaths(
        project_root=curated_paths.project_root,
        results_dir=curated_paths.results_dir,
        curated_dir=curated_paths.curated_dir,
        human_eval_packets_dir=survey_paths.human_eval_packets_dir,
        packets_dir=survey_paths.packets_dir,
        materials_dir=survey_paths.materials_dir,
        templates_dir=survey_paths.templates_dir,
        distribution_dir=survey_paths.distribution_dir,
        audit_dir=survey_paths.audit_dir,
        audit_build_dir=survey_paths.audit_build_dir,
        audit_quality_dir=survey_paths.audit_quality_dir,
        audit_materials_dir=survey_paths.audit_materials_dir,
        expert_packages_dir=survey_paths.expert_packages_dir,
        student_packages_dir=survey_paths.student_packages_dir,
        expert_packet=survey_paths.expert_packet,
        student_packet=survey_paths.student_packet,
        student_packet_zh=survey_paths.student_packet_zh,
        expert_package_manifest=survey_paths.expert_package_manifest,
        student_package_manifest=survey_paths.student_package_manifest,
        expert_batch_template=survey_paths.expert_batch_template,
        student_batch_template=survey_paths.student_batch_template,
        expert_response_template=survey_paths.expert_response_template,
        student_response_template=survey_paths.student_response_template,
        blind_review_booklet_md=survey_paths.blind_review_booklet_md,
        blind_review_booklet_html=survey_paths.blind_review_booklet_html,
        package_materials_manifest=survey_paths.package_materials_manifest,
        human_eval_materials_manifest=survey_paths.human_eval_materials_manifest,
        wjx_expert_question_bank=survey_paths.wjx_expert_question_bank,
        wjx_student_question_bank=survey_paths.wjx_student_question_bank,
        wjx_expert_question_outline=survey_paths.wjx_expert_question_outline,
        wjx_student_question_outline=survey_paths.wjx_student_question_outline,
        wjx_package_manifest=survey_paths.wjx_package_manifest,
        wjx_question_bank_manifest=survey_paths.wjx_question_bank_manifest,
        student_distribution_sheet=survey_paths.student_distribution_sheet,
        student_distribution_with_qrcodes=survey_paths.student_distribution_with_qrcodes,
        student_qrcodes_dir=survey_paths.student_qrcodes_dir,
        student_qrcode_print_sheets=survey_paths.student_qrcode_print_sheets,
        student_packets_zh_manifest=survey_paths.student_packets_zh_manifest,
        eval_packet_manifest=survey_paths.eval_packet_manifest,
        eval_packet_build_issues=survey_paths.eval_packet_build_issues,
        human_eval_fairness_audit=survey_paths.human_eval_fairness_audit,
        human_eval_source_balance=survey_paths.human_eval_source_balance,
        export_dir=export_paths.export_dir,
        student_meta_export=export_paths.student_meta_export,
        student_ratings_export=export_paths.student_ratings_export,
        student_batch_export=export_paths.student_batch_export,
    )


def build_human_eval_paths(project_root: Path) -> HumanEvalPaths:
    curated_paths = build_curated_paths(project_root)
    survey_paths = build_survey_paths(curated_paths)
    export_paths = build_export_paths(project_root)
    return _combine_paths(curated_paths, survey_paths, export_paths)


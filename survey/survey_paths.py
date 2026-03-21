from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    from .curated_paths import CuratedPaths
except ImportError:
    from curated_paths import CuratedPaths


@dataclass(frozen=True)
class SurveyPaths:
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


def build_survey_paths(curated_paths: CuratedPaths) -> SurveyPaths:
    human_eval_packets_dir = curated_paths.curated_dir / "human_eval_packets"
    packets_dir = human_eval_packets_dir / "packets"
    materials_dir = human_eval_packets_dir / "materials"
    templates_dir = human_eval_packets_dir / "templates"
    distribution_dir = human_eval_packets_dir / "distribution"
    audit_dir = human_eval_packets_dir / "audit"
    audit_build_dir = audit_dir / "build"
    audit_quality_dir = audit_dir / "quality"
    audit_materials_dir = audit_dir / "materials"
    expert_packages_dir = packets_dir / "expert_packages"
    student_packages_dir = packets_dir / "student_packages"

    return SurveyPaths(
        human_eval_packets_dir=human_eval_packets_dir,
        packets_dir=packets_dir,
        materials_dir=materials_dir,
        templates_dir=templates_dir,
        distribution_dir=distribution_dir,
        audit_dir=audit_dir,
        audit_build_dir=audit_build_dir,
        audit_quality_dir=audit_quality_dir,
        audit_materials_dir=audit_materials_dir,
        expert_packages_dir=expert_packages_dir,
        student_packages_dir=student_packages_dir,
        expert_packet=packets_dir / "expert_eval_packet.curated.v1.csv",
        student_packet=packets_dir / "student_eval_packet.curated.v1.csv",
        student_packet_zh=packets_dir / "student_eval_packet.zh-CN.curated.v1.csv",
        expert_package_manifest=packets_dir / "expert_package_manifest.curated.v1.csv",
        student_package_manifest=packets_dir / "student_package_manifest.curated.v1.csv",
        expert_batch_template=templates_dir / "expert_batch_template.curated.v1.csv",
        student_batch_template=templates_dir / "student_batch_template.curated.v1.csv",
        expert_response_template=templates_dir / "expert_response_template.curated.v1.csv",
        student_response_template=templates_dir / "student_response_template.curated.v1.csv",
        blind_review_booklet_md=materials_dir / "blind_review_booklet.curated.md",
        blind_review_booklet_html=materials_dir / "blind_review_booklet.curated.html",
        package_materials_manifest=audit_materials_dir / "package_materials_manifest.curated.v1.csv",
        human_eval_materials_manifest=audit_materials_dir / "human_eval_materials_manifest.v1.json",
        wjx_expert_question_bank=materials_dir / "wjx_expert_question_bank.curated.txt",
        wjx_student_question_bank=materials_dir / "wjx_student_question_bank.curated.txt",
        wjx_expert_question_outline=materials_dir / "wjx_expert_question_outline.curated.csv",
        wjx_student_question_outline=materials_dir / "wjx_student_question_outline.curated.csv",
        wjx_package_manifest=audit_dir / "wjx_package_manifest.curated.v1.csv",
        wjx_question_bank_manifest=audit_dir / "wjx_question_bank_manifest.v1.json",
        student_distribution_sheet=distribution_dir / "student_distribution_sheet.curated.v1.csv",
        student_distribution_with_qrcodes=distribution_dir / "student_distribution_with_qrcodes.curated.v1.csv",
        student_qrcodes_dir=distribution_dir / "student_qrcodes",
        student_qrcode_print_sheets=distribution_dir / "student_qrcode_print_sheets.curated.html",
        student_packets_zh_manifest=audit_build_dir / "student_packets.zh-CN.manifest.v1.json",
        eval_packet_manifest=audit_build_dir / "eval_packet_manifest.v1.json",
        eval_packet_build_issues=audit_build_dir / "eval_packet_build_issues.v1.csv",
        human_eval_fairness_audit=audit_quality_dir / "human_eval_fairness_audit.curated.v1.csv",
        human_eval_source_balance=audit_quality_dir / "human_eval_source_balance.curated.v1.csv",
    )


from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_DIR = PROJECT_ROOT / "results" / "curated" / "human_eval_packets"


@dataclass(frozen=True)
class MoveRule:
    section: str
    source: str
    target: str


@dataclass
class PlannedMove:
    section: str
    source: str
    target: str
    status: str
    detail: str = ""


MOVE_RULES = [
    MoveRule("packets", "expert_packages", "packets/expert_packages"),
    MoveRule("packets", "student_packages", "packets/student_packages"),
    MoveRule(
        "packets",
        "expert_eval_packet.curated.v1.csv",
        "packets/expert_eval_packet.curated.v1.csv",
    ),
    MoveRule(
        "packets",
        "student_eval_packet.curated.v1.csv",
        "packets/student_eval_packet.curated.v1.csv",
    ),
    MoveRule(
        "packets",
        "student_eval_packet.zh-CN.curated.v1.csv",
        "packets/student_eval_packet.zh-CN.curated.v1.csv",
    ),
    MoveRule(
        "packets",
        "expert_package_manifest.curated.v1.csv",
        "packets/expert_package_manifest.curated.v1.csv",
    ),
    MoveRule(
        "packets",
        "student_package_manifest.curated.v1.csv",
        "packets/student_package_manifest.curated.v1.csv",
    ),
    MoveRule(
        "materials",
        "blind_review_booklet.curated.html",
        "materials/blind_review_booklet.curated.html",
    ),
    MoveRule(
        "materials",
        "blind_review_booklet.curated.md",
        "materials/blind_review_booklet.curated.md",
    ),
    MoveRule(
        "materials",
        "wjx_expert_question_bank.curated.txt",
        "materials/wjx_expert_question_bank.curated.txt",
    ),
    MoveRule(
        "materials",
        "wjx_student_question_bank.curated.txt",
        "materials/wjx_student_question_bank.curated.txt",
    ),
    MoveRule(
        "materials",
        "wjx_expert_question_outline.curated.csv",
        "materials/wjx_expert_question_outline.curated.csv",
    ),
    MoveRule(
        "materials",
        "wjx_student_question_outline.curated.csv",
        "materials/wjx_student_question_outline.curated.csv",
    ),
    MoveRule(
        "templates",
        "expert_response_template.curated.v1.csv",
        "templates/expert_response_template.curated.v1.csv",
    ),
    MoveRule(
        "templates",
        "student_response_template.curated.v1.csv",
        "templates/student_response_template.curated.v1.csv",
    ),
    MoveRule(
        "templates",
        "expert_batch_template.curated.v1.csv",
        "templates/expert_batch_template.curated.v1.csv",
    ),
    MoveRule(
        "templates",
        "student_batch_template.curated.v1.csv",
        "templates/student_batch_template.curated.v1.csv",
    ),
    MoveRule(
        "distribution",
        "student_distribution_sheet.curated.v1.csv",
        "distribution/student_distribution_sheet.curated.v1.csv",
    ),
    MoveRule(
        "distribution",
        "student_distribution_with_qrcodes.curated.v1.csv",
        "distribution/student_distribution_with_qrcodes.curated.v1.csv",
    ),
    MoveRule(
        "distribution",
        "student_qrcode_print_sheets.curated.html",
        "distribution/student_qrcode_print_sheets.curated.html",
    ),
    MoveRule("distribution", "student_qrcodes", "distribution/student_qrcodes"),
    MoveRule(
        "audit",
        "eval_packet_build_issues.v1.csv",
        "audit/build/eval_packet_build_issues.v1.csv",
    ),
    MoveRule("audit", "eval_packet_manifest.v1.json", "audit/build/eval_packet_manifest.v1.json"),
    MoveRule(
        "audit",
        "human_eval_fairness_audit.curated.v1.csv",
        "audit/quality/human_eval_fairness_audit.curated.v1.csv",
    ),
    MoveRule(
        "audit",
        "human_eval_source_balance.curated.v1.csv",
        "audit/quality/human_eval_source_balance.curated.v1.csv",
    ),
    MoveRule(
        "audit",
        "human_eval_materials_manifest.v1.json",
        "audit/materials/human_eval_materials_manifest.v1.json",
    ),
    MoveRule(
        "audit",
        "package_materials_manifest.curated.v1.csv",
        "audit/materials/package_materials_manifest.curated.v1.csv",
    ),
    MoveRule(
        "audit",
        "student_packets.zh-CN.manifest.v1.json",
        "audit/build/student_packets.zh-CN.manifest.v1.json",
    ),
    MoveRule(
        "audit",
        "wjx_package_manifest.curated.v1.csv",
        "audit/wjx_package_manifest.curated.v1.csv",
    ),
    MoveRule(
        "audit",
        "wjx_question_bank_manifest.v1.json",
        "audit/wjx_question_bank_manifest.v1.json",
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Restructure results/curated/human_eval_packets into packets/, materials/, "
            "templates/, distribution/, and audit/. Default mode is dry-run."
        )
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=DEFAULT_BASE_DIR,
        help="Base human_eval_packets directory to restructure.",
    )
    parser.add_argument(
        "--sections",
        nargs="+",
        choices=["packets", "materials", "templates", "distribution", "audit"],
        default=["packets", "materials", "templates", "distribution", "audit"],
        help="Subset of sections to include in the migration plan.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually move files. Without this flag the script only reports the plan.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Optional JSON manifest output path. Defaults to <base-dir>/audit/build/restructure_manifest.v1.json.",
    )
    return parser.parse_args()


def build_plan(base_dir: Path, sections: set[str]) -> list[PlannedMove]:
    plan: list[PlannedMove] = []
    for rule in MOVE_RULES:
        if rule.section not in sections:
            continue
        source_path = base_dir / rule.source
        target_path = base_dir / rule.target

        if source_path.exists() and not target_path.exists():
            status = "pending"
            detail = "ready to move"
        elif source_path.exists() and target_path.exists():
            status = "conflict"
            detail = "source and target both exist"
        elif not source_path.exists() and target_path.exists():
            status = "already_migrated"
            detail = "source missing, target already present"
        else:
            status = "missing"
            detail = "source and target both missing"

        plan.append(
            PlannedMove(
                section=rule.section,
                source=rule.source,
                target=rule.target,
                status=status,
                detail=detail,
            )
        )
    return plan


def execute_plan(base_dir: Path, plan: list[PlannedMove]) -> list[PlannedMove]:
    executed: list[PlannedMove] = []
    for item in plan:
        if item.status != "pending":
            executed.append(item)
            continue

        source_path = base_dir / item.source
        target_path = base_dir / item.target
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_path), str(target_path))
        executed.append(
            PlannedMove(
                section=item.section,
                source=item.source,
                target=item.target,
                status="moved",
                detail="moved successfully",
            )
        )
    return executed


def summarize_plan(plan: list[PlannedMove]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for item in plan:
        summary[item.status] = summary.get(item.status, 0) + 1
    return summary


def print_plan(plan: list[PlannedMove], apply: bool) -> None:
    mode = "APPLY" if apply else "DRY-RUN"
    print(f"[{mode}] human_eval_packets restructure plan")
    print("-" * 88)
    for item in plan:
        print(f"{item.status:<16} {item.section:<12} {item.source} -> {item.target}")
        if item.detail:
            print(f"{'':<16} {'':<12} {item.detail}")
    print("-" * 88)
    summary = summarize_plan(plan)
    for status in sorted(summary):
        print(f"{status}: {summary[status]}")


def write_manifest(manifest_path: Path, base_dir: Path, sections: list[str], apply: bool, plan: list[PlannedMove]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "base_dir": str(base_dir),
        "mode": "apply" if apply else "dry-run",
        "sections": sections,
        "summary": summarize_plan(plan),
        "moves": [asdict(item) for item in plan],
        "note": (
            "This script only restructures human_eval_packets artifacts. "
            "Downstream readers still need path updates before the new layout becomes the runtime default."
        ),
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    base_dir = args.base_dir.resolve()
    manifest_path = args.manifest or (base_dir / "audit" / "build" / "restructure_manifest.v1.json")

    plan = build_plan(base_dir, set(args.sections))
    final_plan = execute_plan(base_dir, plan) if args.apply else plan
    print_plan(final_plan, apply=args.apply)
    write_manifest(manifest_path, base_dir, args.sections, args.apply, final_plan)
    print(f"\nManifest written to: {manifest_path}")


if __name__ == "__main__":
    main()

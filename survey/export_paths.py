from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExportPaths:
    export_dir: Path
    student_meta_export: Path
    student_ratings_export: Path
    student_batch_export: Path


def build_export_paths(project_root: Path) -> ExportPaths:
    export_dir = project_root / "data" / "human_eval"
    return ExportPaths(
        export_dir=export_dir,
        student_meta_export=export_dir / "student_meta.csv",
        student_ratings_export=export_dir / "student_ratings.csv",
        student_batch_export=export_dir / "student_batch.csv",
    )

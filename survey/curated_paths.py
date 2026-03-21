from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CuratedPaths:
    project_root: Path
    results_dir: Path
    curated_dir: Path


def build_curated_paths(project_root: Path) -> CuratedPaths:
    results_dir = project_root / "results"
    curated_dir = results_dir / "curated"
    return CuratedPaths(
        project_root=project_root,
        results_dir=results_dir,
        curated_dir=curated_dir,
    )

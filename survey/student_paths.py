from __future__ import annotations

from pathlib import Path

try:
    from .human_eval_paths import HumanEvalPaths as StudentSurveyPaths
    from .human_eval_paths import build_human_eval_paths
except ImportError:
    from human_eval_paths import HumanEvalPaths as StudentSurveyPaths
    from human_eval_paths import build_human_eval_paths


def build_student_survey_paths(project_root: Path) -> StudentSurveyPaths:
    return build_human_eval_paths(project_root)


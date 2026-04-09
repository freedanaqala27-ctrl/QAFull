from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from _shared_io import read_jsonl_rows, write_jsonl_rows

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CURATED_DIR = PROJECT_ROOT / "results" / "curated"
REFERENCE_SOLUTIONS = CURATED_DIR / "reference_solutions.curated.v1.jsonl"
EXECUTABLE_TESTS = CURATED_DIR / "executable_tests.curated.v1.jsonl"


def dedent(code: str) -> str:
    return textwrap.dedent(code).strip() + "\n"


REFERENCE_UPDATES: dict[str, dict[str, Any]] = {
    "CNN-02": {
        "evaluation_mode": "concept_to_code",
        "entry_point": "comp_conv2d",
        "solution": dedent(
            """
            import torch
            import torch.nn as nn


            def comp_conv2d(conv2d, X):
                X = X.reshape((1, 1) + X.shape)
                Y = conv2d(X)
                return Y.reshape(Y.shape[2:])


            X = torch.rand(size=(8, 8))
            conv2d = nn.LazyConv2d(1, kernel_size=(3, 5), padding=(0, 1), stride=(3, 4))
            output_shape = comp_conv2d(conv2d, X).shape
            """
        ),
        "solution_format": "full_code",
        "setup_code": "",
        "timeout_seconds": 5,
        "required_packages": ["torch"],
        "reference_solution_authority": "expert_reconstructed",
        "overlay_status": "implemented_concept_to_code",
    }
}


TEST_UPDATES: dict[str, dict[str, Any]] = {
    "CNN-02": {
        "public_tests_py": [
            "assert callable(comp_conv2d)",
            "assert tuple(output_shape) == (2, 2)",
        ],
        "hidden_tests_py": [
            "X2 = torch.rand(size=(10, 12)); conv = nn.LazyConv2d(1, kernel_size=(3, 3), padding=(1, 1), stride=(2, 2)); assert tuple(comp_conv2d(conv, X2).shape) == (5, 6)",
        ],
        "surface_checks": [
            {"type": "api_check", "name": "torch_conv_used", "code": "assert isinstance(conv2d, nn.Conv2d)"},
        ],
        "overlay_status": "implemented_concept_to_code",
    }
}


def update_rows(path: Path, updates: dict[str, dict[str, Any]]) -> None:
    rows = read_jsonl_rows(path)
    for row in rows:
        exercise_id = str(row.get("exercise_id", "") or "")
        if exercise_id in updates:
            row.update(updates[exercise_id])
    write_jsonl_rows(rows, path)


def main() -> None:
    update_rows(REFERENCE_SOLUTIONS, REFERENCE_UPDATES)
    update_rows(EXECUTABLE_TESTS, TEST_UPDATES)
    print(f"Updated concept-to-code overlays -> {REFERENCE_SOLUTIONS}")
    print(f"Updated concept-to-code tests -> {EXECUTABLE_TESTS}")


if __name__ == "__main__":
    main()

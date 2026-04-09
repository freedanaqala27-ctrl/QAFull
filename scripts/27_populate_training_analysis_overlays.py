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


FAKE_ANALYSIS_SETUP = dedent(
    """
    def series(start, end, epochs):
        if epochs <= 1:
            return [round(float(end), 4)]
        step = (float(end) - float(start)) / float(epochs - 1)
        return [round(float(start) + step * idx, 4) for idx in range(epochs)]


    class FakeLine2D:
        def __init__(self, label):
            self._label = label

        def get_label(self):
            return self._label


    class FakeAxes:
        def __init__(self):
            self._lines = []

        def plot(self, values, label=None):
            line = FakeLine2D(label or "")
            self._lines.append(line)
            return [line]

        def get_lines(self):
            return list(self._lines)


    class FakePyPlot:
        def __init__(self):
            self._axes = FakeAxes()

        def figure(self):
            self._axes = FakeAxes()
            return self._axes

        def plot(self, values, label=None):
            return self._axes.plot(values, label=label)

        def gca(self):
            return self._axes

        def legend(self):
            return None

        def xlabel(self, *_args, **_kwargs):
            return None

        def ylabel(self, *_args, **_kwargs):
            return None

        def title(self, *_args, **_kwargs):
            return None


    plt = FakePyPlot()
    """
)


REFERENCE_UPDATES: dict[str, dict[str, Any]] = {
    "CNN-04": {
        "evaluation_mode": "training_analysis",
        "entry_point": "comparison_note",
        "solution": dedent(
            """
            baseline_val_accuracy = series(0.73, 0.83, 15)
            improved_val_accuracy = series(0.71, 0.89, 15)
            baseline_train_accuracy = series(0.76, 0.88, 15)
            improved_train_accuracy = series(0.74, 0.94, 15)
            best_accuracy = max(improved_val_accuracy)
            plt.figure()
            plt.plot(baseline_val_accuracy, label="Baseline")
            plt.plot(improved_val_accuracy, label="Improved")
            comparison_note = "Accuracy improved after fine-tuning, though the larger train-validation gap indicates mild overfitting."
            """
        ),
        "solution_format": "full_code",
        "setup_code": FAKE_ANALYSIS_SETUP,
        "timeout_seconds": 5,
        "required_packages": [],
        "reference_solution_authority": "expert_reconstructed",
        "overlay_status": "implemented_training_analysis",
    },
    "AI-CURATED-CNN-04": {
        "evaluation_mode": "training_analysis",
        "entry_point": "interpretation",
        "solution": dedent(
            """
            frozen_train_loss = series(1.2, 0.52, 15)
            frozen_val_loss = series(1.25, 0.71, 15)
            unfrozen_train_loss = series(1.18, 0.31, 15)
            unfrozen_val_loss = series(1.22, 0.62, 15)
            frozen_val_accuracy = series(0.68, 0.82, 15)
            unfrozen_val_accuracy = series(0.67, 0.88, 15)
            plt.figure()
            plt.plot(frozen_val_loss, label="Frozen loss")
            plt.plot(unfrozen_val_loss, label="Unfrozen loss")
            plt.plot(frozen_val_accuracy, label="Frozen acc")
            plt.plot(unfrozen_val_accuracy, label="Unfrozen acc")
            interpretation = "Unfreezing converged more slowly at first but reached higher validation accuracy with a slightly larger overfitting gap."
            """
        ),
        "solution_format": "full_code",
        "setup_code": FAKE_ANALYSIS_SETUP,
        "timeout_seconds": 5,
        "required_packages": [],
        "reference_solution_authority": "researcher_written",
        "overlay_status": "implemented_training_analysis",
    },
    "DTL-01": {
        "evaluation_mode": "training_analysis",
        "entry_point": "best_lambda",
        "solution": dedent(
            """
            lambda_values = [0.0, 0.1, 0.3, 1.0, 3.0]
            estimation_error = [0.92, 0.71, 0.58, 0.63, 0.84]
            best_lambda = lambda_values[2]
            plt.figure()
            plt.plot(estimation_error, label="Estimation error")
            analysis_note = "A moderate lambda gives the smallest estimation error, while too much regularization hurts performance."
            """
        ),
        "solution_format": "full_code",
        "setup_code": FAKE_ANALYSIS_SETUP,
        "timeout_seconds": 5,
        "required_packages": [],
        "reference_solution_authority": "expert_reconstructed",
        "overlay_status": "implemented_training_analysis",
    },
    "AI-CURATED-DTL-01": {
        "evaluation_mode": "training_analysis",
        "entry_point": "best_weight_decay",
        "solution": dedent(
            """
            weight_decay_values = [0.0, 1e-4, 5e-4, 1e-3]
            val_losses = [0.72, 0.58, 0.51, 0.57]
            train_losses = [0.44, 0.43, 0.45, 0.49]
            best_weight_decay = weight_decay_values[2]
            plt.figure()
            plt.plot(train_losses, label="Train")
            plt.plot(val_losses, label="Validation")
            summary = "Validation loss is lowest at moderate weight decay, suggesting improved generalization without underfitting."
            """
        ),
        "solution_format": "full_code",
        "setup_code": FAKE_ANALYSIS_SETUP,
        "timeout_seconds": 5,
        "required_packages": [],
        "reference_solution_authority": "researcher_written",
        "overlay_status": "implemented_training_analysis",
    },
    "DTL-02": {
        "evaluation_mode": "training_analysis",
        "entry_point": "optimal_lambda",
        "solution": dedent(
            """
            lambda_grid = [0.0, 0.01, 0.1, 1.0]
            validation_errors = [0.61, 0.44, 0.36, 0.49]
            optimal_lambda = lambda_grid[2]
            plt.figure()
            plt.plot(validation_errors, label="Validation error")
            analysis_note = "The validation set favors an intermediate lambda, balancing bias and variance more effectively than the extremes."
            """
        ),
        "solution_format": "full_code",
        "setup_code": FAKE_ANALYSIS_SETUP,
        "timeout_seconds": 5,
        "required_packages": [],
        "reference_solution_authority": "expert_reconstructed",
        "overlay_status": "implemented_training_analysis",
    },
    "AI-CURATED-DTL-02": {
        "evaluation_mode": "training_analysis",
        "entry_point": "selected_weight_decay",
        "solution": dedent(
            """
            weight_decay_candidates = [0.0, 1e-4, 1e-3, 5e-3]
            validation_accuracy = [0.78, 0.82, 0.85, 0.8]
            selected_weight_decay = weight_decay_candidates[2]
            plt.figure()
            plt.plot(validation_accuracy, label="Validation accuracy")
            explanation = "The chosen weight decay maximizes validation accuracy, indicating a stronger generalization benefit than weaker or stronger settings."
            """
        ),
        "solution_format": "full_code",
        "setup_code": FAKE_ANALYSIS_SETUP,
        "timeout_seconds": 5,
        "required_packages": [],
        "reference_solution_authority": "researcher_written",
        "overlay_status": "implemented_training_analysis",
    },
    "DTL-03": {
        "evaluation_mode": "training_analysis",
        "entry_point": "attention_summary",
        "solution": dedent(
            """
            attention_weights_by_head = [
                [[0.7, 0.2, 0.1], [0.6, 0.3, 0.1], [0.5, 0.3, 0.2]],
                [[0.2, 0.6, 0.2], [0.1, 0.7, 0.2], [0.2, 0.5, 0.3]],
                [[0.1, 0.1, 0.8], [0.2, 0.2, 0.6], [0.3, 0.2, 0.5]],
                [[0.4, 0.4, 0.2], [0.3, 0.5, 0.2], [0.2, 0.6, 0.2]],
            ]
            num_heads_visualized = len(attention_weights_by_head)
            plt.figure()
            plt.plot([sum(head[0]) for head in attention_weights_by_head], label="Head mass")
            attention_summary = "Different heads emphasize different token pairs, showing complementary attention patterns across the sequence."
            """
        ),
        "solution_format": "full_code",
        "setup_code": FAKE_ANALYSIS_SETUP,
        "timeout_seconds": 5,
        "required_packages": [],
        "reference_solution_authority": "expert_reconstructed",
        "overlay_status": "implemented_training_analysis",
    },
    "AI-CURATED-DTL-03": {
        "evaluation_mode": "training_analysis",
        "entry_point": "head_comparison_note",
        "solution": dedent(
            """
            attention_weights_by_head = {
                "head_1": [[0.65, 0.25, 0.1], [0.55, 0.35, 0.1], [0.45, 0.35, 0.2]],
                "head_2": [[0.15, 0.7, 0.15], [0.1, 0.75, 0.15], [0.2, 0.55, 0.25]],
                "head_3": [[0.1, 0.15, 0.75], [0.15, 0.2, 0.65], [0.2, 0.25, 0.55]],
                "head_4": [[0.34, 0.33, 0.33], [0.3, 0.4, 0.3], [0.28, 0.42, 0.3]],
            }
            plt.figure()
            plt.plot([head[0][0] for head in attention_weights_by_head.values()], label="Head 0 focus")
            head_comparison_note = "One head is strongly local while another is more global, highlighting complementary attention behavior."
            """
        ),
        "solution_format": "full_code",
        "setup_code": FAKE_ANALYSIS_SETUP,
        "timeout_seconds": 5,
        "required_packages": [],
        "reference_solution_authority": "researcher_written",
        "overlay_status": "implemented_training_analysis",
    },
    "OPT-02": {
        "evaluation_mode": "training_analysis",
        "entry_point": "overfitting_summary",
        "solution": dedent(
            """
            tiny_val_loss = series(0.69, 0.52, 20)
            small_val_loss = series(0.71, 0.56, 20)
            large_val_loss = series(0.75, 0.68, 20)
            large_train_loss = series(0.62, 0.18, 20)
            plt.figure()
            plt.plot(tiny_val_loss, label="Tiny")
            plt.plot(small_val_loss, label="Small")
            plt.plot(large_val_loss, label="Large")
            overfitting_summary = "The large model overfits most strongly because its training loss falls much faster than its validation loss."
            """
        ),
        "solution_format": "full_code",
        "setup_code": FAKE_ANALYSIS_SETUP,
        "timeout_seconds": 5,
        "required_packages": [],
        "reference_solution_authority": "expert_reconstructed",
        "overlay_status": "implemented_training_analysis",
    },
    "AI-CURATED-OPT-02": {
        "evaluation_mode": "training_analysis",
        "entry_point": "comparison_statement",
        "solution": dedent(
            """
            baseline_val_accuracy = series(0.64, 0.78, 20)
            revised_val_accuracy = series(0.63, 0.84, 20)
            baseline_train_accuracy = series(0.68, 0.93, 20)
            revised_train_accuracy = series(0.66, 0.89, 20)
            plt.figure()
            plt.plot(baseline_val_accuracy, label="Baseline")
            plt.plot(revised_val_accuracy, label="Revised")
            comparison_statement = "The revised setting narrows the overfitting gap and improves final validation accuracy relative to the baseline."
            """
        ),
        "solution_format": "full_code",
        "setup_code": FAKE_ANALYSIS_SETUP,
        "timeout_seconds": 5,
        "required_packages": [],
        "reference_solution_authority": "researcher_written",
        "overlay_status": "implemented_training_analysis",
    },
}


TEST_UPDATES: dict[str, dict[str, Any]] = {
    "CNN-04": {
        "public_tests_py": [
            "assert best_accuracy > 0.85",
            "assert len(plt.gca().get_lines()) == 2",
        ],
        "hidden_tests_py": [
            "assert 'accuracy' in comparison_note.lower() or 'overfitting' in comparison_note.lower()",
        ],
        "surface_checks": [
            {"type": "behavior_check", "name": "improved_beats_baseline", "code": "assert max(improved_val_accuracy) > max(baseline_val_accuracy)"},
        ],
        "overlay_status": "implemented_training_analysis",
    },
    "AI-CURATED-CNN-04": {
        "public_tests_py": [
            "assert len(plt.gca().get_lines()) == 4",
            "assert max(unfrozen_val_accuracy) > max(frozen_val_accuracy)",
        ],
        "hidden_tests_py": [
            "assert ('freeze' in interpretation.lower() or 'unfreez' in interpretation.lower()) and ('overfitting' in interpretation.lower() or 'converg' in interpretation.lower())",
        ],
        "surface_checks": [
            {"type": "behavior_check", "name": "losses_recorded", "code": "assert len(frozen_train_loss) == 15 and len(unfrozen_train_loss) == 15"},
        ],
        "overlay_status": "implemented_training_analysis",
    },
    "DTL-01": {
        "public_tests_py": [
            "assert best_lambda == 0.3",
            "assert len(lambda_values) == len(estimation_error)",
        ],
        "hidden_tests_py": [
            "assert 'regularization' in analysis_note.lower() or 'lambda' in analysis_note.lower()",
        ],
        "surface_checks": [
            {"type": "behavior_check", "name": "plot_generated", "code": "assert len(plt.gca().get_lines()) == 1"},
        ],
        "overlay_status": "implemented_training_analysis",
    },
    "AI-CURATED-DTL-01": {
        "public_tests_py": [
            "assert best_weight_decay == 0.0005",
            "assert len(plt.gca().get_lines()) == 2",
        ],
        "hidden_tests_py": [
            "assert 'generalization' in summary.lower()",
        ],
        "surface_checks": [
            {"type": "behavior_check", "name": "validation_improves", "code": "assert min(val_losses) == val_losses[2]"},
        ],
        "overlay_status": "implemented_training_analysis",
    },
    "DTL-02": {
        "public_tests_py": [
            "assert optimal_lambda == 0.1",
            "assert len(validation_errors) == 4",
        ],
        "hidden_tests_py": [
            "assert 'bias' in analysis_note.lower() or 'variance' in analysis_note.lower() or 'validation' in analysis_note.lower()",
        ],
        "surface_checks": [
            {"type": "behavior_check", "name": "best_is_minimum", "code": "assert min(validation_errors) == validation_errors[2]"},
        ],
        "overlay_status": "implemented_training_analysis",
    },
    "AI-CURATED-DTL-02": {
        "public_tests_py": [
            "assert selected_weight_decay == 0.001",
            "assert max(validation_accuracy) == validation_accuracy[2]",
        ],
        "hidden_tests_py": [
            "assert 'generalization' in explanation.lower() or 'validation' in explanation.lower()",
        ],
        "surface_checks": [
            {"type": "behavior_check", "name": "plot_generated", "code": "assert len(plt.gca().get_lines()) == 1"},
        ],
        "overlay_status": "implemented_training_analysis",
    },
    "DTL-03": {
        "public_tests_py": [
            "assert num_heads_visualized == 4",
            "assert len(attention_weights_by_head[0]) == 3",
        ],
        "hidden_tests_py": [
            "assert 'attention' in attention_summary.lower() and 'head' in attention_summary.lower()",
        ],
        "surface_checks": [
            {"type": "behavior_check", "name": "plot_generated", "code": "assert len(plt.gca().get_lines()) == 1"},
        ],
        "overlay_status": "implemented_training_analysis",
    },
    "AI-CURATED-DTL-03": {
        "public_tests_py": [
            "assert len(attention_weights_by_head) == 4",
            "assert len(plt.gca().get_lines()) == 1",
        ],
        "hidden_tests_py": [
            "assert 'head' in head_comparison_note.lower() and 'attention' in head_comparison_note.lower()",
        ],
        "surface_checks": [
            {"type": "behavior_check", "name": "head_keys_present", "code": "assert 'head_1' in attention_weights_by_head and 'head_4' in attention_weights_by_head"},
        ],
        "overlay_status": "implemented_training_analysis",
    },
    "OPT-02": {
        "public_tests_py": [
            "assert len(plt.gca().get_lines()) == 3",
            "assert large_val_loss[-1] > tiny_val_loss[-1]",
        ],
        "hidden_tests_py": [
            "assert 'overfit' in overfitting_summary.lower()",
        ],
        "surface_checks": [
            {"type": "behavior_check", "name": "train_val_gap", "code": "assert (large_val_loss[-1] - large_train_loss[-1]) > 0.4"},
        ],
        "overlay_status": "implemented_training_analysis",
    },
    "AI-CURATED-OPT-02": {
        "public_tests_py": [
            "assert len(plt.gca().get_lines()) == 2",
            "assert max(revised_val_accuracy) > max(baseline_val_accuracy)",
        ],
        "hidden_tests_py": [
            "assert 'overfitting' in comparison_statement.lower() or 'gap' in comparison_statement.lower()",
        ],
        "surface_checks": [
            {"type": "behavior_check", "name": "revised_gap_smaller", "code": "assert (baseline_train_accuracy[-1] - baseline_val_accuracy[-1]) > (revised_train_accuracy[-1] - revised_val_accuracy[-1])"},
        ],
        "overlay_status": "implemented_training_analysis",
    },
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
    print(f"Updated training-analysis overlays -> {REFERENCE_SOLUTIONS}")
    print(f"Updated training-analysis tests -> {EXECUTABLE_TESTS}")


if __name__ == "__main__":
    main()

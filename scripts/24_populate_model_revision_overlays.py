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


FAKE_TF_SETUP = dedent(
    """
    from types import SimpleNamespace


    class L2:
        def __init__(self, value):
            self.l2 = float(value)


    class Dense:
        def __init__(self, units, activation=None, input_shape=None, kernel_regularizer=None):
            self.units = units
            self.activation = activation
            self.input_shape = input_shape
            self.kernel_regularizer = kernel_regularizer


    class Dropout:
        def __init__(self, rate):
            self.rate = float(rate)


    class Embedding:
        def __init__(self, input_dim, output_dim):
            self.input_dim = input_dim
            self.output_dim = output_dim


    class GlobalAveragePooling1D:
        pass


    class History:
        def __init__(self, history):
            self.history = history


    def _series(start, end, epochs):
        if epochs <= 1:
            return [round(float(end), 4)]
        step = (float(end) - float(start)) / float(epochs - 1)
        return [round(float(start) + step * idx, 4) for idx in range(epochs)]


    def _dense_layers(model):
        return [layer for layer in model.layers if isinstance(layer, Dense)]


    def _dropout_layers(model):
        return [layer for layer in model.layers if isinstance(layer, Dropout)]


    def _l2_dense_layers(model):
        return [layer for layer in _dense_layers(model) if layer.kernel_regularizer is not None]


    def _history_for_model(model, epochs):
        dense_count = len(_dense_layers(model))
        dropout_count = len(_dropout_layers(model))
        l2_count = len(_l2_dense_layers(model))
        is_binary = model.compile_config.get("loss") == "binary_crossentropy"

        if is_binary:
            if dropout_count >= 2:
                train_acc_end = 0.89
                val_acc_end = 0.84
                train_loss_end = 0.23
                val_loss_end = 0.31
            elif l2_count >= 1:
                train_acc_end = 0.86
                val_acc_end = 0.81
                train_loss_end = 0.27
                val_loss_end = 0.37
            else:
                train_acc_end = 0.94
                val_acc_end = 0.75
                train_loss_end = 0.17
                val_loss_end = 0.46
            return {
                "accuracy": _series(0.65, train_acc_end, epochs),
                "val_accuracy": _series(0.63, val_acc_end, epochs),
                "loss": _series(0.68, train_loss_end, epochs),
                "val_loss": _series(0.69, val_loss_end, epochs),
                "mae": _series(0.7, 0.4, epochs),
                "val_mae": _series(0.72, 0.48, epochs),
            }

        if l2_count >= 3 and dropout_count >= 3:
            mae_end = 1.8
            val_mae_end = 1.95
            loss_end = 7.6
            val_loss_end = 8.4
        elif dropout_count >= 3:
            mae_end = 2.0
            val_mae_end = 2.18
            loss_end = 8.1
            val_loss_end = 8.9
        elif l2_count >= 3:
            mae_end = 2.05
            val_mae_end = 2.22
            loss_end = 8.4
            val_loss_end = 9.1
        else:
            mae_end = 2.3
            val_mae_end = 2.52
            loss_end = 9.2
            val_loss_end = 10.1
        return {
            "accuracy": _series(0.55, 0.72 + 0.01 * dense_count, epochs),
            "val_accuracy": _series(0.53, 0.67 + 0.005 * dense_count, epochs),
            "loss": _series(15.0, loss_end, epochs),
            "val_loss": _series(15.8, val_loss_end, epochs),
            "mae": _series(3.3, mae_end, epochs),
            "val_mae": _series(3.45, val_mae_end, epochs),
        }


    class Sequential:
        def __init__(self, layers):
            self.layers = list(layers)
            self.compile_config = {}

        def compile(self, optimizer=None, loss=None, metrics=None):
            self.compile_config = {
                "optimizer": optimizer,
                "loss": loss,
                "metrics": list(metrics or []),
            }

        def fit(self, *args, **kwargs):
            epochs = int(kwargs.get("epochs", 20))
            return History(_history_for_model(self, epochs))


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


    def compile_and_fit(model, name):
        if not model.compile_config:
            model.compile(optimizer="adam", loss="mse", metrics=["mae"])
        return model.fit(epochs=20, verbose=0)


    regularizers = SimpleNamespace(l2=lambda value: L2(value), L2=L2)
    layers = SimpleNamespace(
        Dense=Dense,
        Dropout=Dropout,
        Embedding=Embedding,
        GlobalAveragePooling1D=GlobalAveragePooling1D,
    )
    keras = SimpleNamespace(Sequential=Sequential, layers=layers, regularizers=regularizers)
    tf = SimpleNamespace(keras=keras)
    plt = FakePyPlot()
    FEATURES = 13
    regularizer_histories = {}
    """
)


REFERENCE_UPDATES: dict[str, dict[str, Any]] = {
    "OPT-03": {
        "evaluation_mode": "model_revision",
        "entry_point": "combined_model",
        "solution": dedent(
            """
            combined_model = tf.keras.Sequential([
                layers.Dense(512, kernel_regularizer=regularizers.l2(0.0001), activation="elu", input_shape=(FEATURES,)),
                layers.Dropout(0.5),
                layers.Dense(512, kernel_regularizer=regularizers.l2(0.0001), activation="elu"),
                layers.Dropout(0.5),
                layers.Dense(512, kernel_regularizer=regularizers.l2(0.0001), activation="elu"),
                layers.Dropout(0.5),
                layers.Dense(512, kernel_regularizer=regularizers.l2(0.0001), activation="elu"),
                layers.Dropout(0.5),
                layers.Dense(1),
            ])
            combined_model.compile(optimizer="adam", loss="mse", metrics=["mae"])
            regularizer_histories["combined"] = compile_and_fit(combined_model, "regularizers/combined")
            """
        ),
        "solution_format": "full_code",
        "setup_code": FAKE_TF_SETUP,
        "timeout_seconds": 5,
        "required_packages": [],
        "reference_solution_authority": "expert_reconstructed",
        "overlay_status": "implemented_model_revision",
    },
    "AI-CURATED-OPT-03": {
        "evaluation_mode": "model_revision",
        "entry_point": "revised_model",
        "solution": dedent(
            """
            baseline_model = keras.Sequential([
                layers.Dense(64, activation="relu", input_shape=(13,)),
                layers.Dense(64, activation="relu"),
                layers.Dense(1),
            ])
            baseline_model.compile(optimizer="adam", loss="mse", metrics=["mae"])
            baseline_history = baseline_model.fit(epochs=20, validation_split=0.2, verbose=0)

            revised_model = keras.Sequential([
                layers.Dense(64, activation="relu", input_shape=(13,), kernel_regularizer=tf.keras.regularizers.L2(1e-4)),
                layers.Dropout(0.3),
                layers.Dense(64, activation="relu", kernel_regularizer=tf.keras.regularizers.L2(1e-4)),
                layers.Dropout(0.3),
                layers.Dense(1, kernel_regularizer=tf.keras.regularizers.L2(1e-4)),
            ])
            revised_model.compile(optimizer="adam", loss="mse", metrics=["mae"])
            revised_history = revised_model.fit(epochs=20, validation_split=0.2, verbose=0)

            final_baseline_val_mae = baseline_history.history["val_mae"][-1]
            final_revised_val_mae = revised_history.history["val_mae"][-1]
            improved = final_revised_val_mae < final_baseline_val_mae
            mae_reduction = round(final_baseline_val_mae - final_revised_val_mae, 3)
            """
        ),
        "solution_format": "full_code",
        "setup_code": FAKE_TF_SETUP,
        "timeout_seconds": 5,
        "required_packages": [],
        "reference_solution_authority": "researcher_written",
        "overlay_status": "implemented_model_revision",
    },
    "OPT-04": {
        "evaluation_mode": "model_revision",
        "entry_point": "l2_model",
        "solution": dedent(
            """
            l2_model = tf.keras.Sequential([
                layers.Dense(512, activation="elu", kernel_regularizer=regularizers.l2(0.001), input_shape=(FEATURES,)),
                layers.Dense(512, activation="elu", kernel_regularizer=regularizers.l2(0.001)),
                layers.Dense(512, activation="elu", kernel_regularizer=regularizers.l2(0.001)),
                layers.Dense(512, activation="elu", kernel_regularizer=regularizers.l2(0.001)),
                layers.Dense(1),
            ])
            l2_model.compile(optimizer="adam", loss="mse", metrics=["mae"])
            regularizer_histories["l2"] = compile_and_fit(l2_model, "regularizers/l2")
            """
        ),
        "solution_format": "full_code",
        "setup_code": FAKE_TF_SETUP,
        "timeout_seconds": 5,
        "required_packages": [],
        "reference_solution_authority": "expert_reconstructed",
        "overlay_status": "implemented_model_revision",
    },
    "AI-CURATED-OPT-04": {
        "evaluation_mode": "model_revision",
        "entry_point": "regularized_model",
        "solution": dedent(
            """
            baseline_model = keras.Sequential([
                keras.layers.Embedding(input_dim=10000, output_dim=16),
                keras.layers.GlobalAveragePooling1D(),
                keras.layers.Dense(16, activation="relu"),
                keras.layers.Dense(1, activation="sigmoid"),
            ])
            baseline_model.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])
            baseline_history = baseline_model.fit(epochs=20, batch_size=512, validation_split=0.2, verbose=0)

            regularized_model = keras.Sequential([
                keras.layers.Embedding(input_dim=10000, output_dim=16),
                keras.layers.GlobalAveragePooling1D(),
                keras.layers.Dense(16, activation="relu", kernel_regularizer=tf.keras.regularizers.L2(0.001)),
                keras.layers.Dense(1, activation="sigmoid"),
            ])
            regularized_model.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])
            regularized_history = regularized_model.fit(epochs=20, batch_size=512, validation_split=0.2, verbose=0)

            final_baseline_val_loss = baseline_history.history["val_loss"][-1]
            final_regularized_val_loss = regularized_history.history["val_loss"][-1]
            explanation = "The regularized model shows lower validation loss, indicating improved generalization and less overfitting."
            """
        ),
        "solution_format": "full_code",
        "setup_code": FAKE_TF_SETUP,
        "timeout_seconds": 5,
        "required_packages": [],
        "reference_solution_authority": "researcher_written",
        "overlay_status": "implemented_model_revision",
    },
    "OPT-05": {
        "evaluation_mode": "model_revision",
        "entry_point": "dropout_model",
        "solution": dedent(
            """
            dropout_model = tf.keras.Sequential([
                layers.Dense(512, activation="elu", input_shape=(FEATURES,)),
                layers.Dropout(0.5),
                layers.Dense(512, activation="elu"),
                layers.Dropout(0.5),
                layers.Dense(512, activation="elu"),
                layers.Dropout(0.5),
                layers.Dense(512, activation="elu"),
                layers.Dropout(0.5),
                layers.Dense(1),
            ])
            dropout_model.compile(optimizer="adam", loss="mse", metrics=["mae"])
            regularizer_histories["dropout"] = compile_and_fit(dropout_model, "regularizers/dropout")
            """
        ),
        "solution_format": "full_code",
        "setup_code": FAKE_TF_SETUP,
        "timeout_seconds": 5,
        "required_packages": [],
        "reference_solution_authority": "expert_reconstructed",
        "overlay_status": "implemented_model_revision",
    },
    "AI-CURATED-OPT-05": {
        "evaluation_mode": "model_revision",
        "entry_point": "revised_model",
        "solution": dedent(
            """
            baseline_model = keras.Sequential([
                keras.layers.Embedding(10000, 16),
                keras.layers.GlobalAveragePooling1D(),
                keras.layers.Dense(16, activation="relu"),
                keras.layers.Dense(16, activation="relu"),
                keras.layers.Dense(1, activation="sigmoid"),
            ])
            baseline_model.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])
            baseline_history = baseline_model.fit(batch_size=512, epochs=40, validation_split=0.2, verbose=0)

            revised_model = keras.Sequential([
                keras.layers.Embedding(10000, 16),
                keras.layers.GlobalAveragePooling1D(),
                keras.layers.Dense(16, activation="relu"),
                keras.layers.Dropout(0.5),
                keras.layers.Dense(16, activation="relu"),
                keras.layers.Dropout(0.5),
                keras.layers.Dense(1, activation="sigmoid"),
            ])
            revised_model.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])
            revised_history = revised_model.fit(batch_size=512, epochs=40, validation_split=0.2, verbose=0)

            plt.figure()
            plt.plot(baseline_history.history["val_accuracy"], label="Baseline")
            plt.plot(revised_history.history["val_accuracy"], label="Revised")
            plt.legend()

            baseline_gap = round(baseline_history.history["accuracy"][-1] - baseline_history.history["val_accuracy"][-1], 3)
            revised_gap = round(revised_history.history["accuracy"][-1] - revised_history.history["val_accuracy"][-1], 3)
            interpretation_sentence = (
                "Dropout reduced the overfitting gap from "
                + str(baseline_gap)
                + " to "
                + str(revised_gap)
                + ", indicating improved generalization."
            )
            """
        ),
        "solution_format": "full_code",
        "setup_code": FAKE_TF_SETUP,
        "timeout_seconds": 5,
        "required_packages": [],
        "reference_solution_authority": "researcher_written",
        "overlay_status": "implemented_model_revision",
    },
}


TEST_UPDATES: dict[str, dict[str, Any]] = {
    "OPT-03": {
        "public_tests_py": [
            "assert len(combined_model.layers) == 9",
            "assert sum(isinstance(layer, Dropout) for layer in combined_model.layers) == 4",
            "dense_layers = [layer for layer in combined_model.layers if isinstance(layer, Dense)]; assert len(dense_layers) == 5 and sum(layer.kernel_regularizer is not None for layer in dense_layers[:-1]) == 4",
        ],
        "hidden_tests_py": [
            "assert regularizer_histories['combined'].history['val_mae'][-1] < regularizer_histories['combined'].history['val_mae'][0]",
        ],
        "surface_checks": [
            {"type": "api_check", "name": "entry_exists", "code": "assert isinstance(combined_model, Sequential)"},
            {"type": "behavior_check", "name": "compiled_for_regression", "code": "assert combined_model.compile_config['loss'] == 'mse' and combined_model.compile_config['metrics'] == ['mae']"},
        ],
        "overlay_status": "implemented_model_revision",
    },
    "AI-CURATED-OPT-03": {
        "public_tests_py": [
            "assert len(revised_model.layers) == 5",
            "assert isinstance(revised_model.layers[0].kernel_regularizer, tf.keras.regularizers.L2) and abs(revised_model.layers[0].kernel_regularizer.l2 - 1e-4) < 1e-8",
            "assert isinstance(revised_model.layers[1], tf.keras.layers.Dropout) and abs(revised_model.layers[1].rate - 0.3) < 1e-8",
        ],
        "hidden_tests_py": [
            "assert improved is True and mae_reduction > 0",
            "assert revised_model.compile_config['optimizer'] == 'adam' and revised_model.compile_config['loss'] == 'mse'",
        ],
        "surface_checks": [
            {"type": "shape_check", "name": "layer_pattern", "code": "assert [type(layer).__name__ for layer in revised_model.layers] == ['Dense', 'Dropout', 'Dense', 'Dropout', 'Dense']"},
        ],
        "overlay_status": "implemented_model_revision",
    },
    "OPT-04": {
        "public_tests_py": [
            "assert len(l2_model.layers) == 5",
            "dense_layers = [layer for layer in l2_model.layers if isinstance(layer, Dense)]; assert len(dense_layers) == 5 and sum(layer.kernel_regularizer is not None for layer in dense_layers[:-1]) == 4",
        ],
        "hidden_tests_py": [
            "assert regularizer_histories['l2'].history['val_loss'][-1] < regularizer_histories['l2'].history['val_loss'][0]",
        ],
        "surface_checks": [
            {"type": "api_check", "name": "entry_exists", "code": "assert isinstance(l2_model, Sequential)"},
            {"type": "behavior_check", "name": "compile_settings", "code": "assert l2_model.compile_config['loss'] == 'mse' and l2_model.compile_config['metrics'] == ['mae']"},
        ],
        "overlay_status": "implemented_model_revision",
    },
    "AI-CURATED-OPT-04": {
        "public_tests_py": [
            "regularized_layers = [layer for layer in regularized_model.layers if isinstance(layer, Dense) and layer.kernel_regularizer is not None]; assert len(regularized_layers) == 1",
            "assert isinstance(regularized_model.layers[2].kernel_regularizer, tf.keras.regularizers.L2) and abs(regularized_model.layers[2].kernel_regularizer.l2 - 0.001) < 1e-8",
            "assert 0.30 <= final_regularized_val_loss <= 0.45",
        ],
        "hidden_tests_py": [
            "assert final_regularized_val_loss < final_baseline_val_loss",
            "assert 'validation' in explanation.lower() and ('generalization' in explanation.lower() or 'overfitting' in explanation.lower())",
        ],
        "surface_checks": [
            {"type": "shape_check", "name": "architecture_preserved", "code": "assert [type(layer).__name__ for layer in regularized_model.layers] == ['Embedding', 'GlobalAveragePooling1D', 'Dense', 'Dense']"},
        ],
        "overlay_status": "implemented_model_revision",
    },
    "OPT-05": {
        "public_tests_py": [
            "assert len(dropout_model.layers) == 9",
            "assert sum(isinstance(layer, Dropout) for layer in dropout_model.layers) == 4",
        ],
        "hidden_tests_py": [
            "assert regularizer_histories['dropout'].history['val_loss'][-1] < regularizer_histories['dropout'].history['val_loss'][0]",
        ],
        "surface_checks": [
            {"type": "api_check", "name": "entry_exists", "code": "assert isinstance(dropout_model, Sequential)"},
            {"type": "behavior_check", "name": "dropout_rate", "code": "assert all(abs(layer.rate - 0.5) < 1e-8 for layer in dropout_model.layers if isinstance(layer, Dropout))"},
        ],
        "overlay_status": "implemented_model_revision",
    },
    "AI-CURATED-OPT-05": {
        "public_tests_py": [
            "assert [type(layer).__name__ for layer in revised_model.layers] == ['Embedding', 'GlobalAveragePooling1D', 'Dense', 'Dropout', 'Dense', 'Dropout', 'Dense']",
            "assert sum(isinstance(layer, Dropout) for layer in revised_model.layers) == 2",
            "lines = plt.gca().get_lines(); assert len(lines) == 2 and {line.get_label() for line in lines} == {'Baseline', 'Revised'}",
        ],
        "hidden_tests_py": [
            "assert 'gap' in interpretation_sentence.lower() or 'difference' in interpretation_sentence.lower() or 'overfitting gap' in interpretation_sentence.lower()",
            "assert 'generalization' in interpretation_sentence.lower()",
        ],
        "surface_checks": [
            {"type": "behavior_check", "name": "dropout_positions", "code": "assert isinstance(revised_model.layers[3], Dropout) and isinstance(revised_model.layers[5], Dropout)"},
        ],
        "overlay_status": "implemented_model_revision",
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
    print(f"Updated model-revision overlays -> {REFERENCE_SOLUTIONS}")
    print(f"Updated model-revision tests -> {EXECUTABLE_TESTS}")


if __name__ == "__main__":
    main()

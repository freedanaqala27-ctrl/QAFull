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


FAKE_MODEL_SETUP = dedent(
    """
    class Layer:
        pass


    class Conv2D(Layer):
        def __init__(self, filters, kernel_size, activation=None, input_shape=None):
            self.filters = filters
            self.kernel_size = kernel_size
            self.activation = activation
            self.input_shape = input_shape


    class MaxPooling2D(Layer):
        def __init__(self, pool_size=(2, 2)):
            self.pool_size = pool_size


    class Flatten(Layer):
        pass


    class Dense(Layer):
        def __init__(self, units, activation=None):
            self.units = units
            self.activation = activation


    class Dropout(Layer):
        def __init__(self, rate):
            self.rate = float(rate)


    class Embedding(Layer):
        def __init__(self, input_dim, output_dim):
            self.input_dim = input_dim
            self.output_dim = output_dim


    class LSTM(Layer):
        def __init__(self, units, return_sequences=False, return_state=False):
            self.units = units
            self.return_sequences = return_sequences
            self.return_state = return_state


    class Bidirectional(Layer):
        def __init__(self, layer):
            self.layer = layer


    class MultiHeadAttention(Layer):
        def __init__(self, num_heads, key_dim):
            self.num_heads = num_heads
            self.key_dim = key_dim


    class FakeHistory:
        def __init__(self, history):
            self.history = history


    class FakeModel:
        def __init__(self, layers, name="model"):
            self.layers = list(layers)
            self.name = name
            self.compile_config = {}

        def compile(self, optimizer=None, loss=None, metrics=None):
            self.compile_config = {
                "optimizer": optimizer,
                "loss": loss,
                "metrics": list(metrics or []),
            }

        def fit(self, *args, **kwargs):
            epochs = int(kwargs.get("epochs", 10))
            history = {
                "loss": [round(1.2 - 0.06 * i, 4) for i in range(epochs)],
                "val_loss": [round(1.3 - 0.05 * i, 4) for i in range(epochs)],
                "accuracy": [round(0.45 + 0.04 * i, 4) for i in range(epochs)],
                "val_accuracy": [round(0.42 + 0.035 * i, 4) for i in range(epochs)],
            }
            return FakeHistory(history)
    """
)
REFERENCE_UPDATES: dict[str, dict[str, Any]] = {
    "CNN-03": {
        "evaluation_mode": "model_building",
        "entry_point": "model",
        "solution": dedent(
            """
            import torch
            import torch.nn as nn
            import torch.optim as optim


            class SimpleImageClassifier(nn.Module):
                def __init__(self, num_classes=10):
                    super().__init__()
                    self.features = nn.Sequential(
                        nn.Conv2d(1, 16, kernel_size=3, padding=1),
                        nn.ReLU(),
                        nn.MaxPool2d(2),
                        nn.Conv2d(16, 32, kernel_size=3, padding=1),
                        nn.ReLU(),
                        nn.MaxPool2d(2),
                    )
                    self.classifier = nn.Sequential(
                        nn.Flatten(),
                        nn.Linear(32 * 7 * 7, 64),
                        nn.ReLU(),
                        nn.Linear(64, num_classes),
                    )

                def forward(self, x):
                    return self.classifier(self.features(x))


            model = SimpleImageClassifier()
            optimizer = optim.Adam(model.parameters(), lr=1e-3)
            criterion = nn.CrossEntropyLoss()
            x_batch = torch.randn(8, 1, 28, 28)
            y_batch = torch.randint(0, 10, (8,))
            logits = model(x_batch)
            loss = criterion(logits, y_batch)
            loss.backward()
            optimizer.step()
            train_loss = float(loss.item())
            """
        ),
        "solution_format": "full_code",
        "setup_code": "",
        "timeout_seconds": 5,
        "required_packages": ["torch"],
        "reference_solution_authority": "expert_reconstructed",
        "overlay_status": "implemented_model_building",
    },
    "AI-CURATED-CNN-03": {
        "evaluation_mode": "model_building",
        "entry_point": "model",
        "solution": dedent(
            """
            import torch
            import torch.nn as nn
            import torch.optim as optim


            class CIFARClassifier(nn.Module):
                def __init__(self, num_classes=10):
                    super().__init__()
                    self.features = nn.Sequential(
                        nn.Conv2d(3, 32, kernel_size=3, padding=1),
                        nn.ReLU(),
                        nn.MaxPool2d(2),
                        nn.Conv2d(32, 64, kernel_size=3, padding=1),
                        nn.ReLU(),
                        nn.MaxPool2d(2),
                    )
                    self.classifier = nn.Sequential(
                        nn.Flatten(),
                        nn.Linear(64 * 8 * 8, 128),
                        nn.ReLU(),
                        nn.Linear(128, num_classes),
                    )

                def forward(self, x):
                    return self.classifier(self.features(x))


            model = CIFARClassifier()
            optimizer = optim.Adam(model.parameters(), lr=1e-3)
            criterion = nn.CrossEntropyLoss()
            x_batch = torch.randn(8, 3, 32, 32)
            y_batch = torch.randint(0, 10, (8,))
            logits = model(x_batch)
            loss = criterion(logits, y_batch)
            loss.backward()
            optimizer.step()
            train_loss = float(loss.item())
            """
        ),
        "solution_format": "full_code",
        "setup_code": "",
        "timeout_seconds": 5,
        "required_packages": ["torch"],
        "reference_solution_authority": "researcher_written",
        "overlay_status": "implemented_model_building",
    },
    "MIT-02": {
        "evaluation_mode": "model_building",
        "entry_point": "CNN",
        "solution": dedent(
            """
            import torch
            import torch.nn as nn
            import torch.optim as optim


            class CNN(nn.Module):
                def __init__(self):
                    super().__init__()
                    self.conv1 = nn.Conv2d(1, 16, kernel_size=3, padding=1)
                    self.conv2 = nn.Conv2d(16, 32, kernel_size=3, padding=1)
                    self.pool = nn.MaxPool2d(2)
                    self.relu = nn.ReLU()
                    self.fc1 = nn.Linear(32 * 7 * 7, 64)
                    self.fc2 = nn.Linear(64, 10)

                def forward(self, x):
                    x = self.pool(self.relu(self.conv1(x)))
                    x = self.pool(self.relu(self.conv2(x)))
                    x = x.view(x.size(0), -1)
                    x = self.relu(self.fc1(x))
                    return self.fc2(x)


            model = CNN()
            optimizer = optim.Adam(model.parameters(), lr=1e-3)
            criterion = nn.CrossEntropyLoss()
            x_batch = torch.randn(8, 1, 28, 28)
            y_batch = torch.randint(0, 10, (8,))
            logits = model(x_batch)
            loss = criterion(logits, y_batch)
            loss.backward()
            optimizer.step()
            """
        ),
        "solution_format": "full_code",
        "setup_code": "",
        "timeout_seconds": 5,
        "required_packages": ["torch"],
        "reference_solution_authority": "expert_reconstructed",
        "overlay_status": "implemented_model_building",
    },
    "AI-CURATED-MIT-02": {
        "evaluation_mode": "model_building",
        "entry_point": "TwoBlockCNN",
        "solution": dedent(
            """
            import torch
            import torch.nn as nn
            import torch.optim as optim


            class TwoBlockCNN(nn.Module):
                def __init__(self, num_classes=10):
                    super().__init__()
                    self.block1 = nn.Sequential(
                        nn.Conv2d(1, 16, kernel_size=3, padding=1),
                        nn.ReLU(),
                        nn.MaxPool2d(2),
                    )
                    self.block2 = nn.Sequential(
                        nn.Conv2d(16, 32, kernel_size=3, padding=1),
                        nn.ReLU(),
                        nn.MaxPool2d(2),
                    )
                    self.fc = nn.Sequential(
                        nn.Flatten(),
                        nn.Linear(32 * 7 * 7, 64),
                        nn.ReLU(),
                        nn.Linear(64, num_classes),
                    )

                def forward(self, x):
                    x = self.block1(x)
                    x = self.block2(x)
                    return self.fc(x)


            model = TwoBlockCNN()
            optimizer = optim.Adam(model.parameters(), lr=1e-3)
            criterion = nn.CrossEntropyLoss()
            x_batch = torch.randn(8, 1, 28, 28)
            y_batch = torch.randint(0, 10, (8,))
            loss = criterion(model(x_batch), y_batch)
            loss.backward()
            optimizer.step()
            """
        ),
        "solution_format": "full_code",
        "setup_code": "",
        "timeout_seconds": 5,
        "required_packages": ["torch"],
        "reference_solution_authority": "researcher_written",
        "overlay_status": "implemented_model_building",
    },
    "RNN-02": {
        "evaluation_mode": "model_building",
        "entry_point": "ParserModel",
        "solution": dedent(
            """
            import torch
            import torch.nn as nn
            import torch.optim as optim


            class ParserModel(nn.Module):
                def __init__(self, vocab_size=500, embed_dim=32, hidden_dim=64, num_actions=3, num_features=6):
                    super().__init__()
                    self.embedding = nn.Embedding(vocab_size, embed_dim)
                    self.proj = nn.Linear(num_features * embed_dim, hidden_dim)
                    self.output = nn.Linear(hidden_dim, num_actions)

                def embedding_lookup(self, features):
                    embedded = self.embedding(features)
                    return embedded.reshape(features.size(0), -1)

                def forward(self, features):
                    x = torch.relu(self.proj(self.embedding_lookup(features)))
                    return self.output(x)


            model = ParserModel()
            optimizer = optim.Adam(model.parameters(), lr=1e-3)
            criterion = nn.CrossEntropyLoss()
            features = torch.randint(0, 500, (8, 6))
            actions = torch.randint(0, 3, (8,))
            logits = model(features)
            loss = criterion(logits, actions)
            loss.backward()
            optimizer.step()
            """
        ),
        "solution_format": "full_code",
        "setup_code": "",
        "timeout_seconds": 5,
        "required_packages": ["torch"],
        "reference_solution_authority": "expert_reconstructed",
        "overlay_status": "implemented_model_building",
    },
    "AI-CURATED-RNN-02": {
        "evaluation_mode": "model_building",
        "entry_point": "StackLSTMParser",
        "solution": dedent(
            """
            import torch
            import torch.nn as nn
            import torch.optim as optim


            class StackLSTMParser(nn.Module):
                def __init__(self, vocab_size, embed_dim, hidden_dim, num_actions=3):
                    super().__init__()
                    self.embedding = nn.Embedding(vocab_size, embed_dim)
                    self._stack_lstm = nn.LSTM(embed_dim, hidden_dim, batch_first=True)
                    self._buffer_lstm = nn.LSTM(embed_dim, hidden_dim, batch_first=True)
                    self.classifier = nn.Linear(hidden_dim * 2, num_actions)

                def forward(self, tokens, actions_mask=None):
                    embedded = self.embedding(tokens)
                    stack_out, _ = self._stack_lstm(embedded)
                    buffer_out, _ = self._buffer_lstm(embedded)
                    features = torch.cat([stack_out, buffer_out], dim=-1)
                    logits = self.classifier(features)
                    if actions_mask is not None:
                        logits = logits[actions_mask]
                    else:
                        logits = logits.reshape(-1, logits.size(-1))
                    return logits


            BATCH_SIZE, SEQ_LEN, VOCAB_SIZE = 8, 10, 1000
            model = StackLSTMParser(VOCAB_SIZE, 64, 128)
            tokens = torch.randint(0, VOCAB_SIZE, (BATCH_SIZE, SEQ_LEN))
            actions = torch.randint(0, 3, (BATCH_SIZE, SEQ_LEN))
            actions_mask = torch.ones_like(actions, dtype=torch.bool)
            optimizer = optim.Adam(model.parameters(), lr=1e-3)
            criterion = nn.CrossEntropyLoss()
            logits = model(tokens, actions_mask)
            loss = criterion(logits, actions.reshape(-1))
            loss.backward()
            optimizer.step()
            """
        ),
        "solution_format": "full_code",
        "setup_code": "",
        "timeout_seconds": 5,
        "required_packages": ["torch"],
        "reference_solution_authority": "researcher_written",
        "overlay_status": "implemented_model_building",
    },
    "RNN-03": {
        "evaluation_mode": "model_building",
        "entry_point": "Seq2Seq",
        "solution": dedent(
            """
            import torch
            import torch.nn as nn
            import torch.optim as optim


            class Seq2Seq(nn.Module):
                def __init__(self, src_vocab=30, tgt_vocab=35, emb_dim=16, hidden_dim=32):
                    super().__init__()
                    self.src_embedding = nn.Embedding(src_vocab, emb_dim)
                    self.tgt_embedding = nn.Embedding(tgt_vocab, emb_dim)
                    self.encoder = nn.LSTM(emb_dim, hidden_dim, batch_first=True)
                    self.decoder = nn.LSTM(emb_dim, hidden_dim, batch_first=True)
                    self.output = nn.Linear(hidden_dim, tgt_vocab)

                def forward(self, src_tokens, tgt_tokens):
                    _, (h, c) = self.encoder(self.src_embedding(src_tokens))
                    dec_out, _ = self.decoder(self.tgt_embedding(tgt_tokens), (h, c))
                    return self.output(dec_out)


            model = Seq2Seq()
            optimizer = optim.Adam(model.parameters(), lr=1e-3)
            criterion = nn.CrossEntropyLoss()
            src = torch.randint(0, 30, (4, 7))
            tgt_in = torch.randint(0, 35, (4, 6))
            tgt_out = torch.randint(0, 35, (4, 6))
            logits = model(src, tgt_in)
            loss = criterion(logits.reshape(-1, logits.size(-1)), tgt_out.reshape(-1))
            loss.backward()
            optimizer.step()
            """
        ),
        "solution_format": "full_code",
        "setup_code": "",
        "timeout_seconds": 5,
        "required_packages": ["torch"],
        "reference_solution_authority": "expert_reconstructed",
        "overlay_status": "implemented_model_building",
    },
    "AI-CURATED-RNN-03": {
        "evaluation_mode": "model_building",
        "entry_point": "TeacherForcedSeq2Seq",
        "solution": dedent(
            """
            import torch
            import torch.nn as nn
            import torch.optim as optim


            class TeacherForcedSeq2Seq(nn.Module):
                def __init__(self, src_vocab=30, tgt_vocab=35, emb_dim=16, hidden_dim=32):
                    super().__init__()
                    self.src_embedding = nn.Embedding(src_vocab, emb_dim)
                    self.tgt_embedding = nn.Embedding(tgt_vocab, emb_dim)
                    self.encoder = nn.GRU(emb_dim, hidden_dim, batch_first=True)
                    self.decoder = nn.GRU(emb_dim, hidden_dim, batch_first=True)
                    self.output = nn.Linear(hidden_dim, tgt_vocab)

                def forward(self, src_tokens, tgt_tokens, teacher_forcing_ratio=1.0):
                    _, hidden = self.encoder(self.src_embedding(src_tokens))
                    dec_out, _ = self.decoder(self.tgt_embedding(tgt_tokens), hidden)
                    return self.output(dec_out)


            model = TeacherForcedSeq2Seq()
            optimizer = optim.Adam(model.parameters(), lr=1e-3)
            criterion = nn.CrossEntropyLoss()
            src = torch.randint(0, 30, (4, 7))
            tgt_in = torch.randint(0, 35, (4, 6))
            tgt_out = torch.randint(0, 35, (4, 6))
            logits = model(src, tgt_in, teacher_forcing_ratio=1.0)
            loss = criterion(logits.reshape(-1, logits.size(-1)), tgt_out.reshape(-1))
            loss.backward()
            optimizer.step()
            """
        ),
        "solution_format": "full_code",
        "setup_code": "",
        "timeout_seconds": 5,
        "required_packages": ["torch"],
        "reference_solution_authority": "researcher_written",
        "overlay_status": "implemented_model_building",
    },
    "KER-01": {
        "evaluation_mode": "model_building",
        "entry_point": "model",
        "solution": dedent(
            """
            model = FakeModel([
                Conv2D(32, (3, 3), activation="relu", input_shape=(28, 28, 1)),
                MaxPooling2D((2, 2)),
                Conv2D(64, (3, 3), activation="relu"),
                MaxPooling2D((2, 2)),
                Flatten(),
                Dense(128, activation="relu"),
                Dense(10, activation="softmax"),
            ], name="mnist_convnet")
            model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])
            history = model.fit(epochs=10, verbose=0)
            """
        ),
        "solution_format": "full_code",
        "setup_code": FAKE_MODEL_SETUP,
        "timeout_seconds": 5,
        "required_packages": [],
        "reference_solution_authority": "expert_reconstructed",
        "overlay_status": "implemented_model_building",
    },
    "AI-CURATED-KER-01": {
        "evaluation_mode": "model_building",
        "entry_point": "model",
        "solution": dedent(
            """
            model = FakeModel([
                Conv2D(16, (3, 3), activation="relu", input_shape=(28, 28, 1)),
                MaxPooling2D((2, 2)),
                Conv2D(32, (3, 3), activation="relu"),
                Flatten(),
                Dense(64, activation="relu"),
                Dense(10, activation="softmax"),
            ], name="minimal_mnist_convnet")
            model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])
            history = model.fit(epochs=8, verbose=0)
            """
        ),
        "solution_format": "full_code",
        "setup_code": FAKE_MODEL_SETUP,
        "timeout_seconds": 5,
        "required_packages": [],
        "reference_solution_authority": "researcher_written",
        "overlay_status": "implemented_model_building",
    },
    "KER-02": {
        "evaluation_mode": "model_building",
        "entry_point": "sentiment_model",
        "solution": dedent(
            """
            sentiment_model = FakeModel([
                Embedding(20000, 128),
                Bidirectional(LSTM(64, return_sequences=True)),
                Bidirectional(LSTM(64)),
                Dropout(0.5),
                Dense(1, activation="sigmoid"),
            ], name="imdb_bilstm")
            sentiment_model.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])
            history = sentiment_model.fit(epochs=6, verbose=0)
            """
        ),
        "solution_format": "full_code",
        "setup_code": FAKE_MODEL_SETUP,
        "timeout_seconds": 5,
        "required_packages": [],
        "reference_solution_authority": "expert_reconstructed",
        "overlay_status": "implemented_model_building",
    },
    "AI-CURATED-KER-02": {
        "evaluation_mode": "model_building",
        "entry_point": "sentiment_model",
        "solution": dedent(
            """
            sentiment_model = FakeModel([
                Embedding(10000, 64),
                Bidirectional(LSTM(32, return_sequences=True)),
                Bidirectional(LSTM(32)),
                Dense(1, activation="sigmoid"),
            ], name="minimal_bilstm")
            sentiment_model.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])
            history = sentiment_model.fit(epochs=5, verbose=0)
            """
        ),
        "solution_format": "full_code",
        "setup_code": FAKE_MODEL_SETUP,
        "timeout_seconds": 5,
        "required_packages": [],
        "reference_solution_authority": "researcher_written",
        "overlay_status": "implemented_model_building",
    },
    "KER-03": {
        "evaluation_mode": "model_building",
        "entry_point": "transformer_model",
        "solution": dedent(
            """
            transformer_model = FakeModel([
                Embedding(15000, 128),
                Embedding(15000, 128),
                MultiHeadAttention(num_heads=4, key_dim=64),
                Dense(256, activation="relu"),
                Dense(15000, activation="softmax"),
            ], name="transformer_translation")
            transformer_model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])
            history = transformer_model.fit(epochs=4, verbose=0)
            """
        ),
        "solution_format": "full_code",
        "setup_code": FAKE_MODEL_SETUP,
        "timeout_seconds": 5,
        "required_packages": [],
        "reference_solution_authority": "expert_reconstructed",
        "overlay_status": "implemented_model_building",
    },
    "AI-CURATED-KER-03": {
        "evaluation_mode": "model_building",
        "entry_point": "transformer_model",
        "solution": dedent(
            """
            transformer_model = FakeModel([
                Embedding(12000, 96),
                Embedding(12000, 96),
                MultiHeadAttention(num_heads=2, key_dim=48),
                Dense(192, activation="relu"),
                Dense(12000, activation="softmax"),
            ], name="minimal_transformer")
            transformer_model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])
            history = transformer_model.fit(epochs=3, verbose=0)
            """
        ),
        "solution_format": "full_code",
        "setup_code": FAKE_MODEL_SETUP,
        "timeout_seconds": 5,
        "required_packages": [],
        "reference_solution_authority": "researcher_written",
        "overlay_status": "implemented_model_building",
    },
    "KER-04": {
        "evaluation_mode": "model_building",
        "entry_point": "seq2seq_model",
        "solution": dedent(
            """
            seq2seq_model = FakeModel([
                LSTM(128, return_state=True),
                LSTM(128, return_sequences=True),
                Dense(27, activation="softmax"),
            ], name="char_seq2seq")
            seq2seq_model.compile(optimizer="adam", loss="categorical_crossentropy", metrics=["accuracy"])
            history = seq2seq_model.fit(epochs=5, verbose=0)
            """
        ),
        "solution_format": "full_code",
        "setup_code": FAKE_MODEL_SETUP,
        "timeout_seconds": 5,
        "required_packages": [],
        "reference_solution_authority": "expert_reconstructed",
        "overlay_status": "implemented_model_building",
    },
    "AI-CURATED-KER-04": {
        "evaluation_mode": "model_building",
        "entry_point": "seq2seq_model",
        "solution": dedent(
            """
            seq2seq_model = FakeModel([
                Embedding(27, 32),
                LSTM(64, return_state=True),
                LSTM(64, return_sequences=True),
                Dense(27, activation="softmax"),
            ], name="teacher_forced_char_seq2seq")
            seq2seq_model.compile(optimizer="adam", loss="categorical_crossentropy", metrics=["accuracy"])
            history = seq2seq_model.fit(epochs=5, verbose=0)
            """
        ),
        "solution_format": "full_code",
        "setup_code": FAKE_MODEL_SETUP,
        "timeout_seconds": 5,
        "required_packages": [],
        "reference_solution_authority": "researcher_written",
        "overlay_status": "implemented_model_building",
    },
}

TEST_UPDATES: dict[str, dict[str, Any]] = {
    "CNN-03": {
        "public_tests_py": [
            "x = torch.randn(4, 1, 28, 28); logits = model(x); assert logits.shape == (4, 10)",
            "assert train_loss > 0",
        ],
        "hidden_tests_py": [
            "assert all(p.grad is not None for p in model.parameters() if p.requires_grad)",
        ],
        "surface_checks": [
            {"type": "api_check", "name": "conv_layers_exist", "code": "conv_layers = [m for m in model.modules() if isinstance(m, nn.Conv2d)]; assert len(conv_layers) >= 2"},
        ],
        "overlay_status": "implemented_model_building",
    },
    "AI-CURATED-CNN-03": {
        "public_tests_py": [
            "x = torch.randn(4, 3, 32, 32); logits = model(x); assert logits.shape == (4, 10)",
            "assert train_loss > 0",
        ],
        "hidden_tests_py": [
            "assert all(p.grad is not None for p in model.parameters() if p.requires_grad)",
        ],
        "surface_checks": [
            {"type": "api_check", "name": "classifier_has_two_convs", "code": "conv_layers = [m for m in model.modules() if isinstance(m, nn.Conv2d)]; assert len(conv_layers) == 2"},
        ],
        "overlay_status": "implemented_model_building",
    },
    "MIT-02": {
        "public_tests_py": [
            "x = torch.randn(4, 1, 28, 28); logits = model(x); assert logits.shape == (4, 10)",
            "cnn = CNN(); assert hasattr(cnn, 'conv1') and hasattr(cnn, 'conv2')",
        ],
        "hidden_tests_py": [
            "assert all(p.grad is not None for p in model.parameters() if p.requires_grad)",
        ],
        "surface_checks": [
            {"type": "api_check", "name": "fully_connected_head", "code": "cnn = CNN(); assert hasattr(cnn, 'fc1') and hasattr(cnn, 'fc2')"},
        ],
        "overlay_status": "implemented_model_building",
    },
    "AI-CURATED-MIT-02": {
        "public_tests_py": [
            "x = torch.randn(4, 1, 28, 28); logits = model(x); assert logits.shape == (4, 10)",
            "assert callable(TwoBlockCNN)",
        ],
        "hidden_tests_py": [
            "assert all(p.grad is not None for p in model.parameters() if p.requires_grad)",
        ],
        "surface_checks": [
            {"type": "api_check", "name": "two_blocks_exist", "code": "net = TwoBlockCNN(); assert hasattr(net, 'block1') and hasattr(net, 'block2')"},
        ],
        "overlay_status": "implemented_model_building",
    },
    "RNN-02": {
        "public_tests_py": [
            "features = torch.randint(0, 500, (4, 6)); logits = model(features); assert logits.shape == (4, 3)",
            "embedded = model.embedding_lookup(features); assert embedded.shape[0] == 4",
        ],
        "hidden_tests_py": [
            "assert all(p.grad is not None for p in model.parameters() if p.requires_grad)",
        ],
        "surface_checks": [
            {"type": "api_check", "name": "methods_exist", "code": "assert hasattr(model, 'embedding_lookup') and callable(model.forward)"},
        ],
        "overlay_status": "implemented_model_building",
    },
    "AI-CURATED-RNN-02": {
        "public_tests_py": [
            "tokens = torch.randint(0, 1000, (8, 10)); logits = model(tokens); assert logits.shape == (80, 3)",
            "assert hasattr(model, '_stack_lstm') and hasattr(model, '_buffer_lstm')",
        ],
        "hidden_tests_py": [
            "assert all(p.grad is not None for p in model.parameters() if p.requires_grad)",
        ],
        "surface_checks": [
            {"type": "api_check", "name": "embedding_exists", "code": "assert hasattr(model, 'embedding')"},
        ],
        "overlay_status": "implemented_model_building",
    },
    "RNN-03": {
        "public_tests_py": [
            "src = torch.randint(0, 30, (4, 7)); tgt = torch.randint(0, 35, (4, 6)); logits = model(src, tgt); assert logits.shape == (4, 6, 35)",
            "assert hasattr(model, 'encoder') and hasattr(model, 'decoder')",
        ],
        "hidden_tests_py": [
            "assert all(p.grad is not None for p in model.parameters() if p.requires_grad)",
        ],
        "surface_checks": [
            {"type": "api_check", "name": "embeddings_exist", "code": "assert hasattr(model, 'src_embedding') and hasattr(model, 'tgt_embedding')"},
        ],
        "overlay_status": "implemented_model_building",
    },
    "AI-CURATED-RNN-03": {
        "public_tests_py": [
            "src = torch.randint(0, 30, (4, 7)); tgt = torch.randint(0, 35, (4, 6)); logits = model(src, tgt, teacher_forcing_ratio=1.0); assert logits.shape == (4, 6, 35)",
            "assert callable(TeacherForcedSeq2Seq)",
        ],
        "hidden_tests_py": [
            "assert all(p.grad is not None for p in model.parameters() if p.requires_grad)",
        ],
        "surface_checks": [
            {"type": "api_check", "name": "gru_layers_exist", "code": "assert hasattr(model, 'encoder') and hasattr(model, 'decoder')"},
        ],
        "overlay_status": "implemented_model_building",
    },
    "KER-01": {
        "public_tests_py": [
            "assert len(model.layers) == 7",
            "assert sum(isinstance(layer, Conv2D) for layer in model.layers) == 2",
        ],
        "hidden_tests_py": [
            "assert model.compile_config['loss'] == 'sparse_categorical_crossentropy' and history.history['accuracy'][-1] > history.history['accuracy'][0]",
        ],
        "surface_checks": [
            {"type": "api_check", "name": "pooling_and_flatten_present", "code": "assert any(isinstance(layer, MaxPooling2D) for layer in model.layers) and any(isinstance(layer, Flatten) for layer in model.layers)"},
        ],
        "overlay_status": "implemented_model_building",
    },
    "AI-CURATED-KER-01": {
        "public_tests_py": [
            "assert sum(isinstance(layer, Conv2D) for layer in model.layers) == 2",
            "assert model.layers[-1].units == 10",
        ],
        "hidden_tests_py": [
            "assert model.compile_config['metrics'] == ['accuracy']",
        ],
        "surface_checks": [
            {"type": "api_check", "name": "model_named", "code": "assert model.name == 'minimal_mnist_convnet'"},
        ],
        "overlay_status": "implemented_model_building",
    },
    "KER-02": {
        "public_tests_py": [
            "assert any(isinstance(layer, Bidirectional) for layer in sentiment_model.layers)",
            "assert sentiment_model.layers[-1].activation == 'sigmoid'",
        ],
        "hidden_tests_py": [
            "assert sentiment_model.compile_config['loss'] == 'binary_crossentropy'",
        ],
        "surface_checks": [
            {"type": "api_check", "name": "embedding_present", "code": "assert isinstance(sentiment_model.layers[0], Embedding)"},
        ],
        "overlay_status": "implemented_model_building",
    },
    "AI-CURATED-KER-02": {
        "public_tests_py": [
            "assert sum(isinstance(layer, Bidirectional) for layer in sentiment_model.layers) == 2",
            "assert sentiment_model.layers[-1].units == 1",
        ],
        "hidden_tests_py": [
            "assert sentiment_model.compile_config['metrics'] == ['accuracy']",
        ],
        "surface_checks": [
            {"type": "api_check", "name": "history_improves", "code": "assert history.history['val_accuracy'][-1] >= history.history['val_accuracy'][0]"},
        ],
        "overlay_status": "implemented_model_building",
    },
    "KER-03": {
        "public_tests_py": [
            "assert sum(isinstance(layer, Embedding) for layer in transformer_model.layers) == 2",
            "assert any(isinstance(layer, MultiHeadAttention) for layer in transformer_model.layers)",
        ],
        "hidden_tests_py": [
            "assert transformer_model.compile_config['loss'] == 'sparse_categorical_crossentropy'",
        ],
        "surface_checks": [
            {"type": "api_check", "name": "output_dense_exists", "code": "assert isinstance(transformer_model.layers[-1], Dense)"},
        ],
        "overlay_status": "implemented_model_building",
    },
    "AI-CURATED-KER-03": {
        "public_tests_py": [
            "assert any(isinstance(layer, MultiHeadAttention) for layer in transformer_model.layers)",
            "assert transformer_model.layers[-1].units == 12000",
        ],
        "hidden_tests_py": [
            "assert history.history['loss'][-1] < history.history['loss'][0]",
        ],
        "surface_checks": [
            {"type": "api_check", "name": "model_named", "code": "assert transformer_model.name == 'minimal_transformer'"},
        ],
        "overlay_status": "implemented_model_building",
    },
    "KER-04": {
        "public_tests_py": [
            "assert sum(isinstance(layer, LSTM) for layer in seq2seq_model.layers) >= 2",
            "assert seq2seq_model.layers[-1].units == 27",
        ],
        "hidden_tests_py": [
            "assert seq2seq_model.compile_config['loss'] == 'categorical_crossentropy'",
        ],
        "surface_checks": [
            {"type": "api_check", "name": "accuracy_metric", "code": "assert seq2seq_model.compile_config['metrics'] == ['accuracy']"},
        ],
        "overlay_status": "implemented_model_building",
    },
    "AI-CURATED-KER-04": {
        "public_tests_py": [
            "assert any(isinstance(layer, Embedding) for layer in seq2seq_model.layers)",
            "assert sum(isinstance(layer, LSTM) for layer in seq2seq_model.layers) >= 2",
        ],
        "hidden_tests_py": [
            "assert history.history['val_accuracy'][-1] >= history.history['val_accuracy'][0]",
        ],
        "surface_checks": [
            {"type": "api_check", "name": "model_named", "code": "assert seq2seq_model.name == 'teacher_forced_char_seq2seq'"},
        ],
        "overlay_status": "implemented_model_building",
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
    print(f"Updated model-building overlays -> {REFERENCE_SOLUTIONS}")
    print(f"Updated model-building tests -> {EXECUTABLE_TESTS}")


if __name__ == "__main__":
    main()

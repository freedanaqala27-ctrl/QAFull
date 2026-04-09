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


REFERENCE_UPDATES: dict[str, dict[str, Any]] = {}
TEST_UPDATES: dict[str, dict[str, Any]] = {}

REFERENCE_UPDATES.update(
    {
        "CNN-01": {
            "evaluation_mode": "function_completion",
            "entry_point": "conv_forward_naive",
            "solution": dedent(
                """
                def conv_forward_naive(x, w, b, conv_param):
                    import numpy as np

                    stride = conv_param["stride"]
                    pad = conv_param["pad"]
                    N, C, H, W = x.shape
                    F, _, HH, WW = w.shape

                    H_out = 1 + (H + 2 * pad - HH) // stride
                    W_out = 1 + (W + 2 * pad - WW) // stride

                    x_padded = np.pad(x, ((0, 0), (0, 0), (pad, pad), (pad, pad)), mode="constant")
                    out = np.zeros((N, F, H_out, W_out), dtype=x.dtype)

                    for n in range(N):
                        for f in range(F):
                            for i in range(H_out):
                                for j in range(W_out):
                                    h_start = i * stride
                                    h_end = h_start + HH
                                    w_start = j * stride
                                    w_end = w_start + WW
                                    window = x_padded[n, :, h_start:h_end, w_start:w_end]
                                    out[n, f, i, j] = np.sum(window * w[f]) + b[f]

                    cache = (x, w, b, conv_param)
                    return out, cache
                """
            ),
            "solution_format": "full_code",
            "setup_code": "import numpy as np",
            "timeout_seconds": 5,
            "required_packages": ["numpy"],
            "reference_solution_authority": "expert_reconstructed",
            "overlay_status": "implemented_code_completion",
        },
        "AI-CURATED-CNN-01": {
            "evaluation_mode": "function_completion",
            "entry_point": "conv_forward_naive",
            "solution": dedent(
                """
                def conv_forward_naive(x, w, b, pad, stride):
                    import numpy as np

                    N, C, H, W = x.shape
                    F, _, HH, WW = w.shape
                    H_out = 1 + (H + 2 * pad - HH) // stride
                    W_out = 1 + (W + 2 * pad - WW) // stride

                    x_padded = np.pad(x, ((0, 0), (0, 0), (pad, pad), (pad, pad)), mode="constant")
                    out = np.zeros((N, F, H_out, W_out), dtype=x.dtype)

                    for n in range(N):
                        for f in range(F):
                            for i in range(H_out):
                                for j in range(W_out):
                                    h_start = i * stride
                                    h_end = h_start + HH
                                    w_start = j * stride
                                    w_end = w_start + WW
                                    window = x_padded[n, :, h_start:h_end, w_start:w_end]
                                    out[n, f, i, j] = np.sum(window * w[f]) + b[f]

                    return out
                """
            ),
            "solution_format": "full_code",
            "setup_code": "import numpy as np",
            "timeout_seconds": 5,
            "required_packages": ["numpy"],
            "reference_solution_authority": "researcher_written",
            "overlay_status": "implemented_code_completion",
        },
        "AI-CURATED-CNN-02": {
            "evaluation_mode": "function_completion",
            "entry_point": "compute_conv2d_output_shape",
            "solution": dedent(
                """
                def _pair(value):
                    if isinstance(value, tuple):
                        return value
                    return (value, value)


                def compute_conv2d_output_shape(input_h, input_w, kernel_size, stride=1, padding=0):
                    kernel_h, kernel_w = _pair(kernel_size)
                    stride_h, stride_w = _pair(stride)
                    pad_h, pad_w = _pair(padding)
                    output_h = ((input_h + 2 * pad_h - kernel_h) // stride_h) + 1
                    output_w = ((input_w + 2 * pad_w - kernel_w) // stride_w) + 1
                    return output_h, output_w
                """
            ),
            "solution_format": "full_code",
            "setup_code": "",
            "timeout_seconds": 5,
            "required_packages": [],
            "reference_solution_authority": "researcher_written",
            "overlay_status": "implemented_code_completion",
        },
        "MIT-01": {
            "evaluation_mode": "class_implementation",
            "entry_point": "LSTMModel",
            "solution": dedent(
                """
                import torch
                import torch.nn as nn


                class LSTMModel(nn.Module):
                    def __init__(self, vocab_size, embedding_dim, hidden_size):
                        super(LSTMModel, self).__init__()
                        self.hidden_size = hidden_size
                        self.embedding = nn.Embedding(vocab_size, embedding_dim)
                        self.lstm = nn.LSTM(embedding_dim, hidden_size, batch_first=True)
                        self.fc = nn.Linear(hidden_size, vocab_size)

                    def init_hidden(self, batch_size, device):
                        return (
                            torch.zeros(1, batch_size, self.hidden_size, device=device),
                            torch.zeros(1, batch_size, self.hidden_size, device=device),
                        )

                    def forward(self, x, state=None, return_state=False):
                        x = self.embedding(x)
                        if state is None:
                            state = self.init_hidden(x.size(0), x.device)
                        out, state = self.lstm(x, state)
                        out = self.fc(out)
                        return out if not return_state else (out, state)
                """
            ),
            "solution_format": "full_code",
            "setup_code": "",
            "timeout_seconds": 5,
            "required_packages": ["torch"],
            "reference_solution_authority": "expert_reconstructed",
            "overlay_status": "implemented_code_completion",
        },
        "AI-CURATED-MIT-01": {
            "evaluation_mode": "class_implementation",
            "entry_point": "MusicRNNCell",
            "solution": dedent(
                """
                import torch
                import torch.nn as nn


                class MusicRNNCell(nn.Module):
                    def __init__(self, input_size, hidden_size, vocab_size):
                        super().__init__()
                        self.input_size = input_size
                        self.hidden_size = hidden_size
                        self.vocab_size = vocab_size
                        self.W_ih = nn.Parameter(torch.randn(input_size, hidden_size) * 0.01)
                        self.W_hh = nn.Parameter(torch.randn(hidden_size, hidden_size) * 0.01)
                        self.b_h = nn.Parameter(torch.zeros(hidden_size))
                        self.W_ho = nn.Parameter(torch.randn(hidden_size, vocab_size) * 0.01)
                        self.b_o = nn.Parameter(torch.zeros(vocab_size))

                    def forward(self, x_t, h_prev):
                        h_t = torch.tanh(x_t @ self.W_ih + h_prev @ self.W_hh + self.b_h)
                        logits = h_t @ self.W_ho + self.b_o
                        return h_t, logits
                """
            ),
            "solution_format": "full_code",
            "setup_code": "",
            "timeout_seconds": 5,
            "required_packages": ["torch"],
            "reference_solution_authority": "researcher_written",
            "overlay_status": "implemented_code_completion",
        },
    }
)

TEST_UPDATES.update(
    {
        "CNN-01": {
            "public_tests_py": [
                "x = np.arange(16, dtype=float).reshape(1, 1, 4, 4); w = np.ones((1, 1, 2, 2), dtype=float); b = np.array([0.0]); out, cache = conv_forward_naive(x, w, b, {'stride': 1, 'pad': 0}); assert out.shape == (1, 1, 3, 3); assert cache[0].shape == x.shape",
                "x = np.ones((1, 1, 3, 3), dtype=float); w = np.ones((1, 1, 2, 2), dtype=float); b = np.array([1.0]); out, _ = conv_forward_naive(x, w, b, {'stride': 1, 'pad': 0}); assert abs(out[0, 0, 1, 1] - 5.0) < 1e-8",
            ],
            "hidden_tests_py": [
                "x = np.array([[[[1.0]]]]); w = np.array([[[[1.0]]]]); b = np.array([0.0]); out, _ = conv_forward_naive(x, w, b, {'stride': 1, 'pad': 1}); assert out.shape == (1, 1, 3, 3); assert abs(out[0, 0, 0, 0] - 0.0) < 1e-8",
            ],
            "surface_checks": [
                {"type": "shape_check", "name": "returns_cache_tuple", "code": "x = np.zeros((1, 1, 2, 2)); w = np.ones((1, 1, 1, 1)); b = np.array([0.0]); result = conv_forward_naive(x, w, b, {'stride': 1, 'pad': 0}); assert isinstance(result, tuple) and len(result) == 2"},
                {"type": "api_check", "name": "function_exists", "code": "assert callable(conv_forward_naive)"},
            ],
            "overlay_status": "implemented_code_completion",
        },
        "AI-CURATED-CNN-01": {
            "public_tests_py": [
                "x = np.random.randn(2, 3, 8, 8); w = np.random.randn(4, 3, 3, 3); b = np.zeros(4); out = conv_forward_naive(x, w, b, 1, 2); assert out.shape == (2, 4, 4, 4)",
                "x = np.ones((1, 1, 4, 4)); w = np.ones((1, 1, 2, 2)); b = np.array([1.0]); out = conv_forward_naive(x, w, b, 0, 1); assert abs(out[0, 0, 1, 1] - 5.0) < 1e-8",
            ],
            "hidden_tests_py": [
                "x = np.array([[[[1.0]]]]); w = np.array([[[[1.0]]]]); b = np.array([0.0]); out = conv_forward_naive(x, w, b, 1, 1); assert out.shape == (1, 1, 3, 3); assert abs(out[0, 0, 0, 0] - 0.0) < 1e-8",
            ],
            "surface_checks": [
                {"type": "shape_check", "name": "returns_array", "code": "x = np.zeros((1, 1, 2, 2)); w = np.ones((1, 1, 1, 1)); b = np.array([0.0]); out = conv_forward_naive(x, w, b, 0, 1); assert hasattr(out, 'shape') and out.shape == (1, 1, 2, 2)"},
                {"type": "api_check", "name": "function_exists", "code": "assert callable(conv_forward_naive)"},
            ],
            "overlay_status": "implemented_code_completion",
        },
        "AI-CURATED-CNN-02": {
            "public_tests_py": [
                "assert compute_conv2d_output_shape(32, 32, 3, stride=1, padding=0) == (30, 30)",
                "assert compute_conv2d_output_shape(64, 128, (5, 3), stride=(2, 1), padding=(2, 1)) == (32, 128)",
            ],
            "hidden_tests_py": [
                "assert compute_conv2d_output_shape(28, 28, 7, stride=3, padding=1) == (8, 8)",
            ],
            "surface_checks": [
                {"type": "api_check", "name": "function_exists", "code": "assert callable(compute_conv2d_output_shape)"},
            ],
            "overlay_status": "implemented_code_completion",
        },
        "MIT-01": {
            "public_tests_py": [
                "import torch; model = LSTMModel(vocab_size=12, embedding_dim=8, hidden_size=16); x = torch.randint(0, 12, (4, 5)); out = model(x); assert out.shape == (4, 5, 12)",
                "import torch; model = LSTMModel(vocab_size=10, embedding_dim=6, hidden_size=7); h, c = model.init_hidden(3, torch.device('cpu')); assert h.shape == (1, 3, 7) and c.shape == (1, 3, 7)",
            ],
            "hidden_tests_py": [
                "import torch; model = LSTMModel(vocab_size=9, embedding_dim=4, hidden_size=5); x = torch.randint(0, 9, (2, 3)); out, state = model(x, return_state=True); assert out.shape == (2, 3, 9) and state[0].shape == (1, 2, 5)",
            ],
            "surface_checks": [
                {"type": "api_check", "name": "lstm_layer_exists", "code": "import torch.nn as nn; model = LSTMModel(8, 4, 6); assert isinstance(model.lstm, nn.LSTM) and model.lstm.batch_first"},
            ],
            "overlay_status": "implemented_code_completion",
        },
        "AI-CURATED-MIT-01": {
            "public_tests_py": [
                "import torch; cell = MusicRNNCell(64, 128, 88); x_t = torch.randn(4, 64); h_prev = torch.randn(4, 128); h_t, logits = cell(x_t, h_prev); assert h_t.shape == (4, 128) and logits.shape == (4, 88)",
                "import torch; cell = MusicRNNCell(2, 2, 3); cell.W_ih.data.zero_(); cell.W_hh.data.zero_(); cell.b_h.data.copy_(torch.tensor([1.0, 0.0])); cell.W_ho.data.zero_(); cell.b_o.data.zero_(); h_t, logits = cell(torch.zeros(1, 2), torch.zeros(1, 2)); assert torch.allclose(h_t, torch.tanh(torch.tensor([[1.0, 0.0]])), atol=1e-6)",
            ],
            "hidden_tests_py": [
                "import torch; cell = MusicRNNCell(4, 6, 5); cell.b_h.data.copy_(torch.arange(6.0)); h_t, _ = cell(torch.ones(8, 4), torch.ones(8, 6)); assert not torch.allclose(h_t[:, 0], h_t[:, 1])",
            ],
            "surface_checks": [
                {"type": "api_check", "name": "module_exists", "code": "assert callable(MusicRNNCell)"},
            ],
            "overlay_status": "implemented_code_completion",
        },
    }
)

REFERENCE_UPDATES.update(
    {
        "TRF-02": {
            "evaluation_mode": "class_implementation",
            "entry_point": "DotProductAttention",
            "solution": dedent(
                """
                import math

                import torch
                import torch.nn as nn


                def masked_softmax(scores, valid_lens=None):
                    if valid_lens is None:
                        return torch.softmax(scores, dim=-1)
                    shape = scores.shape
                    scores = scores.reshape(-1, shape[-1])
                    if valid_lens.dim() == 1:
                        valid_lens = valid_lens.repeat_interleave(shape[1])
                    mask = torch.arange(shape[-1], device=scores.device)[None, :] < valid_lens[:, None]
                    scores = scores.masked_fill(~mask, float("-inf"))
                    return torch.softmax(scores.reshape(shape), dim=-1)


                class DotProductAttention(nn.Module):
                    def __init__(self, dropout):
                        super().__init__()
                        self.dropout = nn.Dropout(dropout)

                    def forward(self, queries, keys, values, valid_lens=None):
                        d = queries.shape[-1]
                        scores = -(torch.cdist(queries, keys, p=2) ** 2) / math.sqrt(d)
                        self.attention_weights = masked_softmax(scores, valid_lens)
                        return torch.bmm(self.dropout(self.attention_weights), values)
                """
            ),
            "solution_format": "full_code",
            "setup_code": "",
            "timeout_seconds": 5,
            "required_packages": ["torch"],
            "reference_solution_authority": "expert_reconstructed",
            "overlay_status": "implemented_code_completion",
        },
        "AI-CURATED-TRF-02": {
            "evaluation_mode": "function_completion",
            "entry_point": "additive_attention_scores",
            "solution": dedent(
                """
                import torch
                import torch.nn as nn


                def additive_attention_scores(
                    queries: torch.Tensor,
                    keys: torch.Tensor,
                    W_q: nn.Parameter,
                    W_k: nn.Parameter,
                    v: nn.Parameter,
                    d_h: int = 128,
                ) -> torch.Tensor:
                    q_proj = torch.einsum("bqd,hd->bqh", queries, W_q)
                    k_proj = torch.einsum("bkd,hd->bkh", keys, W_k)
                    features = torch.tanh(q_proj.unsqueeze(2) + k_proj.unsqueeze(1))
                    return torch.einsum("bqkh,h->bqk", features, v)
                """
            ),
            "solution_format": "full_code",
            "setup_code": "",
            "timeout_seconds": 5,
            "required_packages": ["torch"],
            "reference_solution_authority": "researcher_written",
            "overlay_status": "implemented_code_completion",
        },
        "UVA-02": {
            "evaluation_mode": "class_implementation",
            "entry_point": "MultiheadAttention",
            "solution": dedent(
                """
                import math

                import torch
                import torch.nn as nn
                import torch.nn.functional as F


                def scaled_dot_product(q, k, v, mask=None):
                    d_k = q.size()[-1]
                    attn_logits = torch.matmul(q, k.transpose(-2, -1))
                    attn_logits = attn_logits / math.sqrt(d_k)
                    if mask is not None:
                        attn_logits = attn_logits.masked_fill(mask == 0, -9e15)
                    attention = F.softmax(attn_logits, dim=-1)
                    values = torch.matmul(attention, v)
                    return values, attention


                def expand_mask(mask):
                    assert mask.ndim >= 2
                    if mask.ndim == 3:
                        mask = mask.unsqueeze(1)
                    while mask.ndim < 4:
                        mask = mask.unsqueeze(0)
                    return mask


                class MultiheadAttention(nn.Module):
                    def __init__(self, input_dim, embed_dim, num_heads):
                        super().__init__()
                        assert embed_dim % num_heads == 0
                        self.embed_dim = embed_dim
                        self.num_heads = num_heads
                        self.head_dim = embed_dim // num_heads
                        self.qkv_proj = nn.Linear(input_dim, 3 * embed_dim)
                        self.o_proj = nn.Linear(embed_dim, input_dim)

                    def forward(self, x, mask=None, return_attention=False):
                        batch_size, seq_len, _ = x.shape
                        qkv = self.qkv_proj(x).reshape(batch_size, seq_len, self.num_heads, 3 * self.head_dim)
                        qkv = qkv.permute(0, 2, 1, 3)
                        q, k, v = qkv.chunk(3, dim=-1)
                        if mask is not None:
                            mask = expand_mask(mask)
                        values, attention = scaled_dot_product(q, k, v, mask=mask)
                        values = values.permute(0, 2, 1, 3).reshape(batch_size, seq_len, self.embed_dim)
                        output = self.o_proj(values)
                        return (output, attention) if return_attention else output
                """
            ),
            "solution_format": "full_code",
            "setup_code": "",
            "timeout_seconds": 5,
            "required_packages": ["torch"],
            "reference_solution_authority": "expert_reconstructed",
            "overlay_status": "implemented_code_completion",
        },
        "AI-CURATED-UVA-02": {
            "evaluation_mode": "function_completion",
            "entry_point": "scaled_dot_product_attention",
            "solution": dedent(
                """
                import math

                import torch
                import torch.nn.functional as F


                def scaled_dot_product_attention(
                    q: torch.Tensor,
                    k: torch.Tensor,
                    v: torch.Tensor,
                    mask: torch.Tensor = None,
                ) -> torch.Tensor:
                    head_dim = q.size(-1)
                    scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(head_dim)
                    if mask is not None:
                        scores = scores.masked_fill(mask, float("-inf"))
                    attention = torch.softmax(scores, dim=-1)
                    return torch.matmul(attention, v)
                """
            ),
            "solution_format": "full_code",
            "setup_code": "",
            "timeout_seconds": 5,
            "required_packages": ["torch"],
            "reference_solution_authority": "researcher_written",
            "overlay_status": "implemented_code_completion",
        },
    }
)

TEST_UPDATES.update(
    {
        "TRF-02": {
            "public_tests_py": [
                "import torch; attention = DotProductAttention(dropout=0.0); queries = torch.tensor([[[0.0, 0.0], [2.0, 2.0]]]); keys = torch.tensor([[[0.0, 0.0], [2.0, 2.0]]]); values = torch.tensor([[[1.0, 0.0], [0.0, 1.0]]]); out = attention(queries, keys, values); assert out.shape == (1, 2, 2)",
                "import torch; attention = DotProductAttention(dropout=0.0); queries = torch.tensor([[[0.0, 0.0], [2.0, 2.0]]]); keys = torch.tensor([[[0.0, 0.0], [2.0, 2.0]]]); values = torch.tensor([[[1.0, 0.0], [0.0, 1.0]]]); _ = attention(queries, keys, values); assert attention.attention_weights[0, 0, 0] > attention.attention_weights[0, 0, 1] and attention.attention_weights[0, 1, 1] > attention.attention_weights[0, 1, 0]",
            ],
            "hidden_tests_py": [
                "import torch; attention = DotProductAttention(dropout=0.0); queries = torch.randn(2, 3, 4); keys = torch.randn(2, 5, 4); values = torch.randn(2, 5, 6); out = attention(queries, keys, values); assert out.shape == (2, 3, 6)",
            ],
            "surface_checks": [
                {"type": "api_check", "name": "class_exists", "code": "assert callable(DotProductAttention)"},
            ],
            "overlay_status": "implemented_code_completion",
        },
        "AI-CURATED-TRF-02": {
            "public_tests_py": [
                "import torch, torch.nn as nn; queries = torch.randn(2, 3, 64); keys = torch.randn(2, 5, 64); W_q = nn.Parameter(torch.randn(128, 64)); W_k = nn.Parameter(torch.randn(128, 64)); v = nn.Parameter(torch.randn(128)); scores = additive_attention_scores(queries, keys, W_q, W_k, v); assert scores.shape == (2, 3, 5)",
                "import torch, torch.nn as nn; queries = torch.ones(1, 1, 4); keys = torch.tensor([[[1., 0., 0., 0.], [0., 1., 0., 0.]]]); W_q = nn.Parameter(torch.eye(4)); W_k = nn.Parameter(torch.eye(4)); v = nn.Parameter(torch.tensor([1.0, -1.0, 0.5, 0.0])); scores = additive_attention_scores(queries, keys, W_q, W_k, v, d_h=4); assert torch.isfinite(scores).all() and abs((scores[0, 0, 0] - scores[0, 0, 1]).item()) > 1e-6",
            ],
            "hidden_tests_py": [
                "import torch, torch.nn as nn; queries = torch.randn(1, 2, 8); keys = torch.randn(1, 4, 8); W_q = nn.Parameter(torch.randn(32, 8)); W_k = nn.Parameter(torch.randn(32, 8)); v = nn.Parameter(torch.randn(32)); scores = additive_attention_scores(queries, keys, W_q, W_k, v, d_h=32); assert scores.shape == (1, 2, 4)",
            ],
            "surface_checks": [
                {"type": "api_check", "name": "function_exists", "code": "assert callable(additive_attention_scores)"},
            ],
            "overlay_status": "implemented_code_completion",
        },
        "UVA-02": {
            "public_tests_py": [
                "import torch; mha = MultiheadAttention(input_dim=8, embed_dim=8, num_heads=2); x = torch.randn(2, 4, 8); out = mha(x); assert out.shape == (2, 4, 8)",
                "import torch; mha = MultiheadAttention(input_dim=8, embed_dim=8, num_heads=2); x = torch.randn(1, 4, 8); out, attn = mha(x, return_attention=True); assert attn.shape == (1, 2, 4, 4)",
            ],
            "hidden_tests_py": [
                "import torch; mha = MultiheadAttention(input_dim=4, embed_dim=4, num_heads=1); x = torch.randn(1, 3, 4); mask = torch.tril(torch.ones(3, 3)); out = mha(x, mask=mask); assert out.shape == (1, 3, 4)",
            ],
            "surface_checks": [
                {"type": "api_check", "name": "class_exists", "code": "assert callable(MultiheadAttention) and callable(scaled_dot_product)"},
            ],
            "overlay_status": "implemented_code_completion",
        },
        "AI-CURATED-UVA-02": {
            "public_tests_py": [
                "import torch; q = torch.randn(2, 4, 10, 16); k = torch.randn(2, 4, 10, 16); v = torch.randn(2, 4, 10, 16); out = scaled_dot_product_attention(q, k, v); assert out.shape == (2, 4, 10, 16)",
                "import torch, math; q = torch.tensor([[[[1.0, 0.0]]]]); k = torch.tensor([[[[1.0, 0.0], [0.0, 1.0]]]]); v = torch.tensor([[[[2.0, 0.0], [0.0, 3.0]]]]); out = scaled_dot_product_attention(q, k, v); scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(2.0); expected = torch.matmul(torch.softmax(scores, dim=-1), v); assert torch.allclose(out, expected, atol=1e-6)",
            ],
            "hidden_tests_py": [
                "import torch; q = torch.tensor([[[[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]]]]); k = q.clone(); v1 = torch.tensor([[[[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]]]]); v2 = v1.clone(); v2[0, 0, 2] = torch.tensor([9.0, 9.0]); mask = torch.triu(torch.ones(1, 1, 3, 3), diagonal=1).bool(); out1 = scaled_dot_product_attention(q, k, v1, mask); out2 = scaled_dot_product_attention(q, k, v2, mask); assert torch.allclose(out1[..., 0, :], out2[..., 0, :], atol=1e-6)",
            ],
            "surface_checks": [
                {"type": "api_check", "name": "function_exists", "code": "assert callable(scaled_dot_product_attention)"},
            ],
            "overlay_status": "implemented_code_completion",
        },
    }
)

REFERENCE_UPDATES.update(
    {
        "RNN-01": {
            "evaluation_mode": "class_implementation",
            "entry_point": "RNNScratch",
            "solution": dedent(
                """
                import torch


                class RNNScratch:
                    def __init__(self, input_size, num_hiddens):
                        self.input_size = input_size
                        self.num_hiddens = num_hiddens
                        self.W_xh = torch.randn(input_size, num_hiddens) * 0.01
                        self.W_hh = torch.randn(num_hiddens, num_hiddens) * 0.01
                        self.b_h = torch.zeros(num_hiddens)

                    def forward(self, inputs, state=None):
                        if state is None:
                            state = torch.zeros((inputs.shape[1], self.num_hiddens), device=inputs.device, dtype=inputs.dtype)
                        outputs = []
                        for X in inputs:
                            state = torch.tanh(X @ self.W_xh + state @ self.W_hh + self.b_h)
                            outputs.append(state)
                        return outputs, state
                """
            ),
            "solution_format": "full_code",
            "setup_code": "",
            "timeout_seconds": 5,
            "required_packages": ["torch"],
            "reference_solution_authority": "expert_reconstructed",
            "overlay_status": "implemented_code_completion",
        },
        "AI-CURATED-RNN-01": {
            "evaluation_mode": "class_implementation",
            "entry_point": "RNNScratch",
            "solution": dedent(
                """
                import torch
                import torch.nn.functional as F


                class RNNScratch:
                    def __init__(self, input_size, hidden_size):
                        self.input_size = input_size
                        self.hidden_size = hidden_size
                        self.W_xh = torch.randn(input_size, hidden_size) * 0.01
                        self.W_hh = torch.randn(hidden_size, hidden_size) * 0.01
                        self.b_h = torch.zeros(hidden_size)

                    def forward_step(self, x_t, h_prev):
                        return torch.tanh(x_t @ self.W_xh + h_prev @ self.W_hh + self.b_h)
                """
            ),
            "solution_format": "full_code",
            "setup_code": "",
            "timeout_seconds": 5,
            "required_packages": ["torch"],
            "reference_solution_authority": "researcher_written",
            "overlay_status": "implemented_code_completion",
        },
        "TRF-01": {
            "evaluation_mode": "class_implementation",
            "entry_point": "CausalAttention",
            "solution": dedent(
                """
                import math
                from dataclasses import dataclass

                import torch
                import torch.nn as nn


                @dataclass
                class ModelConfig:
                    d_model: int
                    n_heads: int
                    context_length: int


                class CausalAttention(nn.Module):
                    def __init__(self, config: ModelConfig):
                        super().__init__()
                        assert config.d_model % config.n_heads == 0
                        self.n_heads = config.n_heads
                        self.d_attention = int(config.d_model / config.n_heads)
                        self.W_k = nn.Linear(config.d_model, self.d_attention * config.n_heads)
                        self.W_q = nn.Linear(config.d_model, self.d_attention * config.n_heads)
                        self.W_v = nn.Linear(config.d_model, self.d_attention * config.n_heads)
                        self.W_o = nn.Linear(self.d_attention * config.n_heads, config.d_model)
                        self.register_buffer(
                            "causal_mask",
                            torch.tril(torch.ones(config.context_length, config.context_length)).view(
                                1, 1, config.context_length, config.context_length
                            ),
                            persistent=False,
                        )

                    def forward(self, x):
                        batch_size, seq_len, _ = x.shape
                        q = self.W_q(x).view(batch_size, seq_len, self.n_heads, self.d_attention).transpose(1, 2)
                        k = self.W_k(x).view(batch_size, seq_len, self.n_heads, self.d_attention).transpose(1, 2)
                        v = self.W_v(x).view(batch_size, seq_len, self.n_heads, self.d_attention).transpose(1, 2)
                        scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.d_attention)
                        mask = self.causal_mask[:, :, :seq_len, :seq_len]
                        scores = scores.masked_fill(mask == 0, float("-inf"))
                        self.attention_weights = torch.softmax(scores, dim=-1)
                        out = torch.matmul(self.attention_weights, v)
                        out = out.transpose(1, 2).contiguous().view(batch_size, seq_len, self.n_heads * self.d_attention)
                        return self.W_o(out)
                """
            ),
            "solution_format": "full_code",
            "setup_code": "",
            "timeout_seconds": 5,
            "required_packages": ["torch"],
            "reference_solution_authority": "expert_reconstructed",
            "overlay_status": "implemented_code_completion",
        },
        "AI-CURATED-TRF-01": {
            "evaluation_mode": "class_implementation",
            "entry_point": "CausalSelfAttention",
            "solution": dedent(
                """
                import math

                import torch
                import torch.nn as nn
                import torch.nn.functional as F


                class CausalSelfAttention(nn.Module):
                    def __init__(self, embed_dim: int, num_heads: int, dropout: float = 0.1):
                        super().__init__()
                        assert embed_dim % num_heads == 0
                        self.embed_dim = embed_dim
                        self.num_heads = num_heads
                        self.head_dim = embed_dim // num_heads
                        self.q_proj = nn.Linear(embed_dim, embed_dim)
                        self.k_proj = nn.Linear(embed_dim, embed_dim)
                        self.v_proj = nn.Linear(embed_dim, embed_dim)
                        self.out_proj = nn.Linear(embed_dim, embed_dim)
                        self.dropout = nn.Dropout(dropout)

                    def forward(self, x: torch.Tensor) -> torch.Tensor:
                        batch_size, seq_len, embed_dim = x.shape
                        q = self.q_proj(x).view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
                        k = self.k_proj(x).view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
                        v = self.v_proj(x).view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
                        scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.head_dim)
                        mask = torch.tril(torch.ones(seq_len, seq_len, device=x.device, dtype=torch.bool))
                        scores = scores.masked_fill(~mask.view(1, 1, seq_len, seq_len), float("-inf"))
                        attn = torch.softmax(scores, dim=-1)
                        attn = self.dropout(attn)
                        out = torch.matmul(attn, v)
                        out = out.transpose(1, 2).contiguous().view(batch_size, seq_len, embed_dim)
                        return self.out_proj(out)
                """
            ),
            "solution_format": "full_code",
            "setup_code": "",
            "timeout_seconds": 5,
            "required_packages": ["torch"],
            "reference_solution_authority": "researcher_written",
            "overlay_status": "implemented_code_completion",
        },
    }
)

TEST_UPDATES.update(
    {
        "RNN-01": {
            "public_tests_py": [
                "import torch; model = RNNScratch(3, 5); inputs = torch.randn(4, 2, 3); outputs, state = model.forward(inputs); assert len(outputs) == 4 and outputs[0].shape == (2, 5) and state.shape == (2, 5)",
                "import torch; model = RNNScratch(2, 3); model.W_xh.zero_(); model.W_hh.zero_(); model.b_h = torch.tensor([1.0, 0.0, -1.0]); outputs, state = model.forward(torch.zeros(1, 1, 2)); expected = torch.tanh(torch.tensor([[1.0, 0.0, -1.0]])); assert torch.allclose(outputs[0], expected, atol=1e-6)",
            ],
            "hidden_tests_py": [
                "import torch; model = RNNScratch(2, 4); inputs = torch.randn(3, 1, 2); outputs, state = model.forward(inputs); assert torch.allclose(outputs[-1], state)",
            ],
            "surface_checks": [
                {"type": "api_check", "name": "class_exists", "code": "assert callable(RNNScratch)"},
            ],
            "overlay_status": "implemented_code_completion",
        },
        "AI-CURATED-RNN-01": {
            "public_tests_py": [
                "import torch; model = RNNScratch(3, 5); x_t = torch.ones(4, 3); h_prev = torch.zeros(4, 5); h_t = model.forward_step(x_t, h_prev); assert h_t.shape == (4, 5)",
                "import torch; model = RNNScratch(2, 2); model.W_xh.zero_(); model.W_hh.zero_(); model.b_h = torch.tensor([1.0, 0.0]); h_t = model.forward_step(torch.zeros(1, 2), torch.zeros(1, 2)); assert torch.allclose(h_t, torch.tanh(torch.tensor([[1.0, 0.0]])), atol=1e-6)",
            ],
            "hidden_tests_py": [
                "import torch; model = RNNScratch(4, 6); model.b_h = torch.arange(6.0); h_t = model.forward_step(torch.ones(8, 4), torch.ones(8, 6)); assert not torch.allclose(h_t[:, 0], h_t[:, 1])",
            ],
            "surface_checks": [
                {"type": "api_check", "name": "forward_step_exists", "code": "model = RNNScratch(2, 3); assert hasattr(model, 'forward_step')"},
            ],
            "overlay_status": "implemented_code_completion",
        },
        "TRF-01": {
            "public_tests_py": [
                "import torch; config = ModelConfig(d_model=8, n_heads=2, context_length=4); attn = CausalAttention(config); x = torch.randn(2, 4, 8); out = attn(x); assert out.shape == (2, 4, 8)",
                "import torch; config = ModelConfig(d_model=4, n_heads=1, context_length=4); attn = CausalAttention(config); eye = torch.eye(4); attn.W_q.weight.data.copy_(eye); attn.W_k.weight.data.copy_(eye); attn.W_v.weight.data.copy_(eye); attn.W_o.weight.data.copy_(eye); attn.W_q.bias.data.zero_(); attn.W_k.bias.data.zero_(); attn.W_v.bias.data.zero_(); attn.W_o.bias.data.zero_(); x1 = torch.tensor([[[1., 0., 0., 0.],[0., 1., 0., 0.],[0., 0., 1., 0.],[0., 0., 0., 1.]]]); x2 = x1.clone(); x2[0, 3] = torch.tensor([10., 10., 10., 10.]); out1 = attn(x1); out2 = attn(x2); assert torch.allclose(out1[:, 0], out2[:, 0], atol=1e-6)",
            ],
            "hidden_tests_py": [
                "import torch; config = ModelConfig(d_model=8, n_heads=2, context_length=4); attn = CausalAttention(config); x = torch.randn(1, 4, 8); _ = attn(x); assert attn.attention_weights.shape == (1, 2, 4, 4)",
            ],
            "surface_checks": [
                {"type": "api_check", "name": "class_exists", "code": "assert callable(CausalAttention)"},
            ],
            "overlay_status": "implemented_code_completion",
        },
        "AI-CURATED-TRF-01": {
            "public_tests_py": [
                "import torch; attn = CausalSelfAttention(embed_dim=8, num_heads=2, dropout=0.0); x = torch.randn(2, 5, 8); out = attn(x); assert out.shape == (2, 5, 8)",
                "import torch; attn = CausalSelfAttention(embed_dim=4, num_heads=1, dropout=0.0); eye = torch.eye(4); attn.q_proj.weight.data.copy_(eye); attn.k_proj.weight.data.copy_(eye); attn.v_proj.weight.data.copy_(eye); attn.out_proj.weight.data.copy_(eye); attn.q_proj.bias.data.zero_(); attn.k_proj.bias.data.zero_(); attn.v_proj.bias.data.zero_(); attn.out_proj.bias.data.zero_(); x1 = torch.tensor([[[1., 0., 0., 0.],[0., 1., 0., 0.],[0., 0., 1., 0.],[0., 0., 0., 1.]]]); x2 = x1.clone(); x2[0, 3] = torch.tensor([9., 9., 9., 9.]); out1 = attn(x1); out2 = attn(x2); assert torch.allclose(out1[:, 0], out2[:, 0], atol=1e-6)",
            ],
            "hidden_tests_py": [
                "import torch; attn = CausalSelfAttention(embed_dim=16, num_heads=4, dropout=0.0); x = torch.randn(1, 3, 16); out = attn(x); assert out.shape[-1] == 16",
            ],
            "surface_checks": [
                {"type": "api_check", "name": "class_exists", "code": "assert callable(CausalSelfAttention)"},
            ],
            "overlay_status": "implemented_code_completion",
        },
    }
)


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
    print(f"Updated code-completion overlays -> {REFERENCE_SOLUTIONS}")
    print(f"Updated code-completion tests -> {EXECUTABLE_TESTS}")


if __name__ == "__main__":
    main()

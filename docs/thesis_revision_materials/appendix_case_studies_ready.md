# 附录案例题面对照成稿版

以下内容可作为论文附录中的“案例题面对照”部分直接使用。为便于读者对照，三组案例均采用相同结构：先给出题目基本信息，再分别呈现专家原题与 AI 生成题的题干、要求与起始代码。正文中如果引用第 5.3 节的案例分析，可将本附录标注为“附录 C”或“附录 D”。

## C.1 案例一：PAIR-CURATED-MIT-01

主题：RNN  
难度：intermediate  
任务类型：code completion

### C.1.1 专家原题

题目标题：Define the RNN model for music generation  
来源：MIT Introduction to Deep Learning / Lab 1: Music Generation with RNNs  
原始链接：[PT_Part2_Music_Generation.ipynb](https://raw.githubusercontent.com/MITDeepLearning/introtodeeplearning/master/lab1/PT_Part2_Music_Generation.ipynb)

题干：

Let's define our model as an `nn.Module`. Fill in the TODOs to define the RNN model. Add the LSTM and Linear layers so that the model embeds character indices, processes them with an LSTM of `hidden_size`, and maps outputs back to the vocabulary size.

预期输出：

A completed `LSTMModel` class that produces predictions of shape `(batch_size, sequence_length, vocab_size)` for character-level music generation.

约束条件：

1. Use `nn.Module` to define the model.
2. Use an embedding layer, an `nn.LSTM` layer, and a linear output layer.
3. The LSTM hidden size should be `hidden_size`.
4. The linear layer should map the LSTM output to `vocab_size`.

起始代码：

```python
class LSTMModel(nn.Module):
    def __init__(self, vocab_size, embedding_dim, hidden_size):
        super(LSTMModel, self).__init__()
        self.hidden_size = hidden_size

        self.embedding = nn.Embedding(vocab_size, embedding_dim)

        # TODO: Layer 2: LSTM with hidden_size `hidden_size`
        self.lstm = nn.LSTM('''TODO''')  # TODO

        # TODO: Layer 3: Linear layer to project to vocab_size
        self.fc = nn.Linear('''TODO''')  # TODO

    def init_hidden(self, batch_size, device):
        return (torch.zeros(1, batch_size, self.hidden_size).to(device),
                torch.zeros(1, batch_size, self.hidden_size).to(device))

    def forward(self, x, state=None, return_state=False):
        x = self.embedding(x)
        if state is None:
            state = self.init_hidden(x.size(0), x.device)
        out, state = self.lstm(x, state)
        out = self.fc(out)
        return out if not return_state else (out, state)
```

### C.1.2 AI 生成题

题目标题：Complete the RNN Cell Forward Pass for Music Sequence Generation  
生成模型：`qwen-plus`  
调用方式：`bailian` 接口，生成记录 `GEN-MIT-01-run-20260317-140705-01`

题干：

Implement the forward method of a custom PyTorch RNN cell that processes one time step of a music sequence. The cell takes an input note embedding and the previous hidden state, then returns the updated hidden state and output logits over the vocabulary. Assume autoregressive generation: the output logits at time `t` will be used to sample the next note (`t+1`). Do not modify any other part of the class.

预期输出：

A correctly implemented `forward` method that returns two tensors: (1) the updated hidden state `h_t` of shape `(batch_size, hidden_size)`, and (2) output logits of shape `(batch_size, vocab_size)`, computed using the provided parameters and `tanh` activation.

约束条件：

1. Use only `torch.nn.functional.tanh`; do not use ReLU or sigmoid.
2. Do not use `nn.RNN`, `nn.LSTM`, or any built-in RNN modules.
3. Do not reshape, transpose, or permute tensors beyond what is required for matrix multiplication.
4. All operations must be batched and support arbitrary `batch_size > 0`.

起始代码：

```python
import torch
import torch.nn as nn

class MusicRNNCell(nn.Module):
    def __init__(self, input_size, hidden_size, vocab_size):
        super().__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.vocab_size = vocab_size

        # Learnable parameters
        self.W_ih = nn.Parameter(torch.randn(input_size, hidden_size) * 0.01)
        self.W_hh = nn.Parameter(torch.randn(hidden_size, hidden_size) * 0.01)
        self.b_h = nn.Parameter(torch.zeros(hidden_size))
        self.W_ho = nn.Parameter(torch.randn(hidden_size, vocab_size) * 0.01)
        self.b_o = nn.Parameter(torch.zeros(vocab_size))

    def forward(self, x_t, h_prev):
        """
        Args:
            x_t (torch.Tensor): Input note embedding at time t, shape (batch_size, input_size)
            h_prev (torch.Tensor): Previous hidden state, shape (batch_size, hidden_size)
        Returns:
            h_t (torch.Tensor): Updated hidden state, shape (batch_size, hidden_size)
            logits (torch.Tensor): Output logits over vocabulary, shape (batch_size, vocab_size)
        """
        # TODO: Compute h_t using tanh( x_t @ W_ih + h_prev @ W_hh + b_h )
        # TODO: Compute logits using h_t @ W_ho + b_o
        # Return both h_t and logits
        pass
```

## C.2 案例二：PAIR-CURATED-OPT-02

主题：Optimization  
难度：beginner-intermediate  
任务类型：training-analysis

### C.2.1 专家原题

题目标题：Demonstrate overfitting  
来源：TensorFlow tutorial: Overfit and underfit > Demonstrate overfitting

题干：

The simplest way to prevent overfitting is to start with a small model. To check if you can beat the performance of the small model, progressively train some larger models. Try two hidden layers with 16 units each. Then try three hidden layers with 64 units each. As an exercise, create an even larger model and check how quickly it begins overfitting. Plot the training and validation losses and compare how validation behavior changes with model capacity.

预期输出：

Training and validation loss curves showing that the Tiny model usually avoids overfitting while larger models overfit more quickly.

约束条件：

1. Each model uses the same training configuration.
2. Plot and compare validation metrics to training metrics.
3. Use a log-scale plot for the large model when needed.

起始代码：

```python
def compile_and_fit(model, name, optimizer=None, max_epochs=10000):
    if optimizer is None:
        optimizer = get_optimizer()
    model.compile(
        optimizer=optimizer,
        loss=tf.keras.losses.BinaryCrossentropy(from_logits=True),
        metrics=[
            tf.keras.metrics.BinaryCrossentropy(from_logits=True, name='binary_crossentropy'),
            'accuracy'
        ]
    )
    model.summary()
    history = model.fit(
        train_ds,
        steps_per_epoch=STEPS_PER_EPOCH,
        epochs=max_epochs,
        validation_data=validate_ds,
        callbacks=get_callbacks(name),
        verbose=0
    )
    return history
```

### C.2.2 AI 生成题

题目标题：Analyze Overfitting Across Model Sizes Using Binary Classification Curves  
生成模型：`qwen-plus`  
调用方式：`bailian` 接口，生成记录 `GEN-OPT-02-run-20260317-135431-01`

题干：

Using the provided starter code, train four `tf.keras.Sequential` binary classifiers: Tiny (2 layers, 4 units each), Small (2 layers, 16 units), Medium (3 layers, 32 units), and Large (4 layers, 64 units) on the same synthetic imbalanced binary dataset generated in the starter code. Plot training and validation binary cross-entropy loss curves for all four models on a single figure. Then, for each model, identify and report: (i) the epoch at which validation loss stops improving, and (ii) whether validation loss increases for at least 5 consecutive epochs after that point, indicating clear overfitting. Your analysis must be based solely on the plotted curves and computed metrics.

预期输出：

A single matplotlib figure showing training and validation binary cross-entropy loss curves for all four models, plus a structured text summary listing for each model: (1) the stagnation epoch and (2) a boolean `overfits` flag.

约束条件：

1. Use exactly 50 training epochs for all models.
2. Use binary cross-entropy loss and Adam optimizer with default learning rate.
3. Do not apply regularization such as dropout, L2, or early stopping.
4. Plot all four validation loss curves and all four training loss curves on the same axes using distinct line styles and a legend.
5. Report epoch numbers and overfitting status only from observed curve behavior; do not use heuristic smoothing.

起始代码：

```python
import numpy as np
import tensorflow as tf
import matplotlib.pyplot as plt
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split

tf.random.set_seed(42)
np.random.seed(42)

# Generate synthetic binary classification dataset
X, y = make_classification(
    n_samples=2000,
    n_features=20,
    n_informative=10,
    n_redundant=5,
    n_clusters_per_class=1,
    weights=[0.85, 0.15],  # imbalanced
    random_state=42
)
X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.3, stratify=y, random_state=42)

# Normalize features
mean, std = X_train.mean(axis=0), X_train.std(axis=0)
X_train = (X_train - mean) / std
X_val = (X_val - mean) / std

# Define model architectures as functions
def build_tiny_model():
    return tf.keras.Sequential([
        tf.keras.layers.Dense(4, activation='relu', input_shape=(20,)),
        tf.keras.layers.Dense(4, activation='relu'),
        tf.keras.layers.Dense(1, activation='sigmoid')
    ])

def build_small_model():
    return tf.keras.Sequential([
        tf.keras.layers.Dense(16, activation='relu', input_shape=(20,)),
        tf.keras.layers.Dense(16, activation='relu'),
        tf.keras.layers.Dense(1, activation='sigmoid')
    ])

def build_medium_model():
    return tf.keras.Sequential([
        tf.keras.layers.Dense(32, activation='relu', input_shape=(20,)),
        tf.keras.layers.Dense(32, activation='relu'),
        tf.keras.layers.Dense(32, activation='relu'),
        tf.keras.layers.Dense(1, activation='sigmoid')
    ])

def build_large_model():
    return tf.keras.Sequential([
        tf.keras.layers.Dense(64, activation='relu', input_shape=(20,)),
        tf.keras.layers.Dense(64, activation='relu'),
        tf.keras.layers.Dense(64, activation='relu'),
        tf.keras.layers.Dense(64, activation='relu'),
        tf.keras.layers.Dense(1, activation='sigmoid')
    ])

# Compile and train each model (you will implement this)
models = {
    'Tiny': build_tiny_model(),
    'Small': build_small_model(),
    'Medium': build_medium_model(),
    'Large': build_large_model()
}

# You will add training logic here — use 50 epochs, batch_size=32, binary_crossentropy, Adam optimizer
# Store history objects in a dictionary: histories[model_name] = history
histories = {}

# Plot setup
plt.figure(figsize=(10, 6))
```

## C.3 案例三：PAIR-CURATED-KER-04

主题：RNN  
难度：intermediate  
任务类型：model building

### C.3.1 专家原题

题目标题：Implement a character-level recurrent seq2seq translator  
来源：Keras Code Examples / Machine translation / Character-level recurrent sequence-to-sequence model  
原始链接：[lstm_seq2seq](https://keras.io/examples/nlp/lstm_seq2seq/)

题干：

Implement a basic character-level recurrent sequence-to-sequence model for translating short English sentences into short French sentences. Build an encoder LSTM that returns its final states, then build a decoder LSTM initialized with the encoder states, followed by a dense softmax layer. Train the model on vectorized character sequences and use the trained model for decoding.

预期输出：

A trained character-level seq2seq model that maps short English sentences to short French sentences and can be used for decoding at inference time.

约束条件：

1. Use a character-level encoder-decoder architecture.
2. Use an encoder LSTM with `return_state=True`.
3. Initialize the decoder LSTM with the encoder states.
4. Use a dense softmax layer over the decoder outputs.

起始代码：

```python
encoder_inputs = keras.Input(shape=(None, num_encoder_tokens))
encoder = keras.layers.LSTM(latent_dim, return_state=True)
encoder_outputs, state_h, state_c = encoder(encoder_inputs)
encoder_states = [state_h, state_c]

decoder_inputs = keras.Input(shape=(None, num_decoder_tokens))
decoder_lstm = keras.layers.LSTM(latent_dim, return_sequences=True, return_state=True)
decoder_outputs, _, _ = decoder_lstm(decoder_inputs, initial_state=encoder_states)
decoder_dense = keras.layers.Dense(num_decoder_tokens, activation="softmax")
decoder_outputs = decoder_dense(decoder_outputs)

model = keras.Model([encoder_inputs, decoder_inputs], decoder_outputs)
model.compile(optimizer="rmsprop", loss="categorical_crossentropy", metrics=["accuracy"])
model.fit(
    [encoder_input_data, decoder_input_data],
    decoder_target_data,
    batch_size=batch_size,
    epochs=epochs,
    validation_split=0.2,
)
```

### C.3.2 AI 生成题

题目标题：Build a Character-Level Seq2Seq Model with Teacher Forcing  
生成模型：`qwen-plus`  
调用方式：`bailian` 接口，生成记录 `GEN-KER-04-run-20260317-134150-01`

题干：

Implement a character-level sequence-to-sequence model using LSTM layers in Keras to translate short English words into their Pig Latin equivalents (for example, `hello -> ellohay`, `apple -> appleway`). Your implementation must include: (1) an encoder LSTM that processes the input word and returns its final hidden state; (2) a decoder LSTM initialized with the encoder’s final state and trained with teacher forcing; and (3) a dense output layer with softmax over the character vocabulary. Use one-hot encoded inputs and outputs for characters from a fixed vocabulary of 27 symbols (`a-z` plus space). Train for exactly 10 epochs on the provided synthetic dataset generated inline, and return the compiled Keras model object.

预期输出：

A compiled Keras model object `model` with input tensors matching `encoder_inputs.shape[1:]` and `decoder_inputs.shape[1:]`, and output matching `decoder_targets.shape[1:]`, trainable and ready for `model.fit()`.

约束条件：

1. Use exactly one LSTM layer for encoder and one for decoder; do not stack LSTMs.
2. Encoder must return only the final hidden and cell states (`return_state=True`), not sequences.
3. Decoder must be initialized with encoder final states and consume teacher-forced inputs.
4. Output layer must apply `Dense(vocab_size) + Softmax` timestep-wise, for example via `TimeDistributed`.
5. Do not modify the provided data generation or preprocessing functions.

起始代码：

```python
import numpy as np
import tensorflow as tf
from tensorflow.keras import layers, models

# Vocabulary: 26 lowercase letters + space
chars = 'abcdefghijklmnopqrstuvwxyz '
char_indices = {ch: i for i, ch in enumerate(chars)}
indices_char = {i: ch for i, ch in enumerate(chars)}
vocab_size = len(chars)
max_len = 12

# Helper: convert word to one-hot tensor of shape (max_len, vocab_size)
def word_to_onehot(word):
    x = np.zeros((max_len, vocab_size))
    for t, ch in enumerate(word[:max_len]):
        if ch in char_indices:
            x[t, char_indices[ch]] = 1.0
    return x

# Synthetic data generation (50 English→PigLatin pairs)
def generate_sample_data():
    pairs = [
        ('hello', 'ellohay'), ('world', 'orldway'), ('apple', 'appleway'),
        ('orange', 'angeoray'), ('eat', 'eatway'), ('under', 'underway'),
        ('ice', 'iceway'), ('object', 'jectobay'), ('python', 'onpythay'),
        ('train', 'aintray')
    ] * 5
    # Pad both sides to max_len
    encoder_inputs = np.array([word_to_onehot(p[0]) for p in pairs])
    decoder_inputs = np.array([word_to_onehot(' ' + p[1]) for p in pairs])  # teacher forcing: prepend ' '
    decoder_targets = np.array([word_to_onehot(p[1] + ' ') for p in pairs])  # shift right
    return encoder_inputs, decoder_inputs, decoder_targets

encoder_inputs, decoder_inputs, decoder_targets = generate_sample_data()

# TODO: Define your encoder-decoder model below.
# - Encoder: LSTM returning state (not sequences)
# - Decoder: LSTM taking initial_state from encoder, with teacher-forced inputs
# - Output: Dense + softmax over vocab_size, applied timestep-wise
# Compile with 'categorical_crossentropy' and 'adam'
# Return the compiled model as `model`.
```

## 使用建议

1. 如果附录篇幅允许，建议完整保留三组案例。
2. 如果学校格式要求附录尽量简短，可只保留“题干 + 起始代码”，将“预期输出”和“约束条件”并入题干后的说明段。
3. 若需要中文化，可只翻译说明性标题，不建议改动题干英文原文，以保持与原始数据集完全一致。

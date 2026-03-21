from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from _shared_io import read_csv_rows, write_csv_rows
from survey.human_eval_paths import build_human_eval_paths


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HUMAN_EVAL_PATHS = build_human_eval_paths(PROJECT_ROOT)
PACKETS_DIR = HUMAN_EVAL_PATHS.packets_dir
AUDIT_DIR = HUMAN_EVAL_PATHS.audit_build_dir
STUDENT_PACKET = HUMAN_EVAL_PATHS.student_packet
STUDENT_PACKAGES_DIR = HUMAN_EVAL_PATHS.student_packages_dir
ZH_PACKET = HUMAN_EVAL_PATHS.student_packet_zh
MANIFEST_PATH = HUMAN_EVAL_PATHS.student_package_manifest

TOPIC_TRANSLATIONS = {
    "CNN": "CNN",
    "RNN": "RNN",
    "Transformer": "Transformer",
    "Optimization": "优化与训练分析",
}

TRANSLATIONS: dict[str, dict[str, str]] = {
    "B0002": {
        "title": "构建带 Teacher Forcing 的字符级 Seq2Seq 模型",
        "instruction_text": "请使用 Keras 中的 LSTM 构建一个字符级序列到序列模型，把简短英文单词翻译成对应的 Pig Latin 形式（例如 hello → ellohay，apple → appleway）。模型必须包含：1）编码器 LSTM，读取输入单词并输出最后的隐藏状态；2）以编码器最终状态初始化的解码器 LSTM，并在训练时使用 teacher forcing；3）对字符词表做 softmax 预测的输出层。输入和输出都使用固定 27 个符号（a-z 加空格）的 one-hot 编码。请在给定的合成数据集上训练 10 个 epoch，并返回编译好的 Keras 模型。",
        "expected_output": "返回一个已编译的 Keras 模型 `model`。它的输入形状应与 `encoder_inputs` 和 `decoder_inputs` 匹配，输出形状应与 `decoder_targets` 匹配，并且可以直接用于 `model.fit()`。",
        "constraints_text": "- 只能使用 1 个编码器 LSTM 和 1 个解码器 LSTM。\n- 编码器只返回最终 hidden/cell state，不返回整段序列。\n- 解码器必须用编码器最终状态初始化，并使用 teacher forcing 输入。\n- 输出层需要对每个时间步做字符分类。\n- 不要修改给定的数据生成与预处理函数。",
        "test_cases_text": "测试 1：模型可以同时接收编码器输入和解码器输入，输出形状应为 `(1, max_len, vocab_size)`。\n\n测试 2：模型中应恰好包含 2 个 LSTM 层（1 个编码器、1 个解码器）。\n\n测试 3：模型应使用 `categorical_crossentropy` 作为损失函数。",
    },
    "B0005": {
        "title": "补全音乐生成 RNN Cell 的前向传播",
        "instruction_text": "请完成一个自定义 PyTorch RNN cell 的 `forward` 方法，用于处理音乐序列的单个时间步。输入是当前音符的 embedding 和上一个隐藏状态，输出是更新后的隐藏状态以及对整个音符词表的 logits。默认这是自回归生成场景：时刻 t 的 logits 会用于采样下一个音符。除 `forward` 外，不要修改类中的其他部分。",
        "expected_output": "返回两个张量：1）更新后的隐藏状态 `h_t`，形状为 `(batch_size, hidden_size)`；2）输出 logits，形状为 `(batch_size, vocab_size)`。",
        "constraints_text": "- 非线性只能使用 `torch.nn.functional.tanh`。\n- 不要使用 `nn.RNN`、`nn.LSTM` 等内置循环模块。\n- 除矩阵乘法所需操作外，不要额外 reshape、transpose 或 permute。\n- 计算必须支持任意 batch 大小。",
        "test_cases_text": "测试 1：检查 `h_t` 与 `logits` 的输出形状是否正确。\n\n测试 2：在固定随机种子下，输出应可复现。\n\n测试 3：隐藏状态应经过 tanh，取值位于 `(-1, 1)` 之间。",
    },
    "B0008": {
        "title": "使用 Dropout 改写稠密网络以提升泛化",
        "instruction_text": "给定一个在 IMDB 数据集上快速过拟合的 `tf.keras.Sequential` 基线模型，请仅在每个 Dense 层之后（最后输出层除外）加入 `Dropout(0.5)`。其余设置必须保持不变，包括层数、神经元数量、激活函数、优化器、损失函数、指标、batch size、训练 epoch 数以及训练/验证划分。请分别训练基线模型和改写后的模型，并绘制它们的验证准确率曲线进行比较。最后用一句话说明 Dropout 对泛化的影响。",
        "expected_output": "提交内容应包含：1）定义好的 `revised_model`；2）训练代码；3）一张叠加比较两条验证准确率曲线的图；4）一句说明 Dropout 是否改善了泛化的解释。",
        "constraints_text": "- 只允许在 Dense 层后加入 `Dropout(0.5)`，不要加在 Embedding 或输出层前。\n- 不要改动优化器、损失函数、batch size、epoch 或数据预处理。\n- 必须使用与基线完全相同的训练/验证划分。\n- 需要把基线与修改版的验证准确率画在同一张图上。",
        "test_cases_text": "测试 1：模型中应恰好有 2 个 Dropout 层，且位置正确。\n\n测试 2：图中应包含两条曲线，分别代表 Baseline 与 Revised。\n\n测试 3：解释语句需要明确提到验证集表现与泛化/过拟合差距。",
    },
    "B0011": {
        "title": "构建用于依存句法分析的 Stack-LSTM 转移解析器",
        "instruction_text": "请使用 PyTorch 实现一个基于转移动作的依存句法分析器，模型采用 stack-LSTM 架构。输入为 token embedding 与动作序列（SHIFT、LEFT-ARC、RIGHT-ARC），模型需要预测下一步动作。要求使用两个 LSTM：一个表示栈状态，一个表示缓冲区状态。将栈顶隐藏状态与缓冲区首元素隐藏状态拼接后，送入线性分类器预测 3 个动作类别。请在一批合成数据上训练 1 个 epoch，并返回训练后的模型实例。",
        "expected_output": "返回一个训练好的 PyTorch `nn.Module`，调用后输出形状应为 `(batch_size * seq_len, 3)`。",
        "constraints_text": "- 必须使用两个独立的 LSTM，分别表示 stack 和 buffer。\n- 用张量索引模拟 push/pop，不要使用 Python 列表做栈。\n- 分类器输入只能使用当前栈顶和缓冲区首元素的隐藏状态。\n- 训练 1 个 epoch，优化器使用 Adam，学习率 0.001。\n- 只返回训练好的模型对象。",
        "test_cases_text": "测试 1：前向传播输出形状应为 `(80, 3)`。\n\n测试 2：模型应包含 embedding、stack LSTM 和 buffer LSTM 等必要模块。\n\n测试 3：反向传播后，模型参数都应具有非空梯度。",
    },
    "B0013": {
        "title": "实现仅解码器 Transformer 的因果自注意力",
        "instruction_text": "请补全 `CausalSelfAttention` 类中的 `forward` 方法，实现带因果掩码的缩放点积注意力。输入的 query、key、value 张量形状均为 `(batch_size, seq_len, embed_dim)`。你需要完成多头拆分、注意力分数计算、因果掩码、softmax、dropout 以及多头合并，最终返回形状为 `(batch_size, seq_len, embed_dim)` 的输出。",
        "expected_output": "返回形状为 `(batch_size, seq_len, embed_dim)` 的张量，数值行为应符合因果自注意力的预期。",
        "constraints_text": "- 只能使用 PyTorch 运算，不要按时间步写循环。\n- 因果掩码必须保证位置 i 只能关注 `<= i` 的位置。\n- softmax 前必须按 `1/sqrt(head_dim)` 缩放。\n- dropout 应作用在注意力权重上。\n- 需要正确处理 reshape / transpose，保持多头语义。",
        "test_cases_text": "测试 1：输出形状应与输入的 batch 和 seq_len 对应。\n\n测试 2：未来位置的注意力权重应被掩蔽到接近 0。\n\n测试 3：必须正确使用 `1/sqrt(head_dim)` 的缩放因子。",
    },
    "B0014": {
        "title": "构建双卷积块的 MNIST CNN",
        "instruction_text": "请定义一个名为 `MNIST_CNN` 的 PyTorch `nn.Module`，用于 MNIST 手写数字分类。模型包含两个相同的卷积块，每个卷积块都由以下部分组成：1）3×3 卷积，输出通道数为 8，并接 ReLU；2）2×2 最大池化；3）`Dropout(p=0.1)`。两个卷积块之后，将特征展平，并接一个输出 10 类 logits 的线性层。请训练 5 个 epoch，使用 SGD（lr=0.01）、交叉熵损失与 batch size=128，最后返回测试准确率。",
        "expected_output": "返回一个介于 0.0 到 1.0 之间的浮点数，表示模型训练 5 个 epoch 后在测试集上的准确率。",
        "constraints_text": "- 只能使用 `Conv2d`、`MaxPool2d`、`Dropout`、`ReLU`、`Linear`、`Flatten`。\n- 卷积层参数固定：kernel_size=3、stride=1、padding=1。\n- 不要增加 BatchNorm、数据增强或其他额外层。\n- 必须训练满 5 个 epoch。",
        "test_cases_text": "测试 1：最终测试准确率应不低于约 97.5%。\n\n测试 2：模型结构应为两个 conv→relu→pool→dropout 块，之后再接 Flatten 与 Linear。",
    },
    "B0016": {
        "title": "加入 Dropout",
        "instruction_text": "请在较大的基线网络中加入 Dropout 层，观察其对过拟合的影响。使用 `tf.keras.layers.Dropout`，并将 Dropout 应用于前一层的输出。完成网络改写后，沿用原有的 `compile_and_fit` 过程训练模型。",
        "expected_output": "一个加入 Dropout 后训练完成的模型，以及与未正则化 Large 模型相比的现象或结果说明。",
        "constraints_text": "- 保持与教程前面相同的训练配置。\n- 使用 `tf.keras.layers.Dropout` 实现 Dropout。\n- 需要将结果与 Tiny 基线和前面的正则化变体进行比较。",
        "test_cases_text": "",
    },
    "B0017": {
        "title": "实现 RNN 隐状态更新步骤",
        "instruction_text": "请补全 `RNNScratch` 类中的 `forward_step` 方法，按标准 RNN 递推公式计算下一个隐藏状态：`h_t = tanh(W_xh @ x_t + W_hh @ h_{t-1} + b_h)`。输入为当前时间步 `x_t` 和前一时刻隐藏状态 `h_prev`，返回更新后的隐藏状态 `h_t`。不要修改类中的其他部分。",
        "expected_output": "返回形状为 `[batch_size, hidden_size]` 的张量 `h_t`。",
        "constraints_text": "- 只能使用 `torch.tanh` 与矩阵乘法 `@`。\n- 不要额外引入新参数或调用其他外部函数。\n- 仅在必要时进行张量广播，不要随意 reshape。",
        "test_cases_text": "测试 1：检查输出形状。\n\n测试 2：检查 tanh 是否作用在预激活结果上。\n\n测试 3：检查偏置是否能正确按 batch 维度广播。",
    },
    "B0019": {
        "title": "实现带因果掩码的缩放点积注意力",
        "instruction_text": "请补全 `scaled_dot_product_attention` 函数，实现带可选因果掩码的缩放点积注意力。输入的 query、key、value 形状为 `(batch_size, num_heads, seq_len, head_dim)`。函数需要完成：按 `sqrt(head_dim)` 缩放、计算 `Q @ K^T`、在 softmax 前应用掩码，并返回对 value 的加权求和结果。",
        "expected_output": "返回形状为 `(batch_size, num_heads, seq_len, head_dim)` 的注意力输出张量，且缩放、掩码、归一化处理正确。",
        "constraints_text": "- 不要使用任何内置 attention 模块。\n- 只能使用批量矩阵乘法，不要按 head 或 batch 写循环。\n- 缩放因子必须按 `sqrt(head_dim)` 计算。\n- 掩码必须在 softmax 前生效，被屏蔽位置应变为 `-inf`。\n- 需要保持 batch 与 head 维度不丢失。",
        "test_cases_text": "测试 1：输出形状应与输入 query 的形状对应。\n\n测试 2：因果掩码应使未来位置的注意力权重变为接近 0。\n\n测试 3：必须正确使用缩放因子 `1/sqrt(head_dim)`。",
    },
    "B0020": {
        "title": "加入权重正则化",
        "instruction_text": "请在现有模型中加入权重正则化（weight regularization），并训练修改后的模型以比较正则化对过拟合的影响。",
        "expected_output": "一个加入权重正则化后训练完成的模型，以及相应的比较结果或观察结论。",
        "constraints_text": "- 保持原始训练流程和数据不变。\n- 只修改与权重正则化相关的部分。\n- 需要对比修改前后的效果。",
        "test_cases_text": "",
    },
    "B0021": {
        "title": "给稠密网络加入 L2 权重正则化",
        "instruction_text": "给定一个在 IMDB 数据集上训练的 `tf.keras.Sequential` 基线模型，请只对第一个 Dense 层的 kernel 加入 `L2(0.001)` 正则化，其他结构、预处理、优化器和训练设置保持不变。分别训练基线模型和正则化模型 20 个 epoch，对比验证损失曲线，并说明正则化是否改善了泛化。",
        "expected_output": "提交内容应包含：1）定义并编译 `regularized_model`；2）训练代码；3）`final_baseline_val_loss`、`final_regularized_val_loss` 和解释文本。",
        "constraints_text": "- 只对第一个 Dense 层的 kernel 做 L2 正则化。\n- 不要修改层数、激活函数、优化器、loss、batch size、epoch 或验证集划分。\n- 数据加载与预处理必须和基线保持一致。\n- 需要报告两个模型的最终验证损失并给出简短解释。",
        "test_cases_text": "测试 1：模型中应只有一个 L2 正则化器，且位置正确。\n\n测试 2：正则化模型的最终验证损失应处于合理范围。\n\n测试 3：解释语句需要提到 validation loss 与 generalization / overfitting。",
    },
    "B0022": {
        "title": "展示过拟合现象",
        "instruction_text": "请基于给定模型和训练设置，运行实验并展示模型发生过拟合的现象，说明训练集与验证集表现的差异。",
        "expected_output": "一组能够体现过拟合现象的训练结果、曲线或简短分析说明。",
        "constraints_text": "- 保持给定模型结构与训练设置。\n- 需要展示训练集与验证集的差异。\n- 分析应围绕过拟合现象本身。",
        "test_cases_text": "",
    },
    "B0023": {
        "title": "定义并训练用于 MNIST 分类的 CNN",
        "instruction_text": "在 MIT 深度学习导论 Lab 2 Part 1 的背景下，请使用 `nn.Conv2d` 和 `nn.MaxPool2d` 等层定义一个用于手写数字分类的 CNN，并在 MNIST 上完成训练与测试评估。你还需要定义优化器和损失函数，运行训练循环，并报告测试准确率。",
        "expected_output": "一个在 MNIST 上训练完成的 CNN 模型，以及最终测试准确率。",
        "constraints_text": "- 使用 notebook 中给定的 MNIST 训练集和测试集。\n- 采用实验要求中的 CNN 结构。\n- 模型、训练与评估过程都用 PyTorch 完成。\n- 训练后需要报告测试准确率。",
        "test_cases_text": "",
    },
    "B0024": {
        "title": "实现字符级循环 Seq2Seq 翻译器",
        "instruction_text": "请实现一个基础的字符级循环序列到序列模型，把简短英文句子翻译成简短法语句子。构建一个返回最终状态的编码器 LSTM，再构建一个以编码器状态初始化的解码器 LSTM，并接上字符级 softmax 输出层。使用向量化后的字符序列训练模型，并用训练后的模型完成解码。",
        "expected_output": "一个训练完成的字符级 seq2seq 模型，能够将短英文句子映射为短法语句子，并可用于推理解码。",
        "constraints_text": "- 使用字符级 encoder-decoder 架构。\n- 编码器 LSTM 需设置 `return_state=True`。\n- 解码器必须使用编码器状态初始化。\n- 输出层应对每个时间步做 softmax 分类。",
        "test_cases_text": "",
    },
    "B0025": {
        "title": "定义用于音乐生成的 RNN 模型",
        "instruction_text": "请补全 `LSTMModel` 类中的 TODO，使用 `nn.Module` 定义一个 RNN 模型。模型应先对字符索引做 embedding，再通过 LSTM 处理序列，最后通过线性层把输出映射回词表大小。",
        "expected_output": "一个补全后的 `LSTMModel` 类，能够输出形状为 `(batch_size, sequence_length, vocab_size)` 的预测结果。",
        "constraints_text": "- 使用 `nn.Module` 定义模型。\n- 模型需要包含 embedding 层、`nn.LSTM` 层和线性输出层。\n- LSTM 的隐藏维度应为 `hidden_size`。\n- 线性层应把 LSTM 输出映射到 `vocab_size`。",
        "test_cases_text": "",
    },
    "B0028": {
        "title": "卷积：朴素前向传播",
        "instruction_text": "卷积神经网络的核心是卷积运算。请在 `cs231n/layers.py` 中实现 `conv_forward_naive` 的前向传播。现阶段不必过分追求效率，优先写出清晰、正确的实现，并按给定方式运行测试。",
        "expected_output": "返回 `(out, cache)`，其中 `out` 的形状为 `(N, F, H', W')`，`cache = (x, w, b, conv_param)`。",
        "constraints_text": "- 先保证实现清晰正确，不强求高效率。\n- padding 需要在高和宽两个维度上对称添加。\n- 不要直接修改原始输入 `x`。\n- 可以使用 `np.pad` 完成补零。",
        "test_cases_text": "",
    },
    "B0030": {
        "title": "在 IMDB 上构建并训练双层双向 LSTM",
        "instruction_text": "请为 IMDB 影评情感分类任务构建一个文本分类模型：先用 embedding 层表示输入，再接两个双向 LSTM 层，最后接一个 sigmoid 输出层。完成训练与评估，并报告验证集准确率和损失。",
        "expected_output": "一个在 IMDB 情感分类任务上训练完成的 Keras 模型，以及训练后的验证指标。",
        "constraints_text": "- 使用 `num_words=max_features` 加载 IMDB 数据集。\n- 将输入序列 padding 到 `maxlen=200`。\n- 必须使用两个双向 LSTM 层。\n- 输出层使用 sigmoid 做二分类。",
        "test_cases_text": "",
    },
    "B0031": {
        "title": "实现缩放点积注意力与多头注意力",
        "instruction_text": "在 UvA Deep Learning Tutorial 6 的对应部分中，实现缩放点积注意力和多头注意力模块。具体需要完成：根据 queries 和 keys 计算注意力 logits，做缩放与掩码，softmax 归一化后加权 values；然后完成 MultiheadAttention 模块中的 Q/K/V 投影、分头、应用注意力、拼接多头结果以及输出投影。",
        "expected_output": "一个可运行的缩放点积注意力实现，以及支持掩码、多头和返回注意力图的 `MultiheadAttention` 模块。",
        "constraints_text": "- 仅实现 Tutorial 6 中“Scaled Dot Product Attention”和“Multi-Head Attention”这部分。\n- 不要扩展到 Transformer Encoder、位置编码或完整实验流程。\n- 需要实现 Q/K/V 投影、分头、mask、softmax、拼接和输出投影。\n- 任务粒度保持在模块级，不要做成完整 Transformer 项目。",
        "test_cases_text": "",
    },
    "B0033": {
        "title": "实现神经转移式依存句法分析器",
        "instruction_text": "请在 `parser_model.py` 中实现一个基于神经网络的依存句法分析器，并在 `run.py` 中补全训练相关函数。模型通过提取当前状态的特征向量、查词向量、拼接输入，再经过前馈网络和 softmax 输出动作概率。完成 `init`、`embedding_lookup`、`forward`、`train_for_epoch` 和 `train` 后，运行 `python run.py` 进行训练，并在 Penn Treebank（Universal Dependencies 标注）上评估 UAS。",
        "expected_output": "一个可运行的依存句法分析器实现，包括 `parser_model.py` 与 `run.py` 中所需函数，并报告 dev 集最佳 UAS 以及 test 集 UAS。",
        "constraints_text": "- 不要使用 `torch.nn.Linear` 或 `torch.nn.Embedding`。\n- 如果 TODO 中有命名要求，请遵守。\n- 实现 `embedding_lookup` 时尽量使用高效写法，避免不必要的 for 循环。",
        "test_cases_text": "测试 1：运行 `embedding_lookup` 的 sanity check。\n\n测试 2：运行 `forward` 的 sanity check。\n\n测试 3：debug 模式下，期望 dev loss < 0.2 且 dev UAS > 65。\n\n测试 4：完整训练下，期望 train loss < 0.08 且 dev UAS > 87。",
    },
    "B0036": {
        "title": "基于二分类曲线分析不同模型规模下的过拟合",
        "instruction_text": "使用给定 starter code，在同一个合成的类别不平衡二分类数据集上训练四个 `tf.keras.Sequential` 模型：Tiny、Small、Medium 和 Large。请在一张图上画出四个模型的训练集与验证集 binary cross-entropy 曲线，并报告每个模型：1）验证损失首次不再改善的 epoch；2）此后是否连续 5 个 epoch 以上持续上升，从而体现明显过拟合。",
        "expected_output": "一张同时展示四个模型训练/验证损失曲线的图，以及一份结构化文字总结，列出每个模型的停滞 epoch 和 `overfits` 标记。",
        "constraints_text": "- 所有模型都训练 50 个 epoch。\n- 优化器使用默认 Adam，损失为 binary cross-entropy。\n- 不要加入 dropout、L2 或 early stopping。\n- 所有训练/验证曲线需要画在同一张图上并标明图例。\n- 结论必须基于曲线与指标本身，不要做额外推测。",
        "test_cases_text": "测试 1：图中应有 8 条曲线（4 条训练 + 4 条验证）。\n\n测试 2：Tiny 模型通常停滞较晚，且不应被判定为明显过拟合。\n\n测试 3：Large 模型通常较早停滞，并应被判定为过拟合。",
    },
    "B0038": {
        "title": "RNN 模型前向传播",
        "instruction_text": "下方 `forward` 方法描述了在任意时间步如何根据当前输入和前一时刻状态计算输出与隐藏状态。该模型会沿着输入的最外层维度逐时间步循环更新隐藏状态，并使用 tanh 激活函数。请完成该前向传播逻辑。",
        "expected_output": "一个补全后的 `forward` 方法，能够正确逐步更新隐藏状态，并返回 `outputs` 和最终 `state`。",
        "constraints_text": "- 按输入的最外层维度逐时间步循环。\n- 用当前输入和上一时刻状态更新隐藏状态。\n- 使用 tanh 激活。\n- 返回所有输出以及最终状态。",
        "test_cases_text": "",
    },
    "B0041": {
        "title": "构建、训练并评估一个简单的 MNIST 卷积网络",
        "instruction_text": "请使用 Keras Sequential 构建一个用于 MNIST 的卷积网络，结构包括两层 `Conv2D`、两层 `MaxPooling2D`、`Flatten`、`Dropout` 以及一个 Dense softmax 分类器。之后使用 `categorical_crossentropy` 和 Adam 训练 15 个 epoch，并在测试集上评估模型。",
        "expected_output": "一个训练完成的 MNIST 卷积网络，以及 `model.evaluate` 输出的测试损失与测试准确率。",
        "constraints_text": "- 使用 `keras.datasets.mnist` 提供的数据集。\n- 模型结构按示例要求构建。\n- 训练使用 `categorical_crossentropy` 与 Adam。\n- 训练结束后必须在测试集上评估。",
        "test_cases_text": "",
    },
    "B0042": {
        "title": "使用 Keras 构建最简 MNIST 卷积网络",
        "instruction_text": "请使用 Keras 构建一个紧凑的卷积神经网络，用于 MNIST 手写数字分类。模型必须包含两层 `Conv2D`（每层后接 ReLU 和 `MaxPooling2D`）、一层 `Flatten`、一层带 ReLU 的隐藏层，以及一个 10 类 softmax 输出层。使用 categorical crossentropy 和 Adam 编译模型，并训练 5 个 epoch，最后返回训练好的 `model`。",
        "expected_output": "一个已经定义、编译并在 MNIST 上训练 5 个 epoch 的 Keras Sequential 模型对象 `model`。",
        "constraints_text": "- 只能使用 Keras Sequential API。\n- 两个卷积层固定为 32 / 64 个 filter，3×3 卷积核，`same` padding。\n- 不要使用 Dropout 或 BatchNormalization。\n- 不进行数据增强。\n- 使用 batch_size=128，训练 5 个 epoch。",
        "test_cases_text": "测试 1：`model` 应是 `keras.models.Sequential` 实例。\n\n测试 2：模型应恰好有 7 层。\n\n测试 3：最后一层应为 10 单元 softmax。\n\n测试 4：第 5 个 epoch 的训练准确率应达到合理水平（约 97.5% 及以上）。",
    },
    "B0043": {
        "title": "构建用于 IMDB 情感分类的双向 LSTM 模型",
        "instruction_text": "请构建一个 Keras 模型，用于 IMDB 影评的二分类情感分析。模型结构为：Embedding 层后接一个双向 LSTM 层，再接一个 sigmoid 输出层。使用 binary crossentropy 和 Adam 编译，训练 5 个 epoch，batch size 为 32，并返回训练好的模型对象。",
        "expected_output": "一个已经构建、编译并训练完成的 Keras Sequential 模型，可对 padding 后的 IMDB 序列进行情感二分类。",
        "constraints_text": "- 必须是 1 个 Embedding + 1 个 Bidirectional(LSTM) + 1 个 Dense 输出层。\n- 不要增加额外的 RNN 或 Dense 层。\n- 使用 binary crossentropy 与 Adam。\n- 训练固定为 5 个 epoch，batch_size=32。\n- 不要改标签预处理或额外加入 callback。",
        "test_cases_text": "测试 1：`model.predict(x_test[:1])` 的输出形状应为 `(1, 1)`。\n\n测试 2：模型应恰好有 3 层。\n\n测试 3：第二层必须是包裹了 LSTM 的 `Bidirectional` 层。",
    },
    "B0044": {
        "title": "显式 Padding 与 Stride 的卷积层前向传播",
        "instruction_text": "请用 NumPy 实现二维卷积层的前向传播。给定输入张量 `(N, C, H, W)`、卷积核张量 `(F, C, HH, WW)`、padding `p` 和 stride `s`，计算输出激活张量。默认对输入四周做零填充，输出形状满足标准卷积公式。禁止使用内置卷积函数，必须用循环显式实现。",
        "expected_output": "返回形状为 `(N, F, H_out, W_out)` 的 NumPy 数组 `out`，其中每个位置的值由对应局部窗口与卷积核逐元素乘加并加上偏置得到。",
        "constraints_text": "- 只能使用 NumPy，不要调用外部卷积函数。\n- 必须显式对输入做 zero-padding。\n- 保持 NCHW 张量布局。\n- 实现应支持满足形状条件的任意整数 padding 与 stride。",
        "test_cases_text": "测试 1：检查输出形状是否正确。\n\n测试 2：检查中心位置的卷积结果是否与手算一致。\n\n测试 3：检查边界位置在 padding 后是否正确使用 0 值。",
    },
    "B0046": {
        "title": "实现 `CausalAttention.forward`",
        "instruction_text": "请在 `model_solution.py` 中实现 Transformer 的 `CausalAttention.forward` 方法，并通过对应测试。题目文件中还包含其他类，但本题只要求完成这一部分。",
        "expected_output": "一个可以通过对应测试的 `CausalAttention.forward` 实现。",
        "constraints_text": "- 不要修改单元测试文件。\n- 只需实现本题要求的 `CausalAttention.forward`。\n- 完成后应通过给定测试。",
        "test_cases_text": "测试 1：运行 `tests/test_student.py::test_attention`，输出应与快照文件匹配。",
    },
}


def translate_row(row: dict[str, Any]) -> dict[str, Any]:
    blind_exercise_id = row.get("blind_exercise_id", "")
    translated = dict(row)
    if blind_exercise_id not in TRANSLATIONS:
        raise KeyError(f"Missing zh-CN translation for {blind_exercise_id}")
    payload = TRANSLATIONS[blind_exercise_id]
    translated["title"] = payload["title"]
    translated["instruction_text"] = payload["instruction_text"]
    translated["expected_output"] = payload["expected_output"]
    translated["constraints_text"] = payload["constraints_text"]
    translated["test_cases_text"] = payload["test_cases_text"]
    translated["topic"] = TOPIC_TRANSLATIONS.get(row.get("topic", ""), row.get("topic", ""))
    return translated


def main() -> None:
    base_rows = read_csv_rows(STUDENT_PACKET)
    translated_rows = [translate_row(row) for row in base_rows]
    write_csv_rows(translated_rows, ZH_PACKET)

    package_manifest = read_csv_rows(MANIFEST_PATH)
    package_outputs: list[dict[str, Any]] = []
    for package_row in package_manifest:
        package_id = package_row.get("package_id", "")
        packet_path = STUDENT_PACKAGES_DIR / package_id / "student_eval_packet.curated.v1.csv"
        zh_path = STUDENT_PACKAGES_DIR / package_id / "student_eval_packet.zh-CN.curated.v1.csv"
        rows = read_csv_rows(packet_path)
        translated_package_rows = [translate_row(row) for row in rows]
        write_csv_rows(translated_package_rows, zh_path)
        package_outputs.append(
            {
                "package_id": package_id,
                "rows": len(translated_package_rows),
                "output": str(zh_path),
            }
        )

    manifest = {
        "source_packet": str(STUDENT_PACKET),
        "translated_packet": str(ZH_PACKET),
        "translated_package_count": len(package_outputs),
        "packages": package_outputs,
    }
    (AUDIT_DIR / "student_packets.zh-CN.manifest.v1.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote translated student packet -> {ZH_PACKET}")
    print(f"Wrote translated package manifest -> {AUDIT_DIR / 'student_packets.zh-CN.manifest.v1.json'}")


if __name__ == "__main__":
    main()

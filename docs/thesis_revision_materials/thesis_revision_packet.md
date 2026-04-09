# 论文修订说明

## 1. 这次必须补上的四类内容

### 1.1 模型与调用方式

当前项目中的 AI 题目不是通过网页端手工生成，而是通过本地脚本调用模型接口批量生成。根据 `scripts/02_generate_candidates.py` 的实现，生成脚本采用阿里云百炼兼容 OpenAI Chat Completions 的 HTTP API，请求地址默认为 `https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions`，通过 `Authorization: Bearer <API_KEY>` 鉴权，并在请求体中显式传入 `model`、`messages`、`temperature`、`max_tokens` 等参数。当前保留下来的运行记录 `outputs/raw_generations/generation_manifest.v1.json` 与 `outputs/raw_generations/generation_summary.v1.csv` 表明，本项目正式保留的生成记录对应的 provider 为 `bailian`，模型名为 `qwen-plus`。

### 1.2 13 道专家题来源与知识点统计

正式进入学生主分析的样本不是全部 23 对初始配对题，而是经过结构完整性筛选后的 13 对练习。论文里需要把这 13 道专家题分别来自哪个数据源、属于哪类任务、覆盖哪些知识点写清楚。可直接引用 `docs/thesis_revision_materials/expert_source_statistics.csv` 作为制表基础。

### 1.3 学生样本统计

现有数据可以明确支持以下事实：系统共为 6 个题包预生成了 60 个唯一参与编号及专属链接；最终收到 30 份提交记录；按当前分析脚本的过滤规则，剔除 3 份无效记录后，主分析纳入 27 名学生。有效样本背景分布已经整理在 `docs/thesis_revision_materials/student_profile_statistics.csv`。

### 1.4 附录中的案例题面对照

正文第 5.3 节已经讨论了 `PAIR-CURATED-MIT-01`、`PAIR-CURATED-OPT-02` 和 `PAIR-CURATED-KER-04` 三组案例，但附录里没有把这些题目本身放出来。至少应把其中两组补入附录，最好三组都补。用于附录整理的题目信息已导出到 `docs/thesis_revision_materials/case_appendix_materials.csv`。

## 2. 可直接替换到论文正文的文字

### 2.1 可替换 3.2 节末尾的段落

本研究用于正式学生评价与主分析的样本，并非全部初始生成结果，而是经过结构完整性与配对可比性筛选后的 13 对练习。对应的 13 道专家题来源覆盖教材习题、课程作业、官方教程任务和整理后的推导型练习单元，主题覆盖卷积神经网络、循环神经网络、Transformer 以及优化与训练分析四类知识主题，任务类型覆盖代码补全、模型构建、模型修改和训练分析。为保证数据来源透明，本文进一步对 13 道专家题的来源标题、来源定位信息、任务类型与主要知识点进行了汇总统计，见表 X。

### 2.2 可替换 3.3 节中“模型与调用方式”说明的段落

本研究中的人工智能练习不是通过网页端交互式生成，而是通过本地脚本调用大语言模型接口批量生成。具体而言，系统在提示构建完成后，通过 `scripts/02_generate_candidates.py` 向阿里云百炼兼容 OpenAI Chat Completions 的接口发送 HTTP POST 请求，请求地址默认为 `https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions`，并以 `Authorization: Bearer <API_KEY>` 方式完成鉴权。请求体中显式设置 `model`、`messages`、`temperature` 与 `max_tokens` 等参数。根据保留下来的生成日志与运行清单，本研究正式记录的生成模型为 `qwen-plus`，provider 为 `bailian`。因此，本文所讨论的 AI 练习属于“基于脚本调用 API 的受控生成”，而非网页端手工逐题生成。

### 2.3 可替换 3.5.2 节“问卷对象与实施方式”的段落

学生评价环节采用题包化问卷设计。系统共为 6 个题包预生成了 60 个唯一参与编号及其专属链接/二维码，用于问卷分发；最终回收 30 份已提交记录。按照当前分析流程的过滤规则，主分析中剔除了 3 名无效参与者，最终纳入 27 名学生。其中，S030 未通过注意力检验且整包作答时间低于 180 秒，S059 与 S060 未通过注意力检验。纳入主分析的 27 名学生中，本科高年级与本科低年级各 11 人，硕士研究生 4 人，博士研究生 1 人；19 人表示已学习过深度学习相关课程，8 人未学习过相关课程。样本的详细背景分布见表 Y。

## 3. 建议新增的表

### 表 X 13 道专家题来源与知识点统计表

| 编号 | 主题 | 难度 | 任务类型 | 来源标题 | 数据源定位 | 主要知识点 |
| --- | --- | --- | --- | --- | --- | --- |
| CNN-01 | CNN | intermediate | code completion | Convolution: Naive Forward Pass | Expert-Assignment Exercise；Stanford CS231n Assignment 2, Q3: Convolutional Neural Networks, Convolution: Naive Forward Pass | 卷积层前向传播实现；padding 与 stride 对输出形状的影响；NumPy 下 NCHW 张量操作 |
| KER-01 | CNN | beginner | model building | Build, train, and evaluate a simple MNIST convnet | https://keras.io/examples/vision/mnist_convnet/；Keras Code Examples / Computer Vision / Simple MNIST convnet | Keras 中紧凑 CNN 搭建；MNIST 分类训练与测试；端到端图像分类流程 |
| KER-02 | RNN | intermediate | model building | Build and train a 2-layer bidirectional LSTM on IMDB | https://keras.io/examples/nlp/bidirectional_lstm_imdb/；Keras Code Examples / NLP / Text classification / Bidirectional LSTM on IMDB | 双向 LSTM 文本分类；序列建模；Keras 中的情感分析任务 |
| KER-04 | RNN | intermediate | model building | Implement a character-level recurrent seq2seq translator | https://keras.io/examples/nlp/lstm_seq2seq/；Keras Code Examples / Machine translation / Character-level recurrent sequence-to-sequence model | 编码器-解码器框架；teacher forcing；字符级序列到序列学习；机器翻译 |
| MIT-01 | RNN | intermediate | code completion | Define the RNN model for music generation | https://raw.githubusercontent.com/MITDeepLearning/introtodeeplearning/master/lab1/PT_Part2_Music_Generation.ipynb；MIT Introduction to Deep Learning / Lab 1: Music Generation with RNNs | 循环神经网络序列生成；自回归生成；PyTorch 训练循环 |
| MIT-02 | CNN | beginner-intermediate | model building | Define and train a CNN for MNIST digit classification | https://raw.githubusercontent.com/MITDeepLearning/introtodeeplearning/master/lab2/PT_Part1_MNIST.ipynb；MIT Introduction to Deep Learning / Laboratory 2: Computer Vision / Part 1: MNIST Digit Classification | 卷积与池化；MNIST 分类；PyTorch 中 CNN 搭建与训练 |
| OPT-02 | Optimization | beginner-intermediate | training-analysis | Demonstrate overfitting | Expert-Tutorial Task；TensorFlow tutorial: Overfit and underfit > Demonstrate overfitting | 模型容量与过拟合；训练/验证损失曲线解释；二分类训练行为分析 |
| OPT-04 | Optimization | intermediate | model revision | Add weight regularization | https://www.tensorflow.org/tutorials/keras/overfit_and_underfit；TensorFlow tutorial: Overfit and underfit > Strategies to prevent overfitting > Add weight regularization | L2 正则化；过拟合缓解；正则化前后训练行为比较 |
| OPT-05 | Optimization | intermediate | model revision | Add dropout | https://www.tensorflow.org/tutorials/keras/overfit_and_underfit；TensorFlow tutorial: Overfit and underfit > Strategies to prevent overfitting > Add dropout | Dropout 正则化；泛化性能改善；训练/验证曲线比较 |
| RNN-01 | RNN | intermediate | code completion | RNN Model | Expert-Derived Exercise Unit；D2L RNN chapter / sec_rnn-scratch | 隐状态更新；RNN 前向传播；矩阵乘法与 `tanh` 激活 |
| RNN-02 | RNN | intermediate | model building | Neural Transition-Based Dependency Parsing — implement parser_model.py and run.py | Expert-Assignment Exercise；Stanford CS224N Winter 2026 Assignment 2, Part 3(e)(iii): Neural Transition-Based Dependency Parsing | 词向量查表；前馈依存句法分析器；UAS 评测；PyTorch 张量计算 |
| TRF-01 | Transformer | intermediate-advanced | code completion | Implement CausalAttention.forward | Expert-Assignment Exercise；CS224N Winter 2026 Assignment 3 > Coding a transformer from scratch > Implement CausalAttention.forward | 掩码自注意力；causal masking；多头投影与张量形状变换 |
| UVA-02 | Transformer | intermediate-advanced | code completion | Implement scaled dot-product attention and multi-head attention | https://github.com/phlippe/uvadlc_notebooks；UvA Deep Learning Tutorials / Tutorial 6: Transformers and Multi-Head Attention | scaled dot-product attention；multi-head attention；Q/K/V 张量重排；PyTorch 模块实现 |

### 表 X+1 13 道专家题总体分布

| 维度 | 类别 | 数量 |
| --- | --- | --- |
| 知识主题 | CNN | 3 |
| 知识主题 | RNN | 5 |
| 知识主题 | Transformer | 2 |
| 知识主题 | Optimization | 3 |
| 难度 | beginner | 1 |
| 难度 | beginner-intermediate | 2 |
| 难度 | intermediate | 8 |
| 难度 | intermediate-advanced | 2 |
| 任务类型 | code completion | 5 |
| 任务类型 | model building | 5 |
| 任务类型 | model revision | 2 |
| 任务类型 | training-analysis | 1 |
| 来源类型 | Expert-Tutorial Task | 9 |
| 来源类型 | Expert-Assignment Exercise | 3 |
| 来源类型 | Expert-Derived Exercise Unit | 1 |

### 表 Y 学生样本概况

| 指标 | 数值 | 说明 |
| --- | --- | --- |
| 预生成参与编号数 | 60 | 对应 6 个题包的专属链接/二维码 |
| 提交人数 | 30 | `student_analysis_master_30.csv` 中具有提交时间的唯一参与者 |
| 纳入主分析的有效人数 | 27 | 过滤条件为 `attention_check_passed=True` 且非 `participant_fast_flag_under_180s=True` |
| 剔除人数 | 3 | S030、S059、S060 |
| 平均作答时长 | 350.08 秒 | 有效样本最短 224.1 秒，最长 444.2 秒 |

### 表 Y+1 有效样本背景统计

| 统计项 | 类别 | 人数 | 占比 |
| --- | --- | --- | --- |
| 学习阶段 | 本科高年级 | 11 | 40.74% |
| 学习阶段 | 本科低年级 | 11 | 40.74% |
| 学习阶段 | 硕士研究生 | 4 | 14.81% |
| 学习阶段 | 博士研究生 | 1 | 3.70% |
| 编程背景 | 几乎没有编程基础 | 12 | 44.44% |
| 编程背景 | 学过机器学习或深度学习基础 | 7 | 25.93% |
| 编程背景 | 学过基础编程 | 6 | 22.22% |
| 编程背景 | 有较多相关课程或项目经验 | 2 | 7.41% |
| Python 熟悉度 | 一般 | 12 | 44.44% |
| Python 熟悉度 | 比较熟悉 | 8 | 29.63% |
| Python 熟悉度 | 非常熟悉 | 4 | 14.81% |
| Python 熟悉度 | 不太熟悉 | 3 | 11.11% |
| 深度学习框架熟悉度 | 一般 | 8 | 29.63% |
| 深度学习框架熟悉度 | 比较熟悉 | 7 | 25.93% |
| 深度学习框架熟悉度 | 不太熟悉 | 5 | 18.52% |
| 深度学习框架熟悉度 | 非常熟悉 | 4 | 14.81% |
| 深度学习框架熟悉度 | 非常不熟悉 | 3 | 11.11% |
| 是否学过深度学习课程 | 是 | 19 | 70.37% |
| 是否学过深度学习课程 | 否 | 8 | 29.63% |

## 4. 附录里的题目建议怎么放

最稳妥的格式不是做复杂矩阵表，而是每组案例单独成一个小节，按“专家题在前，AI 生成题在后”直接粘贴。推荐结构如下：

### 附录 C 案例题面对照（示例格式）

#### C.1 `PAIR-CURATED-MIT-01`

1. 专家题  
题目标题：Define the RNN model for music generation  
来源：MIT Introduction to Deep Learning / Lab 1: Music Generation with RNNs  
下面直接粘贴完整题干；如果起始代码较长，单独放一个代码块。

2. AI 生成题  
题目标题：对应 AI 题标题  
模型信息：`qwen-plus`，通过 `bailian` 接口生成  
下面直接粘贴完整题干；如有起始代码，同样单独放代码块。

#### C.2 `PAIR-CURATED-OPT-02`

1. 专家题  
题目标题：Demonstrate overfitting  
来源：TensorFlow tutorial: Overfit and underfit

2. AI 生成题  
题目标题：对应 AI 题标题  
模型信息：`qwen-plus`，通过 `bailian` 接口生成

#### C.3 `PAIR-CURATED-KER-04`

1. 专家题  
题目标题：Implement a character-level recurrent seq2seq translator  
来源：Keras Code Examples / Machine translation

2. AI 生成题  
题目标题：对应 AI 题标题  
模型信息：`qwen-plus`，通过 `bailian` 接口生成

## 5. 你还需要手工补一句的地方

下面这三项，当前数据库和代码仓库里没有足够证据，不能硬编：

1. 学生具体从哪里招募，例如某门课、某个班级、微信群、线下课堂等。
2. 是否向参与者支付报酬或提供课程奖励。
3. “学习编程平均时间”这一指标。

如果老师坚持要“平均学习编程时间”，你需要从线下招募记录补回原始信息；否则建议把这一项改写为“编程背景分类统计”，因为这是当前数据中真实存在、且可以被验证的字段。

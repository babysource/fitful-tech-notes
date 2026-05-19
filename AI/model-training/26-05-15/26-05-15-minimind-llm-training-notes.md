# 26-05-15 MiniMind / LLM 工程化训练学习笔记

> 学习目标：通过 MiniMind 项目理解从零训练小型语言模型的工程流程，并用 MicroGPT 的极简原理辅助理解。  
> 核心主线：tokenizer → dataset → model → pretrain → full_sft → LoRA → eval → convert/publish。

---

## 0. 学习总览

本次学习围绕两个项目展开：

- `minimind`：文本大语言模型训练工程。
- `minimind-o`：基于 MiniMind 的多模态/语音/视觉 Omni 模型。

当前重点是 `minimind`，因为它更适合从头理解 LLM 训练工程。

### MiniMind 和 MicroGPT 的关系

| 项目 | 作用 | 适合学习什么 |
|---|---|---|
| MicroGPT | 极简 GPT 教学代码 | 理解 GPT 的最小原理 |
| MiniMind | 工程化小模型训练项目 | 理解真实训练脚本、数据、权重、SFT、LoRA、发布 |

可以这样理解：

```text
MicroGPT = 透明教学模型
MiniMind = 工程化训练项目
```

两者的核心训练逻辑是一致的：

```python
for input_ids, labels in dataloader:
    result = model(input_ids, labels=labels)
    loss = result.loss
    loss.backward()
    optimizer.step()
    optimizer.zero_grad()
```

MiniMind 只是增加了更多工程能力：

```text
Dataset / DataLoader
混合精度
梯度累积
梯度裁剪
学习率调度
checkpoint
多卡训练
SFT
LoRA
DPO / RL
Transformers 导出
```

---

## 1. MiniMind 训练流程总图

MiniMind 的基本训练链路是：

```text
准备 tokenizer
↓
准备 pretrain 数据
↓
train_pretrain.py 预训练
↓
得到 out/pretrain_768.pth
↓
准备 sft 数据
↓
train_full_sft.py 指令微调
↓
得到 out/full_sft_768.pth
↓
eval_llm.py 简单推理测试
↓
convert_model.py 转成 Transformers 发布格式
```

如果继续做领域适配：

```text
full_sft 基础模型
↓
train_lora.py
↓
得到 LoRA 权重
↓
推理时 base + LoRA，或合并成完整模型
```

---

## 2. tokenizer：文本和 token id 之间的字典

### 2.1 tokenizer 是什么？

专业术语：

```text
tokenizer
vocabulary / vocab
BPE
ByteLevel
```

通俗解释：

```text
tokenizer 是文字和数字之间的翻译器。
```

模型不能直接理解中文、英文，它只能处理数字。tokenizer 负责：

```text
文本 -> token id
模型输出 token id -> 文本
```

例如：

```text
你好
↓
[1968]
↓
你好
```

### 2.2 MiniMind tokenizer 从哪里加载？

训练时在 `trainer_utils.py` 中加载：

```python
tokenizer = AutoTokenizer.from_pretrained('../model')
```

也就是说 MiniMind 默认使用：

```text
minimind/model/tokenizer.json
minimind/model/tokenizer_config.json
```

### 2.3 tokenizer 字典是怎么来的？

MiniMind 自带 tokenizer，同时提供学习用脚本：

```text
trainer/train_tokenizer.py
```

核心逻辑：

```python
tokenizer = Tokenizer(models.BPE())
tokenizer.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
trainer = trainers.BpeTrainer(vocab_size=6400, special_tokens=...)
tokenizer.train_from_iterator(texts, trainer=trainer)
```

也就是：

```text
BPE + ByteLevel
```

### 2.4 BPE 是什么？

专业术语：

```text
Byte Pair Encoding
字节对编码
```

通俗解释：

```text
经常一起出现的片段，会被合并成一个 token。
```

例如：

```text
人 / 工 / 智 / 能
↓
人工 / 智能
↓
人工智能
```

如果某个词很少出现，比如“贾诩”，可能就会被拆得比较碎。

### 2.5 ByteLevel 为什么中文看起来像乱码？

MiniMind 的 tokenizer 使用 ByteLevel，所以词表里中文可能显示成：

```text
ä½łå¥½
äººå·¥æĻºèĥ½
```

这不是模型意义上的乱码，而是 UTF-8 字节映射后的可见形式。

验证 tokenizer 是否支持中文，不要直接看 `tokenizer.json` 中是否有原始中文，而要看：

```python
ids = tokenizer.encode('你好')
text = tokenizer.decode(ids)
```

只要能 decode 回原文，就说明支持。

### 2.6 tokenizer 是否包含知识？

不包含。

tokenizer 只负责编码，不负责理解。

```text
tokenizer = 字典 / 编码系统
模型权重 = 大脑 / 知识与能力
```

即使 tokenizer 能编码“量子色动力学”，也不代表模型懂它。

### 2.7 推理时是否必须带 tokenizer？

必须。

推理流程是：

```text
用户输入文字
↓
tokenizer.encode
↓
input_ids
↓
model.generate
↓
生成 token id
↓
tokenizer.decode
↓
输出文字
```

训练、SFT、LoRA、推理必须使用同一套 tokenizer：

```text
pretrain tokenizer = full_sft tokenizer = LoRA tokenizer = inference tokenizer
```

否则 token id 的含义会错乱，甚至出现 embedding 越界。

---

## 3. 词表大小与模型参数量

### 3.1 tokenizer 没有“维度”，准确说是 vocab_size

- `vocab_size`：词表大小，有多少个 token。
- `hidden_size`：每个 token 在模型内部表示成多少维向量。

MiniMind 默认：

```text
vocab_size = 6400
hidden_size = 768
```

### 3.2 词表影响哪些参数？

主要影响：

```text
Embedding 层
lm_head 输出层
```

MiniMind 中：

```python
self.embed_tokens = nn.Embedding(config.vocab_size, config.hidden_size)
self.lm_head = nn.Linear(config.hidden_size, config.vocab_size, bias=False)
```

如果 embedding 和 lm_head 权重共享：

```text
词表相关参数 ≈ vocab_size × hidden_size
```

如果不共享：

```text
词表相关参数 ≈ 2 × vocab_size × hidden_size
```

### 3.3 MiniMind 与 Qwen 词表对比

| 模型 | 词表大小 | 影响 |
|---|---:|---|
| MiniMind | 6400 | 小模型友好，参数少，但压缩率一般 |
| Qwen3.5/3.6 | 约 248k | 多语言/代码更友好，但 embedding/lm_head 很大 |

如果 MiniMind 直接使用 Qwen 的 248k tokenizer：

```text
248000 × 768 ≈ 190M 参数
```

仅 embedding 就会非常大，不适合 MiniMind 这种小模型。

### 3.4 从头训练能否使用开源 tokenizer？

可以，但必须从零训练，并设置：

```python
vocab_size = len(tokenizer)
```

不能拿 MiniMind 官方权重直接换 Qwen tokenizer。

---

## 4. Dataset：数据如何变成 input_ids 和 labels

MiniMind 数据文件：

```text
pretrain_t2t_mini.jsonl
sft_t2t_mini.jsonl
```

### 4.1 JSONL 是什么？

JSONL 是：

```text
一行一个 JSON 对象
```

例如：

```jsonl
{"text": "人工智能正在改变世界。"}
{"text": "Transformer 是现代大语言模型的重要结构。"}
```

### 4.2 PretrainDataset

对应文件：

```text
dataset/lm_dataset.py
```

核心代码：

```python
tokens = tokenizer(sample['text'], add_special_tokens=False, max_length=max_length-2, truncation=True).input_ids
tokens = [bos_token_id] + tokens + [eos_token_id]
input_ids = tokens + [pad_token_id] * (max_length - len(tokens))
labels = input_ids.clone()
labels[input_ids == pad_token_id] = -100
```

预训练数据格式：

```jsonl
{"text": "如何才能摆脱拖延症？治愈拖延症并不容易..."}
```

训练目标：

```text
预测下一个 token
```

### 4.3 input_ids 和 labels

- `input_ids`：模型输入的 token id。
- `labels`：模型要预测的正确答案。
- `-100`：表示这个位置不参与 loss 计算。

例如：

```text
input_ids = [BOS, 我, 喜欢, AI, EOS, PAD, PAD]
labels    = [BOS, 我, 喜欢, AI, EOS, -100, -100]
```

模型内部会 shift：

```text
看到 BOS，预测 我
看到 我，预测 喜欢
看到 喜欢，预测 AI
看到 AI，预测 EOS
```

### 4.4 SFTDataset

SFT 数据格式：

```jsonl
{"conversations": [{"role": "user", "content": "你好"}, {"role": "assistant", "content": "你好，有什么可以帮你？"}]}
```

SFTDataset 会使用：

```python
tokenizer.apply_chat_template(...)
```

把对话转换成：

```text
<|im_start|>user
你好
<|im_end|>
<|im_start|>assistant
你好，有什么可以帮你？
<|im_end|>
```

SFT 的关键点：

```text
只对 assistant 回答部分计算 loss。
user 部分作为条件，不参与 loss。
```

---

## 5. 模型结构：input_ids 如何变成 logits 和 loss

MiniMind 主模型文件：

```text
model/model_minimind.py
```

### 5.1 整体结构

```text
MiniMindForCausalLM
└── MiniMindModel
    ├── Embedding
    ├── MiniMindBlock × N
    │   ├── Attention
    │   └── FeedForward / MoEFeedForward
    └── RMSNorm
└── lm_head
```

### 5.2 Embedding

```python
self.embed_tokens = nn.Embedding(vocab_size, hidden_size)
```

通俗解释：

```text
把 token id 变成向量。
```

例如：

```text
321 -> [0.12, -0.03, ..., 0.55]
```

### 5.3 Transformer Block

一个 block 包含：

```text
Attention：让 token 看上下文
MLP：让每个 token 自己加工信息
RMSNorm：稳定数值
Residual：保留原信息并叠加新信息
```

通俗类比：

```text
Attention = 开会交流
MLP = 回座位自己消化
```

### 5.4 Attention

标准 attention 公式：

```text
Attention(Q, K, V) = softmax(QKᵀ / sqrt(d))V
```

通俗解释：

```text
每个 token 判断自己应该关注前文哪些 token。
```

MiniMind 使用 causal attention：

```text
只能看当前和前面的 token，不能偷看未来。
```

### 5.5 MLP / FeedForward

MiniMind 使用 SwiGLU 风格：

```python
down_proj(act(gate_proj(x)) * up_proj(x))
```

作用：

```text
对每个 token 的表示进一步加工。
```

### 5.6 logits

`lm_head` 把 hidden_states 转成词表大小的分数：

```text
hidden_states: [batch, seq_len, hidden_size]
↓
lm_head
↓
logits: [batch, seq_len, vocab_size]
```

`logits` 是模型给每个候选 token 的原始分数，不是概率。

### 5.7 loss

MiniMind 中：

```python
x = logits[..., :-1, :]
y = labels[..., 1:]
loss = F.cross_entropy(x.view(-1, x.size(-1)), y.view(-1), ignore_index=-100)
```

也就是：

```text
当前位置预测下一个 token。
```

---

## 6. train_pretrain.py：预训练工程

核心流程：

```text
读取参数
初始化分布式/随机种子
创建 MiniMindConfig
加载 model + tokenizer
创建 PretrainDataset
创建 DataLoader
创建 optimizer
循环训练
保存权重和 checkpoint
```

### 6.1 关键代码

创建模型和 tokenizer：

```python
model, tokenizer = init_model(lm_config, args.from_weight, device=args.device)
```

创建数据集：

```python
train_ds = PretrainDataset(args.data_path, tokenizer, max_length=args.max_seq_len)
```

训练：

```python
res = model(input_ids, labels=labels)
loss = res.loss + res.aux_loss
loss.backward()
optimizer.step()
```

### 6.2 工程术语

| 术语 | 通俗解释 |
|---|---|
| epoch | 数据集完整训练一遍 |
| batch_size | 每次喂给模型多少条样本 |
| step | 训练一个 batch 叫一步 |
| learning_rate | 参数每次改动幅度 |
| optimizer | 根据梯度更新参数的工具 |
| gradient | 参数该往哪个方向改 |
| backward | 反向传播，计算梯度 |
| grad_clip | 防止一次改得太猛 |
| accumulation_steps | 多批梯度攒起来再更新 |
| checkpoint | 训练存档，用于中断恢复 |

---

## 7. full_sft：全量监督微调

### 7.1 full_sft 是什么？

```text
full_sft = 全量参数 SFT
```

作用：

```text
把预训练模型从“会续写文本”训练成“会按用户指令回答”。
```

训练链路：

```text
pretrain_768.pth
↓
train_full_sft.py
↓
full_sft_768.pth
```

### 7.2 和 pretrain 的区别

| 项目 | pretrain | full_sft |
|---|---|---|
| 数据 | `{"text": ...}` | `{"conversations": [...]}` |
| Dataset | PretrainDataset | SFTDataset |
| 目标 | 学语言 | 学对话/指令 |
| 默认 from_weight | none | pretrain |
| 默认 save_weight | pretrain | full_sft |
| 学习率 | 较大 | 较小 |

### 7.3 full_sft 是否改变参数数量？

不会。

它只改变参数值，不改变：

```text
层数
hidden_size
vocab_size
参数数量
```

### 7.4 为什么 full_sft 可能导致模型坍塌？

因为它会更新整个模型参数。

如果 SFT 数据：

```text
少
差
重复
分布窄
训练太久
学习率太大
```

模型可能出现：

```text
灾难性遗忘
过拟合
模式坍塌
通用能力下降
重复输出
答非所问
```

---

## 8. LoRA：低成本适配

### 8.1 LoRA 是什么？

专业术语：

```text
Low-Rank Adaptation
低秩适配
```

通俗解释：

```text
冻结原模型，只训练额外的小矩阵插件。
```

### 8.2 MiniMind LoRA 实现

`model_lora.py` 中：

```python
self.A = nn.Linear(in_features, rank, bias=False)
self.B = nn.Linear(rank, out_features, bias=False)
```

LoRA 增量：

```text
ΔW = B × A
W' = W + ΔW
```

### 8.3 LoRA 能否学新知识？

能学少量稳定知识，但不适合大规模知识注入。

适合：

```text
风格
格式
角色设定
领域表达
特定任务习惯
```

不适合：

```text
大量公司知识库
实时知识
必须精确引用的事实
```

大量知识更适合 RAG 或工具调用。

---

## 9. 推理生成：eval_llm.py 和 generate

### 9.1 eval_llm.py 是什么？

它是简单推理测试脚本，类似：

```text
smoke test / 冒烟测试
```

作用：

```text
加载模型
输入 prompt
调用 generate
观察模型是否正常回答
```

它不是完整 benchmark。

### 9.2 generate 如何生成？

生成流程：

```text
prompt
↓
tokenizer.encode
↓
model.forward
↓
取最后一个 token 的 logits
↓
temperature / top_k / top_p 处理
↓
采样 next_token
↓
拼回 input_ids
↓
循环直到 EOS
```

### 9.3 temperature

代码中是：

```python
logits / temperature
```

不是乘以 temperature。

```text
temperature 越低，越保守
temperature 越高，越随机
```

严格 `temperature=0` 会除以 0，不应直接使用。想要完全不随机，应使用：

```text
do_sample=False
```

也就是 greedy decoding。

---

## 10. 模型评估与 benchmark

### 10.1 loss 不等于交付能力

loss 下降只说明：

```text
模型更拟合训练数据。
```

但不代表：

```text
真实业务能力一定更强。
```

### 10.2 MiniMind 自带评估能力

包括：

```text
训练 loss 日志
eval_llm.py 简单人工测试
eval_toolcall.py 工具调用测试
wandb/swanlab 曲线
```

但没有完整企业级 benchmark。

### 10.3 公司模型为什么需要 benchmark？

因为交付不能靠感觉。

需要评估：

```text
准确性
有用性
安全性
格式遵循
业务流程正确性
鲁棒性
响应速度
成本
```

企业常见评估链路：

```text
训练 loss
↓
验证集 loss
↓
离线 benchmark
↓
业务测试集
↓
安全测试集
↓
人工评审
↓
灰度发布
↓
线上监控
```

### 10.4 人工评审

人工评审是让人按照标准检查模型回答：

```text
是否准确
是否相关
是否完整
是否安全
是否符合业务口吻
是否可以交付
```

---

## 11. checkpoint 与 .pth

### 11.1 .pth 是什么？

`.pth` 是 PyTorch 权重文件。

```text
pretrain_768.pth
full_sft_768.pth
```

通常保存：

```text
模型参数 state_dict
```

### 11.2 checkpoint 是什么？

checkpoint 是训练存档，通常保存：

```text
model
optimizer
scaler
epoch
step
wandb_id
```

区别：

```text
.pth = 成品权重
checkpoint = 训练存档
```

### 11.3 为什么 checkpoint 占空间？

因为 AdamW optimizer 会保存：

```text
参数
一阶动量 m
二阶动量 v
```

所以训练 checkpoint 往往比推理权重大很多。

---

## 12. 模型发布与转换

### 12.1 MiniMind 训练产物

训练时得到：

```text
out/full_sft_768.pth
```

但发布通常不是直接发 `.pth`，而是转成 Transformers 格式目录。

### 12.2 convert_model.py

MiniMind 使用：

```text
scripts/convert_model.py
```

将 `.pth` 转成 Transformers 格式。

核心逻辑：

```python
state_dict = torch.load(torch_path)
qwen_model.load_state_dict(state_dict)
qwen_model.save_pretrained(transformers_path)
tokenizer.save_pretrained(transformers_path)
```

### 12.3 发布目录

发布后通常是：

```text
minimind-3/
├── config.json
├── generation_config.json
├── pytorch_model.bin 或 model.safetensors
├── tokenizer.json
├── tokenizer_config.json
├── special_tokens_map.json
└── model_minimind.py 可选
```

### 12.4 config.json

`config.json` 是模型结构说明书。

不同模型家族字段不同。

例如 Qwen3.5 有：

```text
text_config
vision_config
layer_types
linear_attention
full_attention
mrope
```

MiniMind 更简单：

```text
hidden_size
num_hidden_layers
vocab_size
num_attention_heads
num_key_value_heads
intermediate_size
rope_theta
use_moe
```

---

## 13. 模型架构设计与参数量

### 13.1 模型参数量是训练前设计好的

```text
训练改变参数值，不改变参数数量。
```

参数量由这些决定：

```text
vocab_size
hidden_size
num_hidden_layers
intermediate_size
attention heads
是否 MoE
是否共享 embedding
```

### 13.2 基本参数计算

Embedding：

```text
V × H
```

Full Attention：

```text
约 4H²
```

GQA Attention：

```text
H×H + H×KV×D + H×KV×D + H×H
```

SwiGLU MLP：

```text
3 × H × I
```

一个 Dense Block：

```text
Attention + MLP + Norm
```

MoE Block 总参数：

```text
Attention + E × MLP + Router + Norm
```

MoE 激活参数：

```text
Attention + K × MLP + Norm
```

### 13.3 MiniMind 参数量直觉

默认：

```text
H = 768
L = 8
V = 6400
```

大致量级：

```text
每层约 7M+
8 层约 59M
embedding 约 4.9M
总计约 64M
```

---

## 14. layer_types 与不同类型层

Qwen3.5 config 中有：

```json
"layer_types": ["linear_attention", "linear_attention", "linear_attention", "full_attention", ...]
```

含义：

```text
每一层使用哪种 block / attention 算法。
```

- `full_attention`：标准 self-attention，表达强，但长文本成本高。
- `linear_attention`：线性注意力，适合长上下文，计算更省。

MiniMind 没有类似逐层 `layer_types` 设计。MiniMind 每层都是统一的：

```text
MiniMindBlock = Attention + MLP/MoE + RMSNorm + Residual
```

不同类型层本质是：

```text
forward 计算方式不同
参数结构不同
计算复杂度不同
适用场景不同
```

---

## 15. 训练是不是一层一层进行？

不是。

LLM 通常是端到端训练：

```text
所有层一起 forward
loss 从最后算出
backward 从后往前传播梯度
optimizer 更新所有可训练参数
```

forward 时数据确实一层一层流过；

但训练不是单独训练第 1 层、第 2 层，而是整个模型一起训练。

---

## 16. 大模型、小模型与边缘模型设计

### 16.1 大模型和小模型关注点不同

小模型：

```text
有限容量里塞进尽可能多的有效能力。
```

关注：

```text
小词表
紧凑层数
高质量数据
蒸馏
LoRA
量化
端侧部署
```

大模型：

```text
大规模参数、数据、算力下如何稳定高效训练和部署。
```

关注：

```text
分布式训练
数据管线
checkpoint
并行策略
推理吞吐
成本控制
```

### 16.2 边缘小模型

边缘小模型要精打细算：

```text
词表大小
hidden_size
层数
上下文长度
量化
任务范围
数据质量
```

核心思想：

```text
用最少参数和计算，覆盖最明确的任务。
```

---

## 17. 量化

量化通常不改变参数个数，而是改变每个参数的存储精度。

```text
FP32：4 bytes
FP16：2 bytes
INT8：1 byte
INT4：0.5 byte
```

例如：

```text
8B FP16 ≈ 16GB
8B INT4 ≈ 4GB
```

参数数量仍然是 8B，只是文件大小和显存占用变小。

---

## 18. 当前阶段建议学习路线

建议继续按这个顺序学习：

```text
1. 跑通 MiniMind 官方 pretrain mini
2. 跑通 full_sft mini
3. 用 eval_llm.py 做人工测试
4. 观察 loss 和输出变化
5. 看 train_lora.py 和 model_lora.py
6. 尝试做一个自己的小 eval_prompts.jsonl
7. 再研究 tokenizer 替换、模型结构改动、benchmark
```

不要急着上来就：

```text
换 Qwen tokenizer
改复杂 layer_types
训练大模型
做 RL
```

先把官方链路跑通最重要。

---

## 19. 核心记忆卡片

### 卡片 1：tokenizer

```text
tokenizer 是文字和 token id 的翻译器，不是知识库。
```

### 卡片 2：pretrain

```text
pretrain 学语言规律和基础知识，目标是 next-token prediction。
```

### 卡片 3：full_sft

```text
full_sft 用对话数据全量微调模型，让它学会按指令回答。
```

### 卡片 4：LoRA

```text
LoRA 是低成本适配插件，适合风格/格式/领域表达，不适合大规模知识库。
```

### 卡片 5：loss

```text
loss 是训练指标，不等于真实交付能力。
```

### 卡片 6：benchmark

```text
benchmark 是交付质量评估，不是训练日志。
```

### 卡片 7：参数量

```text
参数量训练前由架构决定，训练只改变参数值。
```

### 卡片 8：量化

```text
量化不减少参数个数，只减少每个参数占用的 bit。
```

### 卡片 9：checkpoint

```text
checkpoint 是训练存档，.pth 通常是模型权重。
```

### 卡片 10：层类型

```text
不同 layer_types 表示不同 block 算法，例如 full_attention 和 linear_attention。
```

---

## 20. 自测题

1. tokenizer 是否包含模型知识？为什么？
2. 为什么 full_sft 不能换 tokenizer？
3. `input_ids` 和 `labels` 有什么区别？
4. 为什么 SFT 通常只对 assistant 回答部分计算 loss？
5. logits 是概率吗？如果不是，它是什么？
6. `.pth` 和 checkpoint 有什么区别？
7. full_sft 会改变模型参数数量吗？
8. LoRA 更适合学知识还是学风格/格式？
9. 为什么大词表不适合很小的模型？
10. MiniMind 为什么没有 Qwen3.5 那样的 `layer_types`？
11. 训练是逐层单独训练吗？
12. 为什么企业模型交付需要 benchmark？

---

## 21. 一句话总总结

MiniMind 是一个适合学习 LLM 工程化训练的小型项目；它把 MicroGPT 的极简训练原理扩展成真实工程链路，包括 tokenizer、dataset、model、pretrain、SFT、LoRA、eval、checkpoint 和模型发布。理解它之后，再看 Qwen、LLaMA 等大模型，会发现核心原理相同，但大模型的复杂度主要来自规模、架构变体、数据治理和工程系统。

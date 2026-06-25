# Transformer 知识点与 Agent 开发指南

> 目标：用最短时间掌握 Agent 开发面试中所需的 Transformer 知识
> 定位：作为 `docs/agent-interview-prep.md` 的技术基础补充

---

## 目录

- [一、Attention 机制（最高频）](#一attention-机制最高频)
- [二、Multi-Head Attention](#二multi-head-attention)
- [三、Transformer 整体架构](#三transformer-整体架构)
- [四、Embedding 与位置编码](#四embedding-与位置编码)
- [五、Tokenization](#五tokenization)
- [六、自回归解码与采样策略](#六自回归解码与采样策略)
- [七、分阶段面试问答](#七分阶段面试问答)
- [八、Agent 开发高频面试题](#八agent-开发高频面试题)
- [九、手撕代码](#九手撕代码)
- [十、快速记忆卡](#十快速记忆卡)

---

## 一、Attention 机制（最高频）

### 核心公式

```
Attention(Q, K, V) = softmax(Q × K^T / √d_k) × V
```

### 四个关键角色

| 角色 | 符号 | 维度 | 通俗理解 |
|------|------|------|----------|
| **Query** | Q | (seq_len, d_k) | 当前 token 想"问"什么 |
| **Key** | K | (seq_len, d_k) | 其他 token 能"回答"什么 |
| **Value** | V | (seq_len, d_v) | 其他 token 的"实际内容" |
| **d_k** | 缩放因子 | 标量 | 防止 softmax 梯度消失 |

### 计算流程（4 步）

```
输入序列 [我, 爱, 你]
         │
         ▼
┌─────────────────────┐
│  1. 每个 token → QKV │  线性变换（3 个权重矩阵）
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  2. Q × K^T         │  得到注意力分数矩阵 (seq_len × seq_len)
│     ÷ √d_k          │  缩放防止 softmax 饱和
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  3. softmax(行)      │  每行归一化，权重之和 = 1
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  4. × V (加权求和)   │  用权重融合所有位置的信息
└─────────┬───────────┘
          │
          ▼
   输出: 融合了上下文的"我"的表示
```

### 直观数值示例

假设序列 `[我, 爱, 你]`，计算"我"位置的 Attention 输出：

```
Step 1: Q_我 × [K_我, K_爱, K_你] = [0.8, 0.4, 0.5]  原始分数
Step 2: ÷ √64 (假设 d_k=64)     → [0.10, 0.05, 0.06]  缩放后
Step 3: softmax                  → [0.35, 0.30, 0.35]  权重
Step 4: 加权求和                 → 0.35×V_我 + 0.30×V_爱 + 0.35×V_你
```

### 关键问题：为什么除以 √d_k？

- Q×K^T 的结果是 d_k 个独立随机变量的和，方差 = d_k
- d_k 越大，方差越大，softmax 的分布越极端（接近 one-hot）
- one-hot 意味着梯度几乎为 0，模型学不动
- 除以 √d_k 把方差拉回 1，保持 softmax 的"软"特性

---

## 二、Multi-Head Attention

### 为什么需要多个 Head？

一个 Attention 只能学一种分布模式，多个 head 可以并行学不同的模式：

```
Head 1: 关注语法关系     → "我" → "爱"（主谓关系）
Head 2: 关注语义相似度   → "爱" → "喜欢"（近义词）
Head 3: 关注位置距离     → 相邻位置的关联
Head 4: 关注指代关系     → "他" → "张三"（共指消解）
```

### 结构图

```
输入
 │
 ├──→ Head 1: Attention(Q₁,K₁,V₁) ──┐
 ├──→ Head 2: Attention(Q₂,K₂,V₂) ──┤
 ├──→ Head 3: Attention(Q₃,K₃,V₃) ──┼──→ Concat ──→ Linear ──→ 输出
 │              ...                  │
 └──→ Head h: Attention(Qₕ,Kₕ,Vₕ) ──┘
```

### 实现要点

```python
# d_model = 512, num_heads = 8 → d_k = 64
# 每个 head 独立算 64 维的 Attention
# 8 个结果拼成 512 维，再线性投影回 512 维

d_model = 512
num_heads = 8
d_k = d_model // num_heads  # = 64

# 每个 head 的参数量: 3 × d_model × d_k = 3 × 512 × 64
# 8 个头总参数量: 8 × 3 × 512 × 64 = 786,432
# 单头 d_model→d_model: 3 × 512 × 512 = 786,432
# 参数量相同，但表达能力更强（学到不同的分布）
```

---

## 三、Transformer 整体架构

### 架构总览（Decoder-only = GPT 系列）

```
输入: "中国的首都是"
         │
         ▼
┌──────────────────────┐
│   Token Embedding    │  词 → 向量
│   + Position Encoding│  注入位置信息
└──────────┬───────────┘
           │
┌──────────▼───────────┐
│   Masked Multi-Head   │  ← 核心！只能看左边
│   Self-Attention      │     保证自回归性
└──────────┬───────────┘
           │
┌──────────▼───────────┐
│   Add & Norm          │  残差连接 + LayerNorm
└──────────┬───────────┘
           │
┌──────────▼───────────┐
│   Feed Forward        │  两层线性 + ReLU/GELU
│   (FFN)               │  每个位置独立计算
└──────────┬───────────┘
           │
┌──────────▼───────────┐
│   Add & Norm          │  又一个残差 + 归一化
└──────────┬───────────┘
           │
     ┌─────┴─────┐
     │  × N 层    │  ← 堆叠多层（如 12/24/32 层）
     └───────────┘
           │
┌──────────▼───────────┐
│   Linear + Softmax    │  预测下一个 token
└──────────┬───────────┘
           │
       "北" (输出)
```

### Encoder vs Decoder

| 特性 | Encoder（BERT） | Decoder（GPT） |
|------|-----------------|----------------|
| Attention | 双向（看到全部） | 单向（只看左侧） |
| 任务 | 理解、分类、Embedding | 生成 |
| 对 Agent 的意义 | Embedding 模型/RAG 向量化 | 你用的 LLM 本身 |
| 代表模型 | BERT, BGE, text-embedding | GPT-4, Claude, LLaMA |

**现状**：Decoder-only 是绝对主流。Agent 开发主要和 Decoder-only 模型打交道。

### 各组件的作用速记

| 组件 | 一句话 | 为什么重要 |
|------|--------|------------|
| **Self-Attention** | 每个位置看所有位置 | 解决长距离依赖 |
| **Masked** | 只能看左边，不能看未来 | 保证自回归 |
| **FFN** | 每个位置做非线性变换 | 增加表达能力 |
| **残差连接** | 输出 = 输入 + 子层输出 | 解决深层梯度消失 |
| **LayerNorm** | 对每个样本做归一化 | 训练稳定 |
| **位置编码** | 给序列注入位置信息 | Attention 是位置无关的 |

---

## 四、Embedding 与位置编码

### Embedding 的本质

```
离散符号 → 稠密向量

"猫"     → [0.23, -0.45, 0.12, ..., 0.67]   (d_model=768)
"狗"     → [0.20, -0.42, 0.15, ..., 0.65]   (语义相近 → 向量距离近)
"苹果"   → [0.51, 0.23, -0.34, ..., 0.12]   (语义不同 → 向量距离远)
```

### 为什么需要位置编码？

Attention 是"集合"操作，不是"序列"操作——交换两个 token 的位置，Attention 结果不变。所以需要注入位置信息。

### Sinusoidal 位置编码（原始 Transformer）

```python
PE(pos, 2i)   = sin(pos / 10000^(2i/d_model))   # 偶数维度
PE(pos, 2i+1) = cos(pos / 10000^(2i/d_model))   # 奇数维度
```

特点：
- 每个维度有不同的周期（从 2π 到 10000×2π）
- 不需要学习
- 理论上可外推到更长序列（但实际效果有限）

### RoPE（当代主流）

**应用**：LLaMA、ChatGLM、Qwen、Yi 等几乎所有开源模型。

核心思路：**旋转 Q 和 K 向量**，旋转角度 = 位置 × 预设频率。

```
Q'_pos = R(θ×pos) × Q_pos    # 旋转 Q
K'_pos = R(θ×pos) × K_pos    # 旋转 K

Q'_i × K'_j = Q_i × R(θ×(j-i)) × K_j  # 结果只和相对距离有关！
```

优点：
- 天然表达相对位置（Q_i×K_j 只取决于 i-j 的相对距离）
- 外推能力更强
- 不影响 Attention 计算效率

### 对 Agent 开发的启示

- Embedding 模型本身就是一个 Transformer（一般是 BERT-style encoder）
- 选择 Embedding 模型时关注：维度（越低越快）、最大长度（需匹配 chunk 大小）、语言支持

---

## 五、Tokenization

### BPE（Byte-Pair Encoding）核心思想

```
训练阶段:
1. 把所有文本拆成单字符
2. 统计最常出现的相邻字符对
3. 合并成新 token
4. 重复直到词表达到目标大小（如 50k）

推理阶段:
用学到的词表，从长到短匹配输入文本
```

### 中英文 Token 差异

```
英文: "I love programming" → ["I", "love", "programming"] → 3 tokens
英文: "pneumonoultramicroscopicsilicovolcanoconiosis"
     → 可能拆成 5-6 个 subword tokens

中文: "我爱你"                → ["我爱你"] 或 ["我", "爱你"] → 1-3 tokens
中文: "今天天气真好啊"        → 3-5 tokens（看分词器）
中文: "在哪儿啊"              → 1-2 tokens
```

**经验数据（cl100k_base）**：
- 英文平均 ≈ 1 token / 4 字符
- 中文平均 ≈ 1 token / 1.5-2 字符
- 中文比英文多占约 2-3 倍 token

### 对 Agent 开发的影响

- **Prompt 设计**：中文 prompt 占用更多 token，需更精炼
- **上下文窗口**：同样 128K 窗口，中文能容纳的内容更少
- **成本控制**：token=钱，中文场景成本是英文的 2-3 倍
- **Chunk 策略**：RAG 分块时，中文 chunk 大小需按 token 而非字符数计算

### tiktoken 使用

```python
import tiktoken

# 获取编码器
enc = tiktoken.encoding_for_model("gpt-4")  # cl100k_base

# 编码 → token id 列表
tokens = enc.encode("你好世界")
# [30266, 17793, 23397] ← 每个 id 对应词表中的一个 token

# 解码 → 还原文本
text = enc.decode(tokens)  # "你好世界"

# 统计 token 数
def count_tokens(text: str, model: str = "gpt-4") -> int:
    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(text))
```

---

## 六、自回归解码与采样策略

### 自回归解码

```
LLM 生成文本的方式：一次一个 token，把新 token 拼回输入继续生成

输入: "中国的首都是"
         │
         ▼
LLM 计算: P(下一个 token | "中国的首都是")
         │
         ▼
   P(北) = 0.60   ← 最高
   P(上) = 0.20
   P(东) = 0.10
   P(成) = 0.05
   ...
         │
         ▼
   选择"北" → 输出
   输入变成 "中国的首都是北"
         │
         ▼
   LLM 计算: P(下一个 token | "中国的首都是北")
         │
         ▼
   P(京) = 0.85   ← 最高
         │
         ▼
   ...重复直到遇到 <EOS> 或达到 max_tokens
```

**关键特性**：
- 串行生成：必须等第 t 步生成完才能做第 t+1 步
- 每一步都要重新算所有位置的 Attention（所以长上下文慢）
- 当前输出 = 之前所有输出 + 输入 的拼接

### Temperature

```
softmax(x_i / T)  ← 在 softmax 之前对 logits 做缩放

T → 0:   分布极尖锐 → 总是选最高概率 → 确定性输出
T = 1.0: 原始分布     → 默认设置
T → ∞:   分布极均匀 → 完全随机 → 胡言乱语

对 Agent 的实践:
  工具调用 → T=0.1-0.3  (要精确)
  创意写作 → T=0.7-0.9  (要多样性)
  代码生成 → T=0.1-0.2  (要正确性)
```

### Top-K / Top-P 采样

```
两者都是从概率分布中选 token 的策略，常在生成参数中同时设置。

Top-K: 只从概率最高的 K 个 token 中采样
  top_k=50 → 每步只在 top 50 个候选里选
  优点: 避免选到极低概率的奇怪 token
  缺点: K 是固定值，不适合所有场景（有些分布集中，有些分散）

Top-P (Nucleus): 从累计概率 ≥ p 的最小 token 集中采样
  top_p=0.9 → 按概率从高到低累加，加满 0.9 就停
  优点: 自适应，分布集中时候选少，分散时候选多
  缺点: 计算稍复杂

最佳实践: top_p=0.9, temperature=0.3（适用于大多数 Agent 场景）
```

---

## 七、分阶段面试问答

### 基础阶段

#### Q1：什么是 Attention？为什么需要它？

**回答要点**：
- Attention 让模型在处理当前 token 时"关注"序列中其他 token
- 解决了 RNN 无法并行计算和长距离依赖的问题
- 核心操作：Q 与 K 算相似度，softmax 归一化，对 V 加权求和
- 公式：Attention(Q,K,V) = softmax(Q×K^T/√d_k)×V

#### Q2：为什么 Transformer 比 RNN 强？

| 维度 | RNN | Transformer |
|------|-----|-------------|
| 并行度 | ❌ 必须串行 | ✅ 全并行 |
| 长距离依赖 | ❌ 距离越远信息越弱 | ✅ 直接 Attention 连接 |
| 训练稳定性 | ❌ 梯度消失/爆炸 | ✅ 残差连接 |
| 可扩展性 | ❌ 深层的收益递减 | ✅ 可以堆 100+ 层 |

### 进阶阶段

#### Q3：为什么要用 Multi-Head 而不是一个更大的 Head？

- 一个 Attention 只能学到一种分布，多个 head 可以并行学不同模式
- 计算量和单头基本一致（参数量相同），但表达能力更强
- 不同 head 关注不同的语言特征（语法、语义、位置等）

#### Q4：Self-Attention 的时间复杂度？

```
O(n² × d)

n = 序列长度
d = 隐藏维度

n=1000  → 约 1M 次计算
n=10000 → 约 100M 次计算（100 倍！）
n=100000 → 约 10B 次计算

这就是为什么长上下文很慢，也是 Flash Attention 等优化的动机
```

#### Q5：为什么 Q×K 后要除以 √d_k？

- d_k 个独立随机变量的和，方差 = d_k
- d_k 越大，方差越大，softmax 输入会很大或很小
- 导致 softmax 输出极端（接近 one-hot），梯度近乎 0
- 除以 √d_k 把方差拉回 1，保持梯度流动

### 应用阶段

#### Q6：Attention 在 Agent 中有哪些应用场景？

| 场景 | Attention 的角色 |
|------|-----------------|
| LLM 推理生成 | 每一步关注前面所有 token |
| RAG Embedding | 最后一层输出 = 语义向量 |
| Function Calling | 关注函数 schema 中的相关描述 |
| 记忆系统 | Cross-Attention 压缩历史 |
| 多模态 Agent | 对齐文本和图像特征 |

#### Q7：上下文窗口限制如何影响 Agent？

```
问题 1 - 遗忘：长对话早期信息被截断
问题 2 - 稀释：中间位置的 Attention 权重被摊薄
问题 3 - 成本：O(n²) 复杂度，长上下文直接推高延迟和费用
问题 4 - Agent 多步推理：ReAct 每多一步都要重新算全部 Attention

常用缓解方案：
├── 滑动窗口     → 只保留最近 N 轮对话（简单但丢信息）
├── 摘要压缩     → 定期 LLM 总结历史（有损但可控）
├── RAG          → 外部检索，上下文只放相关片段（最灵活）
├── 分层记忆     → 短期（最近）+ 长期（压缩摘要）
└── Flash Attention → 硬件优化，不丢信息但加速计算
```

---

## 八、Agent 开发高频面试题

### Q8：LLM 是怎么生成回复的？

**自回归解码，每次一个 token**。在第 t 步，模型以输入 + 已生成的 t-1 个 token 为条件，预测第 t 个 token。新 token 拼回输入后继续。这就是为什么 LLM 生成是串行的，也是为什么流式输出可以做到逐 token 返回。

### Q9：Function Calling 和 Transformer 有什么关系？

**本质是"生成 JSON 文本"**，不是"调用函数"。模型看到函数 schema（也是 token），通过 Attention 理解函数描述和用户问题的关联，在输出时按训练时学会的格式输出 JSON。Agent 系统解析这个 JSON 后实际调用函数。所以 Function Calling 的质量取决于：
- 函数描述是否清晰（影响 Attention 匹配）
- Schema 是否在模型训练数据中常见
- 上下文是否能容纳完整的 Schema+ 用户问题

### Q10：什么是温度系数？Agent 系统中怎么设？

Temperature 控制 softmax 分布的形状：
- 低（0.1-0.3）：概率集中，输出稳定 → Agent 工具调用、代码生成
- 中（0.7）：平衡 → 通用对话
- 高（0.9+）：概率平滑，输出多样 → 创意任务

**Agent 开发经验**：工具调用用低温度（0-0.3），回答生成用中温度（0.3-0.7）。系统需要确定性时用低温度。

### Q11：RAG 中的 Embedding 向量从哪来？

从一个 Transformer Encoder 模型（如 BERT、BGE）的最后一层输出。模型把变长的文本编码成一个固定维度的向量。语义相似的文本，向量在空间中的距离也近。这个向量和 LLM Attention 中计算的 QKV 向量本质上是同一类东西——都是 Transformer 产生的表示。

### Q12：如何解决 Agent 的长上下文丢失问题？

分层方案（面试推荐回答模板）：

```
第 1 层 - 滑动窗口：保留最近 N 轮对话 → 简单有效
第 2 层 - 摘要记忆：定期对历史做压缩摘要 → 有损但可控
第 3 层 - RAG：检索相关历史片段注入上下文 → 灵活
第 4 层 - 结构化记忆：提取关键实体和偏好存数据库 → 精确

实际系统中，通常 1+3 组合：
  滑动窗口保证实时性
  RAG 保证关键信息不丢失
```

### Q13：Agent 的"幻觉"和 Transformer 有什么关系？

根源在 Attention 的统计本质：
- Attention 权重是概率分布，可能给不相关的内容高权重
- 模型学的是"统计相关性"而非"事实"
- 自回归解码时，一旦选错一个 token，后续会偏差更大
- Softmax 强制所有概率和为 1，即使输入不包含正确答案

缓解方法：RAG（事实验证）、低温度（减少随机性）、Constraint Decoding（限制输出空间）。

### Q14：Embedding 模型选型考虑什么？

| 指标 | 说明 | 选择建议 |
|------|------|----------|
| 向量维度 | 384-1024 不等 | 维度越低检索越快 |
| 最大长度 | 512 tokens 常见 | 匹配你的 chunk 大小 |
| 语言 | 单语/双语 | 中文场景选双语模型 |
| MTEB 分数 | 标准榜单 | 参考但不盲信 |
| 推理速度 | 延迟 | 线上服务优先快的 |

中文常用：bge-large-zh-v1.5、moka-ai/m3e

### Q15：向量检索和 Attention 有什么联系？

**同源不同用**：

```
向量检索 (RAG)               Attention (LLM)
───────────────              ───────────────
用余弦/内积算两个向量相似度    用 Q×K^T 算序列内关系
独立于上下文                  依赖上下文
用于找相关文档                用于理解语义
模型 = Transformer Encoder   模型 = Transformer Decoder
```

Embedding 模型和 LLM 都基于 Transformer，只是 Embedding 模型取的是最后一层的 CLS 向量或 pooling 结果，LLM 取的是每一步的解码输出。

---

## 九、手撕代码

### 题 1：Scaled Dot-Product Attention

```python
import numpy as np

def attention(Q, K, V, mask=None):
    """
    Args:
        Q: (batch, seq_len, d_k)
        K: (batch, seq_len, d_k)
        V: (batch, seq_len, d_v)
        mask: (seq_len, seq_len), 1 表示屏蔽
    Returns:
        output: (batch, seq_len, d_v)
        weights: (batch, seq_len, seq_len)
    """
    d_k = Q.shape[-1]

    # 1. Q × K^T
    scores = np.matmul(Q, K.transpose(0, 2, 1))  # (B, L, L)

    # 2. 缩放
    scores = scores / np.sqrt(d_k)

    # 3. 可选：Mask（Decoder 用，屏蔽未来 token）
    if mask is not None:
        scores = scores + mask * -1e9  # 屏蔽位置设为负无穷

    # 4. Softmax
    exp_scores = np.exp(scores - np.max(scores, axis=-1, keepdims=True))
    weights = exp_scores / np.sum(exp_scores, axis=-1, keepdims=True)

    # 5. 加权求和
    output = np.matmul(weights, V)  # (B, L, d_v)

    return output, weights


def softmax(x, axis=-1):
    """数值稳定的 softmax"""
    x_max = np.max(x, axis=axis, keepdims=True)
    exp_x = np.exp(x - x_max)
    return exp_x / np.sum(exp_x, axis=axis, keepdims=True)
```

### 题 2：Multi-Head Attention

```python
class MultiHeadAttention:
    def __init__(self, d_model, num_heads):
        assert d_model % num_heads == 0
        self.d_model = d_model
        self.num_heads = num_heads
        self.d_k = d_model // num_heads

        # 模拟权重（面试中说明即可，不用真写初始化）
        self.W_q = np.random.randn(d_model, d_model)
        self.W_k = np.random.randn(d_model, d_model)
        self.W_v = np.random.randn(d_model, d_model)
        self.W_o = np.random.randn(d_model, d_model)

    def split_heads(self, x):
        """(B, L, d_model) → (B, h, L, d_k)"""
        B, L, _ = x.shape
        x = x.reshape(B, L, self.num_heads, self.d_k)
        return x.transpose(0, 2, 1, 3)

    def combine_heads(self, x):
        """(B, h, L, d_k) → (B, L, d_model)"""
        B, _, L, _ = x.shape
        x = x.transpose(0, 2, 1, 3)
        return x.reshape(B, L, self.d_model)

    def forward(self, Q, K, V):
        # 1. 线性投影
        Q = Q @ self.W_q
        K = K @ self.W_k
        V = V @ self.W_v

        # 2. 分头
        Q = self.split_heads(Q)
        K = self.split_heads(K)
        V = self.split_heads(V)

        # 3. 每个 head 独立算 Attention
        output, weights = attention(Q, K, V)

        # 4. 合并头
        output = self.combine_heads(output)

        # 5. 输出投影
        output = output @ self.W_o
        return output
```

### 题 3：Token 计数器

```python
import tiktoken

def count_tokens(text: str, model: str = "gpt-4") -> dict:
    """统计 token 数并返回详情"""
    enc = tiktoken.encoding_for_model(model)
    tokens = enc.encode(text)
    return {
        "text_len": len(text),
        "token_count": len(tokens),
        "ratio": round(len(tokens) / len(text), 2),
        "model": model,
    }


def truncate_to_limit(text: str, max_tokens: int, model: str = "gpt-4") -> str:
    """截断到 max_tokens 以内"""
    enc = tiktoken.encoding_for_model(model)
    tokens = enc.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return enc.decode(tokens[:max_tokens])
```

### 题 4：文本分块（RAG 预处理）

```python
def chunk_by_tokens(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """按 token 数分块（用简单切词，演示原理）"""
    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start = end - overlap  # 重叠

    return chunks


def chunk_by_paragraphs(text: str, max_chars: int = 1000) -> list[str]:
    """按段落边界分块，保持语义完整性"""
    paragraphs = text.split("\n\n")
    chunks = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) > max_chars and current:
            chunks.append(current.strip())
            current = para
        else:
            current = (current + "\n\n" + para) if current else para

    if current:
        chunks.append(current.strip())

    return chunks
```

### 题 5：简单的 RAG 检索框架

```python
class SimpleRAG:
    """面试展示 RAG 原理"""

    def __init__(self, embed_fn=None):
        self.embed_fn = embed_fn or (lambda x: np.random.randn(384))
        self.documents = []
        self.embeddings = []

    def add(self, docs: list[str]):
        for doc in docs:
            self.documents.append(doc)
            self.embeddings.append(self.embed_fn(doc))
        self.embeddings = np.array(self.embeddings)

    def retrieve(self, query: str, k: int = 3) -> list[tuple[str, float]]:
        q_vec = self.embed_fn(query)

        # 余弦相似度
        dots = np.dot(self.embeddings, q_vec)
        norms = np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(q_vec)
        scores = dots / (norms + 1e-8)

        # Top-K
        top_idx = np.argsort(scores)[-k:][::-1]
        return [(self.documents[i], float(scores[i])) for i in top_idx]
```

---

## 十、快速记忆卡

> 面试前 30 分钟看这个就够了

```
Attention 公式: softmax(Q×K^T/√d_k)×V
            Q=问什么, K=答什么, V=实际内容, √d_k=防梯度消失

为啥除以 √d_k: d_k 越大方差越大 → softmax 太极端 → 梯度消失

Multi-Head: h 个 Attention 并行，学不同模式

Self-Attention 复杂度: O(n²d) ← 上下文越长越慢

Decoder-only: 只看左边，逐个生成 ← GPT 系列

RoPE: 旋转位置编码 ← LLaMA/Qwen/ChatGLM 都在用

Temperature 低→确定（工具调用） 高→多样（创意）

Function Calling: 生成 JSON 不是调函数 ← 面试必提

RAG Embedding: Transformer Encoder 最后一层向量

幻觉根源: Attention 的统计本质 + 自回归的误差累积

Agent 记忆方案: 滑动窗口(最简单) / 摘要(有损) / RAG(最灵活)
```

---

> **写在最后**：面试官不是要你手写 Transformer，而是要确认你理解你在用什么东西。能说清 Attention 原理、知道哪里是瓶颈、会用 tiktoken 处理 token、能把 Function Calling 和 Attention 联系起来——这就已经超过大部分候选人了。

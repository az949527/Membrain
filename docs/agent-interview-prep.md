# Agent 准备方案

参考 [AgentGuide](https://github.com/adongwanai/AgentGuide) 框架，结合 MemBrain 项目定制的面试准备方案。

---

## Part 1：Agent 面试题库分析

从 AgentGuide 及市场 JD 中提取 Agent 相关考点，标注与 MemBrain 相关性和重要程度。

### 考点总览

| # | 考点 | 相关性 | 重要性 | 状态 | 备注 |
|---|------|--------|--------|------|------|
| 1 | Tool Calling / Function Calling 原理 | 🔴 高 | ⭐⭐⭐ 必考 | ✅ 已掌握 | `nodes.py` reasoning_node |
| 2 | ReAct 循环设计 | 🔴 高 | ⭐⭐⭐ 必考 | ✅ 已掌握 | LangGraph 循环边 |
| 3 | tool_choice 参数选项 | 🔴 高 | ⭐⭐⭐ 必考 | ✅ 已掌握 | `tool_choice="auto"` |
| 4 | Agent vs Prompt 路由区别 | 🔴 高 | ⭐⭐⭐ 必考 | ✅ 已掌握 | 旧版 classify 升级到 Tool Calling |
| 5 | 多工具并行调用 | 🔴 高 | ⭐⭐⭐ 必考 | ✅ 已掌握 | `asyncio.gather` |
| 6 | 异常处理/降级策略 | 🔴 高 | ⭐⭐⭐ 必考 | ✅ 已掌握 | 三层降级 |
| 7 | 两层架构（检索与生成分离） | 🔴 高 | ⭐⭐⭐ 必考 | ✅ 已掌握 | ReAct 只检索，chat.py 单独生成 |
| 8 | 工具定义 Schema 设计 | 🔴 高 | ⭐⭐⭐ 必考 | ✅ 已掌握 | `tools.py` 定义 |
| 9 | LangGraph 状态机设计 | 🔴 高 | ⭐⭐⭐ 必考 | ✅ 已掌握 | `graph.py` + `state.py` |
| 10 | 全链路数据流 | 🔴 高 | ⭐⭐⭐ 必考 | ✅ 已掌握 | chat.py 6 步流程 |
| 11 | RAG 优化（chunk/reranker/query改写） | 🟡 中 | ⭐⭐ 常考 | ⚠️ 部分掌握 | 基本 RAG 有，reranker/HyDE 缺失 |
| 12 | Agent Memory 机制 | 🟡 中 | ⭐⭐ 常考 | ❌ 缺失 | 对话摘要/长期记忆未实现 |
| 13 | Guardrails / LLM 输出校验 | 🟡 中 | ⭐⭐ 常考 | ⚠️ 部分掌握 | try/except 有，格式校验弱 |
| 14 | Agent 评估方法论 | 🟡 中 | ⭐⭐ 常考 | ❌ 缺失 | 无评估数据集 |
| 15 | 上下文工程（Context 优化） | 🟡 中 | ⭐⭐ 常考 | ❌ 缺失 | 无系统化上下文管理 |
| 16 | MCP 协议 | 🟡 中 | ⭐⭐ 常考 | ❌ 缺失 | 概念层面需了解 |
| 17 | 多 Agent 协作 | 🟢 低 | ⭐ 了解 | ❌ 缺失 | 高级岗位会问 |
| 18 | Prompt 工程体系化 | 🟢 低 | ⭐ 了解 | ⚠️ 部分掌握 | prompt 散落，未集中管理 |
| 19 | System Design（高并发 Agent 服务） | 🟡 中 | ⭐⭐ 常考 | ❌ 缺失 | 需要专项准备 |
| 20 | Agent 流式推理中间过程输出 | 🟢 低 | ⭐ 了解 | ❌ 缺失 | 优化项 |

### 考点详解与 MemBrain 话术

---

#### 【必考】考点 1：Tool Calling / Function Calling 原理

**面试问法**："你的 Agent 怎么决定调什么工具的？"

**用 MemBrain 回答**：
```
MemBrain 用的是 OpenAI 的 Tool Calling 机制。
在 reasoning_node 里，我传了 tools=TOOLS 参数给 LLM，
TOOLS 定义了三个工具（rag_search、graph_query、web_search），
每个工具都有 name、description、parameters。
LLM 根据用户问题和工具描述自主决策，返回结构化的 tool_calls，
代码直接读 tc.function.name 就知道调什么工具。

核心区别：不是让 LLM 输出文本然后我解析——而是 LLM 知道"有工具可用"，
主动选择调用工具，返回格式由 API 保证。
```

**埋点引导**："这里有一个关键设计——description。LLM 看不到工具的实现代码，唯一决策依据就是 description。"

---

#### 【必考】考点 2：ReAct 循环设计

**面试问法**："调完工具拿到的结果怎么处理的？一次不够怎么办？"

**用 MemBrain 回答**：
```
我在 LangGraph 里构建了一个循环：reasoning → execute_tools → reasoning。

第1轮：reasoning_node 收到问题，LLM 决定调 graph_query
     → execute_tools_node 执行图谱查询，拿到结果
     → 结果写入 messages，iteration+1
第2轮：reasoning_node 看到历史记录（上轮结果），LLM 觉得够了
     → 返回 __answer__ → 结束

最多 3 轮强制终止防死循环。
这其实就是 ReAct（Reasoning + Acting）模式。
```

**埋点引导**："这里我踩过一个坑——当初数据流没设计好，LLM 看不到之前的工具结果，每轮都在重复调同一个工具。后来把 tool 结果追加到 messages 里才解决。"

---

#### 【必考】考点 3：tool_choice 参数选项

**面试问法**："tool_choice 有哪些选项？你们用的什么？"

**用 MemBrain 回答**：
```
项目用 tool_choice="auto"，让 LLM 自己决定。

四种选项：
- "auto"（默认）— LLM 自己决策，适合大多数场景
- "none" — 强制不调工具，适合闲聊省 token
- "required" — 强制调工具，适合必须走工具的管线
- {"type":"function","function":{"name":"xxx"}} — 强制调特定工具

我项目里用 auto，因为不知道用户问的是需要检索的还是闲聊。
如果用 required，用户说"你好"也会去调工具，浪费 token 和延迟。
```

---

#### 【必考】考点 4：Agent vs Prompt 路由区别

**面试问法**："你说的 Tool Calling 和传统的 prompt 分类有什么区别？"

**用 MemBrain 回答**（注意 qa-records.md 已有完整答案）：
```
我的项目经历过这个演进。
最早是 classify 模式——写 prompt 让 LLM 输出 ["rag"] 之类的文本，
代码手动解析。缺点：LLM 不知道"有工具可用"，格式不稳定。

后来改成 Tool Calling——传 tools 参数，LLM 返回结构化 tool_calls。
优点：①路由准确率提升 ②格式由 API 保证 ③面试价值高。

类似"替换引擎不换车架"——检索节点、LangGraph 构建、chat.py 集成完全不变。
```

---

#### 【必考】考点 5：多工具并行调用

**面试问法**："同时调了 RAG 和搜索，怎么做的？"

**用 MemBrain 回答**：
```
execute_tools_node 里用 asyncio.gather 并行执行。
比如 LLM 决定需要 rag + graph + web 三个源，
三个检索任务同时跑，总耗时 ≈ 最慢的那个。
互不依赖的工具并行，依赖的串行。

LangGraph 天然支持这种并行路由。
```

---

#### 【必考】考点 6：异常处理/降级策略

**面试问法**："LLM 挂了或者检索失败了怎么办？"

**用 MemBrain 回答**：
```
三层降级：

第一层（单节点）：某个检索节点失败只跳过自身，
其他节点不受影响。

第二层（路由层）：LLM 调用失败 → 返回全源检索，
宁可多跑不能空手。

第三层（系统层）：整张 LangGraph 全炸 →
降级为纯 LLM 聊天，用户至少能正常对话。

各层独立 try/except，单点故障不扩散。
```

---

#### 【必考】考点 7：两层架构设计

**面试问法**："LangGraph 里 LLM 已经回答了，怎么又调一次 LLM？"

**用 MemBrain 回答**：
```
这是故意设计的"检索与生成分离"架构。

第一层（LangGraph ReAct）：只负责检索决策。
LLM + tools 参数决定调什么工具，__answer__ 时丢弃 choice_msg.content。

第二层（chat.py）：从 state 取出三个 context 字段，
插入 api_messages 后另起一次 LLM 调用（stream=True）生成最终回答。

好处：两部分可独立优化。
代价：每次回答多调一次 LLM API（但可以接受）。
```

---

#### 【常考】考点 11：RAG 优化

**面试问法**："你们 RAG 效果怎么样？怎么优化的？"

**当前 MemBrain 状态**：基本 RAG 有（分块 → embedding → FAISS → 检索），缺 reranker 和 query 改写。

**回答策略（实话实说 + 补全思路）**：
```
目前实现了基础 RAG 管线：500 字符分块 → sentence-transformers 向量化 →
FAISS 检索 top-k → 从 DB 取原文 → 组装上下文。

优化方向（建议着重讲这些思路，即使没实现）：
1. Reranker 精排：FAISS 粗排后加 cross-encoder 重排序，把最相关的排前面
2. HyDE：短查询先用 LLM 生成假设回答，再向量化检索，提高命中率
3. 相似度阈值：低于 0.3 的不返回，避免无关内容污染上下文
```

---

#### 【常考】考点 12：Agent Memory 机制

**面试问法**："你们的 Agent 有记忆吗？怎么实现多轮对话？"

**当前 MemBrain 状态**：对话历史从 DB 加载，但无长期记忆/摘要记忆。

**回答策略**：
```
目前通过 DB 加载完整消息历史实现"短期记忆"（每轮聊天的上下文）。
长期记忆方面正在规划：对话超过 N 轮时自动摘要压缩，
以及提取关键实体存入结构化记忆。

【关键是】能说出记忆分几种：情景记忆（历史）、语义记忆（知识）、程序记忆（偏好）。
```

---

#### 【常考】考点 16：MCP 协议

**面试问法**："了解 MCP 吗？跟你项目的 Tool Calling 有什么关系？"

**回答策略**（概念层面，不需要实现）：
```
MCP = Model Control Protocol，是 Agent 和工具之间的标准化通信协议。
类比：MCP for Agent ≈ USB-C for devices。

我项目的 Tool Calling 已经实现了类似的思想——
工具通过标准 schema 定义（name + description + parameters），
LLM 通过这个 schema 了解工具并调用。

区别：Tool Calling 是 API 级的，MCP 是协议级的标准化方案。
```

---

## Part 2：STAR 话术 — 用 MemBrain 讲故事

参考 AgentGuide STAR 框架，准备两个版本。

### 30 秒电梯演讲

```
我们团队（1人）发现知识分散在文档、笔记和网络中，
找信息很耗时。我用 LangGraph + OpenAI Tool Calling 构建了一个
Agentic RAG 系统，让 LLM 自主判断需要查哪个知识源
（本地文档、知识图谱还是网络搜索），
通过 ReAct 循环最多 3 轮检索后给出答案。
项目用 FastAPI 上线，全异步，带 JWT 认证和语义缓存。
```

### 2 分钟标准版本（面试讲故事）

**S — Situation（背景，15%）**
```
我个人有大量学习资料（文档、笔记、网页），
每次找信息要在不同工具之间切换，没有统一入口。
市面上虽然有知识库产品，但要么数据不在本地，
要么不支持多知识源联合检索。
```

**T — Task（任务，10%）**
```
我想构建一个个人知识助手，能：
1. 自动判断用户问的是文档内容、关系查询还是实时信息
2. 从多个知识源检索并融合结果
3. 用 LLM 给出最终回答
4. 数据全在本地，隐私可控
```

**A — Action（行动，40%）⭐ 重点**

架构设计决策：
```
第一层：LangGraph ReAct 循环
- reasoning_node：用 OpenAI Tool Calling（tools 参数）让 LLM 自主选工具
- execute_tools_node：asyncio.gather 并行执行选中的工具
- 循环直到 LLM 认为信息够了（__answer__）

第二层：检索与生成分离
- ReAct 只负责检索，结果写入 context 字段
- chat.py 另起 LLM 调用生成最终回答（stream=True）

降级策略：三层兜底（单节点→全源→纯聊天）

可观测性：AgentTracer 记录每次路由决策和耗时

多知识源：FAISS 向量库（文档）、Neo4j 图谱（实体关系）、SerpAPI（网络搜索）
```

技术栈选择：
```
LangGraph（循环图而非 DAG）、FastAPI（全异步）、
FAISS（轻量，不需额外服务）、DeepSeek API（OpenAI 兼容）
```

**R — Result（结果，35%）**
```
- 支持 3 种知识源的自主路由和联合检索
- 路由失败时三层降级保证服务可用
- AgentTracer 可观测每次决策链路
- 语义缓存命中时跳过 LLM，降低延迟和成本
- 全异步架构，聊天流式输出

【面试埋点】"这个项目让我深入理解了 Tool Calling 的边界——
比如 LLM 可能构造不存在的参数，所以我们做了 try/except 校验。
另外 ReAct 循环也有坑，当初 LLM 看不到上轮结果导致重复调用..."
```

### 备用追问应对

**Q："LangGraph 和直接调 API 有什么区别？"**
```
直接调 API 做一次"请求→回答"简单，但要做多轮推理就很麻烦。
LangGraph 提供状态机，天然支持循环边（reasoning→execute→reasoning），
条件边（__answer__→END），而且状态 AgentState 集中管理。
手写 while 循环的话，状态管理、历史维护都要自己造轮子。
```

**Q："为什么用 DeepSeek 不用 GPT？"**
```
DeepSeek API 兼容 OpenAI 格式，代码层面用 openai 库，
切换只需要改 base_url。当时选它是因为性价比高，
而且 DeepSeek 是国内模型，延迟更低。
这是项目初期的合理选择，不锁定 vendor。
```

**Q："语义缓存怎么实现的？"**
```
用户问题向量化 → Redis SCAN 找候选 → 余弦相似度计算 →
超过 0.92 阈值则命中直接返回，跳过 LLM。
没命中就正常走流程，同时把回答写入缓存。
TTL 1 小时自动过期，高频问题自动缓存。
```

---

## Part 3：个性化学习路线图

### 当前画像

```
背景：自学转行，非科班
项目：MemBrain Agentic RAG 系统
目标：Agent 应用开发 / AI 应用工程师
对标：①模型应用工程师 ②Agent 中台/框架开发 ③业务 Agent
```

### 各阶段规划

#### Week 1：夯实已有（梳理 MemBrain）

| 任务 | 产出 | 参考 |
|------|------|------|
| 整理所有设计决策 | 30 分钟项目讲解稿 | qa-records.md + 本文 Part 2 |
| 梳理架构图 | 一页纸画出全链路 | graph.py + chat.py 数据流 |
| 整理面试话术 | 10 个高频考点回答 | 本文 Part 1 |
| 部署到 AutoDL | 可访问的线上 demo | FUTURE_IMPROVEMENTS.md |

#### Week 2：补齐短板（动手实现）

| 任务 | 优先级 | 预估时间 | 说明 |
|------|--------|----------|------|
| Reranker 精排 | 🔴 高 | 1 天 | cross-encoder 对 FAISS 结果重排序 |
| Query 改写（HyDE） | 🔴 高 | 1 天 | LLM 生成假设回答 → 向量化检索 |
| 相似度阈值 | 🟡 中 | 0.5 天 | 低于 0.3 的 chunk 不返回 |
| 评估数据集 | 🟡 中 | 1 天 | 30-50 条 question → expected_sources |
| Prompt 集中管理 | 🟢 低 | 0.5 天 | 建 `app/core/prompts.py` |

#### Week 3：面试专题（概念准备）

| 任务 | 预估时间 | 说明 |
|------|----------|------|
| MCP 协议精读 | 2h | 读官方文档，理解设计思想 |
| 多 Agent 架构了解 | 2h | 了解 Supervisor 模式、Task 分解 |
| 上下文工程学习 | 2h | Context Pack、动态注入、Token 预算 |
| 记忆机制学习 | 1h | 情景/语义/程序记忆分层 |
| System Design 准备 | 4h | "设计百万 QPS Agent 服务"思路 |
| 刷 10 道 Agent 面试题 | 2h | 从 qa-records.md + AgentGuide 选 |

**概念准备投入产出比**

| 模块 | 面试价值 | 投入 | 说明 |
|------|----------|------|------|
| MCP 协议 | ⭐⭐ | 2h 精读 | 标准化协议，面试常被问"了解 MCP 吗"；类比 USB-C 解释 |
| 多 Agent 架构 | ⭐⭐ | 2h 了解 | 高级岗考点；Supervisor 模式 + Task 分解套路固定 |
| 上下文工程 | ⭐⭐ | 2h 学习 | Context Pack / 动态注入 / Token 预算；属于工程经验类问题 |
| 记忆机制 | ⭐ | 1h 了解 | 情景/语义/程序记忆三层；说清概念即可，少追问 |
| System Design | ⭐⭐⭐ | 4h 重点 | 高并发 Agent 服务设计；本文 Part 5 已覆盖全部 6 维度 |

#### Week 4：模拟冲刺

| 任务 | 说明 |
|------|------|
| STAR 项目讲解演练 | 对着镜子/录音讲 3 遍 |
| Mock Interview | 找朋友或付费模拟 |
| 简历投递 | 投 10-20 家（Boss/猎聘/内推） |
| 复盘优化 | 每轮面试后记录问题，调整话术 |

### 技术栈对标

```
你有的（面试重点讲）：                    面试可以讲的（概念层）：
✅ Python                               ⚠️ MCP 协议概念
✅ LangGraph / LangGraph                 ⚠️ 多 Agent 架构
✅ FastAPI 全异步                        ⚠️ HyDE query 改写
✅ OpenAI Tool Calling                   ⚠️ Reranker 精排
✅ RAG（FAISS + embedding）              ⚠️ RLHF/DPO 概念
✅ ReAct 循环                            ❌ 分布式训练/推理
✅ 三层降级策略
✅ 语义缓存（Redis）
✅ AgentTracer 追踪
✅ JWT 认证
✅ Neo4j 知识图谱
✅ Docker Compose
```

### 最终建议

1. **先讲透已有的** — 你有的 70% 比缺失的 30% 重要得多。面试官更关心"你会什么"而不是"你不会什么"
2. **补概念 > 补实现** — Week 3 的概念准备（MCP、多Agent、System Design）投入产出比高于 Week 2 的代码实现
3. **建立评估闭环** — 如果有时间做一件事，做评估数据集（30 条测试用例）。面试说"我们在测试集上准确率 85%"比说"效果不错"有力 10 倍
4. **简历写项目别写技能列表** — "用 LangGraph 构建了 ReAct 循环的 Agentic RAG 系统" > "熟悉 LangGraph"

---

## Part 4：概念专项（面试话术）

### 4.1 MCP 协议 ⭐⭐

**场景题**
> "了解 MCP 吗？跟你的 Tool Calling 有什么关系？"
> "MCP 和 API 有什么区别？"

**一句话总结**
```
MCP（Model Context Protocol）是 Agent 和工具之间的标准化通信协议。
类比：MCP for Agent ≈ USB-C for devices——统一接口，即插即用。
```

**核心理解（说清 3 点就够了）**

```
1. 解决了什么问题
   每个 Agent 框架都有自己的工具调用格式（OpenAI tool_calls、LangChain Tool、
   Google function_declaration 格式都不一样）。MCP 统一了"Agent 怎么发现工具、
   怎么调用工具、工具怎么返回结果"这个流程。

2. 核心概念
   Host：Agent 应用（如 Claude Desktop、IDE 插件）
   Client：与 MCP 服务器建立会话的客户端
   Server：暴露工具、资源、prompts 的服务器
   传输层：stdio（本地进程通信）或 HTTP+SSE（远程服务）

3. 与 MemBrain 的关系
   我项目里用 Tool Calling 已经实现了类似思想——工具通过标准 schema 定义，
   LLM 根据 schema 自主调用。区别是 Tool Calling 是 API 级的，
   MCP 是协议级的标准化方案。

   如果要接入 MCP，改造很小：
   - 把每个检索工具（rag_search / graph_query / web_search）包装成 MCP tool
   - 启动一个 MCP Server 暴露这些工具
   - FastAPI 侧通过 MCP Client 调用
```

**追问应对**

| 追问 | 回答 |
|------|------|
| "MCP 和 Function Calling 什么关系？" | Function Calling 是"LLM 调用工具的能力"，MCP 是"工具怎么被发现的标准化协议"。两者不在同一层——FC 是能力，MCP 是协议。可以用 MCP 做工具管理，底层还是 FC 实现 |
| "MCP 的竞争对手？" | OpenAI 的 GPT Actions（封闭生态）和 Google 的 A2A（Agent-to-Agent）。MCP 是开源标准，Anthropic 提出的。如果面试官问选型，说"倾向 MCP——开源、社区活跃、和现有 Tool Calling 不冲突" |
| "生产环境用 MCP 有什么坑？" | ①MCP 协议还很新，生产案例少 ②每个工具一个 Server，部署成本增加 ③协议本身还在演进（2025 年初才发布） |

**话术模板（3 句）**
```
"MCP 是 Agent 工具调用的标准化协议，类似 USB-C 统一了外设接口。
我的 MemBrain 用 Tool Calling 已经实现了类似思想——工具通 schema 定义，
LLM 自主决策调用。
如果要接入 MCP，只需把三个检索工具包装成 MCP Server，改造量很小。"
```

**面试考察点分级**

| 级别 | 知识点 | 追问概率 |
|------|--------|----------|
| ⭐⭐⭐ 必问 | MCP 是什么、解决什么问题、和 FC 什么关系 | 几乎必追 |
| ⭐⭐ 常问 | 三层架构(Host/Client/Server)、传输层(stdio vs SSE) | 50% |
| ⭐ 加分 | 竞品对比(GPT Actions/A2A)、生产坑点、生态现状 | 深挖时追 |
| 💡 亮点 | **MemBrain vs MCP 对比**（见下表） | 主动引出 |

**MemBrain vs MCP 深度对比（主动埋点用）**

| 对比维度 | MemBrain（当前做法） | MCP（协议标准） | 面试价值 |
|----------|---------------------|-----------------|----------|
| 工具定义 | `tools.py` 手写 dict schema | 标准 Tool 对象，IDE 友好+类型校验 | 展示对标准化认知 |
| 工具发现 | 静态 `TOOLS` 列表，编译时确定 | 动态 `list_tools()`，运行时广播 | 展示架构扩展思维 |
| 调用流程 | `execute_tools_node` 硬编码分发 | Client→Server 协议层通用调用 | 展示解耦思维 |
| 部署方式 | 进程内函数调用，3 个工具在内存里 | 独立 Server 进程/容器，可独立扩缩 | 展示微服务意识 |
| 安全边界 | JWT 统一鉴权，无工具级权限 | 按工具/Server 细粒度授权 | 展示企业级安全思维 |

**话术**："MemBrain 和 MCP 在思想上一脉相承——工具通过 schema 定义、LLM 自主决策。区别在于 MCP 把这些做了标准化和协议化。如果接入 MCP，工具逻辑不变，只加一层协议包装，改造量很小。"

**3 段式回答框架（标准话术，建议脱稿练）**

```
第 1 段：MCP 是什么（30 秒）
→ "MCP 是 Anthropic 推出的 Agent 工具调用标准化协议，
   解决每个框架各有各的工具格式的问题。
   三层架构：Host（应用层）、Client（会话层）、Server（工具层），
   传输支持 stdio 和 HTTP+SSE。"
   埋点："打个比方——MCP for Agent = USB-C for Devices。"

第 2 段：和 MemBrain 的关系（30 秒）
→ "MemBrain 目前用 Tool Calling + 静态 TOOLS 列表，
   本质上也是工具 schema + LLM 自主决策。
   核心区别：FC 是 LLM 调用工具的能力，MCP 是工具管理的协议。
   两者不在同一层，可以共存。"
   埋点："如果面试官问 FC 会不会被 MCP 取代——不会，MCP 依赖 FC 做最终调用。"

第 3 段：如果接入怎么改（30 秒，展示架构思维）
→ "三个检索工具包装成 MCP Server，FastAPI 起 Client 连接。
   工具逻辑不变，只加协议包装。收益：
   ①工具管理和 LLM 解耦  ②新工具注册不用改代码  ③工具可独立扩缩
   ④未来可复用社区的 MCP Server。"
   埋点："这也和 MemBrain 的微服务化方向一致。"
```

**代码对比：当前 vs MCP 形式**

以下是 MemBrain 三个核心文件接入 MCP 前后的代码变化，面试官追问"具体怎么改"时展示。

**1. `app/agent/tools.py` — 工具定义**

```python
# ── 当前：手写 dict schema ──
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "rag_search",
            "description": "从本地知识库搜索私有文档...",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"}
                },
                "required": ["query"],
            },
        },
    },
]

# ── MCP 形式：标准 Tool 对象 + Server ──
from mcp import Tool
from mcp.server import Server

tools = [
    Tool(
        name="rag_search",
        description="从本地知识库搜索私有文档...",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"}
            },
            "required": ["query"],
        },
    ),
]

server = Server("membrain-tools")

@server.list_tools()       # 动态发现
async def handle_list_tools() -> list[Tool]:
    return tools

@server.call_tool()       # 统一入口
async def handle_call_tool(name: str, arguments: dict):
    if name == "rag_search":
        ctx = await RAGRetriever.retrieve(arguments["query"])
        return [TextContent(type="text", text=ctx)]
```

| 变化 | 当前 | MCP |
|------|------|-----|
| 工具描述 | dict 字面量 | `Tool()` 对象，IDE 类型提示 |
| 工具注册 | 静态列表 | `list_tools()` 动态发现 |
| 调用入口 | 函数名硬编码 | `call_tool()` 统一路由 |

**2. `app/agent/nodes.py` — 工具调用**

```python
# ── 当前：3 个独立函数 ──
async def execute_tools_node(state, embedder, vector_store, db, neo4j):
    async def run_rag():
        retriever = RAGRetriever(embedder, vector_store, db)
        chunks = await retriever.retrieve(question)
        return ("rag", ctx)

    async def run_graph():
        ctx = await GraphRetriever.retrieve(neo4j, question)
        return ("graph", ctx)

    async def run_web():
        results = await WebSearchTool.search(question)
        return ("web", ctx)

    results = await asyncio.gather(run_rag(), run_graph(), run_web())

# ── MCP 形式：统一 call_tool ──
async def execute_tools_node(state, mcp_client):
    results = await asyncio.gather(*[
        mcp_client.call_tool(
            SOURCE_TO_TOOL[source], {"query": question}
        )
        for source in sources
    ])
```

| 变化 | 当前 | MCP |
|------|------|-----|
| 调用方式 | 每个工具一个函数 | 统一 `call_tool(name, args)` |
| 结果格式 | 各函数格式不同 | 统一 `ToolResult` |
| 依赖注入 | embedder/db/neo4j 全要注进来 | 仅需 `mcp_client` |

**3. 新增 `app/agent/mcp_server.py`**

```
MCP Server（独立进程/容器）
  ├─ rag_search   → 内部调 RAGRetriever
  ├─ graph_query  → 内部调 GraphRetriever
  └─ web_search   → 内部调 WebSearchTool
        │
        │ stdio 或 HTTP+SSE
        ▼
MCP Client（在 chat.py / graph.py 中）
        │
        ▼
FastAPI → LangGraph → execute_tools_node → mcp_client.call_tool()
```

**变化总结**

| 层面 | 当前 | MCP | 改造成本 |
|------|------|-----|----------|
| `tools.py` | 手写 3 个 dict | 3 个 `Tool()` + Server 注册 | 低（逐行翻译） |
| `nodes.py` | 3 个独立函数 + asyncio.gather | 统一 `call_tool()` 循环 | 低（更简洁） |
| `graph.py` | embedder/db/neo4j 注入 | MCP Server/Client 生命周期 | 低（lifespan 管理） |
| 新增 | 无 | `mcp_server.py` | 新文件，工具逻辑迁入 |

**核心结论**：MCP 不改工具内部逻辑（检索逻辑完全不变），只改工具定义和调用方式——标准化定义、统一化调用。

**常见追问 Q&A**

**Q1：动态发现是什么意思？**

```python
# 当前 MemBrain 的"静态"方式 — 编译时就写死了
TOOLS = [
    {"name": "rag_search", ...},
    {"name": "graph_query", ...},
    {"name": "web_search", ...},
]
# 加新工具：改代码 → 重启服务器

# MCP 的"动态发现"方式：
# Client → list_tools() → Server 返回当前可用工具列表
# Server 上新加一个工具 → 下次 list_tools() Client 自动知道
# 不需要改 Client 代码，不需要重启
```

静态 = 写代码时知道有什么工具；动态 = 运行时才知道有什么工具。
MemBrain 目前 3 个工具用静态没问题，但如果扩展到几十个工具、多个团队各自维护，MCP 动态发现的收益就出来了——不需要改 Client、不需要重启，Server 端注册即用。

**Q2：MemBrain 能用 MCP 吗？为什么没用？优缺点？**

能用，改造量确实很小（见上方代码对比，工具逻辑完全不变）。

为什么没用——**项目阶段匹配问题**：
```
MemBrain 只有 3 个工具，静态 TOOLS 列表完全够用。
MCP 的收益（动态发现、独立部署、标准化）在工具数量很少时体现不出来，
反而增加了部署复杂度——多了一个 Server 进程要管理。

如果扩展到企业级，有几十个工具、多个团队各自维护，
需要工具独立上线和权限管控，那时候上 MCP 才有实际收益。
```

优缺点对比：

| 维度 | 当前（静态 TOOLS） | MCP |
|------|-------------------|-----|
| 简单性 | ✅ 极简，文件少，无额外进程 | ❌ 多一个 Server 进程，协议层开销 |
| 改造成本 | ✅ 加工具改一个文件 | ❌ 要建 Server + Client 两套 |
| 动态发现 | ❌ 改工具必须重启 | ✅ Server 热更新，Client 自动感知 |
| 标准化 | ❌ dict schema 格式自己定 | ✅ 业界标准，可对接 Claude Desktop 等生态 |
| 独立部署 | ❌ 工具和聊天在同一个进程 | ✅ 工具可独立扩缩（检索密集型时扩 Server） |
| 代码可读性 | ✅ 3 个函数一目了然 | ❌ 抽象层多了，追踪调用链需要理解 MCP 协议 |
| 社区生态 | ❌ 自己维护工具 | ✅ 未来可复用社区 MCP Server |

**话术**："3 个工具用 MCP ≈ 杀鸡用牛刀。当前阶段静态列表是更务实的选择。但我分析过接入方案，需要时随时可以改。"

**Q3：MCP 的标准格式？**

MCP 基于 **JSON-RPC 2.0** 协议，所有通信都是标准 JSON 格式：

```json
// === 通用请求 ===
{"jsonrpc":"2.0", "id":1, "method":"方法名", "params":{...}}

// === 通用成功响应 ===
{"jsonrpc":"2.0", "id":1, "result":{...}}

// === 错误响应 ===
{"jsonrpc":"2.0", "id":1, "error":{"code":-32601, "message":"Method not found"}}
```

三个核心方法的具体格式：

**① 工具发现 — tools/list**
```json
// Request
{"jsonrpc":"2.0", "id":1, "method":"tools/list", "params":{}}

// Response — 返回工具定义
{"jsonrpc":"2.0", "id":1, "result":{
  "tools": [{
    "name": "rag_search",
    "description": "从本地知识库搜索私有文档内容",
    "inputSchema": {
      "type": "object",
      "properties": {
        "query": {"type": "string", "description": "搜索关键词"}
      },
      "required": ["query"]
    }
  }]
}}
```

**② 工具调用 — tools/call**
```json
// Request — 调 rag_search
{"jsonrpc":"2.0", "id":2, "method":"tools/call", "params":{
  "name": "rag_search",
  "arguments": {"query": "Python 列表用法"}
}}

// Success — 返回结果（支持 text / resource / image 三种类型）
{"jsonrpc":"2.0", "id":2, "result":{
  "content": [
    {"type": "text", "text": "RAG 检索到的内容..."},
    {"type": "resource", "resource": {
      "uri": "file:///documents/xxx.md",
      "mimeType": "text/markdown",
      "text": "原文内容..."
    }}
  ],
  "isError": false
}}

// Error — 调用异常
{"jsonrpc":"2.0", "id":2, "error":{
  "code": -32603,
  "message": "Internal error",
  "data": "Neo4j 连接超时"
}}
```

**③ 传输层：两种连接方式**
```
stdio（本地进程）→ Client 启动 Server 子进程，stdin/stdout 传 JSON
   优点：低延迟；缺点：不能跨网络

HTTP+SSE（远程）→ HTTP POST 发请求，SSE 流式返回
   优点：跨网络，独立部署；缺点：有网络开销
```

**一句话速记 MCP 协议**：
```
JSON-RPC 2.0 格式 + 3 个核心方法（list_tools/call_tool/error）
+ 2 种传输（stdio 本地 / SSE 远程）
+ 3 种内容类型（text/resource/image）
```

---

### 4.2 多 Agent 协作 ⭐⭐

**场景题**
> "什么场景需要用多个 Agent？一个 Agent 不够吗？"
> "多 Agent 之间怎么通信？怎么协调？"

**一句话总结**
```
单 Agent 够用就不上多 Agent。多 Agent 的核心价值是"专业分工 + 状态隔离"，
不是"人多力量大"。
```

**三种常见模式**

```
模式一：Supervisor（管理者模式）
- 一个 Supervisor Agent 负责任务分解和结果汇总
- 多个 Worker Agent 各自执行子任务
- 适用：复杂任务拆分（如"写一篇市场分析报告"→ 搜数据 + 分析 + 写报告）

模式二：Pipeline（管线模式）
- Agent A 的输出 → Agent B 的输入
- 适用：有固定流程的任务（如 意图识别 → 信息抽取 → 生成回答）

模式三：Debate（辩论模式）
- 多个 Agent 各自独立推理后交叉验证
- 适用：需要高准确率的场景（如医疗诊断、法律判断）
```

**MemBrain 的角度（关键——说清楚为什么没用多 Agent）**

```
MemBrain 目前是单 Agent 架构，因为：

1. 复杂度匹配——个人知识助手的任务范围有限，单 Agent 的 ReAct 循环够用
2. 延迟敏感——多 Agent 通信增加延迟，对聊天场景不友好
3. 状态管理简单——单 Agent 的状态都在 LangGraph 的 AgentState 里，集中管理
4. 维护成本低——调试一个 Agent 比调试多个简单得多

如果扩展方向是"企业级知识中台"，我会考虑 Supervisor 模式：
- Supervisor：理解用户问题，决定调用哪个垂直 Agent
- RAG Agent：专注文档检索
- Graph Agent：专注知识图谱查询
- Web Agent：专注网络搜索
```

**追问应对**

| 追问 | 回答 |
|------|------|
| "多 Agent 的通信开销怎么控制？" | 关键原则：异步通信 + 结构化协议。不要传原始文本，传结构化数据（JSON schema）。用消息队列（RabbitMQ/Redis Pub/Sub）解耦 |
| "怎么解决 Agent 之间的冲突？" | ①每个 Agent 有明确的职责边界（prompt 限定）②Supervisor 做最终裁决 ③结果合并时按优先级策略（如"精确数据 > LLM 猜测"） |
| "你说单 Agent 够用，那什么情况下必须上多 Agent？" | ①任务需要不同领域的专业知识（如"分析财报 + 解读法规"）②需要状态隔离（一个 Agent 的状态不能影响另一个）③需要并行执行多个独立任务 |

**话术模板（3 句）**
```
"单 Agent 能解决的问题不要上多 Agent。MemBrain 的个人知识助手场景，
ReAct 循环完全够用。
如果扩展到企业级，我会用 Supervisor 模式——一个总 Agent 负责任务分解，
三个专业 Agent 各自负责一种知识源。"
```

---

### 4.3 上下文工程 ⭐⭐

**场景题**
> "LLM 上下文窗口有限，长对话怎么办？"
> "怎么保证注入的上下文是有效的？"

**一句话总结**
```
上下文工程不是"把所有内容塞进去"，而是"在有限的窗口里放最有效的信息"。
```

**四大策略**

```
策略一：动态上下文注入（Dynamic Context Injection）
- 不是把所有检索结果都塞给 LLM
- 先检索 → 再筛选（reranker 精排）→ 再组装
- 限制：intra 上下文不超过总窗口的 40%（留 60% 给对话和生成）
- MemBrain 实践：rag_context 只放相似度 top-k，graph_context 只放相关实体

策略二：上下文压缩（Context Compression）
- 长文本先让 LLM 总结再注入，而不是原文注入
- 场景：用户上传了一篇 5000 字的文章 → 先总结成 300 字摘要再检索
- 损失精度但节省大量 token

策略三：滑动窗口（Sliding Window）
- 固定窗口大小（如最近 10 轮对话），超出则丢弃最早的历史
- MemBrain 现状：目前加载全部历史，没有窗口限制
- 扩展：当消息数超过 N 时，用 LLM 压缩历史为摘要，替代原始消息

策略四：Token 预算管理（Token Budget）
- 为上下文的每个部分分配 Token 预算
- 示例预算：system(500) + 记忆(300) + 检索结果(2000) + 历史(2000) + 当前(500) = 5300
- 超过预算时优先压缩"历史"部分，保持"检索结果"完整
```

**MemBrain 现状与改进**

```
当前：
- 加载全部历史消息（无上限）
- 检索结果直接注入（无大小限制）
- 无 token 预算管理

改进方案：
- 在 chat.py 的 api_messages 组装处加 token 检查
- 超出 8K 时：历史部分用最近 10 轮 + 摘要压缩之前的
- 超出 12K 时：检索结果用 reranker 精排后只保留 top-3

简单实现（在 chat.py 加一段）：
if len(api_messages) > 20:  # 超过 20 条消息
    # 保留 system + 检索结果 + 最近 6 轮 + 当前问题
    api_messages = api_messages[:4] + api_messages[-13:]
```

**追问应对**

| 追问 | 回答 |
|------|------|
| "窗口满了丢哪些？" | 优先丢：①系统 prompt 可以精简的 ②最早几轮对话历史 ③相似度低的检索结果。保留：④当前问题 ⑤最近的工具结果 ⑥用户明确提到的实体 |
| "压缩历史会丢失信息吗？" | 会，但这是 trade-off。策略是分层压缩: ①最近 3 轮完整保留（细节）②3-10 轮摘要保留（关键信息）③10+ 轮只保留实体和主题（骨架）。越近越详细，越远越抽象 |
| "怎么量化上下文质量？" | 两个指标：①Token 利用率 = 有效信息 token / 总 token（理想值 > 60%）②召回率 = LLM 回答中引用注入内容的占比。用 AgentTracer 可以记录和监控 |

**话术模板（3 句）**
```
"上下文工程的关键不是塞更多，而是在有限窗口里放最有效的内容。
我的项目目前加载全部历史，改进方案是分层压缩——
最近 3 轮完整保留，3-10 轮摘要，10+ 轮只留实体骨架。
核心思路：离当前越近的信息越详细，越远的越抽象。"
```

---

### 4.4 记忆机制 ⭐

**场景题**
> "你的 Agent 有记忆吗？怎么实现多轮对话？"
> "长期记忆和短期记忆怎么区分？"

**一句话总结**
```
记忆分三层：情景记忆（对话历史）→ 语义记忆（知识）→ 程序记忆（偏好）。
不同层级的记忆有不同的存储、检索和更新策略。
```

**三层记忆模型**

```
第一层：情景记忆（Episodic Memory）——短期，自动
- 存储：原始对话历史（Message 表）
- 检索：按时间顺序加载全部
- 更新：每轮对话自动追加
- MemBrain 现状：✅ 已实现，chat.py 从 DB 加载全部历史

第二层：语义记忆（Semantic Memory）——长期，结构化
- 存储：提取的事实和摘要（MemoryRecord 表 / 向量库）
- 检索：基于当前问题的语义相似度
- 更新：定期提取 + 合并去重
- MemBrain 现状：⚠️ 部分实现（memory_service.py 有 extract_facts 和 summarize）
- 代码位置：app/services/memory_service.py

第三层：程序记忆（Procedural Memory）——长期，行为模式
- 存储：用户偏好、习惯、常用操作
- 检索：主动注入（"用户喜欢简洁回答"）
- 更新：观察用户行为后隐式学习
- MemBrain 现状：❌ 未实现

完整链路：
用户提问 → 检索情景记忆（历史上下文）
         → 检索语义记忆（相关事实）
         → 检索程序记忆（用户偏好）
         → 合并注入 → LLM 生成回答
```

**MemBrain memory_service.py 详解**

```
文件位置：app/services/memory_service.py

核心方法：
1. extract_facts(conv_id, history)
   - 从对话历史中提取事实三元组（实体 → 关系 → 实体）
   - 存入 memory_records 表（带 conv_id + 事实内容）
   - 触发条件：对话 ≥ 6 轮

2. summarize(conv_id, history)
   - 对当前对话生成摘要
   - 存入 conversation.summary 字段
   - 用于快速了解对话内容，不用翻全部历史

3. get_memory(conv_id)
   - 加载当前对话的记忆（摘要 + 事实）
   - 组装成文本注入到 chat.py 的 api_messages

改进方向：
- 跨对话记忆：当前只记忆单对话，用户关掉对话后记忆丢失
- 记忆合并：同一实体在不同对话中提取多次时，合并去重
- 记忆衰减：长期不访问的记忆降低权重或淘汰
```

**追问应对**

| 追问 | 回答 |
|------|------|
| "记忆存在哪？DB 还是向量库？" | 目前存在 SQLite（MemoryRecord 表）。扩展方向：事实存向量库（按语义检索相关性），摘要存 DB（按对话 ID 精确匹配） |
| "记忆怎么去重？" | 实体归一化——"字节跳动"和"ByteDance"映射到同一 ID。冲突时按时间戳取最新，或 LLM 判断哪个更准确 |
| "记忆满了怎么办？" | 分层淘汰：最近的记忆完整保留，旧的合并为摘要，最旧的丢弃。和上下文工程的滑动窗口策略一致 |

**话术模板（3 句）**
```
"Agent 记忆分三层——情景记忆存对话历史、语义记忆存提取的事实、
程序记忆存用户偏好。MemBrain 目前实现了前两层，
对话历史从 DB 加载，6 轮以上自动提取事实和生成摘要。
第三层程序记忆是改进方向——把'用户喜欢什么回答风格'这种偏好记录下来。"
```

---

### 5.1 概述

**面试官为什么考 System Design？**
- 验证你不是"只会调 API"——有没有系统架构思维
- 看你能不能把项目扩展到大流量场景
- 评估你的知识边界（不止会用，还知道为什么这么用）

**回答框架：3 句话公式**
```
当前现状 → 生产方案 → 选择理由
"目前 MemBrain 是单机部署，X 方面用的 Y 方案。
如果上线需要扩展到 Z 规模，我会采用 A + B 的组合方案。
选择 A 是因为 C（结合项目实际说理由）。"
```

**核心总结：投入产出比一览**

| 模块 | 面试价值 | 投入 | 说明 |
|------|----------|------|------|
| 缓存策略 | ⭐⭐⭐ | 已实现（语义缓存） | 三级架构 + 一致性 + 雪崩/穿透/击穿 |
| 限流 | ⭐⭐ | 需扩展（代码未实现） | 三层限流 + 算法对比 + 429 处理 |
| 降级策略 | ⭐⭐⭐ | 已实现（四层降级） | 项目亮点，熔断器 + 回退链扩展 |
| 横向扩展 | ⭐⭐⭐ | 需扩展（架构受限） | 三步路径：SQLite→MySQL→微服务 |
| 数据库选型 | ⭐⭐ | 部分实现（SQLite 开发中） | 对比表 + ORM 优势 + 迁移路径 |
| 安全与认证 | ⭐⭐ | 已实现（JWT+bcrypt） | 双 token + API Key 管理 + 审计 |

**6 维度一览表（扩展）**

| # | 维度 | 重要度 | MemBrain 关联度 | 面试频率 | 预备时长 |
|---|------|--------|----------------|----------|----------|
| 1 | 缓存策略 | ⭐⭐⭐ | 🔴 高（已实现语义缓存） | 几乎必问 | 0.5h（回顾代码） |
| 2 | 限流 | ⭐⭐ | 🟡 中（需扩展） | 常见 | 0.5h（概念理解） |
| 3 | 降级策略 | ⭐⭐⭐ | 🔴 高（已实现三层降级） | 几乎必问 | 0.5h（回顾代码） |
| 4 | 横向扩展 | ⭐⭐⭐ | 🟡 中（需扩展） | 高级岗必问 | 1h（理解架构） |
| 5 | 数据库选型 | ⭐⭐ | 🟡 中（SQLite→MySQL） | 常见 | 0.5h（对比记忆） |
| 6 | 安全与认证 | ⭐⭐ | 🔴 高（已实现 JWT） | 常见 | 0.5h（回顾代码） |

---

### 5.2 维度一：缓存策略 ⭐⭐⭐

**场景题**
> "1000 并发怎么扛？缓存怎么设计的？"
> "缓存穿透、缓存雪崩、缓存击穿怎么防？"

**MemBrain 现状**
```
目前实现了 Redis 语义缓存：
- 用户问题向量化 → 余弦相似度 ≥ 0.92 → 直接返回缓存
- TTL 1 小时自动过期
- Redis 不可用时自动跳过（try/except，零侵入）
- 缓存命中时完全跳过 LLM 调用，降低延迟和成本
```

**深入扩展：三级缓存架构**

面试时从"单层语义缓存"扩展到"三级缓存"，展现体系化思维：

```
第一级：本地 LRU 缓存（in-memory）
- 存最热门的 1000 条问答（如"你是谁"、"项目介绍"等固定问题）
- 毫秒级响应，零网络开销
- 用 lru_cache 或 collections.OrderedDict 实现
- 场景：同一个问题 1 秒内被问 100 次，不需要走 Redis

第二级：Redis 语义缓存（分布式）
- 当前已实现：向量化 → 余弦相似度 ≥ 0.92 命中
- 存高频问题 + 对应的 LLM 回答
- TTL 分级管理：
  · 事实类（"Python 列表怎么用"）→ TTL 24h
  · 时效类（"今天天气"）→ TTL 5min
  · 个性化（"我的笔记里有什么"）→ TTL 0（不缓存）

第三级：CDN / HTTP 缓存
- 静态资源、常见错误码、系统状态等
- Nginx 层缓存，反向代理级别
- MemBrain 目前无前端页面，不急需
```

**缓存一致性问题**
```
写穿透（Write-Through）：
- 每次回答写入 DB 后同步写缓存
- 当前做法：chat.py 流结束后 `semantic_cache.set()`
- 优点：实现简单；缺点：淘汰策略单一

失效策略：
- 主动失效：用户删除/修改文档 → 清除相关缓存
- 被动失效：TTL 到期自然淘汰
- 版本号：缓存带 data_version，数据更新时版本号 +1，旧缓存自动失效
```

**追问应对**

| 追问 | 回答 |
|------|------|
| "缓存穿透怎么防？" | 查询不存在的数据 → 缓存和 DB 都没有 → 请求穿透到 DB。方案：布隆过滤器（Bloom Filter），先在过滤器判断 key 是否存在，不存在直接返回 |
| "缓存雪崩怎么防？" | 大量缓存同时过期 → 大量请求打到 DB。方案：①TTL 加随机偏移（基础 TTL + random(0, 300)s）②本地缓存兜底 ③限流降级 |
| "缓存击穿怎么防？" | 热点 key 过期 → 高并发请求同时打到 DB。方案：①互斥锁（Mutex）——只有一个线程去查 DB，其他等待 ②热点 key 永不过期 + 后台异步刷新 |

**话术模板（3 句）**
```
"MemBrain 目前用 Redis 语义缓存，把用户问题向量化后在缓存中找语义相似的结果。
如果扩展到生产环境，我会设计三级缓存架构：本地 LRU 扛热点、Redis 语义缓存扛重复问题、
CDN 扛静态资源。
选择 Redis 是因为它天然支持分布式、TTL 淘汰，而且在项目中已经验证了语义匹配的可行性。"
```

---

### 5.3 维度二：限流 ⭐⭐

**场景题**
> "怎么防止接口被刷？"
> "恶意用户一直调你的 API 怎么办？"

**MemBrain 现状**
```
目前无限流机制（单机项目，用户只有自己）。
但架构预留了限流位置——app/routers/ 层可以无缝接入中间件。
```

**深入扩展：三层限流架构**

```
第一层：Nginx/IP 层面（网关层）
- 限制单 IP 每秒请求数（如 10 req/s）
- 超过则返回 429 Too Many Requests
- nginx.conf 配置 limit_req_zone
- 优点：在入口处拦截，不消耗应用资源

第二层：应用层面（用户级别）
- Redis 滑动窗口：每个 user_id 一个窗口
- 框架：slowapi（FastAPI 限流库）或自定义中间件
- 规则：普通用户 60 req/min，VIP 用户 300 req/min
- 实现简单的漏桶算法：队列大小 N，每秒消费 M 个请求

第三层：LLM API 层面（服务级别）
- Token bucket 算法：每分钟分配一定 token 数
- 消耗：每个 chat 请求消耗 1 token，每个搜索消耗 0.5 token
- 防止单个用户耗尽 API 配额
```

**算法对比（面试常考）**

| 算法 | 原理 | 优点 | 缺点 | 适用场景 |
|------|------|------|------|----------|
| 令牌桶 | 固定速率生成 token，消费 token 才能请求 | 支持突发流量 | 需要预填充 | LLM API 调用 |
| 滑动窗口 | 时间窗口内计数，过期自然滑动 | 实现简单，避免临界问题 | 边界精度不如令牌桶 | 用户级别限流 |
| 漏桶 | 队列缓冲，固定速率消费 | 流量绝对平滑 | 不能应对突发 | 消息队列消费 |

**追问应对**

| 追问 | 回答 |
|------|------|
| "429 之后客户端该怎么做？" | 读取 Retry-After 头，指数退避重试（第一次等 1s，第二次 2s，第三次 4s 直至上限 30s）。同时给用户友好提示："请求太频繁，请稍后再试" |
| "限流和降级什么关系？" | 限流是"不让请求进来"，降级是"请求进来了但给个次优结果"。通常限流在前（Nginx/网关），降级在后（应用层） |

**话术模板（3 句）**
```
"MemBrain 目前是单用户项目还没有限流，但架构上我计划了三层限流：
Nginx IP 限流挡外部攻击、Redis 滑动窗口控制用户频率、
令牌桶限制 LLM API 调用量。
如果面试的是高级岗位，可以补充说我会用令牌桶算法支持突发流量，
同时配合指数退避让客户端平滑降速。"
```

---

### 5.4 维度三：降级策略 ⭐⭐⭐

**场景题**
> "LLM API 挂了怎么办？你的系统怎么保证可用性？"
> "Neo4j 数据库连不上了会怎么样？"

**MemBrain 现状（这是你项目的亮点，重点讲）**
```
项目已经实现了四层降级：

第一层：Guardrails（工具调用校验）
- reasoning_node 只传 tools=TOOLS，不传额外指令
- LLM 可能构造不存在参数 → execute_tools_node 的 try/except 兜底

第二层：节点隔离（Node-level isolation）
- 每个检索节点独立 try/except
- RAG 失败不影响图谱，图谱失败不影响搜索
- 失败的节点只是缺少对应 context，不会炸掉整个请求

第三层：外部服务自动跳过
- Redis 不可用：chat.py 的 try/except 跳过语义缓存
- Neo4j 不可用：graph_retriever 返回 None，注入轮跳过
- Docker 非必需：每个服务都可独立运行

第四层：ReAct 安全网
- 最多 3 轮迭代，防止死循环
- LangGraph 全炸时降级为纯 LLM 聊天（chat.py 的 try/except）
- 用户至少能正常对话，体验不受影响
```

**深入扩展：熔断器模式（Circuit Breaker）**

```
三状态：
Closed（关闭）→ 正常调用
  ↓ 失败次数超过阈值 ↓
Open（断开）→ 直接返回 fallback，不实际调用
  ↓ 超时后 ↓
Half-Open（半开）→ 试探一个请求
  ↓ 成功 → Closed | 失败 → Open

阈值设计：
- 失败计数：连续 5 次失败 → Open
- 超时恢复：Open 状态保持 30s → Half-Open
- 半开试探：1 个请求试探，成功则关闭

回退链（Fallback Chain）：
LLM API 挂了 → 先用语义缓存（有缓存回答）
  → 再用模板回答（"系统暂时无法回答复杂问题"）
    → 最后返回 503（实在没办法了）
```

**追问应对**

| 追问 | 回答 |
|------|------|
| "熔断阈值怎么设？" | 取决于 SLA。如果要求 99.9% 可用性，连续 5 次失败（约 5 秒内）就熔断。阈值太低容易误伤（网络抖动），太高失去熔断意义。通常 3-10 次，配合错误率百分比更合理（如 30s 内错误率 > 50% 则熔断） |
| "半开恢复的判断标准？" | 一个试探请求成功 ≠ 完全恢复。建议连续 3 个试探请求成功才关闭熔断器，避免一次成功后的再次雪崩 |
| "哪些该降级哪些不该？" | 核心链路走降级（聊天功能必须有），非核心链路跳过。MemBrain 的划分：聊天是核心——LLM 挂了也要给用户反馈；语义缓存是非核心——Redis 挂了聊天继续 |

**话术模板（3 句）**
```
"MemBrain 项目本身已经实现了一整套降级策略——从节点级别的 try/except 隔离，
到外部服务自动跳过，再到整张图炸了以后降级为纯 LLM 聊天。
如果上生产，我会引入熔断器模式（Circuit Breaker），
让系统在异常恢复后自动恢复正常，不需要人工介入。"
```

---

### 5.5 维度四：横向扩展 ⭐⭐⭐

**场景题**
> "用户从 1 个变 1 万，你的系统怎么改？"
> "怎么支撑高并发？"

**MemBrain 现有限制（诚实说 + 补方案）**
```
当前限制：
1. SQLite 单文件数据库——写锁竞争，多进程并发读写会报错
2. router 懒加载在进程内存里——多进程各自有一份 router 实例，不一致
3. 检索和聊天在同一个进程——检索耗时阻塞聊天响应
4. 本地文件存储文档——多机部署需要共享存储
5. FAISS 索引在内存中——多进程各自维护一份，不一致
```

**深入扩展：三步扩展路径**

**Step 1：单体→SQLite→MySQL（数据层独立）**

```
当前架构：
Client → FastAPI(SQLite+FAISS+LLM) 

第一步改造：
Client → FastAPI → MySQL（主从）
                   → FAISS（只读副本同步）
                   → Redis（缓存集中）

改动最小：
- SQLAlchemy ORM 只需改连接字符串 (sqlite:// → mysql://)
- chat.py 业务逻辑完全不变
- FAISS 可以定时重建索引，或走共享文件系统
```

**Step 2：检索微服务化（计算层拆分）**

```
拆分后：
Client → FastAPI（聊天网关）→ Retrieval Service（RAG+图谱+搜索）
                              → LLM API
                              → Redis（缓存）

好处：
- 检索服务可以独立扩缩——检索密集时加机器
- 聊天服务无状态——可以水平扩展
- 检索失败不影响聊天服务的稳定性
```

**Step 3：无状态化 + 负载均衡（接入层扩展）**

```
架构：
Client → Nginx（负载均衡）→ Chat Service × N（无状态）
                            → Retrieval Service × M（有状态）
                              → FAISS（MMap 共享或分片）
                              → Neo4j 集群
                              → MySQL 主从

无状态化条件：
- Session 信息存 Redis，不存本地
- 文件存对象存储（S3/MinIO），不存本地磁盘
- 日志集中采集（ELK），不写本地文件
```

**追问应对**

| 追问 | 回答 |
|------|------|
| "负载均衡策略？" | Nginx 层用 IP Hash（粘性会话），应用层用 Round Robin。如果检索服务有状态，用一致性哈希（Consistent Hashing）减少节点变动时的缓存失效 |
| "FAISS 怎么分片？" | 方案一：所有进程共享一个 MMap 文件（只读）。方案二：分片索引，每个分片检索后合并结果。方案三：上专门的向量数据库（Milvus/Qdrant），把 FAISS 替换掉 |
| "数据分片怎么分？" | 按 user_id 哈希分片，每个用户的数据集中在一个分片。跨分片查询复杂，但 MemBrain 是个人知识库，天然按用户隔离 |

**话术模板（3 句）**
```
"目前 MemBrain 是单机架构，如果上线到生产环境，
我会分三步扩展：先把 SQLite 换成 MySQL（ORM 只需改连接字符串），
然后把检索服务拆成独立微服务可以独立扩缩，
最后做无状态化 + 负载均衡，支持水平扩展。
这个路径的好处是每一步都可以独立做，不需要一次性重构。"
```

---

### 5.6 维度五：数据库选型 ⭐⭐

**场景题**
> "为什么开发用 SQLite，上线切 MySQL？"
> "SQLAlchemy ORM 的优势在哪里？"

**对比表格**

| 特性 | SQLite | MySQL | PostgreSQL |
|------|--------|-------|------------|
| 部署 | 零配置（文件） | 需要服务 | 需要服务 |
| 并发写入 | 写锁，单写 | 行锁，高并发 | MVCC，极高并发 |
| 数据类型 | 基础类型 | 丰富 | 最丰富（JSON/Array/向量） |
| 全文搜索 | 支持（FTS5） | 支持 | 支持 |
| 地理位置 | 不支持 | 支持 | PostGIS 最强 |
| 适合场景 | 开发/嵌入式 | 中小型生产 | 复杂查询/分析型 |
| MemBrain 用途 | 开发环境 ✓ | 生产目标 | 可选（有 JSON 字段需求） |

**MemBrain 为什么用 SQLite 开发（面试话术）**
```
开发阶段选择 SQLite 是非常务实的决定：
1. 零配置——不需要安装数据库服务，pip install 完就能跑
2. 快速迭代——改模型直接删文件重建，不需要 migration
3. 单机够用——就我一个人用，SQLite 的并发完全够
4. SQLAlchemy ORM 抽象——切 MySQL 只需要改 database.py 的连接字符串

如果上线生产，切 MySQL 的改造成本极低，
因为所有 SQL 操作都走 SQLAlchemy 的 ORM。
```

**SQLAlchemy ORM 优势**

```
1. 数据库无关——切换数据库只需改连接 URL
2. 连接池管理——async 模式下用 AsyncSession，自动管理连接
3. 迁移支持——Alembic 集成，模型变更可追溯
4. 类型安全——声明式模型定义，IDE 友好
5. 异步支持——AsyncSession + asyncpg，不阻塞事件循环

当前 MemBrain 的 database.py 用 create_async_engine + async_sessionmaker，
切换数据库只需改 SQLALCHEMY_DATABASE_URL 配置。
```

**追问应对**

| 追问 | 回答 |
|------|------|
| "连接池多大合适？" | CPU 核心数 × 2 + 1（默认）。MemBrain 单机 4 核 → 9 个连接。MySQL 最多 100-200 连接，超了会影响 DB 性能 |
| "读写分离怎么做？" | SQLAlchemy 支持多个 bind——写走主库，读走从库。FastAPI 路由层根据请求方法判断读写 |
| "PostgreSQL 对比 MySQL？" | PostgreSQL 的 JSONB 和向量扩展（pgvector）对 MemBrain 有吸引力——可以直接在 PG 里做向量检索，不需要单独 FAISS。但迁移成本更高 |

**话术模板（3 句）**
```
"项目开发用 SQLite 是因为零配置，一个人用完全够。
SQLAlchemy ORM 做好了数据库抽象，切 MySQL 只需要改连接 URL。
这个选择体现了务实的工程思维——开发阶段效率优先，生产阶段切换到合适的数据库。"
```

---

### 5.7 维度六：安全与认证 ⭐⭐

**场景题**
> "你的 API 怎么保证安全？"
> "JWT 怎么防止被伪造？"
> "用户密码怎么存的？"

**MemBrain 现状**
```
- JWT 认证（access_token + 过期时间）
- 密码用 bcrypt 哈希存储（passlib.hash.bcrypt）
- FastAPI Depends 中间件校验 token
- CORS 配置
- 每个请求校验 user_id 归属（防止越权）
```

**深入扩展：生产级安全方案**

**JWT 增强**
```
当前 → 生产方案：
单 token → access_token（15min）+ refresh_token（7d）双 token
无刷新 → 无感刷新（refresh_token 换新 access_token）
token 永不过期 → 黑名单 + 短 TTL
payload 只存 user_id → payload 加 role、permissions

黑名单实现：
- Redis SET 存储被撤销的 token（在 TTL 内有效）
- 用户修改密码/主动退出 → 旧 token 加入黑名单
- 每次验证先查黑名单，在黑名单里直接拒绝
```

**API Key 管理**
```
原则：Key 不存代码、不存日志、不传前端

- 存环境变量（当前做法：.env 文件）
- 生产用 Vault / K8s Secret 管理（不落盘）
- 定期轮换（每 90 天自动更换）
- 权限最小化——每个 key 只开所需权限
- 审计——AgentTracer 可以扩展记录每个 key 的调用量
```

**操作审计**
```
MemBrain 的 AgentTracer 已经记录了每次路由决策和耗时。
扩展到安全审计只需加几个字段：
- user_id + IP + User-Agent
- 调用的 API + 参数
- 响应状态码 + 耗时
- 异常/错误信息

存储到专门的 audit_log 表，定期归档。
```

**追问应对**

| 追问 | 回答 |
|------|------|
| "密码强度怎么保证？" | 最少 8 位 + 大小写 + 数字 + 特殊字符。服务端校验 + 前端提示。避免弱密码（123456、password 等）和常见泄漏密码 |
| "防止 SQL 注入？" | SQLAlchemy ORM 的参数化查询天然防注入。如果写原生 SQL，用 `text()` 的绑定参数，不要字符串拼接 |
| "HTTPS 呢？" | 生产环境用反向代理（Nginx/Caddy）终结 TLS。免费证书 Let's Encrypt，自动续期。开发环境 HTTP 无问题 |

**话术模板（3 句）**
```
"MemBrain 目前用 JWT + bcrypt 做基础认证，每个请求校验 token 和用户归属防止越权。
生产环境我会加双 token 机制（15 分钟 access + 7 天 refresh），
配合 Redis 黑名单让 token 可撤销。
密码存储用的 bcrypt 哈希——这是行业标准，暴力破解成本极高。"
```

---

### 5.8 附录：面试回答速记卡

**缓存**
```
我们项目用 Redis 语义缓存，查询向量化后和缓存做相似度匹配。
生产环境我会设计三级缓存——本地 LRU 扛热点、Redis 抗重复、CDN 抗静态。
缓存穿透用布隆过滤器，雪崩加 TTL 随机偏移，击穿用互斥锁。
```

**限流**
```
三层限流：Nginx IP 限流 → Redis 滑动窗口用户限流 → 令牌桶 LLM 限流。
算法选令牌桶，支持突发流量又平滑输出，配合 429 + Retry-After + 指数退避。
```

**降级（MemBrain 亮点，重点练）**
```
我们项目已经实现了完整降级体系——
节点级别 try/except 隔离、外部服务自动跳过、整图炸了降纯 LLM 聊天。
生产加熔断器 Circuit Breaker，连续 5 次失败熔断 30 秒后半开试探。
我的原则：核心链路必须降级不降体验，非核心链路该跳就跳。
```

**横向扩展**
```
三步走：SQLite 换 MySQL → 检索服务拆微服务 → 无状态化 + 水平扩展。
每一步独立可做，不改业务代码。FAISS 分片或换 Milvus，Redis 集中会话和缓存。
```

**数据库选型**
```
开发用 SQLite 零配置，SQLAlchemy ORM 抽象好了，上线切 MySQL 只改 URL。
SQLAlchemy 的 async_session 支持高并发，连接池 + 读写分离架构可扩展。
```

**安全认证**
```
JWT 双 token 机制 + bcrypt 密码哈希 + Redis 黑名单 + API Key 环境变量管理。
认证、鉴权、审计三层分离，每个接口校验用户归属，防止水平越权。
```

---

**使用建议**：
1. **不要逐字背诵** — 理解每个维度的"为什么"，面试官 follow-up 时能灵活应对
2. **先讲项目现状，再扩展到生产方案** — 让面试官看到你的架构思维，而不是背答案
3. **埋点引导** — 在每个维度末尾留一个可以追问的点（如"缓存穿透这块我了解过布隆过滤器"），引导面试官问你准备好的内容
4. **结合 MemBrain 代码讲** — 提到具体文件（如 chat.py、graph.py）比纯理论有说服力

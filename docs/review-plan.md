# 三周面试复习计划

按"面试考什么"倒推，不是按"文件有什么"顺序读。

---

## 整体策略：三遍过

```
第一遍：搭骨架（3天）     → 知道项目有哪些模块、数据怎么流
第二遍：填血肉（7天）     → 每条话术能用自己的话讲出来
第三遍：模拟输出（7天）   → 对着镜子/录音讲，发现卡壳点
```

---

## 文件优先级

```
必须精读（面试话术本体）：
  interview-cards.md        ← 日常背卡，遮答案复述
  agent-interview-prep.md   ← Part 1-2（STAR + 核心考点）
  qa-records.md             ← 深度理解用

辅助理解（不用背，忘的时候查）：
  MEMBRAIN_GUIDE.md         ← 项目全景
  FUTURE_IMPROVEMENTS.md    ← 被问到"还有什么改进"时用

面试基本不问（技术细节）：
  代码文件（chat.py / nodes.py / graph.py 等）
```

---

## 第一遍：搭骨架（3天）

每天 1-2 小时，只读图表，不碰细节。

| 天 | 看什么 | 产出 |
|----|--------|------|
| Day1 | MEMBRAIN_GUIDE.md 十二阶段表 + 项目结构树 | 画出项目全貌：用户→FastAPI→LangGraph→3个知识源→LLM |
| Day2 | chat.py 6 步流程 + LangGraph astream 数据流 | 能讲出"用户发消息后，代码顺序做了什么" |
| Day3 | agent-interview-prep.md Part 1 考点总览 + Part 5 投入产出比表 | 知道哪些必考、哪些是亮点 |

**检验标准**：对着白纸画出项目架构图（框+箭头）。

---

## 第二遍：填血肉（7天）

按面试问法读，每天 1 个主题。

| 天 | 主题 | 核心材料 | 方法 |
|----|------|----------|------|
| Day4 | **项目 STAR 讲解** | qa-records Q1-Q10 + agent-interview-prep Part 2 | 3 句话讲清背景，2 分钟讲完整。面试第一题，最优先 |
| Day5 | **Agent 核心**（FC/ReAct/路由/工具） | agent-interview-prep Part 1 考点1-10 | 遮答案自己说，卡住再看 |
| Day6 | **RAG + 评估** | qa-records Q11-Q20 + 评估数据 | 说出 Recall@3=77.8%、优化方向 |
| Day7 | **记忆 + Guardrails** | agent-interview-prep Part 4.4 + qa-records 记忆相关 | 三层记忆 + 四层降级（项目亮点） |
| Day8 | **概念专项**（MCP/多Agent/上下文） | interview-cards.md Part 4 | 每张卡 3 句话，重点"和 MemBrain 的关系" |
| Day9 | **System Design 前 3 维度** | interview-cards.md Part 5 缓/限/降 | 每张卡 3 句话，重点"MemBrain 当前怎么做的" |
| Day10 | **System Design 后 3 维度** | interview-cards.md Part 5 横/数/安 | 同上 |

**方法**：interview-cards.md 遮答案自测，卡住再去原文翻。

---

## 第三遍：模拟输出（7天）

不用再读文件，全部是输出练习。

| 天 | 练习 | 时长 |
|----|------|------|
| Day11 | 录音讲 STAR（2分钟版本），听回放改 | 30min × 3 遍 |
| Day12 | Mock：搜"Agent 面试题"，随机抽 5 题回答并录音 | 1h |
| Day13 | 默画全架构图，边画边讲数据流 | 30min × 2 遍 |
| Day14 | Mock 深挖：找朋友或 AI 模拟，专攻追问 | 1h |
| Day15-17 | 投简历 + 复盘：面完立刻记录被问的问题 | -- |

---

## 时间分配建议

```
每天能投入：
  1h  → 跳过 Day11-17，只背核心话术
  2h  → 按上面计划走刚好
  3h+ → 缩短每轮天数，增加模拟次数

优先级（时间不够时）：
  🔴 STAR 项目讲解（面试第一题）
  🔴 Agent 核心考点（FC/ReAct/降级）
  🟡 System Design 缓存+降级
  🟢 数据库选型 / 安全认证（问得少）
```

---

## 各模块一句话速记

```
Part 4 概念：MMCM
  M — MCP：USB-C for Agent
  M — 多Agent：单够用不上市
  C — 上下文：近详远粗
  M — 记忆：三层抽屉

Part 5 系统设计：缓限降横数安
  缓 — 三级缓存：LRU→Redis→CDN
  限 — 三层限流：Nginx→App→LLM
  降 — 四层兜底：隔离→跳过→全炸→纯聊
  横 — 三步走：MySQL→微服务→无状态
  数 — 对比表：SQLite vs MySQL vs PG
  安 — 双token：15min+7d+黑名单
```

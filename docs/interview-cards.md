# 记忆卡片


---

## Part 4：概念专项

### MCP 协议

**Q: MCP 是什么？和 Tool Calling 什么关系？**
>
> A: MCP = Model Context Protocol，Agent 工具调用的标准化协议，类比 USB-C for Agent。
> 三个核心概念：Host（应用）、Client（会话）、Server（工具）。
> 和 Tool Calling 的关系：FC 是"LLM 调工具的能力"，MCP 是"工具怎么被发现的协议"，两者不在同一层。
> MemBrain 用 Tool Calling 已实现类似思想，接入 MCP 只需把三个检索工具包装成 MCP Server。

**Q: MCP 的竞争对手和坑？**
>
> A: 对手是 OpenAI GPT Actions（封闭）和 Google A2A（Agent-to-Agent）。
> MCP 是 Anthropic 提出的开源标准。
> 坑：①协议还新，生产案例少 ②每个工具一个 Server，部署成本增加 ③协议仍在演进。

---

### 多 Agent 协作

**Q: 什么时候需要多 Agent？什么时候不需要？**
>
> A: 单 Agent 够用就不上多 Agent。
> 需要多 Agent 的场景：①跨领域专业知识（财报+法规）②需要状态隔离 ③需要并行独立任务。
> MemBrain 用单 Agent 因为：个人助手范围有限、延迟敏感、状态管理简单。
> 核心原则：多 Agent 的价值是"专业分工 + 状态隔离"，不是"人多力量大"。

**Q: 多 Agent 有哪些协作模式？**
>
> A: 三种常见模式：
> ①Supervisor（管理者）— 一个总 Agent 拆任务，Worker 执行，适用复杂任务
> ②Pipeline（管线）— Agent A → B → C，适用有固定流程的任务
> ③Debate（辩论）— 多个 Agent 独立推理后交叉验证，适用高准确率场景
> MemBrain 如果扩展，会用 Supervisor + RAG/Graph/Web 三个 Specialist。

---

### 上下文工程

**Q: LLM 窗口有限，长对话怎么处理？**
>
> A: 核心思路不是在有限窗口塞更多，而是放最有效的信息。
> 四大策略：
> ①动态注入 — 先检索再筛选再组装，检索结果不超过 40% 窗口
> ②上下文压缩 — 长文本先总结再注入，而不是原文
> ③滑动窗口 — 固定最近 N 轮，超出则丢弃或压缩
> ④Token 预算 — 为每部分分配预算（system+记忆+检索+历史+当前=稳定）

**Q: 窗口满了丢哪些？**
>
> A: 丢的优先级：最早的历史 > 相似度低的检索 > 可精简的 system prompt。
> 保留的优先级：当前问题 > 最近的工具结果 > 用户明确提到的实体。
> 核心原则：离当前越近越详细，越远越抽象。
> 分层压缩：最近 3 轮完整 → 3-10 轮摘要 → 10+ 轮只留实体和主题。

---

### 记忆机制

**Q: Agent 记忆分几层？MemBrain 实现了哪些？**
>
> A: 三层记忆模型：
> ①情景记忆（Episodic）— 对话历史，短期自动 → MemBrain 已实现（DB 加载全部历史）
> ②语义记忆（Semantic）— 提取的事实和摘要，长期结构化 → 已实现（memory_service.py，6 轮以上触发 extract_facts + summarize）
> ③程序记忆（Procedural）— 用户偏好和行为模式 → 未实现
> 完整链路：提问 → 检索情景记忆 → 检索语义记忆 → 检索偏好 → 合并注入 → 回答。

**Q: 记忆怎么去重和淘汰？**
>
> A: 实体归一化 — "字节跳动"和"ByteDance"映射到同一 ID，冲突时取最新。
> 分层淘汰：最近的完整保留，旧的合并为摘要，最旧的丢弃。
> 和上下文工程的滑动窗口策略一致。

---

## Part 5：System Design

### 缓存策略

**Q: 1000 并发怎么扛？缓存怎么设计？**
>
> A: 三级缓存架构：
> ①本地 LRU — 存最热 1000 条（如固定问答），毫秒级，零网络
> ②Redis 语义缓存 — 问题向量化，余弦 ≥0.92 命中，TTL 分级（事实类 24h / 时效类 5min / 个性化不缓存）
> ③CDN — 静态资源
> MemBrain 当前实现了第二级（Redis 语义缓存 + TTL 1h + 不可用时自动跳过）。

**Q: 缓存雪崩、穿透、击穿怎么防？**
>
> A: 穿透（查不存在的数据）→ 布隆过滤器，不存在直接返回。
> 雪崩（大量同时过期）→ TTL 加随机偏移 + 本地缓存兜底 + 限流。
> 击穿（热点 key 过期高并发打 DB）→ 互斥锁（一个线程查 DB，其他等待）或热点 key 永不过期 + 后台异步刷新。

---

### 限流

**Q: 怎么防止接口被刷？**
>
> A: 三层限流：
> ①Nginx IP 限流（10 req/s），入口拦截不消耗应用资源
> ②Redis 滑动窗口用户限流（普通 60/min，VIP 300/min）
> ③令牌桶 LLM API 限流（每分钟分配 token，每个请求消耗 1 个）
> 算法对比：令牌桶支持突发、滑动窗口实现简单、漏桶流量绝对平滑。

**Q: 429 后客户端怎么做？**
>
> A: 读 Retry-After 头，指数退避（1s→2s→4s→...上限 30s）。
> 友好提示用户"请求太频繁，请稍后再试"。
> 限流和降级的关系：限流在入口不让请求进来，降级在应用层给次优结果。

---

### 降级策略

**Q: LLM API 挂了怎么办？MemBrain 怎么保证可用性？**
>
> A: （这是项目亮点，重点练）
> 四层降级：
> ①Guardrails 校验 — LLM 可能构造非法参数，try/except 兜底
> ②节点隔离 — 每个检索节点独立 try/except，RAG 失败不影响图谱
> ③外部服务自动跳过 — Redis 不可用跳过缓存，Neo4j 不可用跳过图谱
> ④ReAct 安全网 — 最多 3 轮防死循环，整图全炸降级为纯 LLM 聊天

**Q: 熔断器怎么设计？**
>
> A: 三状态：Closed（正常）→ Open（断开，直接返回 fallback）→ Half-Open（试探）。
> 阈值：连续 5 次失败 → Open，30s 后 → Half-Open，试探成功 → Closed，失败 → Open。
> 回退链：LLM 挂了 → 查语义缓存 → 模板回答 → 503。
> 核心原则：核心链路必须降级不降体验，非核心该跳就跳。

---

### 横向扩展

**Q: 用户从 1 个变 1 万，系统怎么改？**
>
> A: 三步走：
> ①SQLite → MySQL — ORM 只改连接 URL，业务代码不变
> ②检索拆微服务 — RAG+图谱+搜索独立，聊天服务无状态可水平扩展
> ③无状态化 + 负载均衡 — Session 存 Redis、文件存对象存储、日志集中采集
> 当前限制：SQLite 写锁、router 懒加载有状态、FAISS 在进程内存里。
> 核心思路：每一步独立可做，不改业务代码。

**Q: FAISS 怎么分片？负载均衡策略？**
>
> A: FAISS：方案一 MMap 共享（只读）→ 方案二分片索引 → 方案三换 Milvus/Qdrant。
> 负载均衡：Nginx IP Hash（粘性会话），应用层 Round Robin。
> 数据分片：按 user_id 哈希，个人知识库天然按用户隔离。
> 一致性哈希：检索服务有状态时用，减少节点变动缓存失效。

---

### 数据库选型

**Q: 为什么开发用 SQLite，上线切 MySQL？**
>
> A: 开发选 SQLite 是务实决定：零配置、快速迭代（删文件重建）、单机够用。
> SQLAlchemy ORM 抽象好了，切 MySQL 只改 database.py 的连接 URL。
> 对比：SQLite 写锁不可并发、MySQL 行锁高并发、PostgreSQL MVCC + pgvector。
> 连接池：CPU 核心数 × 2 + 1，MySQL 最多 100-200 连接。

**Q: 读写分离怎么做？**
>
> A: SQLAlchemy 支持多个 bind — 写走主库，读走从库。
> FastAPI 路由层根据请求方法判断读写（POST/PUT/DELETE 写，GET 读）。

---

### 安全与认证

**Q: API 怎么保证安全？JWT 怎么防伪造？**
>
> A: 当前：JWT + bcrypt + FastAPI Depends 校验 + 用户归属检查。
> 生产增强：双 token（15min access + 7d refresh） + Redis 黑名单（改密码/退出时撤销）+ 短 TTL。
> API Key：存环境变量不落盘，生产用 Vault/K8s Secret，每 90 天轮换。
> 密码：bcrypt 哈希（自带 salt + 慢哈希），最少 8 位 + 大小写 + 数字 + 特殊字符。

**Q: 水平越权怎么防？**
>
> A: 每个请求校验 user_id 归属 — 查对话时 where(conversation.user_id == current_user.id)。
> AgentTracer 扩展审计：记录 user_id + IP + API + 参数 + 状态码 + 耗时。
> 原则：认证、鉴权、审计三层分离。

---

## 速记口诀

```
Part 4: MMCM
  M — MCP：USB-C for Agent
  M — 多Agent：单够用不上市
  C — 上下文：近详远粗
  M — 记忆：三层抽屉

Part 5: 缓限降横数安
  缓 — 三级缓存：LRU→Redis→CDN
  限 — 三层限流：Nginx→App→LLM
  降 — 四层兜底：隔离→跳过→全炸→纯聊
  横 — 三步走：MySQL→微服务→无状态
  数 — 对比表：SQLite vs MySQL vs PG
  安 — 双token：15min+7d+黑名单
```

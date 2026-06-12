# MemBrain 个人知识助手 — 搭建指南

一个企业级架构的个人知识助手：上传文档 → RAG 检索 + Neo4j 知识图谱 + 网络搜索 → LLM 一键回答。
数据全在本地，由你自己掌控。

---

## 技术选型

| 组件 | 选择 | 理由 |
|------|------|------|
| 数据库 | SQLite (Stage 1-4) → 后期可切 MySQL | SQLite 零配置，适合开发阶段 |
| LLM | DeepSeek API (OpenAI 兼容) | 和已有 deepseek_agent 项目一致 |
| Embedding | sentence-transformers (local) | 离线可用 |
| 向量库 | FAISS (local) | 几千条数据足够，无需额外服务 |
| 图数据库 | Neo4j (Docker) | 和已有 deepseek_agent 项目一致 |
| 缓存 | Redis (Docker) | 语义缓存需要 |
| Agent 框架 | LangGraph | 和已有 deepseek_agent 项目一致 |

---

## 核心设计决策（不可违背）

- `app/core/config.py` 用 pydantic-settings 统一管理，不从 `os.environ` 直接读取
- 所有函数签名用 `async def`（为后续测试覆盖做铺垫）
- API 版本化：`/api/v1/chat`（养成习惯）
- 依赖注入：所有 service 的函数式依赖（不搞类实例单例）
- Stage 1-4 用 SQLite + aiosqlite，后续按需切换
- LLM 客户端用 openai 库（DeepSeek 兼容），不用 httpx 直接发

---

## 最终项目结构（含已建和规划）

```
membrain/
├── app/
│   ├── __init__.py
│   ├── main.py                    ← FastAPI 应用入口（已建）
│   ├── core/                      ← 基础设施（已建）
│   │   ├── config.py              ← 配置管理
│   │   ├── database.py            ← 数据库引擎 + WAL 模式
│   │   ├── security.py            ← JWT 签发与验证
│   │   ├── hashing.py             ← bcrypt 密码哈希
│   │   ├── logger.py              ← 日志配置
│   │   └── middleware.py          ← 请求日志中间件
│   ├── models/                    ← ORM 模型（已建）
│   │   ├── user.py                ← 用户模型
│   │   ├── conversation.py        ← 对话模型
│   │   ├── message.py             ← 消息模型
│   │   ├── document.py            ← 文档模型
│   │   └── chunk.py               ← 分块模型
│   ├── schemas/                   ← Pydantic 模型（已建）
│   │   ├── auth.py                ← 认证相关
│   │   ├── chat.py                ← 聊天相关
│   │   └── document.py            ← 文档相关
│   ├── services/                  ← 业务逻辑（已建）
│   │   ├── auth.py                ← 注册登录
│   │   ├── chat.py                ← 聊天 + RAG 集成
│   │   └── document_service.py    ← 文档管理
│   ├── routers/                   ← API 路由（已建）
│   │   ├── auth.py                ← 认证端点
│   │   ├── chat.py                ← 聊天端点
│   │   └── document.py            ← 文档端点
│   ├── rag/                       ← RAG 管线（已建）
│   │   ├── chunker.py             ← 文本分块
│   │   ├── embedder.py            ← 向量化
│   │   ├── vector_store.py        ← FAISS 索引
│   │   └── retriever.py           ← 检索 + 组装
│   ├── graph/                     ← Neo4j 知识图谱（已建）
│   ├── tools/                     ← 网络搜索工具（已建）
│   ├── agent/                     ← LangGraph 智能路由（已建）
│   ├── cache/                     ← 语义缓存（已建）
│   │   ├── redis_client.py       ← Redis 连接管理
│   │   └── semantic_cache.py     ← 语义缓存（向量→SCAN→余弦匹配）
├── data/                          ← 本地数据目录（已建）
│   ├── documents/                 ← 上传文件存储
│   └── faiss_index.bin            ← FAISS 索引文件
├── requirements.txt               ← 依赖声明（已建）
├── .env.example                   ← 环境变量模板（已建）
├── pytest.ini                     ← pytest 配置（asyncio_mode = auto）
├── tests/                         ← 基础测试（已建）
│   ├── conftest.py               ← fixtures（db_session/client/auth_token）
│   ├── test_auth.py              ← 认证测试（7 个）
│   └── test_chat.py              ← 聊天测试（2 个）
├── MEMBRAIN_GUIDE.md              ← 本文件（唯一进度源头）
├── TROUBLESHOOTING.md             ← 问题排查记录
├── FUTURE_IMPROVEMENTS.md         ← 待优化清单
└── qa-records.md                  ← 问答记录
```

---

## 六阶段路线图

| Stage | 主题 | 目标 | 状态 |
|-------|------|------|------|
| 1 | 骨架 + 核心聊天 | 注册、登录、JWT 鉴权、流式聊天、会话管理 | ✅ 完成 |
| 2 | 知识库上传 + RAG | 上传文档 → 分块 → FAISS 索引 → 基于知识库问答 | ✅ 完成 |
| 3 | 知识图谱 (Neo4j) | 概念提取 + 关系图 + Text2Cypher 查询 | ✅ 完成 |
| 4 | 网络搜索工具 | SerpAPI 搜索 → 上下文注入 | ✅ 完成 |
| 5 | LangGraph 智能路由 | 统一入口 → 自动分流（直接聊 / RAG / 图谱 / 搜索） | ✅ 完成 |
| 6 | 缓存 + 企业级收尾 | Redis 语义缓存、Docker Compose 一键启动、基础测试 | 📋 进行中（Step 1/2/4 完成，Step 3 待 Docker） |

---

## 当前进度

- **当前阶段**：Stage 6 — 缓存 + 企业级收尾 ✅
  - Step 1（Redis 配置）✅
  - Step 2（语义缓存核心）✅
  - Step 3（Docker Compose 整合）✅ — Neo4j + Redis 通过 `docker compose up -d` 启动并验证成功
  - Step 4（基础测试）✅ — 9/9 passed
- **所有阶段**：Stage 1-6 全部完成 ✅
- **后续**：AutoDL 部署 ✅（已部署至 AutoDL 实例，API 运行正常）
  - 详见下方 "部署到 AutoDL" 章节

---

## 协作方式

### 流程
1. **讲解设计** — 每个 Stage 开始前解释要做什么、为什么、架构图和数据流
2. **动手编码** — 用户创建文件、写代码，AI 指导不代写
3. **验收** — 验收题验证理解，通过才算 Stage 完成

### 自动更新规则
每个 Stage/Step 完成后自动更新以下内容（无需提醒）：
1. 本文件（MEMBRAIN_GUIDE.md）— 更新进度和文件说明
2. `qa-records.md` — 追加关键 Q&A
3. memory 中的 `project_membrain.md` — 更新进度状态

---

## Stage 1：项目骨架与用户认证 ✅

### 说明
Stage 1 搭建项目基础架构，实现用户注册、登录、基础聊天功能。

### 实施步骤

#### Step 1: `app/core/config.py` — 配置管理
- **做什么**：用 pydantic-settings 定义所有配置项（数据库、JWT、LLM、日志）
- **为什么这么干**：所有配置集中管理，不从 `os.environ` 四处读取。改配置只改一个文件，测试时也容易 mock

#### Step 2: `app/core/database.py` — 数据库引擎
- **做什么**：创建异步 SQLAlchemy 引擎、session 工厂、`get_db` 依赖、`init_db` 启动函数
- **为什么这么干**：`get_db` 用 `yield` + `try/commit/rollback` 模式，确保每个请求的事务边界清晰

#### Step 3: `app/core/hashing.py` — 密码哈希
- **做什么**：封装 bcrypt 的 hash 和 verify
- **为什么这么干**：密码绝不存明文，bcrypt 自带 salt + 慢哈希，暴力破解成本高

#### Step 4: `app/core/security.py` — JWT 认证
- **做什么**：JWT 签发 + 校验，`get_current_user` 依赖
- **为什么这么干**：JWT 无状态，token 里包含 user_id，解码即得，不需要服务端存 session

#### Step 5: `app/core/logger.py` — 日志
- **做什么**：配置带格式/级别的日志器
- **为什么这么干**：统一日志格式方便排查问题，级别可配（开发时 DEBUG，线上 INFO）

#### Step 6: `app/core/middleware.py` — 请求日志中间件
- **做什么**：记录每个请求的方法、路径、状态码、耗时
- **为什么这么干**：中间件一次编写全局生效，比在每个路由里加日志更干净

#### Step 7: `app/models/` — 数据模型（User → Conversation → Message）
- **做什么**：三个 ORM 模型形成链式一对多关系
- **为什么这么干**：
  - `hashed_password` 不叫 `password`——看到字段名就知道存的是哈希值
  - `cascade="all, delete-orphan"`——删用户自动删对话，删对话自动删消息
  - `content` 用 Text 类型——VARCHAR 有长度限制，AI 回复可能很长

#### Step 8: `app/schemas/` — Pydantic 模型
- **做什么**：定义 API 请求/响应的数据格式和校验规则
- **为什么这么干**：`response_model` 自动过滤敏感字段，`field_validator` 做自定义校验

#### Step 9: `app/services/` — 业务逻辑
- **做什么**：封装注册/登录/聊天的业务逻辑
- **为什么这么干**：路由层只做 HTTP 解析，不做业务判断。消息先 `flush()` 存库再调 LLM，即使 API 失败用户输入也不丢

#### Step 10: `app/routers/` — API 路由
- **做什么**：定义 HTTP 端点和路由
- **为什么这么干**：路由层只做"传话筒"：取参数 → 调 Service → 返回结果

#### Step 11: `app/main.py` — 应用入口
- **做什么**：创建 FastAPI 实例，挂载中间件、路由，管理生命周期
- **为什么这么干**：用 `lifespan` 替代旧式 `@app.on_event`，启动/关闭成对出现不会遗漏

#### Step 12: `requirements.txt` + `.env.example`
- **做什么**：声明依赖和环境变量模板
- **为什么这么干**：`pip install -r requirements.txt` 一键安装，`.env.example` 告知需要配置哪些参数

### 新增文件说明

#### `app/core/` — 基础设施层
| 文件 | 作用 | 为什么加 |
|------|------|----------|
| `config.py` | pydantic-settings 配置管理（DB/JWT/LLM/日志） | 所有配置集中管理，不从 os.environ 四处读取 |
| `database.py` | 异步 SQLAlchemy 引擎 + session 工厂 + get_db 依赖 | 异步引擎不阻塞事件循环，yield 模式确保事务边界 |
| `hashing.py` | bcrypt 密码哈希与验证 | 密码绝不存明文，bcrypt 自带 salt + 慢哈希 |
| `security.py` | JWT 签发 + 校验 + get_current_user 依赖 | JWT 无状态，token 里包含 user_id，解码即得 |
| `logger.py` | 带格式/级别的日志器配置 | 统一日志格式方便排查 |
| `middleware.py` | 请求日志中间件 | 一次编写全局生效，比在每个路由加日志干净 |

#### `app/models/` — 数据模型层
| 文件 | 作用 | 为什么加 |
|------|------|----------|
| `user.py` | User ORM 模型（id, email, username, hashed_password, timestamps） | 存储用户认证信息 |
| `conversation.py` | Conversation ORM 模型（id, user_id, title, timestamps） | 管理对话会话，将一组消息归组 |
| `message.py` | Message ORM 模型（id, conversation_id, role, content, created_at） | 持久化聊天历史，支持流式保存 |

#### `app/schemas/` — 请求/响应模型层
| 文件 | 作用 | 为什么加 |
|------|------|----------|
| `auth.py` | 注册/登录/用户信息的 Pydantic 模型 + 字段校验 | 确保 API 输入输出格式正确 |
| `chat.py` | 聊天请求/响应/对话列表的 Pydantic 模型 | 定义聊天 API 的数据契约 |

#### `app/services/` — 业务逻辑层
| 文件 | 作用 | 为什么加 |
|------|------|----------|
| `auth.py` | AuthService：注册检查+密码哈希、登录验证 | 将认证逻辑从路由层抽离 |
| `chat.py` | ChatService：对话管理、消息持久化、DeepSeek API 流式调用 | 核心业务逻辑 |

#### `app/routers/` — API 路由层
| 文件 | 作用 | 为什么加 |
|------|------|----------|
| `auth.py` | POST /register, POST /token, GET /me | 用户认证的三个端点 |
| `chat.py` | POST /chat (SSE 流), GET /conversations | 聊天和对话管理 |

### API 端点

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/api/v1/auth/register` | 注册新用户 | 否 |
| POST | `/api/v1/auth/token` | 登录获取 JWT | 否 |
| GET | `/api/v1/auth/me` | 获取当前用户 | 是 |
| POST | `/api/v1/chat` | 流式聊天 | 是 |
| GET | `/api/v1/conversations` | 对话列表 | 是 |
| GET | `/` | 健康检查 | 否 |

---

## Stage 2：知识库上传 + RAG ✅

### 说明
Stage 2 让 AI 能回答用户私有知识的问题：用户上传文档 → 自动分块向量化 → 聊天时自动检索相关内容 → AI 基于知识库回答。

### 核心改动
用 openai 库替代 httpx 调用 DeepSeek API（之前 httpx 手动拼请求，改用官方库更稳定）。

### 实施步骤

#### Step 1: `app/core/config.py` — 新增 RAG 配置项
- **做什么**：在 Settings 类中添加 embedding 模型路径、FAISS 索引路径、分块参数等配置
- **为什么这么干**：所有 RAG 参数集中管理，后续调参改一个文件即可
- **新增字段**：`EMBEDDING_MODEL`, `FAISS_INDEX_PATH`, `DOCUMENTS_DIR`, `CHUNK_SIZE`(500), `CHUNK_OVERLAP`(50), `TOP_K_RETRIEVAL`(3)

#### Step 2: `app/models/document.py` + `app/models/chunk.py` — 文档与分块模型
- **做什么**：Document 记录文档元数据，Chunk 记录每个分块的内容和来源
- **为什么这么干**：
  - FAISS 只存向量 → chunk_id，原文存在 DB 里
  - 删除文档时需要同时清理 FAISS 和 DB
  - Document 的 status 字段让上传异步处理成为可能
- **注意**：要在 `app/models/__init__.py` 中导出新模型

#### Step 3: `app/rag/chunker.py` — 文档分块
- **做什么**：将长文本按递归策略切分成 500 字符左右的片段，片段间重叠 50 字符
- **为什么这么干**：直接喂整篇文档会超上下文窗口。用 `RecursiveCharacterTextSplitter` 按 `\n\n` → `\n` → 句号 → 逗号 逐级分割，不会在句子中间切断

#### Step 4: `app/rag/embedder.py` — 向量化
- **做什么**：加载 SentenceTransformer 模型，将文本转为 768 维向量
- **为什么这么干**：`normalize_embeddings=True` + FAISS 内积索引 = 余弦相似度。模型本地加载，离线可用
- **注意**：SentenceTransformer 不支持 async，同步调用

#### Step 5: `app/rag/vector_store.py` — FAISS 索引
- **做什么**：管理 FAISS 向量索引（创建、添加、搜索、删除、保存、加载）
- **为什么这么干**：用 `IndexFlatIP`（内积）而非 `IndexFlatL2`（欧氏距离），normalize 后内积 = 余弦相似度。FAISS 原生不支持删除单个向量，需要用 `IndexIDMap2` + `remove_ids`

#### Step 6: `app/rag/retriever.py` — RAG 检索 + 上下文组装
- **做什么**：接收用户问题 → 向量化 → FAISS 检索 → 取 chunk 原文 → 组装 RAG prompt 上下文
- **为什么这么干**：将"检索"和"组装"封装在一起。上下文加上来源标记，限制总 token 数约 2000

#### Step 7: `app/schemas/document.py` — 文档 API 的 Pydantic 模型
- **做什么**：定义文档上传响应、文档列表响应的数据格式
- **模型**：`DocumentResponse`（id, filename, file_size, file_type, chunk_count, status, created_at）

#### Step 8: `app/services/document_service.py` — 文档业务逻辑
- **做什么**：文档上传（保存文件→分块→嵌入→索引）、列表查询、删除
- **为什么这么干**：上传流程顺序执行，文件落盘后才开始处理。删除文档三步：删文件 → 删 DB 记录 → 清 FAISS 索引

#### Step 9: `app/routers/document.py` — 文档路由
- **做什么**：定义文档相关的 HTTP 端点
- **端点**：`POST /upload`、`GET /`、`DELETE /{id}`（均需登录）

#### Step 10: 重构 `app/services/chat.py` — openai 库 + RAG 集成
- **做什么**：将 httpx 流式调用替换为 `openai.AsyncOpenAI` 库；在调 LLM 之前插入 RAG 检索步骤
- **为什么这么干**：openai 库更稳定，自动处理重试和超时。RAG 上下文以 system 消息形式插入 messages 列表

#### Step 11: `app/main.py` + `app/core/database.py` — 串联所有组件
- **做什么**：`database.py` 中 import Document 和 Chunk 模型；`main.py` 注册 document router，启动时初始化 RAG 组件

#### Step 12: `requirements.txt` — 新增依赖
- **新增**：sentence-transformers、faiss-cpu、PyMuPDF、openai、numpy

### 新增文件说明

#### `app/rag/` — RAG 管线模块
| 文件 | 作用 | 为什么加 |
|------|------|----------|
| `chunker.py` | 文档分块（RecursiveCharacterTextSplitter 递归分割） | 大文档不能直接塞进 LLM context |
| `embedder.py` | SentenceTransformer 文本向量化（text2vec-base-chinese） | 将文本转为向量才能做语义搜索 |
| `vector_store.py` | FAISS 索引管理（添加/搜索/删除/持久化） | 高效的向量相似度搜索 |
| `retriever.py` | RAG 检索 + 上下文组装 | 编排查询→向量化→搜索→取原文→拼 prompt |

#### `app/models/` — 数据模型层
| 文件 | 作用 | 为什么加 |
|------|------|----------|
| `document.py` | Document ORM 模型（用户上传的文档元数据） | 追踪用户上传了哪些文档、处理状态 |
| `chunk.py` | Chunk ORM 模型（文档分块后的原文） | FAISS 只存向量→chunk_id 映射，原文需要从 DB 查 |

#### `app/schemas/document.py` — 文档 API 模型
定义文档上传/列表/详情/删除的 Pydantic 请求响应格式。

#### `app/services/document_service.py` — 文档业务逻辑
核心编排：上传 → 分块 → 向量化 → 存 FAISS → 存 DB 的完整流程。

#### `app/routers/document.py` — 文档 API 路由
| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/api/v1/documents/upload` | 上传文档（支持 txt/md/pdf） | 是 |
| GET | `/api/v1/documents/` | 文档列表 | 是 |
| GET | `/api/v1/documents/{id}` | 文档详情 | 是 |
| DELETE | `/api/v1/documents/{id}` | 删除文档 | 是 |

### 数据流

#### 文档上传
```
POST /documents/upload (multipart)
  → DocumentService.upload()
    → 保存文件到 data/documents/
    → 创建 Document(status=processing)
    → TextChunker.chunk_text() → chunks[]
    → Embedder.embed(chunks) → vectors[]
    → 保存 Chunks 到 DB
    → VectorStore.add(vectors, chunk_ids)
    → 更新 Document(status=ready)
  → 返回 Document(id, filename, chunk_count, status)
```

#### RAG 聊天
```
POST /chat {messages: [...]}
  → ChatService.chat()
    → 1. 获取/创建对话
    → 2. 保存用户消息
    → 3. 加载历史
    → 4. RAGRetriever.retrieve(用户最新问题)
         → Embedder.embed_query(query) → query_vec
         → VectorStore.search(query_vec, top_k=3) → chunk_ids
         → 从 DB 查 chunk 原文
         → build_rag_context() → context_str
    → 5. 组装 api_messages = [system, rag_context, history...]
    → 6. openai 流式调用
    → 7. 保存回复
```

### API 端点（完整）

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/api/v1/auth/register` | 注册新用户 | 否 |
| POST | `/api/v1/auth/token` | 登录获取 JWT | 否 |
| GET | `/api/v1/auth/me` | 获取当前用户 | 是 |
| POST | `/api/v1/chat` | 流式聊天（支持 RAG） | 是 |
| GET | `/api/v1/conversations` | 对话列表 | 是 |
| POST | `/api/v1/documents/upload` | 上传文档 | 是 |
| GET | `/api/v1/documents/` | 文档列表 | 是 |
| GET | `/api/v1/documents/{id}` | 文档详情 | 是 |
| DELETE | `/api/v1/documents/{id}` | 删除文档 | 是 |
| GET | `/` | 健康检查 | 否 |

---

## Stage 3：知识图谱 (Neo4j) ✅

### 说明
知识图谱让 AI 能理解实体之间的关系。文档上传时自动提取实体关系存入 Neo4j，聊天时通过 Text2Cypher 查询图谱，补全 RAG 无法处理的关系类问题。

### 架构变更
```
文档上传 → RAG (FAISS) ← 已有
         → Neo4j 知识图谱 ← 新增
聊天 → RAG 检索 + 图谱检索 → 合并上下文 → LLM 回答
```

### 实施步骤

#### Step 1: `docker-compose.yml` + Neo4j 容器 ✅
- **做什么**：定义 Neo4j 5-community 容器配置（端口 7474/7687、认证、数据持久化）
- **为什么这么干**：Neo4j 在 Windows 上原生安装麻烦，容器化部署省事
- **状态**：已完成，`docker compose up -d` 一键启动

#### Step 2: `app/core/config.py` — 新增 Neo4j 配置项 ✅
- **做什么**：在 Settings 类中添加 Neo4j 连接参数（URL、用户名、密码、数据库名）
- **新增字段**：`NEO4J_URL`(bolt://localhost:7687)、`NEO4J_USERNAME`(neo4j)、`NEO4J_PASSWORD`、`NEO4J_DATABASE`(neo4j)

#### Step 3: `app/graph/neo4j_conn.py` — Neo4j 连接管理 ✅
- **做什么**：封装 Neo4j 异步驱动（初始化、查询、关闭），使用 `neo4j` Python 驱动
- **为什么这么干**：langchain_neo4j 封装太多不需要的功能，直接用驱动更灵活

#### Step 4: `app/graph/entity_extractor.py` — LLM 实体关系提取 ✅
- **做什么**：用 DeepSeek API 从文本中提取 (实体, 关系, 实体) 三元组
- **为什么这么干**：LLM 提取比 NLP 库泛化能力更强，准确率更高
- **设计**：低温度(0.1)确保确定性输出，JSON 格式返回

#### Step 5: `app/main.py` — 启动时初始化 Neo4j ✅
- **做什么**：在 lifespan 中初始化 Neo4j 连接，存入 `app.state.neo4j`
- **为什么这么干**：连接失败不阻止应用启动，没 Docker 时照常运行

#### Step 6: `app/services/document_service.py` — 上传文档同步图谱 ✅
- **做什么**：在原有 RAG 流程之后，调用 EntityExtractor 提取三元组并存入 Neo4j
- **为什么这么干**：用 `MERGE` 避免重复创建，异常只记录不阻塞上传

#### Step 7: `app/graph/graph_retriever.py` — Text2Cypher 检索 ✅
- **做什么**：获取图 schema → LLM 将问题转 Cypher → 执行查询 → 格式化结果
- **为什么这么干**：Text2Cypher 让 AI 能基于图结构自适应地查询知识图谱

#### Step 8: `app/services/chat.py` — 集成图谱上下文 ✅
- **做什么**：在 RAG 检索之后插入图谱检索，合并上下文后发给 LLM
- **为什么这么干**：RAG 负责模糊搜索，图谱负责精确关系查询，两者互补

#### Step 9: `requirements.txt` — 新增依赖 ✅
- **新增**：`neo4j==5.23.0`

### 新增文件说明

#### `app/graph/` — 知识图谱模块
| 文件 | 作用 | 为什么加 |
|------|------|----------|
| `neo4j_conn.py` | Neo4j 异步连接管理（初始化/查询/关闭） | 封装驱动，统一管理连接生命周期 |
| `entity_extractor.py` | LLM 提取实体关系三元组 | 将非结构化文本转为结构化图谱数据 |
| `graph_retriever.py` | Text2Cypher 图谱查询 | 将自然语言问题转为 Cypher 查询 |

#### 根目录文件
| 文件 | 作用 | 为什么加 |
|------|------|----------|
| `docker-compose.yml` | Neo4j 容器编排（端口/认证/持久化） | 容器化部署，Windows 友好 |

### 数据流

#### 文档上传 → 知识图谱
```
POST /documents/upload
  → DocumentService.upload()
    → ... 原有 RAG 流程 ...
    → EntityExtractor.extract_triples(text)  ← 新增
      → LLM 提取 (实体, 关系, 实体) 三元组
    → Neo4j MERGE 实体和关系
  → 返回 Document
```

#### 图谱问答
```
POST /chat
  → RAGRetriever.retrieve(query)  ← 已有
  → GraphRetriever.retrieve(query)  ← 新增
    → 获取图 schema
    → LLM: 问题 → Cypher
    → 执行 Cypher 查询 Neo4j
    → 格式化为文本
  → 合并 [RAG上下文] + [图谱上下文] → LLM
  → 流式回答
```

### API 端点（当前完整）
| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/api/v1/auth/register` | 注册新用户 | 否 |
| POST | `/api/v1/auth/token` | 登录获取 JWT | 否 |
| GET | `/api/v1/auth/me` | 获取当前用户 | 是 |
| POST | `/api/v1/chat` | 流式聊天（支持 RAG + 图谱） | 是 |
| GET | `/api/v1/conversations` | 对话列表 | 是 |
| POST | `/api/v1/documents/upload` | 上传文档 | 是 |
| GET | `/api/v1/documents/` | 文档列表 | 是 |
| GET | `/api/v1/documents/{id}` | 文档详情 | 是 |
| DELETE | `/api/v1/documents/{id}` | 删除文档 | 是 |
| GET | `/` | 健康检查 | 否 |

---

## Stage 4：网络搜索工具 ✅

### 说明
引入 SerpAPI 网络搜索，让 AI 能获取实时信息（新闻、最新资料等）。每次聊天自动搜索用户问题，将结果作为上下文喂给 LLM（非 Function Calling 模式）。

### 实施步骤

#### Step 1: `.env` + `app/core/config.py` — SerpAPI 配置 ✅
- **做什么**：在 `.env` 中添加 `SERPAPI_API_KEY`，在 `config.py` 中添加对应的配置字段
- **为什么这么干**：API Key 放 `.env` 不提交到 Git，敏感信息与代码分离

#### Step 2: `app/tools/web_search.py` — 创建网络搜索工具 ✅
- **做什么**：封装 WebSearchTool 类，调用 SerpAPI 返回 title/snippet/link 结构化结果
- **为什么这么干**：独立工具类职责单一，chat.py 直接调用即可

#### Step 3: `app/services/chat.py` — 集成到聊天服务 ✅
- **做什么**：在图谱检索之后、LLM 调用之前插入网络搜索结果
- **为什么这么干**：模式与 RAG/图谱一致——try 包住、异常只 warning、不阻塞主流程
- **消息上下文顺序**：`[0]system → [1]RAG → [2]图谱 → [3]网络搜索 → [4..]历史`

---

## Stage 5：LangGraph 智能路由 ✅

### 说明
引入 LangGraph StateGraph，由 LLM（classify 节点）判断用户问题需要哪些知识源，动态选择检索路径，替代原来"无脑全跑"的固定管线。

### 架构变更
```
固定管线（Stage 4 及以前）：
用户问题 → RAG检索 → 图谱检索 → 网络搜索 → LLM 回答
           每次都全跑，浪费额度、增加延迟

LangGraph 智能路由（Stage 5）：
用户问题 → classify (LLM 决策)
             ├→ [] → 直接 LLM 回答（问候语、闲聊）
             ├→ ["rag"] → RAG → 合并 → LLM
             ├→ ["graph"] → 图谱 → 合并 → LLM
             ├→ ["web"] → 搜索 → 合并 → LLM
             └→ ["rag","web"] → RAG + 搜索并行 → 合并 → LLM
```

### 实施步骤

#### Step 1: `requirements.txt` + `app/agent/state.py` ✅
- **requirements.txt**: 新增 `langgraph` 依赖
- **state.py**: 定义 `AgentState` TypedDict（question, rag/graph/web_context, selected_sources）
- **为什么这么干**：LangGraph 节点间通过 TypedDict 传递状态，类型安全可追溯

#### Step 2: `app/agent/nodes.py` — 节点函数 ✅
- **reasoning_node**: ReAct 推理节点，LLM 用 Tool Calling 自主决定调工具还是直接回答
- **execute_tools_node**: 根据 selected_sources 并行执行选中工具，结果写回 state 供下一轮推理
- **为什么这么干**：ReAct 循环替代一次性 classify 路由，LLM 可以多轮思考和验证

#### Step 3: `app/agent/graph.py` — StateGraph 构建 ✅
- **做什么**：用 `StateGraph(AgentState)` 编排 2 个节点（reasoning + execute_tools）
- **条件边**：`reasoning → route_decision` 根据 `selected_sources`：`__answer__` → END，否则 → execute_tools
- **循环边**：execute_tools → reasoning（最多 3 轮）
- **依赖注入**：`functools.partial` 注入 embedder/vector_store/db/neo4j 到 execute_tools_node

#### Step 4: `app/services/chat.py` — LangGraph 集成 ✅
- **做什么**：用 `router.ainvoke()` 替换原来的 3 个 try/except 检索块
- **懒加载**：`request.app.state.router` 首次聊天时构建
- **安全兜底**：ainvoke 异常时只 warning 不阻塞聊天

### 新增文件说明

#### `app/agent/` — LangGraph 智能路由模块
| 文件 | 作用 | 为什么加 |
|------|------|----------|
| `state.py` | AgentState TypedDict（节点间共享状态） | LangGraph 节点间通过 TypedDict 传递状态 |
| `nodes.py` | 5 个节点函数（classify/rag/graph/web/collect） | 每个节点职责单一，通过 partial 注入依赖 |
| `graph.py` | StateGraph 构建 + route_decision 条件边 | 编排节点、定义数据流、编译可执行图 |

### 数据流

```
用户问题 → classify_node (LLM 分析)
              │
              ├→ selected_sources = []
              │   → collect → LLM 直接回答（问候语、闲聊）
              │
              ├→ selected_sources = ["rag"]
              │   → rag_node → 返回 rag_context → collect → LLM
              │
              ├→ selected_sources = ["graph"]
              │   → graph_node → 返回 graph_context → collect → LLM
              │
              ├→ selected_sources = ["web"]
              │   → web_node → 返回 web_context → collect → LLM
              │
              └→ selected_sources = ["rag", "web"]
                  → rag_node + web_node 并行执行 → collect → LLM

上下文顺序（与 Stage 4 保持一致）：
[0] system → [1] RAG → [2] 图谱 → [3] 搜索 → [4..] 历史
```

### 验收结果

| 场景 | 输入 | classify 返回 | 验证结果 |
|------|------|---------------|----------|
| 问候语 | "你好" | `[]` | ✅ 直接 LLM 回复，不调检索 |
| 知识问题 | "这个项目是关于什么的" | `["rag"]` | ✅ 走 RAG 检索带上下文回复 |
| 实时问题 | "最近的新闻" | `["web"]` | ✅ 走网络搜索（需 SerpAPI Key） |
| 复杂问题 | 多源组合 | `["rag","web"]` | ✅ 并行执行多个检索 |

---

## Stage 6：缓存 + 企业级收尾 📋（进行中）

### 目标
Redis 语义缓存、Docker Compose 一键启动、基础测试。

### 知识点
语义缓存、向量相似度计算、Docker 编排、pytest 异步测试

### 实施步骤

#### Step 1: `app/core/config.py` + `docker-compose.yml` — Redis 配置 ✅
- **做什么**：在配置中添加 `REDIS_URL`，在 docker-compose 中添加 `redis` 服务（redis:7-alpine, port 6379, appendonly 持久化）
- **为什么这么干**：Redis 配置集中管理，Docker 一键启动无需手动安装

#### Step 2: `app/cache/` — 语义缓存核心 ✅
- **做什么**：实现三个核心函数
  - `redis_client.py`：`init_redis` / `close_redis` 连接管理
  - `semantic_cache.py`：`get` / `set` / `clear` 语义缓存
- **为什么这么干**：
  - 问题向量化后 SCAN 遍历所有缓存条目，余弦相似度 ≥0.92 命中
  - Redis Hash 存 4 个字段：`vec`（base64+pickle 序列化）、`question`、`answer`、`ts`
  - `decode_responses=True` 与 pickle bytes 的冲突通过 base64 编码解决
  - TTL 1 小时自动过期
- **chat.py 集成**：第 3.5 步查缓存（命中直接返回），第 6 步写缓存（LLM 回复后）

#### Step 3: Docker Compose 整合 ✅
- **做什么**：编排所有依赖服务（Neo4j + Redis + 应用），单命令启动
- **状态**：已完成，`docker compose up -d` 同时启动 Neo4j + Redis，应用启动日志确认两者连接成功

#### Step 4: `tests/` — 基础测试 ✅（9/9 passed）
- **做什么**：搭建 pytest 异步测试框架，覆盖认证和聊天核心流程
- **测试文件**：
  - `conftest.py`：3 个 fixtures
    - `db_session`（autouse）：内存 SQLite + `dependency_overrides[get_db]`，每个测试独立数据库
    - `client`：`ASGITransport` + `AsyncClient`，不启动 uvicorn 毫秒级测试
    - `auth_token`：先注册再登录，返回 JWT
  - `test_auth.py`：7 个测试（注册成功/重复注册/登录成功/错误密码/获取用户/无 token/错误 token）
  - `test_chat.py`：2 个测试（SSE 流式响应/问候语正常）
- **关键技巧**：`app.dependency_overrides[get_db]` 替换测试数据库，不影响 `membrain.db`

### 进度总结

| Step | 内容 | 状态 | 备注 |
|------|------|------|------|
| 1 | Redis 配置 | ✅ | config.py + docker-compose.yml |
| 2 | 语义缓存 | ✅ | 3 函数 + chat.py 集成 |
| 3 | Docker Compose | ✅ | 已通过 docker-compose 启动 Neo4j + Redis |
| 4 | 基础测试 | ✅ | 9/9 passed |

---

## 部署到 AutoDL

### 环境说明

AutoDL 实例特点：
- **系统盘** — 临时存储，关机后清空（conda 环境、pip 包都在这）
- **`/root/autodl-tmp/`** — 持久化存储，重启不丢（项目代码放这）
- **国内网络** — huggingface.co 被墙，需设置镜像

### 部署步骤

#### 1. 连接实例

```bash
ssh root@<实例IP> -p <端口号>
```

#### 2. 创建 conda 环境（AutoDL 默认 Python 3.8，项目需要 3.10+）

```bash
conda create -n membrain python=3.10 -y
conda activate membrain
```

> conda 环境 ≈ 独立的 Python 文件夹，互不干扰。建一次后每次只需 `conda activate membrain`，不需要重建。

#### 3. 拉代码 + 装依赖

```bash
cd /root/autodl-tmp/
git clone https://github.com/<用户名>/membrain.git
cd membrain
pip install -r requirements.txt
```

#### 4. 配置 .env

在项目目录创建 `.env`，填入：
- `LLM_API_KEY` — DeepSeek API Key（必需）
- `SERPAPI_API_KEY` — 搜索 API Key（可选）
- `DATABASE_URL=sqlite+aiosqlite:///./membrain.db` — SQLite 无需额外服务
- `SECRET_KEY`、`LOG_LEVEL`、`DEBUG` 等

> Neo4j 和 Redis 无需配置，没 Docker 时 app 自动跳过，不影响核心聊天功能。

#### 5. 下载 Embedding 模型（需设置 HuggingFace 镜像）

```bash
export HF_ENDPOINT=https://hf-mirror.com
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('shibing624/text2vec-base-chinese')"
```

> **坑**：不设镜像的话 huggingface.co 连不上，应用启动会卡在模型下载重试 5 次后失败。

#### 6. 启动服务

```bash
cd /root/autodl-tmp/membrain
conda activate membrain
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

预期输出：
```
✅ 数据库初始化完成
✅ RAG 组件初始化完成
⏭️ Neo4j 跳过（无 Docker）
✅ Redis 连接成功
✅ Uvicorn running on http://0.0.0.0:8000
```

#### 7. AutoDL 端口映射（外部访问）

在 AutoDL 控制台 → 实例详情 → 「端口映射」：
- 容器端口：`8000`
- 复制生成的外网地址 → 浏览器访问 `http://<外网地址>/docs` 即可看到 Swagger API 文档

### 常用操作

**下次连接时**：
```bash
conda activate membrain
cd /root/autodl-tmp/membrain
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**更新代码**：
```bash
cd /root/autodl-tmp/membrain
git pull
# 如依赖有变：pip install -r requirements.txt
# 重启服务
```

---

## 面试准备阶段（当前）

### 目标
以面试 Agent 开发岗位为目标，深化项目核心能力。Stage 1-6 已完成封闭，以下步骤在此基础上增强。

| Step | 主题 | 目标 | 状态 |
|------|------|------|------|
| 1 | Function Calling / Tool Calling | 替换 classify prompt 路由为 LLM 自主工具调用 | ✅ 完成 |
| 2 | ReAct 循环 | 实现思考→行动→观察的多轮推理 | ✅ 已完成 |
| 3 | 评估 & 可观测性 | Agent 行为追踪 + 追踪记录 API | ✅ 已完成 |

---

### Step 1: Function Calling / Tool Calling ✅

**说明**：将当前 classify 节点的 prompt 路由（LLM 输出 `["rag"]` 等文本标签）替换为 OpenAI Tool Calling（LLM 通过 `tools=tools` 参数自主决定调什么工具）。

**为什么这么做**：
- Prompt 路由的 LLM 只是"回答问题"，不知道自己有工具可用
- Tool Calling 的 LLM 主动选择调工具，返回标准化的 tool_calls 格式
- Function Calling 是 Agent 面试最高频考点

**改动文件**：
- 新建 `app/agent/tools.py` — 定义 3 个工具的 OpenAI schema
- 修改 `app/agent/nodes.py` — classify_node 传 tools 参数，解析 tool_calls
- 不变：state.py、graph.py、chat.py、各检索节点
- 修复 `app/rag/embedder.py` — 加 `local_files_only=True` 避免模型加载时联网超时

**验证结果**（2026-06-10）：

| 场景 | 输入 | 路由结果 | 状态 |
|------|------|---------|:----:|
| 问候语 | "你好" | 缓存命中（无需工具） | ✅ |
| 文档问题 | "文件里写了什么" | `rag_search` → 源=`['rag']` | ✅ |
| 实时问题 | "现在几点了" | `web_search` → 源=`['web']` | ✅ |
| 关系问题 | "张三和李四是什么关系" | `graph_query` + `rag_search` → 源=`['graph', 'rag']` | ✅ |

注意：关系问题同时触发了 graph + rag，说明 LLM 能智能判断需要多个知识源联合查询。

---

### Step 2: ReAct 循环 ✅

**说明**：在 LangGraph 中实现完整的 reasoning → execute → reasoning 循环，替代旧版"一次 classify + 一次检索"的单轮模式。

**实现**：
- `app/agent/tools.py` — 定义 3 个工具的 OpenAI Tool Calling schema（rag_search / graph_query / web_search）
- `app/agent/nodes.py` — `reasoning_node`（LLM + tools 参数决策）+ `execute_tools_node`（asyncio.gather 并行执行）
- `app/agent/graph.py` — 条件边 `route_decision` 判断 `__answer__` → END 还是循环回 reasoning
- `app/agent/state.py` — 新增 `messages`（记录工具调用历史）+ `iteration`（轮次计数，最多 3 轮防死循环）

**ReAct 流程**：
```
第1轮: reasoning(question, history=[], iteration=0) → LLM选graph_query → sources=["graph"]
       → execute_tools(sources=["graph"]) → 查到结果
       → state: {messages:[tool_call, tool_result], iteration:1}

第2轮: reasoning(question, [tool_call, tool_result], iteration=1)
       → LLM看到结果，觉得够了 → 不选工具 → __answer__ → END
```

**两层架构**：ReAct 只负责检索决策，实际回答由 chat.py 另起 LLM 调用生成（含 rag_context / graph_context / web_context 上下文）。检索与生成分离，各自独立优化。

**验证结果**（2026-06-11）：

| 场景 | 行为 | 状态 |
|------|------|:----:|
| 问候语 | 不调工具直接回答 | ✅ |
| 文档问题 | 调 rag_search → 循环一次 → 回答 | ✅ |
| 实时问题 | 调 web_search → 循环一次 → 回答 | ✅ |
| 关系问题 | 调 graph_query + rag_search 并行 → 回答 | ✅ |
| API 超时 | 降级为全源检索，不崩溃 | ✅ |

### Step 3: 评估 & 可观测性 ✅

**说明**：添加 Agent 行为追踪，每次 LangGraph 路由完成后记录 question / sources / rounds / duration / context_used，持久化到 DB 并提供 API 查询。

**实现**：
- `app/models/agent_trace.py` — 追踪记录模型（question、sources_selected、rounds、duration_ms、context_used）
- `app/services/agent_tracer.py` — `AgentTracer.record()` 封装保存逻辑，异常只 warning 不阻塞主流程
- `app/routers/trace.py` — `GET /api/v1/agent/traces?limit=20` 查看最近追踪记录（需登录）
- `app/schemas/trace.py` — API 响应格式
- `app/services/chat.py` — LangGraph 调用后自动记录，带耗时统计

**效果**：每次聊天后日志输出 `【Agent追踪】问题='张三' 源=['graph'] 轮数=1 耗时=320ms`，同时数据存入 `agent_traces` 表，可通过 API 查询。

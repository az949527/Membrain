# MemBrain Q&A 记录

## Stage 1: 骨架 + 核心聊天

### Q1: 密码字段为什么叫 hashed_password 不叫 password？
- **标准回答**：看到字段名就知道存的是哈希值，不是明文。如果叫 password 容易让人误会存的是密码原文
- **知识点**：数据库设计、安全编码规范

### Q2: 注册登录为什么用 JWT 不用 session？
- **标准回答**：JWT 无状态，token 里包含 user_id，解码即得，不需要服务端存 session。适合小项目，零额外基础设施。缺点是无法主动让 token 失效
- **知识点**：认证机制、JWT vs Session

### Q3: 聊天为什么用 SSE 不用 WebSocket？
- **标准回答**：SSE 基于 HTTP，兼容性好，不需要升级握手。只需要服务端→客户端的单向流，SSE 天然适合。用 StreamingResponse 十几行代码实现。WebSocket 需要状态管理、心跳、重连，复杂度高
- **知识点**：实时通信、SSE vs WebSocket

### Q4: ChatService 为什么要先存消息再调 API？
- **标准回答**：如果先调 API 再存，API 调用失败用户消息就丢了。先存保证用户输入一定不丢。`flush()` 写入事务但不提交，异常被捕获后 generator 正常结束不往上抛，`get_db()` 看到没异常就 commit
- **知识点**：异常处理、数据一致性、事务管理

### Q5: 为什么每次都从 DB 加载历史，而不是用客户端传的 messages？
- **标准回答**：客户端不可信，用户可能篡改历史消息。每次从 DB 加载更安全
- **知识点**：安全设计、前后端信任边界

### Q6: conversation_id 怎么传给客户端的？
- **标准回答**：ChatService 在 yield 第一个 token 之前先 yield 一条 `__conversation_id__:{id}` 特殊消息。`_sse_wrap` 拦截这个前缀不发送给客户端，等流结束时拼到 done 事件里发给客户端
- **知识点**：SSE 协议、进程间通信

### Q7: 如果 DeepSeek API 超时抛异常，用户消息还会被保存吗？
- **标准回答**：会被保存。因为异常被 try/except 捕获了没有往上抛，`get_db()` 看到没异常就 commit
- **知识点**：异常捕获、事务提交、防御性编程

### Q8: 为什么分层设计（routers/services/models/schemas）？
- **标准回答**：每层职责单一。路由层不知道密码怎么 hash，服务层不知道 HTTP 状态码怎么写。将来换数据库或加 OAuth，只改对应层即可
- **知识点**：分层架构、单一职责原则

---

## Stage 2: 知识库上传 + RAG

### Q1: chunk 模型为什么没有 updated_at 字段？
- **标准回答**：chunk 一旦创建就不会再变了。文档重新上传 → 旧的 chunk 全部删除，新的 chunk 重新生成。而 Document 的 status 会从 processing → ready/failed，需要 updated_at
- **知识点**：数据库设计、字段选择标准

### Q2: Document 的 status 字段怎么理解？
- **标准回答**：跟踪文档上传后的处理进度：上传 → processing（正在分块向量化）→ ready（可用于 RAG）→ failed（处理失败）。未来改成异步处理时这个字段是关键
- **知识点**：状态机设计、异步处理流程

### Q3: @staticmethod 是什么？
- **标准回答**：不需要访问类的任何数据，直接能调用的方法。调用时不需要创建对象：`TextChunker.chunk_text("...")`。归类到类下面是为了组织结构清晰
- **知识点**：Python 面向对象、静态方法 vs 实例方法

### Q4: RecursiveCharacterTextSplitter 怎么工作的？
- **标准回答**：按分隔符列表逐级尝试分割：先按段落(\n\n)、再按行(\n)、再按句号(。)、逗号(，)、空格，保证在自然边界处切分。比自己写 split 考虑边界情况更全面
- **知识点**：文本分块策略、langchain 工具使用

### Q5: chunk_text 的参数有哪些？
- **标准回答**：text（原始文本，必填）、chunk_size（目标块大小，默认 500）、chunk_overlap（重叠字符数，默认 50）。返回 list[str]
- **知识点**：分块策略、参数设计

### Q6: FAISS 只搜索不存储吗？向量存 DB？
- **标准回答**：FAISS 既搜索也存储。向量存 FAISS 索引文件（.bin）中，DB 只存 chunk 原文和元数据。FAISS 负责高效向量近似最近邻检索，DB 负责关系型查询。两者互补
- **知识点**：RAG 架构、向量检索、FAISS vs DB

### Q7: FAISS 的存储过程写在哪？
- **标准回答**：vector_store.py 提供 add()（加入内存索引）和 save()（写回磁盘）。调用在 document_service.py：上传文档 → chunker 分块 → embedder 转向量 → vector_store.add() → vector_store.save()。同时 chunk 原文存 DB
- **知识点**：代码流程、service 层职责、RAG 流水线

### Q8: result.scalars().all() 怎么理解？
- **标准回答**：select(Chunk).where(...) 生成 SQL，self.db.execute() 执行返回 Result 对象。.scalars() 把每行原始数据映射成 Chunk ORM 实例，.all() 取出所有行返回 list[Chunk]。对比：result.all() 返回 list[Row] 需用下标取值，scalars() 后可直接 chunk.content
- **知识点**：SQLAlchemy ORM、Result 对象、scalars() 映射

### Q9: 什么是 Pydantic 模型？为什么要分层处理？
- **标准回答**：Pydantic 是 Python 数据校验库，定义数据结构 + 自动校验类型。FastAPI 集成后自动做类型校验、字段校验、响应过滤、生成 OpenAPI 文档。分层处理（上传/详情/列表用不同 Response）是因为：每个接口只需返回对应字段，减少传输量；避免暴露内部敏感字段（如 file_path）；前端能明确知道每个接口返回什么
- **知识点**：Pydantic、数据校验、API 契约、接口设计

### Q10: Pydantic 模型里 BaseModel、Field、datetime、Optional 分别干嘛？
- **标准回答**：BaseModel 是基类，继承后才有自动校验；Field 给字段加额外约束（如 min_length=1）；datetime 是 Python 内置时间类型，Pydantic 自动把字符串转成 datetime 对象；Optional[str] 表示字段可选，等价于 str | None
- **知识点**：Pydantic、Python 类型注解、数据校验

### Q11: document_service.py 如何串联之前写的 RAG 组件？
- **标准回答**：upload() 流程：①校验文件类型 → ②存原始文件 → ③创建 Document 记录(status=processing) → ④_extract_text() 提取文本 → ⑤TextChunker.chunk_text() 分块 → ⑥Embedder.embed() 向量化 → ⑦保存 Chunk 到 DB(两次 flush: 先拿 doc.id, 再拿 chunk.id) → ⑧VectorStore.add()+save() 存 FAISS → ⑨更新 status=ready → commit。try/except 包整个流程，任一失败 rollback + status=failed
- **知识点**：RAG 管线、Service 层编排、事务管理、组件协作

---

## 运维与排错

### 启动服务
**Q**: 如何启动服务？
**A**:

**方式一（推荐 — 终端默认 Python 是 3.13 时）**：
```bash
cd D:/pythonProject/git/membrain
export HF_ENDPOINT=https://hf-mirror.com
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**方式二（终端默认不是 Python 3.13 时，直接指定 3.13 路径）**：
```bash
cd D:/pythonProject/git/membrain
export HF_ENDPOINT=https://hf-mirror.com
"C:/Users/46458/AppData/Local/Programs/Python/Python313/python.exe" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**方式三（Windows cmd 不支持 export）**：
```bash
cd D:\pythonProject\git\membrain
set HF_ENDPOINT=https://hf-mirror.com
"C:/Users/46458/AppData/Local/Programs/Python/Python313/python.exe" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**方式四（虚拟环境激活后）**：
```bash
cd D:\pythonProject\git\membrain
D:\pythonProject\git\membrain\.venv\Scripts\activate
set HF_ENDPOINT=https://hf-mirror.com
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 重启服务
**Q**: 什么时候需要重启，怎么重启？
**A**:
**需要重启的情况**：修改代码后、数据库锁住报 500、邮箱已被注册。

步骤：
```bash
# 1. 杀所有 python 进程
taskkill /F /IM python.exe          # Windows cmd（单斜杠）
taskkill //F //IM python.exe        # Git bash

# 2. 清数据（邮箱被注册、RAG 检索不到时执行）
del membrain.db membrain.db-wal membrain.db-shm data\faiss_index.bin      # Windows
rm -f membrain.db membrain.db-wal membrain.db-shm data/faiss_index.bin    # Git bash

# 3. 重启
cd D:/pythonProject/git/membrain
export HF_ENDPOINT=https://hf-mirror.com
uvicorn app.main:app --port 8000
```
**不用重启的情况**：Swagger 授权过期（重新登录拿 token 即可）、AI 回答不对（改 system prompt）。

### SQLite 数据库锁
**Q**: 注册/上传/聊天报 500，日志显示 database is locked
**A**:
- **原因 1**：`uvicorn --reload` 启动两个进程同时抢 SQLite 写锁
- **原因 2**：进程被 taskkill 强杀后 WAL 文件（.db-wal/.db-shm）残留
- **解决**：`app/core/database.py` 加 WAL 模式 + `busy_timeout=30000` + `NullPool`，且不用 `--reload`
- **如果已经锁死**：删除所有 `*.db*` 文件 + FAISS 索引，重启

### RAG 检索不到内容
**Q**: 上传成功但聊天时 AI 回答"无法访问文件内容"
**A**:
- **原因**：服务器重启后 FAISS 索引与 DB 数据不一致。FAISS 索引文件存磁盘（.bin），SQLite DB 存 chunk 原文和元数据。如果只重建 DB 不删 FAISS，旧 chunk_id 还在 FAISS 索引里
- **解决**：同时删除 `membrain.db*` 和 `data/faiss_index.bin`，一起重建

### Swagger UI 授权失败
**Q**: Authorize 后仍返回 401 无效认证凭据
**A**: JWT token 过期，重新登录拿新 token

### 邮箱已被注册
**Q**: 注册提示邮箱已被注册
**A**: 删除 `membrain.db` 文件（及其 WAL 文件），重启服务自动重建

### 聊天接口 400
**Q**: POST /api/v1/chat 返回 "There was an error parsing the body"
**A**: 路由参数 `request: Request = None` 与 body 解析冲突，调整参数顺序

### HuggingFace 连接超时
**Q**: 服务启动卡在 embedding 模型下载
**A**: 国内网络屏蔽 huggingface.co，设置环境变量 `HF_ENDPOINT=https://hf-mirror.com`

### Python 3.8 类型语法
**Q**: `list[str]` 报 TypeError: 'type' object is not subscriptable
**A**: Python 3.8 不支持 `list[str]` 语法，文件顶部加 `from __future__ import annotations`

---

## 概念补充

### SQLite WAL 模式
**Q**: WAL 模式如何解决并发问题？
**A**: WAL（Write-Ahead Logging）允许读操作不阻塞写操作。读操作读旧的 DB 文件，写操作写 WAL 日志，两者互不干扰。配合 `busy_timeout=30000` 让 SQLite 等待 30 秒而不是立即报错，再加上 `NullPool` 确保每次获取新连接而不是复用池连接。三个措施一起解决 SQLite 并发问题。

### FAISS 索引与 DB 一致性
**Q**: 为什么 FAISS 索引和 DB 数据会不一致？
**A**: FAISS 索引文件存磁盘（.bin），SQLite DB 存 chunk 原文和元数据。如果只重建 DB 不删 FAISS，旧 chunk_id 还在 FAISS 索引里，查出来的是过期的 chunk_id。删除文档或重建 DB 时必须同时操作两者。

### Windows 终端 curl 差异
**Q**: Windows 终端 curl 有哪些坑？
**A**: ①PowerShell 的 `curl` 是 Invoke-WebRequest 别名，用 `curl.exe` 才是真 curl；②cmd 不支持单引号，必须用双引号；③cmd 不支持 `\` 行续符，命令要写在一行；④cmd 发送中文 JSON 要用 `-d @file.json` 方式（文件 UTF-8 编码），直接写中文会 GBK 编码乱码。

### HTTP Header vs Body
**Q**: HTTP 请求的头部和体各负责什么？
**A**: Header 传元数据（Content-Type、Authorization、Content-Length），Body 传实际数据（JSON、文件）。类比：Header 是信封上的信息，Body 是信封里的信。

### 如何评价 RAG 检索质量
**Q**: 如何评价 RAG 检索质量？
**A**: 三个维度：①相似度分数——FAISS 返回的内积值（余弦相似度），越接近 1 越相关，低于 0.3 基本不相关；②chunk 内容是否包含答案所需信息；③top-k 个结果中相关结果的比例。当前待优化点：按 chunk_index 排序（应改为按相似度排序）、缺少相似度阈值、缺少 BM25 混合检索。

---

## 测试流程

### curl 命令行测试

> **系统差异提醒**：
> - Windows cmd：直接用 `curl`，JSON 内引号用 `\"` 转义
> - Windows PowerShell：`curl` 是内置别名，必须写 `curl.exe`
> - Git bash / Linux：直接用 `curl`，支持单引号

#### Git bash / Linux 版
```bash
# 1. 注册
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","username":"test","password":"123456"}'

# 2. 登录拿 token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"123456"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 3. 上传文件
echo "test" > /tmp/test.txt
curl -s -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/test.txt"

# 4. RAG 聊天
curl -s -N -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"文件里写了什么？"}]}'
```

#### Windows PowerShell 版
```powershell
# 1. 注册
$body = '{"email":"test@test.com","username":"test","password":"123456"}'
curl.exe -s -X POST http://localhost:8000/api/v1/auth/register -H "Content-Type: application/json" -d $body

# 2. 登录拿 token
$body = '{"email":"test@test.com","password":"123456"}'
$resp = curl.exe -s -X POST http://localhost:8000/api/v1/auth/token -H "Content-Type: application/json" -d $body
$TOKEN = ($resp | ConvertFrom-Json).access_token

# 3. 上传文件
"测试内容" | Out-File -Encoding UTF8 test.txt
curl.exe -s -X POST http://localhost:8000/api/v1/documents/upload -H "Authorization: Bearer $TOKEN" -F "file=@test.txt"

# 4. RAG 聊天
$chat = '{"messages":[{"role":"user","content":"文件里写了什么？"}]}'
curl.exe -s -N -X POST http://localhost:8000/api/v1/chat -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d $chat
```

#### Windows cmd 版
> cmd 不支持 `\` 换行，每条命令必须写在一行。不支持单引号，JSON 内双引号要用 `\"` 转义。

```cmd
:: 1. 注册
curl -s -X POST http://localhost:8000/api/v1/auth/register -H "Content-Type: application/json" -d "{\"email\":\"test@test.com\",\"username\":\"test\",\"password\":\"123456\"}"

:: 2. 登录拿 token
curl -s -X POST http://localhost:8000/api/v1/auth/token -H "Content-Type: application/json" -d "{\"email\":\"test@test.com\",\"password\":\"123456\"}"
:: 从返回结果中复制 access_token 值

:: 3. 上传文件
echo 测试内容>test.txt
curl -s -X POST http://localhost:8000/api/v1/documents/upload -H "Authorization: Bearer <粘贴TOKEN>" -F "file=@test.txt"

:: 4. RAG 聊天（中文必须用 @file.json，直接写会编码错误）
:: 先创建 chat.json（UTF-8 编码），内容: {"messages":[{"role":"user","content":"文件里写了什么？"}]}
curl -s -N -X POST http://localhost:8000/api/v1/chat -H "Authorization: Bearer <粘贴TOKEN>" -H "Content-Type: application/json" -d @chat.json
```

### Swagger UI 测试流程
**Q**: 如何用 Swagger UI 测试全链路？
**A**:
1. 打开 http://localhost:8000/docs
2. 注册：`POST /api/v1/auth/register` → `{"email":"test@test.com","username":"test","password":"123456"}`
3. 登录拿 token：`POST /api/v1/auth/token` → `{"email":"test@test.com","password":"123456"}` → 复制 `access_token`
4. 授权：点右上角 Authorize → 输入 `Bearer <token>` → Authorize → Close
5. 上传：`POST /api/v1/documents/upload` → 选 .txt 文件 → Execute（返回 status:"ready" 即成功）
6. RAG 聊天：`POST /api/v1/chat` → `{"messages":[{"role":"user","content":"文件里写了什么？"}]}` → Execute

---

## Stage 3: 知识图谱 (Neo4j)

### Q1: 图数据库和关系型数据库的区别？
- **标准回答**：关系型数据库（SQLite）存表，适合"用户列表"这种整齐数据；图数据库（Neo4j）存节点和关系，适合"谁认识谁、什么依赖什么"这种带关系的数据
- **知识点**：数据库分类、图 vs 关系型

### Q2: Neo4j 为什么用 Docker 部署？
- **标准回答**：Windows 上原生安装 Neo4j 麻烦（需要 Java 环境、配置服务），Docker 一行命令搞定。数据通过 volume 映射到本地目录，容器删了数据不丢
- **知识点**：Docker 部署、数据持久化

### Q3: RAG 和知识图谱的关系？
- **标准回答**：两者互补。RAG 存原文做模糊搜索（"这篇文章讲了什么"），图谱存实体关系做精确查询（"张三在哪工作"）。同一份文档两边都存，聊天时两条路并行检索，合并上下文后发给 LLM
- **知识点**：RAG vs 知识图谱、混合检索

### Q4: lifespan 是什么？
- **标准回答**：FastAPI 的生命周期管理，`yield` 之前是启动时执行（初始化数据库、加载模型、连 Neo4j），`yield` 之后是关闭时执行（清理资源）。比旧版 `@app.on_event("startup")` + `@app.on_event("shutdown")` 分开写更安全，不会漏关闭
- **知识点**：FastAPI 生命周期、资源管理

### Q5: Text2Cypher 怎么工作的？
- **标准回答**：用户问题 → 获取图数据库结构（节点标签、关系类型）→ LLM 将问题转为 Cypher 查询语句（低温度保证准确性）→ 执行查询 → 格式化结果。比直接让 LLM 回答更准确，因为查询结果是确定的，LLM 只需做"翻译"工作
- **知识点**：Text2Cypher、LLM 翻译

### Q6: 实体提取为什么用 LLM 而不是 NLP 库？
- **标准回答**：LLM 泛化能力强，能理解上下文，准确率高。NLP 库需要预定义实体类型，遇到没见过的词就漏了。缺点是需要调 API、有延迟和成本。低温度（0.1）确保每次提取结果一致
- **知识点**：实体提取方案选型、LLM vs NLP

### Q7: 为什么用 MERGE 而不是 CREATE 存三元组？
- **标准回答**：`MERGE` = 找得到就用已有的，找不到才新建。防止同一篇文档反复上传时产生重复实体和关系。如果两次上传都提取出 `(张三)--[任职于]-->(字节跳动)`，用 CREATE 会创建两套重复数据，用 MERGE 只会有一套
- **知识点**：Cypher 语法、幂等操作

### Q8: 为什么 Text2Cypher 要做安全检查？
- **标准回答**：限制 LLM 生成的 Cypher 必须以 `MATCH` 或 `CALL` 开头，禁止 `CREATE`、`DELETE`、`MERGE` 等写操作。防止用户通过聊天对话意外篡改图数据。只读查询是安全的，任何写操作都应该通过专门的服务端代码控制
- **知识点**：安全设计、LLM 输出校验

### Q9: 为什么 api_messages 里 RAG 插在 [1]、图谱插在 [2]？
- **标准回答**：RAG 是主要知识来源，图谱是补充。RAG 上下文（原文 chunk）比图谱上下文（关系三元组）信息量更大、更可靠。RAG 插在前面意味着 LLM 在处理上下文时优先看到 RAG 结果。如果图谱插在前面，可能会让 LLM 更偏向关系答案而忽略原文
- **知识点**：Prompt 设计、上下文顺序

### Q10: 为什么用 neo4j 驱动而不是 langchain-neo4j？
- **标准回答**：`neo4j` 驱动轻量（<1MB），只负责执行 Cypher 拿结果。`langchain-neo4j` 是 langchain 的封装，带全家桶依赖。本项目只需要执行 Cypher 语句，不需要 langchain 的链式调用，少一层封装少一层问题
- **知识点**：依赖管理、库选型

### Q11: 为什么 RAG 和图谱的异常都只跳过不报错？
- **标准回答**：RAG 和图谱是"增强"而不是"必需"。两个检索各自用独立 try/except，异常只记 warning 不抛到上层。即使 Neo4j 没开、FAISS 索引为空、LLM 生成 Cypher 失败，聊天也能正常进行，只是回答里缺少相关知识
- **知识点**：异常隔离、防御性编程

### Q12: 为什么用 `getattr(request.app.state, "neo4j", None)` 而不是直接 `.neo4j`？
- **标准回答**：没 Docker 时 lifespan 里 Neo4j 初始化失败，`app.state` 上根本没有 `neo4j` 属性。直接 `.neo4j` 抛 `AttributeError`，`getattr` 返回 `None` 就跳过了。同样原因，路由和 service 里都用 `neo4j=None` 作为默认参数
- **知识点**：Python 安全取值、可选依赖设计

### Q13: 第 10 步（图谱提取）的 try/except 为什么包在 RAG 的 try 里面？
- **标准回答**：第 10 步和第 1-9 步在同一个 try 块里，但第 10 步有自己的独立 try/except。这样分层设计保证：RAG 失败 → 文档上传整体失败（轮不到第 10 步）；RAG 成功、图谱提取失败 → 文档上传成功（图谱只跳过）；不会出现图谱异常导致 RAG 白做的情况
- **知识点**：异常嵌套、事务边界

---

## 项目架构

### Q1: 各文件夹分别干什么？怎么协作？

**标准回答**：

| 层 | 一句话 |
|----|--------|
| `core/` | 项目的基础设施，启动前就要初始化（config、数据库引擎、JWT、日志） |
| `models/` | 定义 SQLite 有什么表、字段（User、Conversation、Message、Document、Chunk） |
| `schemas/` | 定义 API 收什么参数、返什么格式，Pydantic 自动校验 |
| `services/` | 真正的业务逻辑，路由层只是传话的 |
| `routers/` | HTTP 入口，只管接请求传参数，不做业务判断 |
| `rag/` | 文档→向量→FAISS 检索（模糊搜索） |
| `graph/` | 文本→实体→Neo4j 查询（精确关系） |
| `data/` | 本地文件存储（上传的文件、FAISS 索引、Neo4j 数据） |

**上传文档时的协作链**：

```
routers/document.py → services/document_service.py
  → models/ 建 Document + Chunk 记录
  → rag/chunker.py 分块
  → rag/embedder.py 转向量
  → rag/vector_store.py 存 FAISS
  → graph/entity_extractor.py 提取三元组
  → graph/neo4j_conn.py 存 Neo4j
```

**聊天时的协作链**：

```
routers/chat.py → services/chat.py
  → models/ 存消息 + 查历史
  → rag/retriever.py FAISS 检索
  → graph/graph_retriever.py Neo4j 检索
  → 合并上下文 → 调 LLM → 存回复
```

**特点**：每层职责单一，路由层不写业务逻辑，service 层不处理 HTTP。换框架只需改 routers/，换数据库只需改 models/ + core/database.py，换向量库只需改 rag/vector_store.py。每层独立，不影响其他层。

- **知识点**：分层架构、模块职责、数据流


## Stage 4: 网络搜索工具

### Q1: 为什么搜索用 SerpAPI 而不是直接调 Google/Bing API？
- **标准回答**：SerpAPI 是搜索聚合器，一个接口同时支持 Google、Bing、百度等，不需要注册多个搜索引擎的 API。且 SerpAPI 返回的结构化数据（title/snippet/link）比直接爬取网页更稳定
- **知识点**：搜索 API、数据聚合

### Q2: title / snippet / link 各是什么？
- **标准回答**：title=网页标题（蓝色可点击文字），snippet=摘要片段（标题下方的灰色描述），link=网页 URL。LLM 根据这三项信息判断结果是否相关，并引用到回答中
- **知识点**：搜索结果结构、SEO

### Q3: 为什么用直接注入搜索结果的方式，而不是 Function Calling？
- **标准回答**：当前是"无脑搜索"模式——每次聊天都搜，把结果直接塞进消息列表。好处是简单可靠（不依赖 LLM 的判断能力），坏处是每次聊天都消耗 SerpAPI 额度。Function Calling 模式（LLM 自主决策是否搜索）留到 Stage 5 LangGraph 阶段再实现
- **知识点**：工具调用模式、Function Calling vs 固定管线

### Q4: 网络搜索结果在上下文里排第几位？为什么？
- **标准回答**：`[0]system [1]RAG [2]图谱 [3]网络搜索 [4..]历史`。优先级：本地知识 > 实体关系 > 实时信息。RAG 最优先因为它是用户自己的文档，图谱其次因为它是从文档中提取的结构化信息，网络搜索最后因为它是外部信息仅供参考
- **知识点**：上下文优先级、信息融合

### Q5: aiohttp.ClientSession 需要传 engine 参数吗？
- **标准回答**：aiohttp 没有 engine 参数，用的是 connector（`TCPConnector`）。默认的 `ClientSession()` 内部自动创建默认 connector，管理连接池、超时等。只有需要自定义（如限制连接数、设置代理）时才显式传 connector
- **知识点**：aiohttp 连接管理

---

## Stage 5: LangGraph 智能路由

### Q1: 为什么用 LangGraph 替代原来的三个固定检索块？
- **标准回答**：原来每次聊天都无脑执行 RAG → 图谱 → 搜索，问候语也搜、闲聊也查，浪费 API 额度、增加延迟。LangGraph 通过 classify 节点让 LLM 先判断需要哪些知识源，不相关的就不跑。还能并行执行多个检索（如 RAG + 搜索同时跑）
- **知识点**：Agent 框架、动态路由 vs 固定管线

### Q2: classify 节点怎么知道需要哪些知识源？
- **标准回答**：classify_node 用 LLM prompt 分析用户问题，返回 `["rag"]` / `["graph"]` / `["web"]` / 组合 / `[]`。prompt 里描述了每个知识源的能力（rag=本地文档、graph=实体关系、web=实时信息），LLM 根据问题类型判断。返回 `[]` 时直接跳过所有检索进入 LLM 回答
- **知识点**：LLM 决策、Prompt 设计、分类任务

### Q3: route_decision 为什么返回 list？怎么实现并行？
- **标准回答**：LangGraph 的条件边支持两种返回类型：单字符串（走一条边）或 list 字符串（同时走多条边）。`route_decision` 返回 `["rag", "web"]` 时，LangGraph 内部把 rag_node 和 web_node 当作互不依赖的节点同时执行。这是 LangGraph 对比普通状态机的重要优势
- **知识点**：LangGraph 条件边、并行执行、状态机

### Q4: 为什么用 functools.partial 注入依赖？
- **标准回答**：LangGraph 节点函数的签名必须是 `(state: AgentState) -> dict`，没法直接传 embedder/vector_store/db 等外部依赖。用 `partial` 把依赖"预绑定"到节点函数上，生成的偏函数仍然满足 `(state) -> dict` 签名。这样节点函数保持纯函数风格，不搞全局变量或类实例单例
- **知识点**：依赖注入、Python 偏函数、函数式编程

### Q5: LangGraph 为什么只做路由不处理流式回复？
- **标准回答**：LangGraph 负责"路由决策 + 检索执行"，检索完成后把结果写入 AgentState 的各 context 字段。真正的 LLM 流式回复仍在 chat.py 中通过 openai 库 SSE 输出。这样 LangGraph 只做确定性工作（调用节点、传递状态），不需要处理 SSE 长连接、流中断、重连等复杂逻辑。各司其职
- **知识点**：职责分离、SSE 流式处理、Agent 边界

### Q6: 为什么 router 在第一次聊天时懒加载而不是启动时构建？
- **标准回答**：`build_router()` 需要 embedder、vector_store、db、neo4j 等参数，这些在 lifespan 启动时初始化。如果放在启动时构建，lifespan 会变得更重。懒加载在 `request.app.state.router` 上缓存，第一次聊天时构建一次，后续复用。既不影响启动速度，又不需要全局变量
- **知识点**：懒加载、FastAPI app.state、lifespan 优化

### Q7: chat.py 集成时为什么还用 try/except 包住 ainvoke？
- **标准回答**：虽然 LangGraph 路由已经替代了固定管线，但异常兜底仍然需要。ainvoke 可能因为 LLM API 超时（classify 判断失败）、FAISS 索引为空、Neo4j 没开等原因报错。try/except 包住保证即使 LangGraph 路由失败，聊天功能也不中断（只是不带检索上下文）
- **知识点**：异常隔离、防御性编程、降级策略

---

## LangChain 概念

### Q1: LangChain 是什么？为什么用？
- **标准回答**：LLM 开发的工具包，把常见操作（调 LLM、切文档、调工具）封装成了标准接口。核心组件：Document Loaders 加载文档、Text Splitters 分割文本、Embeddings 向量化、Vector Stores 存储向量、Chains/LCEL 编排流程、Tools 工具定义。优势是接口统一、组件丰富、快速原型。缺点是过度封装、调试困难、版本碎片化、依赖重。生产环境大厂很少直接引全量 LangChain
- **知识点**：LangChain 定位、优缺点、适用场景

### Q2: LangChain 的 6 个核心组件分别是什么？
- **标准回答**：
  1. **Document Loaders** — 文档加载器，从 PDF/TXT/MD 等读取文本，如 `PyMuPDFLoader`
  2. **Text Splitters** — 文本分割器，如 `RecursiveCharacterTextSplitter` 按段落/句子递归切分
  3. **Embeddings** — 向量化接口，统一封装不同 embedding 模型（OpenAI/HuggingFace/本地）
  4. **Vector Stores** — 向量存储，FAISS/Chroma/Pinecone 等统一接口
  5. **Chains / LCEL** — 链式调用，用 `|` 管道符串联组件：`chain = prompt | llm | parser`
  6. **Tools** — 工具定义，`@tool` 装饰器自动生成 tool schema 给 LLM
- **知识点**：LangChain 组件体系、LCEL 语法

### Q3: LangChain 和 LangGraph 什么关系？
- **标准回答**：LangGraph 是 LangChain 生态的一部分，专门做 Agent 状态机编排。LangChain 负责单步操作（加载文档、调 LLM），LangGraph 负责多步协作（循环、条件分支、并行）。可以只用 LangGraph 而不用整个 LangChain — 本项目就是例子：只引了 `langgraph`，其他部分（分块、向量化）直接调底层库
- **知识点**：LangChain  vs LangGraph 职责边界

### Q4: Function Calling 和 classify prompt 模式有什么区别？
- **标准回答**：classify 模式是让 LLM 输出自由文本 → 你手动解析关键词匹配到工具。Tool Calling 是 API 层面的原生支持：显式传 `tools=tools`，LLM 返回结构化 `tool_calls` JSON，代码直接读。区别：classify 的 LLM 并不知道"有工具可用"，它只是在回答问题；Tool Calling 的 LLM 是主动选择调工具。后者是 agent 面试的核心考点
- **知识点**：Tool Calling vs Prompt 路由、结构化输出

### Q5: 面试被问到 LangChain 应该怎么回答？
- **标准回答**："LangChain 我主要用到了 LangGraph（智能路由）和 Text Splitters（文本分块）。其他部分（Embeddings、Vector Stores、Document Loaders）我了解 LangChain 有现成的实现，但项目里选择直接调底层库，因为少一层封装更容易理解和调试。LangChain 的优势在快速原型和统一接口，但生产环境我会评估是否需要它的全部功能，通常大厂会自己封装轻量替代或只取特定组件。"
- **知识点**：面试话术、技术选型、独立思考

---

## Stage 6: 缓存 + Docker Compose + 基础测试

### Q1: 存数据有几种方式？Redis、数据库各什么时候用？
- **标准回答**：三种存储各司其职。①**SQLite** 存"不能丢的"——用户信息、对话历史、文档内容、chunk 原文，数据持久化且强一致。②**Redis 语义缓存** 存"丢了再算的"——问题和回答的向量+原文，命中直接返回省 LLM 调用，TTL 过期或缓存清空后下次重新计算。③**FAISS 向量索引** 存"检索专用的"——向量的倒排索引，不做持久化只做相似度搜索。原则：核心数据放 SQLite，加速数据放 Redis，检索专用数据放 FAISS
- **知识点**：多层存储架构、冷热数据分离

### Q2: Redis 语义缓存为什么不直接存原文，而要存向量？
- **标准回答**：语义缓存不是 KV 精确匹配（key=问题，value=回答），而是"语义相似匹配"。存向量是为了计算余弦相似度：新问题"今天天气如何"和缓存里的"今天天气怎么样"虽然字面不同，但语义相似度 ≥0.92 就可以直接复用缓存的回答。如果只存原文就只能精确匹配，失去"语义"的意义
- **知识点**：语义缓存、向量相似度、精确匹配 vs 模糊匹配

### Q3: Redis Hash 存了哪些字段？数据结构是什么？
- **标准回答**：每条缓存用 Redis Hash 存 4 个字段：`vec`（问题的向量，base64 编码的 pickle 序列化）、`question`（问题原文，用于调试/展示）、`answer`（LLM 的完整回答）、`ts`（时间戳，用于 TTL 过期）。key 是 `cache:{hash(question)}`，方便 SCAN 遍历。Hash 结构适合存结构化数据，4 个字段一起读写，比 JSON 字符串更灵活（可单独读某个字段）
- **知识点**：Redis 数据结构、Hash 应用场景、序列化方案

### Q4: pickle 序列化向量怎么理解？
- **标准回答**：numpy 数组（向量）是二进制对象，不能直接存到 Redis（特别是 `decode_responses=True` 时 Redis 会尝试把返回值解码为 UTF-8 字符串）。解决方案：`base64.b64encode(pickle.dumps(vec)).decode()` 把 numpy 数组 → pickle 字节流 → base64 字符串。读的时候逆操作：`pickle.loads(base64.b64decode(data["vec"]))` 还原为 numpy 数组。Base64 编码只增加约 33% 体积，但对 768 维向量来说完全可以接受
- **知识点**：序列化、numpy 存储、base64 编码

### Q5: SCAN 遍历时 cursor、count、match 各是什么？
- **标准回答**：SCAN 是 Redis 的游标迭代器。①**cursor**=游标位置，从 0 开始，每次返回新 cursor 和一批 key，当 cursor 回到 0 时遍历完成（如 cursor=130 表示下次从第 130 个槽位继续）。②**count=100**=建议每批返回约 100 个 key（不是精确值，Redis 按哈希槽取）。③**match="cache:*"**=模式匹配，只返回 key 以 "cache:" 开头的条目。相比 KEYS 命令，SCAN 不阻塞 Redis，适合生产环境
- **知识点**：Redis SCAN 原理、游标迭代、模式匹配

### Q6: 余弦相似度匹配的流程是什么？
- **标准回答**：新问题来的时候做两件事：①用 Embedder 把问题转成向量 q_vec；②SCAN 遍历所有 `cache:*` key，对每个缓存条目取 `vec` 字段反序列化为向量 c_vec，算 `cosine_sim = dot(q_vec, c_vec) / (norm(q_vec) * norm(c_vec))`。如果 `max_sim ≥ 0.92`，直接返回对应缓存的 answer；否则继续调 LLM，收到回复后再写入缓存。阈值 0.92 表示语义高度相似但不是字面完全一致
- **知识点**：余弦相似度算法、阈值判断、缓存命中策略

### Q7: 清空缓存的代码怎么理解？
- **标准回答**：`clear()` 函数用 `async for key in redis.scan_iter(match="cache:*"):` 遍历所有缓存 key（内部也是 SCAN 机制但封装成异步迭代器），然后 `await redis.delete(*keys_batch)` 分批删除。不能直接 `FLUSHALL`（会清空 Redis 所有数据包括其他业务 key），只删 `cache:*` 前缀的 key。删除后下次聊天重新构建缓存
- **知识点**：Redis 批量删除、scan_iter、key 命名空间

### Q8: 为什么测试要用 ASGITransport 而不是启动 uvicorn？
- **标准回答**：ASGITransport 直接调用 FastAPI 的 ASGI 接口，不需要启动 uvicorn 进程，毫秒级响应。如果用 uvicorn 测试需要先启动服务器（`subprocess.Popen`）、等端口监听、再发 HTTP 请求，每个测试用例都要等待服务器启动关闭，慢 100 倍。ASGITransport 是 httpx 提供的测试工具，专门用于 ASGI 框架的单元测试
- **知识点**：ASGI 协议、FastAPI 测试策略、httpx 测试工具

### Q9: dependency_overrides 怎么实现测试数据库隔离？
- **标准回答**：`app.dependency_overrides[get_db] = lambda: session` 替换 FastAPI 的数据库依赖。原本 `get_db` 连接 `membrain.db`，测试时替换为连接 `sqlite+aiosqlite://`（内存数据库）的 session。每个测试用例通过 `autouse=True` 的 `db_session` fixture 创建全新的内存 SQLite → 建表 → 覆盖依赖 → 测试执行 → 关闭引擎 → 清除覆盖。实现"互不干扰、用完即弃"，不影响开发数据库
- **知识点**：依赖注入、FastAPI 测试、数据库隔离

### Q10: SSE 流式聊天测试怎么测？
- **标准回答**：SSE 是流式响应，不能用常规的 `client.post()`（等全部返回才解析）。用 `client.stream("POST", ...)` 逐行读取：①检查 `resp.status_code == 200`；②逐行遍历 `resp.aiter_lines()`，找到 `data:` 前缀的行；③读到 `data: [DONE]` 标记时 break，说明流正常结束。核心验证点是"流能正常走完并输出内容"，不验证具体返回什么文字（因为 LLM 回答不确定）
- **知识点**：SSE 测试、流式断言、httpx stream

---

## AutoDL 部署

### Q1: 为什么 AutoDL 重启后代码/文件就没了？
- **标准回答**：AutoDL 实例有两类存储。①**系统盘**（临时）— conda 环境、pip 包、`/root/` 下的文件都在这，关机后清空。②**`/root/autodl-tmp/`**（持久化）— 挂载的云硬盘，关机重启不丢。所以项目代码一定要放 `/root/autodl-tmp/` 下。conda 环境虽然装一次就能用，但实例销毁后需要重建
- **知识点**：云服务器存储类型、数据持久化

### Q2: conda 环境和"文件夹"有什么关系？
- **标准回答**：可以通俗地理解成"独立的 Python 文件夹"。`conda create -n membrain python=3.10` ≈ 新建一个叫 `membrain` 的文件夹，在里面装 Python 3.10 + 独立包管理。`conda activate membrain` ≈ 告诉系统"接下来用这个文件夹里的 Python"。这样做的好处：不影响系统自带的 Python（如 3.8，系统还要用），一个环境装什么包都不会搞乱别的环境，互不干扰
- **知识点**：虚拟环境、conda 原理、环境隔离

### Q3: 为什么项目路径里有两个 membrain（Membrain/membrain）？
- **标准回答**：第一个 `Membrain/`（大写）是用户手动创建的文件夹，作为项目容器。第二个 `membrain/`（小写）是 `git clone` 自动生成的，里面才是真正的项目文件（`app/`、`requirements.txt` 等）。正常的目录结构是：`/root/autodl-tmp/Membrain/membrain/`。如果觉得嵌套深，可以把子目录内容移到上层
- **知识点**：git clone 行为、目录结构设计

### Q4: huggingface.co 连不上怎么办？
- **标准回答**：AutoDL 实例在国内，huggingface.co 被网络屏蔽。设置镜像环境变量解决：`export HF_ENDPOINT=https://hf-mirror.com`。然后在应用启动前先手动下载模型：`python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('shibing624/text2vec-base-chinese')"`。如果加到 `~/.bashrc` 里就不用每次设了。备用镜像：`https://hf.llm.info`
- **知识点**：国内网络环境、镜像源配置、HuggingFace 模型下载

### Q5: 应用启动时 Neo4j 连接失败、Redis 连不上怎么办？
- **标准回答**：设计上 Neo4j 和 Redis 是可选依赖，连接失败只记 warning，不影响应用启动。Noe4j 失败 → 图谱功能不可用，聊天跳过图谱检索。Redis 失败 → 缓存功能不可用，每次聊天都调 LLM。核心聊天功能（认证、对话、RAG）完全正常。因此 AutoDL 上没有 Docker 也能跑，只是少了图数据库和缓存
- **知识点**：可选依赖设计、优雅降级、防御性编程

### Q6: AutoDL 上怎么让外部访问 API？
- **标准回答**：`uvicorn app.main:app --host 0.0.0.0 --port 8000` 绑定到所有网卡（0.0.0.0），然后在 AutoDL 控制台 → 实例详情 →「端口映射」添加容器端口 8000，复制生成的外网地址。浏览器访问 `http://<外网地址>/docs` 即可看到 Swagger API 文档。注意：`--host 0.0.0.0` 必须加，默认是 localhost 外部访问不到
- **知识点**：AutoDL 端口映射、网络绑定、外网访问

### Q7: AutoDL 开机自启服务怎么做？不想开了怎么关？
- **标准回答**：用 crontab 的 `@reboot` 实现。①创建启动脚本（放 `/root/autodl-tmp/` 持久化目录确保不丢），chmod +x 给执行权限。②`crontab -e` 加一行 `@reboot bash /path/to/script.sh`，保存退出，下次实例重启后自动拉起服务。**不想开了**就 `crontab -e` 删掉或注释那行即可。注意脚本里需要 `source ~/miniconda3/etc/profile.d/conda.sh` 来激活 conda 环境，因为 crontab 不会自动加载 shell 配置
- **知识点**：Linux 开机自启、crontab @reboot、进程守护

---

## Docker 部署

### Q1: Docker Desktop 在国内拉不了镜像怎么办？
- **标准回答**：Docker Hub 在国内被墙，需要代理或镜像加速器。方案一：Docker Desktop → Settings → Resources → Proxies → 配置 HTTP/HTTPS 代理（如 `http://127.0.0.1:10810`）→ Apply & Restart。方案二：配置 `~/.docker/daemon.json` 的 `proxies` 字段。方案三：用国内镜像加速器（中科大 `https://docker.mirrors.ustc.edu.cn`、网易 `https://hub-mirror.c.163.com`），配到 Docker Engine 的 `registry-mirrors` 中
- **知识点**：Docker 网络配置、代理、镜像加速

### Q2: WSL 版本太旧导致 Docker Desktop 无法启动怎么办？
- **标准回答**：Docker Desktop 依赖 WSL2 运行 Linux 虚拟机。WSL 版本过旧时 Docker 引擎无法启动，表现为鲸鱼图标一直转动。解决方案：管理员终端执行 `wsl --update` 更新 WSL 内核，然后 `wsl --shutdown` 重启 WSL，最后重启 Docker Desktop
- **知识点**：WSL2、Docker Desktop 启动流程、Linux 虚拟机

### Q3: docker compose up -d 一键启动了什么？
- **标准回答**：`docker compose up -d` 启动项目依赖的所有服务：①**Neo4j 5-community**（端口 7474 Web 管理 + 7687 Bolt 协议，数据持久化到 `./data/neo4j`）②**Redis 7-alpine**（端口 6379，appendonly 持久化模式）。应用启动时 lifespan 自动连接两者，连接成功日志为 `Neo4j 连接成功` / `Redis 缓存连接成功`，失败只记录 warning 不阻止应用启动
- **知识点**：Docker Compose 编排、服务依赖、优雅降级

### Q4: Docker 容器和 volume 的关系？
- **标准回答**：容器是"临时运行的程序"，volume 是"持久化存储"。容器删除后内部数据全丢，volume 独立于容器生命周期存在。Neo4j 数据通过 `./data/neo4j:/data` 绑定挂载到宿主机目录，Redis 通过命名 volume `redis_data:/data` 管理。原则：数据库等有状态服务必须挂 volume，配置写入代码的可以无状态
- **知识点**：Docker 存储、volume 挂载、数据持久化

### Q5: 本地 Docker 和 AutoDL 的环境差异？
- **标准回答**：本地有 Docker 可启动 Neo4j + Redis，图谱和缓存功能完整；AutoDL 没有 Docker，Neo4j 和 Redis 自动跳过，核心聊天（认证、RAG）不受影响。代码层面已适配两种环境：lifespan 中 try/except 包住连接逻辑，失败只记 warning。本地开发时所有能力全开，生产部署择需取舍
- **知识点**：开发 vs 生产环境、可选依赖、graceful degradation

### Q6: 作为面试作品，需要掌握 Docker 吗？
- **标准回答**：不需要。Docker 在 agent 开发面试中几乎不会作为核心考点。面试更关注 Function Calling / Tool Calling 原理、ReAct 循环、LangGraph 编排、Prompt 工程。Docker 最多被顺带问一句"项目中的 Neo4j 怎么部署的"，回答"用 Docker Compose 编排"就足够了。工作中初/中级 agent 开发也不需要深钻 Docker，能用 `docker compose up` 启动服务就行。时间应该花在 agent 核心能力上
- **知识点**：面试准备、技术选型优先级、学习路径

### Q7: Docker Desktop 界面看不懂、不知道进程在干嘛怎么办？
- **标准回答**：不用管。Docker Desktop 里的英文界面、容器列表、日志输出是为运维准备的，agent 开发者不需要看懂。只需要记住三个命令：`docker compose up -d`（启动服务）、`docker compose down`（停服务）、`docker compose ps`（看状态）。把 Docker 想象成家里的路由器——通了就行，不需要懂工作原理。日常使用就是双击 Docker Desktop 等它稳定，然后跑上面那行命令
- **知识点**：Docker 使用边界、工具 vs 原理、学习效率

---

## 部署流程

### Q1: 上传代码到 AutoDL 是通过 git 还是 GitHub？流程和原理是什么？
- **标准回答**：两者配合使用。本地代码通过 `git push` 推送到 **GitHub 远程仓库**（中间桥梁），然后 SSH 登录 AutoDL 后 `git pull` 拉取代码。GitHub 在这里充当**两端都能访问的中转站**：本地 PC 和 AutoDL 服务器都能连 GitHub，但无法直接互连。传输链路为 `本地 → git push → GitHub → git pull → AutoDL`。`.env`（密钥）和 `data/`（持久数据）在 `.gitignore` 中不进 git，需要手动复制或重新配置
- **知识点**：Git 工作流、远程仓库、CI/CD 基础、持续部署

### Q2: 日常更新代码到 AutoDL 的完整命令是什么？
- **标准回答**：
  ```
  本地：git add . → git commit -m "xxx" → git push
  AutoDL：conda activate membrain → cd /root/autodl-tmp/Membrain → git pull → pip install -r requirements.txt（如有新依赖）→ 杀旧 uvicorn 进程 → 重启 uvicorn
  ```
  核心就三步：本地 push → AutoDL pull → 重启生效
- **知识点**：部署流程、服务重启

### Q3: DEPLOY.md、CHANGELOG.md、CONTRIBUTING.md 是代码规范吗？
- **标准回答**：不是。这些是开源社区**约定俗成的习惯**，不是强制规范。README.md（项目介绍）基本都有，DEPLOY.md（部署说明）看项目是否有部署需要，CHANGELOG.md（版本记录）多人协作/发布时用，CONTRIBUTING.md（贡献指南）开源项目才需要。不写不影响项目运行，写了方便协作和查阅
- **知识点**：项目文档规范、约定 vs 强制

### Q4: 本地 git 仓库在哪？git commit 的每一步做了什么？
- **标准回答**：
  本地 git 仓库就是项目根目录下的 `.git/` 文件夹（`D:\pythonProject\git\membrain\.git`），所有提交历史、分支信息都存在这里。`git commit` 只写入本地 `.git/`，跟 GitHub 无关。

  提交一个修改需要 4 步：

  ```
  第 1 步：git status                   # 看哪些文件改了（红色）和新文件（绿色）
  第 2 步：git add <文件路径>            # 把文件加入"暂存区"（绿色 = 已暂存）
          # 或者 git add app/agent/     # 加整个目录下的所有改动
          # 或者 git add *.py           # 加所有 .py 文件
  第 3 步：git commit -m "说明文字"     # 把暂存区写入本地仓库 (.git/)
  第 4 步：git push                     # 把本地提交推送到 GitHub
  ```

  关系图：
  ```
  本地 .git/  ── git push ──→ GitHub（远程仓库） ── git pull ──→ AutoDL（服务器）
      ↑
  git commit（写入本地，与 GitHub 无关）
      ↑
  git add（暂存，准备提交）
  ```

  核心理解：**commit = 写本地，push = 发到 GitHub，pull = 从 GitHub 拉**。P0 做的 commit + push 只到了 GitHub，AutoDL 还没更新，需要单独 SSH 登录后 `git pull`。
- **知识点**：Git 四步工作流、本地仓库 vs 远程仓库、.git 目录

---

## 面试准备阶段

### Q1: Function Calling / Tool Calling 和 Prompt 路由有什么区别？
- **标准回答**：Prompt 路由是让 LLM 输出自由文本（如 `["rag"]`），然后代码手动解析这个文本来决定调用什么工具。Tool Calling 是 API 层面的原生支持：显式传 `tools=tools` 参数给 LLM，LLM 返回结构化的 `tool_calls` JSON，代码直接读取 `tc.function.name` 即可。核心区别：Prompt 路由的 LLM 并不知道"有工具可用"，它只是在回答问题；Tool Calling 的 LLM 主动选择调什么工具，返回格式由 API 保证，不需要手动解析。后者在面试中能体现对 Agent 原理的理解
- **知识点**：Tool Calling vs Prompt 路由、结构化输出、Agent 原语

### Q2: Tool Calling 的 tools 参数怎么定义的？description 为什么重要？
- **标准回答**：tools 参数按 OpenAI 的 tool schema 格式定义，每个工具包含 name（工具名，如 `rag_search`）、description（工具能力的描述，如"从本地知识库中搜索用户上传的私有文档内容"）、parameters（参数 schema，用 JSON Schema 格式定义）。description 是 LLM 做路由决策的唯一依据——LLM 看不到工具的实现代码，只能靠 description 判断"这个问题是否应该调用这个工具"。所以 description 要写清楚使用场景，而不是写功能说明
- **知识点**：Tool Schema 设计、LLM 决策依据、面试技巧

### Q3: classify_node 返回 []（空列表）时意味着什么？
- **标准回答**：LLM 判断当前问题不需要任何工具（问候语、闲聊等），直接进入 LLM 回答环节，不执行任何检索。这是 Tool Calling 对比"无脑全跑"路线的核心优势——节省 API 额度、减少延迟。面试点：问 LLM 一个问题 → LLM 说不需要工具 → 直接回答。这说明 agent 不是每轮都调工具，而是按需调用
- **知识点**：Agent 按需决策、工具调用策略、效率优化

### Q4: 为什么 "张三和李四是什么关系" 同时触发了 graph_query 和 rag_search？
- **标准回答**：LLM 判断这个问题可能需要两种知识源：①graph_query 查询知识图谱中的实体关系（两人之间的关系链）；②rag_search 搜索文档中是否提到这两人的关系。这说明 LLM 具备多工具并行决策能力——不局限于单一工具，而是判断哪些工具可能有用就都调。在代码层面 LangGraph 天然支持 parallel execution，多个工具并行调用互不阻塞。这个现象说明了 Tool Calling 的智能性，也体现了 LangGraph 并行路由的优势
- **知识点**：多工具协同、并行执行、LLM 决策分析

### Q5: 如果 LLM API 超时或报错，classify 节点怎么处理？
- **标准回答**：classify_node 的整个 LLM 调用被 try/except 包住，任何异常（超时、API 错误、模型不响应）都返回 ，即所有源全开。这是一个"防御性降级"策略——宁可多跑检索浪费额度，也不能因为路由失败让用户完全得不到回答。与各检索节点的异常处理（单节点失败只跳过自身）配合，形成完整的错误容忍链
- **知识点**：错误处理、降级策略、防御性编程

### Q6: 实现 Tool Calling 后系统架构发生了什么变化？
- **标准回答**：路由决策从"写死的 prompt 分类"变成了"LLM 通过 tools 参数自主判断"。其他部分（检索节点、LangGraph 状态机构建、chat.py 集成）完全不变。核心收益是：①路由准确率提升（LLM 知道"有工具可用"）；②结构化输出保证（不用猜 LLM 的文本回复）；③面试价值（Function Calling 是 agent 开发最高频考点）。类似"替换引擎不换车架"——核心替换少、影响小、收益大
- **知识点**：架构演进、最小化改动、增量重构


### Q7: classify_node 的 fallback 策略是什么样的？
- **标准回答**：三层兜底。第一层（LLM 调用失败）：API 超时或报错 → `except` 返回全源 `["rag", "graph", "web"]`，宁可多跑不能空手。第二层（工具参数错误或检索为空）：json.loads 解析 tool_calls 失败时跳过该工具；检索节点搜不到内容时返回空字符串，不影响最终 LLM 回答。第三层（整张图全炸）：LangGraph 的 ainvoke 被 try/except 包住 → 降级为纯 LLM 聊天（无检索无缓存），用户至少能正常对话。各层独立保护，单点故障不扩散
- **知识点**：异常隔离、降级策略、防御性编程

### Q8: tool_choice 参数有哪些选项？各用什么场景？
- **标准回答**：①`"auto"`（默认）— LLM 自己决定是否调工具，适合多数场景，项目用的就是 auto。②`"none"` — 强制不调工具，适合闲聊场景省 token。③`"required"` — 强制调用工具（传给 parallel_tool_calls），适合必须走工具的管线。④`{"type":"function","function":{"name":"xxx"}}` — 强制调某个特定工具，适合定向测试。面到高级岗位时会问这个，答出来能体现对 API 参数的细致理解
- **知识点**：Tool Calling 参数、LLM API 设计

### Q9: Function Calling 有哪些已知缺陷和边界？
- **标准回答**：三个主要缺陷。①**幻觉参数**：LLM 可能构造不存在的工具名或参数格式 → 需要 json.loads try/except + 校验。②**过度调用**：LLM 倾向"用工具比不用好"，不需要时也调用 → 需要下游 fallback（空结果安全）。③**嵌套调用**：一个工具的结果可能触发另一个工具 → 引出了 ReAct 循环。面试中主动指出这些缺陷能体现工程经验
- **知识点**：LLM 幻觉、Agent 边界、ReAct

---

## ReAct 节点

### Q1: nodes.py 里有哪些函数？各自干什么？
- **标准回答**：6 个函数。
  - **在用**：`reasoning_node`（ReAct 推理，LLM 用 Tool Calling 决定调工具还是回答）+ `execute_tools_node`（并行执行选中的工具，结果反馈给下一轮推理）
  - **废弃**（旧版 classify 模式残留，不再被 graph.py 引用）：`rag_node` / `graph_node` / `web_node` / `collect_node`
- **知识点**：ReAct 架构、节点职责

### Q2: reasoning_node 的工作流程是什么？
- **标准回答**：①从 state 取出 question、history（之前工具调用的记录）、iteration（轮次计数）。②组装 api_messages：system prompt（描述三个工具的能力）+ user question + history。③调 OpenAI LLM，传 tools=TOOLS 参数。④LLM 返回两条路：不选工具（tool_calls 为空）→ `["__answer__"]` 表示可直接回答；选了工具 → 映射为内部源名 `["rag","graph"]`，同时记录 tool_call_record 写入 messages。⑤最多 3 轮强制结束。异常时降级为全源检索
- **知识点**：ReAct 推理、Tool Calling、异常降级

### Q3: execute_tools_node 的工作流程是什么？
- **标准回答**：①根据 selected_sources 选中要执行的工具（rag/graph/web）。②用 asyncio.gather 并行执行多个工具，互不阻塞，总耗时≈最慢的那个。③从 state.messages 中提取上一轮 assistant 的 tool_call_id，用于构造合法的 tool role 消息（OpenAI 格式要求：tool 消息必须匹配对应的 tool_call_id）。④遍历结果：更新 response、format 各 context 字段（rag_context/graph_context/web_context），构造 tool role 消息追加到 messages。⑤轮次 iteration +1，回到 reasoning_node 继续推理
- **知识点**：并行执行、消息格式、Tool Calling 协议

### Q4: ReAct 的数据流是怎么走的？
- **标准回答**：
  ```
  第1轮: reasoning(question, [], iteration=0) → LLM选graph_query → sources=["graph"]
         → execute_tools(sources=["graph"]) → 查到(张三→任职于→字节跳动)
         → state: {messages:[tool_call, tool_result], iteration:1}

  第2轮: reasoning(question, [tool_call, tool_result], iteration=1)
         → LLM看到结果，觉得够了 → __answer__ → 结束
  ```
  配合 graph.py 的条件边 route_decision：`__answer__`→ END，其他 → execute_tools → 循环回 reasoning
- **知识点**：ReAct 循环、LangGraph 条件边、数据流

### Q5: graph.py 的 route_decision 函数做了什么？
- **标准回答**：LangGraph 条件边函数。输入 AgentState，检查 selected_sources：含 `__answer__` → 返回 `["__answer__"]` 走向 END（结束）；否则返回 sources 列表（如 `["rag","web"]`）走向 execute_tools 节点。注意返回的是 `sources` 变量（list），不是 state 对象——之前有个 bug 是 `return state` 返回了整个 state 对象，LangGraph 无法匹配条件边导致运行时错误
- **知识点**：LangGraph 条件边、常见 bug

### Q6: `__answer__` 时 LLM 的回答文本怎么处理的？被丢弃了吗？
- **标准回答**：丢弃了，但这是**故意设计的**。项目采用了**两层分离架构**：
  - **第一层 — LangGraph ReAct**（`nodes.py` + `graph.py`）：只负责检索决策。reasoning_node 调用 LLM + tools 参数，决定调什么工具。execute_tools_node 并行执行，把结果写入 `rag_context` / `graph_context` / `web_context`。`__answer__` 时 ReAct 结束，choice_msg.content（LLM 推理过程中的"自言自语"）直接丢弃
  - **第二层 — chat.py 单独 LLM 调用**（`services/chat.py` 第 175-200 行）：从 state 取出三个 context 字段，插入到 api_messages 的 system 位置，然后另起一次 `client.chat.completions.create(stream=True)` 流式生成最终回答给用户
  好处：回答质量不依赖 ReAct 的推理质量，两部分可独立优化。代价：每次回答多调一次 LLM API
- **知识点**：两层架构、检索与生成分离、设计权衡

### Q7: 完整的聊天请求数据流是什么？
- **标准回答**：
  ```
  ① router/chat.py → StreamingResponse(_sse_wrap(generator))
     ↓
  ② services/chat.py:
     第 1 步：获取或创建对话（conversation_id 管理）
     第 2 步：保存用户消息到 DB（先存再调 API，保证不丢）
     第 3 步：从 DB 加载完整历史（防客户端篡改）
     第 3.5 步：查 Redis 语义缓存（命中直接返回，跳过 LLM）
     第 3.x 步：LangGraph ReAct 检索（下文详述）
     第 4 步：流式调用 LLM API（带检索上下文，stream=True）
     第 5 步：保存完整回复到 DB
     第 6 步：写入 Redis 语义缓存
     ↓
  ③ LangGraph 子流程（第 3.x 步内部）:
     router.ainvoke({"question": user_query})
       → reasoning_node（LLM + tools 参数决策）
       → execute_tools_node（asyncio.gather 并行执行）
       → 循环直到 __answer__
       → 返回 {rag_context, graph_context, web_context}
     ↓
  ④ 回到第 4 步：将 context 插入 api_messages，调 LLM 生成回答
     ↓
  ⑤ _sse_wrap 包装为 SSE 格式 → 流式返回给客户端
  ```
- **知识点**：全链路数据流、架构分层、请求生命周期

---

## 项目架构

### Q1: main.py 里的中间件是什么？做什么的？
- **标准回答**：`main.py` 注册了两个中间件。①**CORS Middleware**：跨域处理，开发阶段允许所有来源（`allow_origins=["*"]`），让前端网页能跨域访问 API。②**RequestLogMiddleware**：自定义中间件（`app/core/middleware.py`），每个请求进来时记录方法、路径、状态码、耗时，如 `POST /api/v1/chat → 200 (1.25s)`。中间件像"安检门"，所有请求都会经过，与业务逻辑无关
- **知识点**：FastAPI 中间件、CORS、请求日志

### Q2: 项目完整架构流转图
- **标准回答**：
  ```
  外部客户端 (浏览器/curl)
      │ HTTP
      ▼
  ╔══════════════════════════════════════════════════════════════╗
  ║                    FastAPI 应用入口                          ║
  ║  CORS Middleware → RequestLogMiddleware                     ║
  ║      │                                                     ║
  ║      ▼                                                     ║
  ║  Auth Router  Chat Router  Document Router  Trace Router   ║
  ║      │             │              │              │         ║
  ║      ▼             ▼              ▼              ▼         ║
  ║  AuthService  ChatService  DocumentService  AgentTrace     ║
  ╚═══════════════════════╪═════════════════════════════════════╝
                          │
                          ▼
               ChatService 核心流程
     Step 1  获取/创建对话 ────────→ DB(conversations)
     Step 2  保存用户消息 ─────────→ DB(messages)
     Step 3  加载历史 ────────────→ DB(messages)
     Step 3.5 语义缓存查询 ───────→ Redis
     Step 3.x LangGraph ReAct 路由
        reasoning_node (LLM + tools参数)
           → execute_tools_node (asyncio.gather)
             → RAG检索 / 图谱查询 / 网络搜索
           → 循环直到 __answer__
        AgentTracer.record() → DB(agent_traces)
     Step 4  流式调 LLM (DeepSeek API) → 逐 token 返回
     Step 5  保存 AI 回复 ────────────→ DB(messages)
     Step 6  写入语义缓存 ───────────→ Redis
  ```
- **知识点**：全链路架构、请求生命周期、分层设计

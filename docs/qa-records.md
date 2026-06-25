# MemBrain Q&A 记录

## Stage 1: 骨架 + 核心聊天

### Q1: 密码字段为什么叫 hashed_password 不叫 password？`⭐`
- **标准回答**：看到字段名就知道存的是哈希值，不是明文。如果叫 password 容易让人误会存的是密码原文
- **知识点**：数据库设计、安全编码规范

### Q2: 注册登录为什么用 JWT 不用 session？`⭐⭐`
- **标准回答**：JWT 无状态，token 里包含 user_id，解码即得，不需要服务端存 session。适合小项目，零额外基础设施。缺点是无法主动让 token 失效
- **知识点**：认证机制、JWT vs Session

### Q3: 聊天为什么用 SSE 不用 WebSocket？`⭐⭐`
- **标准回答**：SSE 基于 HTTP，兼容性好，不需要升级握手。只需要服务端→客户端的单向流，SSE 天然适合。用 StreamingResponse 十几行代码实现。WebSocket 需要状态管理、心跳、重连，复杂度高
- **知识点**：实时通信、SSE vs WebSocket

### Q4: ChatService 为什么要先存消息再调 API？`⭐⭐`
- **标准回答**：如果先调 API 再存，API 调用失败用户消息就丢了。先存保证用户输入一定不丢。`flush()` 写入事务但不提交，异常被捕获后 generator 正常结束不往上抛，`get_db()` 看到没异常就 commit
- **知识点**：异常处理、数据一致性、事务管理

### Q5: 为什么每次都从 DB 加载历史，而不是用客户端传的 messages？`⭐`
- **标准回答**：客户端不可信，用户可能篡改历史消息。每次从 DB 加载更安全
- **知识点**：安全设计、前后端信任边界

### Q6: conversation_id 怎么传给客户端的？`⭐`
- **标准回答**：ChatService 在 yield 第一个 token 之前先 yield 一条 `__conversation_id__:{id}` 特殊消息。`_sse_wrap` 拦截这个前缀不发送给客户端，等流结束时拼到 done 事件里发给客户端
- **知识点**：SSE 协议、进程间通信

### Q7: 如果 DeepSeek API 超时抛异常，用户消息还会被保存吗？`⭐`
- **标准回答**：会被保存。因为异常被 try/except 捕获了没有往上抛，`get_db()` 看到没异常就 commit
- **知识点**：异常捕获、事务提交、防御性编程

### Q8: 为什么分层设计（routers/services/models/schemas）？`⭐⭐`
- **标准回答**：每层职责单一。路由层不知道密码怎么 hash，服务层不知道 HTTP 状态码怎么写。将来换数据库或加 OAuth，只改对应层即可
- **知识点**：分层架构、单一职责原则

---

## Stage 2: 知识库上传 + RAG

### Q1: chunk 模型为什么没有 updated_at 字段？`⭐`
- **标准回答**：chunk 一旦创建就不会再变了。文档重新上传 → 旧的 chunk 全部删除，新的 chunk 重新生成。而 Document 的 status 会从 processing → ready/failed，需要 updated_at
- **知识点**：数据库设计、字段选择标准

### Q2: Document 的 status 字段怎么理解？`⭐`
- **标准回答**：跟踪文档上传后的处理进度：上传 → processing（正在分块向量化）→ ready（可用于 RAG）→ failed（处理失败）。未来改成异步处理时这个字段是关键
- **知识点**：状态机设计、异步处理流程

### Q3: @staticmethod 是什么？`⭐`
- **标准回答**：不需要访问类的任何数据，直接能调用的方法。调用时不需要创建对象：`TextChunker.chunk_text("...")`。归类到类下面是为了组织结构清晰
- **知识点**：Python 面向对象、静态方法 vs 实例方法

### Q4: RecursiveCharacterTextSplitter 怎么工作的？`⭐⭐`
- **标准回答**：按分隔符列表逐级尝试分割：先按段落(\n\n)、再按行(\n)、再按句号(。)、逗号(，)、空格，保证在自然边界处切分。比自己写 split 考虑边界情况更全面
- **知识点**：文本分块策略、langchain 工具使用

### Q5: chunk_text 的参数有哪些？`⭐`
- **标准回答**：text（原始文本，必填）、chunk_size（目标块大小，默认 500）、chunk_overlap（重叠字符数，默认 50）。返回 list[str]
- **知识点**：分块策略、参数设计

### Q6: FAISS 只搜索不存储吗？向量存 DB？`⭐⭐`
- **标准回答**：FAISS 既搜索也存储。向量存 FAISS 索引文件（.bin）中，DB 只存 chunk 原文和元数据。FAISS 负责高效向量近似最近邻检索，DB 负责关系型查询。两者互补
- **知识点**：RAG 架构、向量检索、FAISS vs DB

### Q7: FAISS 的存储过程写在哪？`⭐⭐`
- **标准回答**：vector_store.py 提供 add()（加入内存索引）和 save()（写回磁盘）。调用在 document_service.py：上传文档 → chunker 分块 → embedder 转向量 → vector_store.add() → vector_store.save()。同时 chunk 原文存 DB
- **知识点**：代码流程、service 层职责、RAG 流水线

### Q8: result.scalars().all() 怎么理解？`⭐`
- **标准回答**：select(Chunk).where(...) 生成 SQL，self.db.execute() 执行返回 Result 对象。.scalars() 把每行原始数据映射成 Chunk ORM 实例，.all() 取出所有行返回 list[Chunk]。对比：result.all() 返回 list[Row] 需用下标取值，scalars() 后可直接 chunk.content
- **知识点**：SQLAlchemy ORM、Result 对象、scalars() 映射

### Q9: 什么是 Pydantic 模型？为什么要分层处理？`⭐`
- **标准回答**：Pydantic 是 Python 数据校验库，定义数据结构 + 自动校验类型。FastAPI 集成后自动做类型校验、字段校验、响应过滤、生成 OpenAPI 文档。分层处理（上传/详情/列表用不同 Response）是因为：每个接口只需返回对应字段，减少传输量；避免暴露内部敏感字段（如 file_path）；前端能明确知道每个接口返回什么
- **知识点**：Pydantic、数据校验、API 契约、接口设计

### Q10: Pydantic 模型里 BaseModel、Field、datetime、Optional 分别干嘛？`⭐`
- **标准回答**：BaseModel 是基类，继承后才有自动校验；Field 给字段加额外约束（如 min_length=1）；datetime 是 Python 内置时间类型，Pydantic 自动把字符串转成 datetime 对象；Optional[str] 表示字段可选，等价于 str | None
- **知识点**：Pydantic、Python 类型注解、数据校验

### Q11: document_service.py 如何串联之前写的 RAG 组件？`⭐⭐`
- **标准回答**：upload() 流程：①校验文件类型 → ②存原始文件 → ③创建 Document 记录(status=processing) → ④_extract_text() 提取文本 → ⑤TextChunker.chunk_text() 分块 → ⑥Embedder.embed() 向量化 → ⑦保存 Chunk 到 DB(两次 flush: 先拿 doc.id, 再拿 chunk.id) → ⑧VectorStore.add()+save() 存 FAISS → ⑨更新 status=ready → commit。try/except 包整个流程，任一失败 rollback + status=failed
- **知识点**：RAG 管线、Service 层编排、事务管理、组件协作

### Q12: 文档重复上传怎么识别和检测？`⭐⭐⭐⭐`
- **标准回答**：三层递进检测策略，每层解决不同粒度的重复问题。

  **第一层：精确重复（SHA256 文件哈希）**
  上传时计算文件的 SHA256 哈希，存入 Document 表的 `file_hash` 字段（数据库加 UNIQUE 约束）。同一文件再次上传时哈希碰撞直接拒绝——秒级检测，零误判。适合"同一份 eval_doc.txt 传了 3 次"这种场景。

  **第二层：近似重复（MinHash + LSH / SimHash）**
  如果用户改了标题、加了一段话、或把 MD 转成了 TXT，SHA256 不同但内容高度相似。对每个新文档做 MinHash 签名，与已有文档的签名集合做 Jaccard 相似度计算，超过阈值（如 0.85）判定为近似重复。SimHash 是替代方案，适合海量文档的去重（Google 用它做网页去重），但精度略低于 MinHash。面试时点出"MinHash 适合精确控制阈值，SimHash 适合大规模快速过滤"即可。

  **第三层：语义重复（Embedding 相似度）**
  如果用户换了一句话重写整段内容（"密码用什么算法加密" vs "密码存储用的什么哈希方法"），MinHash 也不灵了。上传时用 Embedder 把文档转成向量，去 FAISS 查已有文档的向量，如果相似度 ≥0.95 说明语义高度重复。注意阈值不能太低，否则正常相似文档被误拦。

  **三种策略的适用场景对比**：

  | 策略 | 检测粒度 | 速度 | 误判率 | 典型场景 |
  |------|---------|------|--------|---------|
  | SHA256 | 字节级精确 | 微秒 | 0% | 同一文件改后缀、重复上传 |
  | MinHash/SimHash | 段落级近似 | 毫秒 | 低 | 小幅修改、加段落、转格式 |
  | Embedding 相似度 | 语义级 | 秒级 | 中（需调阈值） | 同义改写、翻译后上传 |

  **面试建议**：提到"三层递进"说明你有工程分层思维。当前项目只做了第一层（SHA256 + UNIQUE 约束），第二第三层预留了扩展点。面试官问为什么没全做——回答"当前阶段精确重复占了 90% 问题，SHA256 就够了。后续用户反馈有近似和语义重复时，再按需加上 MinHash 和 Embedding 检测。"

- **知识点**：文档去重、SHA256、MinHash、SimHash、Embedding 相似度、工程分层思维

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

### SQLite WAL 模式`⭐`
**Q**: WAL 模式如何解决并发问题？
**A**: WAL（Write-Ahead Logging）允许读操作不阻塞写操作。读操作读旧的 DB 文件，写操作写 WAL 日志，两者互不干扰。配合 `busy_timeout=30000` 让 SQLite 等待 30 秒而不是立即报错，再加上 `NullPool` 确保每次获取新连接而不是复用池连接。三个措施一起解决 SQLite 并发问题。

### FAISS 索引与 DB 一致性`⭐⭐`
**Q**: 为什么 FAISS 索引和 DB 数据会不一致？
**A**: FAISS 索引文件存磁盘（.bin），SQLite DB 存 chunk 原文和元数据。如果只重建 DB 不删 FAISS，旧 chunk_id 还在 FAISS 索引里，查出来的是过期的 chunk_id。删除文档或重建 DB 时必须同时操作两者。

### Windows 终端 curl 差异`⭐`
**Q**: Windows 终端 curl 有哪些坑？
**A**: ①PowerShell 的 `curl` 是 Invoke-WebRequest 别名，用 `curl.exe` 才是真 curl；②cmd 不支持单引号，必须用双引号；③cmd 不支持 `\` 行续符，命令要写在一行；④cmd 发送中文 JSON 要用 `-d @file.json` 方式（文件 UTF-8 编码），直接写中文会 GBK 编码乱码。

### HTTP Header vs Body`⭐`
**Q**: HTTP 请求的头部和体各负责什么？
**A**: Header 传元数据（Content-Type、Authorization、Content-Length），Body 传实际数据（JSON、文件）。类比：Header 是信封上的信息，Body 是信封里的信。

### 如何评价 RAG 检索质量`⭐⭐`
**Q**: 如何评价 RAG 检索质量？
**A**: 三个维度：①相似度分数——FAISS 返回的内积值（余弦相似度），越接近 1 越相关，低于 0.3 基本不相关；②chunk 内容是否包含答案所需信息；③top-k 个结果中相关结果的比例。当前待优化点：按 chunk_index 排序（应改为按相似度排序）、缺少相似度阈值、缺少 BM25 混合检索。

### RAG 幻觉：为什么 LLM 不按检索内容回答？`⭐⭐⭐`
**Q**: LLM 不按 RAG 检索到的内容回答，自己编答案，为什么？怎么解决？
**A**: 本质是 LLM 的预训练知识压过了检索到的上下文。即使 RAG 检索到了正确答案，LLM 也可能选择相信自己"学过"的东西，而不是刚给它的材料。解决方法分层递进：

**第一层（最便宜）：改 system prompt**。当前 `chat.py` 的 system prompt 只有"你是一个智能助手"，没有约束 LLM 必须优先使用检索内容。加上"严格基于检索内容回答，不要自行推测"就能大幅缓解。LLM 的"该信检索还是信自己"的权衡，本质上就是 prompt 里的一句话。

**第二层：要求引用来源**。让 LLM 输出"根据知识库[3]，chunk_size 默认是 500"。当需要"说出处"时，编造的成本变高，LLM 会更倾向引用检索内容。

**第三层：提高检索质量**。如果检索到的 top-k chunk 里本来就不包含正确答案，那就不是幻觉问题，是召回问题。需要优化 embedding、chunk 策略或增加检索路数。

### RAG 系统的 5 种常见幻觉类型`⭐⭐⭐`
**Q**: RAG 系统中 LLM 的幻觉有哪些常见类型？

**A**: 5 种，按出现频率从高到低：

**1. 知识冲突**（最常见）
- 现象：检索内容与 LLM 训练数据矛盾时，LLM 选择相信自己的记忆。如 eval 中 chunk_size=500（检索到的） vs 512（LLM 记忆中的），LLM 回答了 512
- 原因：LLM 训练数据里"512 是标准 chunk size"的记忆比刚给的检索内容更强
- 解决：prompt 明确优先级 + 要求引用

**2. 事实捏造**
- 现象：答案中出现检索内容里不存在的人名、日期、数字
- 原因：temperature 偏高、prompt 没约束说"不知道就说不知道"
- 解决：temperature=0 + prompt 明确"不知道就说不知道，别编"

**3. 上下文过载**
- 现象：多源信息（RAG chunk + 图谱 + 网络搜索）混在一起，关键信息被稀释。如 eval 中"数据存在哪里？"答成了"数据可以存在很多地方（云存储、磁盘）"，完全没提 SQLite/FAISS/Neo4j
- 原因：top_k 太大，不相关的 chunk 淹没了相关的；context 过长导致注意力衰减
- 解决：减少 top_k、加相似度阈值（<0.3 的丢掉）、优先把关键信息放在 prompt 靠前位置

**4. 推理链条断裂**
- 现象：需要多步推理的问题，LLM 中间跳了一步。如"上传后系统会做什么"只答了"分块向量化"漏了"存 FAISS"
- 原因：长上下文中越靠后的信息越容易被忽略
- 解决：关键信息放 prompt 前面；让 LLM 分步输出推理过程

**5. 即兴发挥**
- 现象：检索内容不够时，LLM 自己补充"合理但不存在的细节"
- 原因：LLM 的训练目标就是"生成合理的续写"，不是"生成真实的事实"
- 解决：目前最有效的方法还是 prompt 约束 + 引用要求。RAG 2.0（解码时实时查证）还在研究阶段

### 当前项目的防幻觉弱点`⭐⭐⭐`
**Q**: MemBrain 当前在防幻觉方面有哪些具体问题？
**A**: 4 个：

1. **system prompt 太弱**：`chat.py:132` 只有"你是一个智能助手，请用中文回答问题"，没有任何防幻觉约束
2. **没有引用机制**：LLM 不需要为自己的回答负责，编了也没后果
3. **没有检索质量过滤**：相似度低于 0.3 的 chunk 也送进 context，反而成为干扰
4. **两套 prompt 互相独立**：`chat.py` 的 system prompt 和 `nodes.py` 的 reasoning prompt 各自定义，没有统一管理。改了 chat.py 忘了改 nodes.py，或者反过来

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

### Q1: 图数据库和关系型数据库的区别？`⭐⭐`
- **标准回答**：关系型数据库（SQLite）存表，适合"用户列表"这种整齐数据；图数据库（Neo4j）存节点和关系，适合"谁认识谁、什么依赖什么"这种带关系的数据
- **知识点**：数据库分类、图 vs 关系型

### Q2: Neo4j 为什么用 Docker 部署？`⭐`
- **标准回答**：Windows 上原生安装 Neo4j 麻烦（需要 Java 环境、配置服务），Docker 一行命令搞定。数据通过 volume 映射到本地目录，容器删了数据不丢
- **知识点**：Docker 部署、数据持久化

### Q3: RAG 和知识图谱的关系？`⭐⭐⭐`
- **标准回答**：两者互补。RAG 存原文做模糊搜索（"这篇文章讲了什么"），图谱存实体关系做精确查询（"张三在哪工作"）。同一份文档两边都存，聊天时两条路并行检索，合并上下文后发给 LLM
- **知识点**：RAG vs 知识图谱、混合检索

### Q4: lifespan 是什么？`⭐`
- **标准回答**：FastAPI 的生命周期管理，`yield` 之前是启动时执行（初始化数据库、加载模型、连 Neo4j），`yield` 之后是关闭时执行（清理资源）。比旧版 `@app.on_event("startup")` + `@app.on_event("shutdown")` 分开写更安全，不会漏关闭
- **知识点**：FastAPI 生命周期、资源管理

### Q5: Text2Cypher 怎么工作的？`⭐⭐⭐`
- **标准回答**：用户问题 → 获取图数据库结构（节点标签、关系类型）→ LLM 将问题转为 Cypher 查询语句（低温度保证准确性）→ 执行查询 → 格式化结果。比直接让 LLM 回答更准确，因为查询结果是确定的，LLM 只需做"翻译"工作
- **知识点**：Text2Cypher、LLM 翻译

### Q6: 实体提取为什么用 LLM 而不是 NLP 库？`⭐⭐⭐`
- **标准回答**：LLM 泛化能力强，能理解上下文，准确率高。NLP 库需要预定义实体类型，遇到没见过的词就漏了。缺点是需要调 API、有延迟和成本。低温度（0.1）确保每次提取结果一致
- **知识点**：实体提取方案选型、LLM vs NLP

### Q7: 为什么用 MERGE 而不是 CREATE 存三元组？`⭐⭐`
- **标准回答**：`MERGE` = 找得到就用已有的，找不到才新建。防止同一篇文档反复上传时产生重复实体和关系。如果两次上传都提取出 `(张三)--[任职于]-->(字节跳动)`，用 CREATE 会创建两套重复数据，用 MERGE 只会有一套
- **知识点**：Cypher 语法、幂等操作

### Q8: 为什么 Text2Cypher 要做安全检查？`⭐⭐⭐`
- **标准回答**：限制 LLM 生成的 Cypher 必须以 `MATCH` 或 `CALL` 开头，禁止 `CREATE`、`DELETE`、`MERGE` 等写操作。防止用户通过聊天对话意外篡改图数据。只读查询是安全的，任何写操作都应该通过专门的服务端代码控制
- **知识点**：安全设计、LLM 输出校验

### Q9: 为什么 api_messages 里 RAG 插在 [1]、图谱插在 [2]？`⭐⭐`
- **标准回答**：RAG 是主要知识来源，图谱是补充。RAG 上下文（原文 chunk）比图谱上下文（关系三元组）信息量更大、更可靠。RAG 插在前面意味着 LLM 在处理上下文时优先看到 RAG 结果。如果图谱插在前面，可能会让 LLM 更偏向关系答案而忽略原文
- **知识点**：Prompt 设计、上下文顺序

### Q10: 为什么用 neo4j 驱动而不是 langchain-neo4j？`⭐⭐`
- **标准回答**：`neo4j` 驱动轻量（<1MB），只负责执行 Cypher 拿结果。`langchain-neo4j` 是 langchain 的封装，带全家桶依赖。本项目只需要执行 Cypher 语句，不需要 langchain 的链式调用，少一层封装少一层问题
- **知识点**：依赖管理、库选型

### Q11: 为什么 RAG 和图谱的异常都只跳过不报错？`⭐⭐⭐`
- **标准回答**：RAG 和图谱是"增强"而不是"必需"。两个检索各自用独立 try/except，异常只记 warning 不抛到上层。即使 Neo4j 没开、FAISS 索引为空、LLM 生成 Cypher 失败，聊天也能正常进行，只是回答里缺少相关知识
- **知识点**：异常隔离、防御性编程

### Q12: 为什么用 `getattr(request.app.state, "neo4j", None)` 而不是直接 `.neo4j`？`⭐⭐`
- **标准回答**：没 Docker 时 lifespan 里 Neo4j 初始化失败，`app.state` 上根本没有 `neo4j` 属性。直接 `.neo4j` 抛 `AttributeError`，`getattr` 返回 `None` 就跳过了。同样原因，路由和 service 里都用 `neo4j=None` 作为默认参数
- **知识点**：Python 安全取值、可选依赖设计

### Q13: 第 10 步（图谱提取）的 try/except 为什么包在 RAG 的 try 里面？`⭐⭐`
- **标准回答**：第 10 步和第 1-9 步在同一个 try 块里，但第 10 步有自己的独立 try/except。这样分层设计保证：RAG 失败 → 文档上传整体失败（轮不到第 10 步）；RAG 成功、图谱提取失败 → 文档上传成功（图谱只跳过）；不会出现图谱异常导致 RAG 白做的情况
- **知识点**：异常嵌套、事务边界

---

## 项目架构

### Q1: 各文件夹分别干什么？怎么协作？`⭐⭐⭐`

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

### Q1: 为什么搜索用 SerpAPI 而不是直接调 Google/Bing API？`⭐⭐`
- **标准回答**：SerpAPI 是搜索聚合器，一个接口同时支持 Google、Bing、百度等，不需要注册多个搜索引擎的 API。且 SerpAPI 返回的结构化数据（title/snippet/link）比直接爬取网页更稳定
- **知识点**：搜索 API、数据聚合

### Q2: title / snippet / link 各是什么？`⭐`
- **标准回答**：title=网页标题（蓝色可点击文字），snippet=摘要片段（标题下方的灰色描述），link=网页 URL。LLM 根据这三项信息判断结果是否相关，并引用到回答中
- **知识点**：搜索结果结构、SEO

### Q3: 为什么用直接注入搜索结果的方式，而不是 Function Calling？`⭐⭐⭐`
- **标准回答**：当前是"无脑搜索"模式——每次聊天都搜，把结果直接塞进消息列表。好处是简单可靠（不依赖 LLM 的判断能力），坏处是每次聊天都消耗 SerpAPI 额度。Function Calling 模式（LLM 自主决策是否搜索）留到 Stage 5 LangGraph 阶段再实现
- **知识点**：工具调用模式、Function Calling vs 固定管线

### Q4: 网络搜索结果在上下文里排第几位？为什么？`⭐⭐`
- **标准回答**：`[0]system [1]RAG [2]图谱 [3]网络搜索 [4..]历史`。优先级：本地知识 > 实体关系 > 实时信息。RAG 最优先因为它是用户自己的文档，图谱其次因为它是从文档中提取的结构化信息，网络搜索最后因为它是外部信息仅供参考
- **知识点**：上下文优先级、信息融合

### Q5: aiohttp.ClientSession 需要传 engine 参数吗？`⭐`
- **标准回答**：aiohttp 没有 engine 参数，用的是 connector（`TCPConnector`）。默认的 `ClientSession()` 内部自动创建默认 connector，管理连接池、超时等。只有需要自定义（如限制连接数、设置代理）时才显式传 connector
- **知识点**：aiohttp 连接管理

---

## Stage 5: LangGraph 智能路由

### Q1: 为什么用 LangGraph 替代原来的三个固定检索块？`⭐⭐⭐`
- **标准回答**：原来每次聊天都无脑执行 RAG → 图谱 → 搜索，问候语也搜、闲聊也查，浪费 API 额度、增加延迟。LangGraph 通过 classify 节点让 LLM 先判断需要哪些知识源，不相关的就不跑。还能并行执行多个检索（如 RAG + 搜索同时跑）
- **知识点**：Agent 框架、动态路由 vs 固定管线

### Q2: classify 节点怎么知道需要哪些知识源？`⭐⭐⭐`
- **标准回答**：classify_node 用 LLM prompt 分析用户问题，返回 `["rag"]` / `["graph"]` / `["web"]` / 组合 / `[]`。prompt 里描述了每个知识源的能力（rag=本地文档、graph=实体关系、web=实时信息），LLM 根据问题类型判断。返回 `[]` 时直接跳过所有检索进入 LLM 回答
- **知识点**：LLM 决策、Prompt 设计、分类任务

### Q3: route_decision 为什么返回 list？怎么实现并行？`⭐⭐⭐`
- **标准回答**：LangGraph 的条件边支持两种返回类型：单字符串（走一条边）或 list 字符串（同时走多条边）。`route_decision` 返回 `["rag", "web"]` 时，LangGraph 内部把 rag_node 和 web_node 当作互不依赖的节点同时执行。这是 LangGraph 对比普通状态机的重要优势
- **知识点**：LangGraph 条件边、并行执行、状态机

### Q4: 为什么用 functools.partial 注入依赖？`⭐⭐⭐`
- **标准回答**：LangGraph 节点函数的签名必须是 `(state: AgentState) -> dict`，没法直接传 embedder/vector_store/db 等外部依赖。用 `partial` 把依赖"预绑定"到节点函数上，生成的偏函数仍然满足 `(state) -> dict` 签名。这样节点函数保持纯函数风格，不搞全局变量或类实例单例
- **知识点**：依赖注入、Python 偏函数、函数式编程

### Q5: LangGraph 为什么只做路由不处理流式回复？`⭐⭐⭐`
- **标准回答**：LangGraph 负责"路由决策 + 检索执行"，检索完成后把结果写入 AgentState 的各 context 字段。真正的 LLM 流式回复仍在 chat.py 中通过 openai 库 SSE 输出。这样 LangGraph 只做确定性工作（调用节点、传递状态），不需要处理 SSE 长连接、流中断、重连等复杂逻辑。各司其职
- **知识点**：职责分离、SSE 流式处理、Agent 边界

### Q6: 为什么 router 在第一次聊天时懒加载而不是启动时构建？`⭐⭐`
- **标准回答**：`build_router()` 需要 embedder、vector_store、db、neo4j 等参数，这些在 lifespan 启动时初始化。如果放在启动时构建，lifespan 会变得更重。懒加载在 `request.app.state.router` 上缓存，第一次聊天时构建一次，后续复用。既不影响启动速度，又不需要全局变量
- **知识点**：懒加载、FastAPI app.state、lifespan 优化

### Q7: chat.py 集成时为什么还用 try/except 包住 ainvoke？`⭐⭐⭐`
- **标准回答**：虽然 LangGraph 路由已经替代了固定管线，但异常兜底仍然需要。ainvoke 可能因为 LLM API 超时（classify 判断失败）、FAISS 索引为空、Neo4j 没开等原因报错。try/except 包住保证即使 LangGraph 路由失败，聊天功能也不中断（只是不带检索上下文）
- **知识点**：异常隔离、防御性编程、降级策略

---

## LangChain 概念

### Q1: LangChain 是什么？为什么用？`⭐⭐`
- **标准回答**：LLM 开发的工具包，把常见操作（调 LLM、切文档、调工具）封装成了标准接口。核心组件：Document Loaders 加载文档、Text Splitters 分割文本、Embeddings 向量化、Vector Stores 存储向量、Chains/LCEL 编排流程、Tools 工具定义。优势是接口统一、组件丰富、快速原型。缺点是过度封装、调试困难、版本碎片化、依赖重。生产环境大厂很少直接引全量 LangChain
- **知识点**：LangChain 定位、优缺点、适用场景

### Q2: LangChain 的 6 个核心组件分别是什么？`⭐⭐`
- **标准回答**：
  1. **Document Loaders** — 文档加载器，从 PDF/TXT/MD 等读取文本，如 `PyMuPDFLoader`
  2. **Text Splitters** — 文本分割器，如 `RecursiveCharacterTextSplitter` 按段落/句子递归切分
  3. **Embeddings** — 向量化接口，统一封装不同 embedding 模型（OpenAI/HuggingFace/本地）
  4. **Vector Stores** — 向量存储，FAISS/Chroma/Pinecone 等统一接口
  5. **Chains / LCEL** — 链式调用，用 `|` 管道符串联组件：`chain = prompt | llm | parser`
  6. **Tools** — 工具定义，`@tool` 装饰器自动生成 tool schema 给 LLM
- **知识点**：LangChain 组件体系、LCEL 语法

### Q3: LangChain 和 LangGraph 什么关系？`⭐⭐⭐`
- **标准回答**：LangGraph 是 LangChain 生态的一部分，专门做 Agent 状态机编排。LangChain 负责单步操作（加载文档、调 LLM），LangGraph 负责多步协作（循环、条件分支、并行）。可以只用 LangGraph 而不用整个 LangChain — 本项目就是例子：只引了 `langgraph`，其他部分（分块、向量化）直接调底层库
- **知识点**：LangChain  vs LangGraph 职责边界

### Q4: Function Calling 和 classify prompt 模式有什么区别？`⭐⭐⭐`
- **标准回答**：classify 模式是让 LLM 输出自由文本 → 你手动解析关键词匹配到工具。Tool Calling 是 API 层面的原生支持：显式传 `tools=tools`，LLM 返回结构化 `tool_calls` JSON，代码直接读。区别：classify 的 LLM 并不知道"有工具可用"，它只是在回答问题；Tool Calling 的 LLM 是主动选择调工具。后者是 agent 面试的核心考点
- **知识点**：Tool Calling vs Prompt 路由、结构化输出

### Q5: 面试被问到 LangChain 应该怎么回答？`⭐⭐⭐`
- **标准回答**："LangChain 我主要用到了 LangGraph（智能路由）和 Text Splitters（文本分块）。其他部分（Embeddings、Vector Stores、Document Loaders）我了解 LangChain 有现成的实现，但项目里选择直接调底层库，因为少一层封装更容易理解和调试。LangChain 的优势在快速原型和统一接口，但生产环境我会评估是否需要它的全部功能，通常大厂会自己封装轻量替代或只取特定组件。"
- **知识点**：面试话术、技术选型、独立思考

---

## Stage 6: 缓存 + Docker Compose + 基础测试

### Q1: 存数据有几种方式？Redis、数据库各什么时候用？`⭐⭐⭐`
- **标准回答**：三种存储各司其职。①**SQLite** 存"不能丢的"——用户信息、对话历史、文档内容、chunk 原文，数据持久化且强一致。②**Redis 语义缓存** 存"丢了再算的"——问题和回答的向量+原文，命中直接返回省 LLM 调用，TTL 过期或缓存清空后下次重新计算。③**FAISS 向量索引** 存"检索专用的"——向量的倒排索引，不做持久化只做相似度搜索。原则：核心数据放 SQLite，加速数据放 Redis，检索专用数据放 FAISS
- **知识点**：多层存储架构、冷热数据分离

### Q2: Redis 语义缓存为什么不直接存原文，而要存向量？`⭐⭐⭐`
- **标准回答**：语义缓存不是 KV 精确匹配（key=问题，value=回答），而是"语义相似匹配"。存向量是为了计算余弦相似度：新问题"今天天气如何"和缓存里的"今天天气怎么样"虽然字面不同，但语义相似度 ≥0.92 就可以直接复用缓存的回答。如果只存原文就只能精确匹配，失去"语义"的意义
- **知识点**：语义缓存、向量相似度、精确匹配 vs 模糊匹配

### Q3: Redis Hash 存了哪些字段？数据结构是什么？`⭐⭐`
- **标准回答**：每条缓存用 Redis Hash 存 4 个字段：`vec`（问题的向量，base64 编码的 pickle 序列化）、`question`（问题原文，用于调试/展示）、`answer`（LLM 的完整回答）、`ts`（时间戳，用于 TTL 过期）。key 是 `cache:{hash(question)}`，方便 SCAN 遍历。Hash 结构适合存结构化数据，4 个字段一起读写，比 JSON 字符串更灵活（可单独读某个字段）
- **知识点**：Redis 数据结构、Hash 应用场景、序列化方案

### Q4: pickle 序列化向量怎么理解？`⭐`
- **标准回答**：numpy 数组（向量）是二进制对象，不能直接存到 Redis（特别是 `decode_responses=True` 时 Redis 会尝试把返回值解码为 UTF-8 字符串）。解决方案：`base64.b64encode(pickle.dumps(vec)).decode()` 把 numpy 数组 → pickle 字节流 → base64 字符串。读的时候逆操作：`pickle.loads(base64.b64decode(data["vec"]))` 还原为 numpy 数组。Base64 编码只增加约 33% 体积，但对 768 维向量来说完全可以接受
- **知识点**：序列化、numpy 存储、base64 编码

### Q5: SCAN 遍历时 cursor、count、match 各是什么？`⭐⭐`
- **标准回答**：SCAN 是 Redis 的游标迭代器。①**cursor**=游标位置，从 0 开始，每次返回新 cursor 和一批 key，当 cursor 回到 0 时遍历完成（如 cursor=130 表示下次从第 130 个槽位继续）。②**count=100**=建议每批返回约 100 个 key（不是精确值，Redis 按哈希槽取）。③**match="cache:*"**=模式匹配，只返回 key 以 "cache:" 开头的条目。相比 KEYS 命令，SCAN 不阻塞 Redis，适合生产环境
- **知识点**：Redis SCAN 原理、游标迭代、模式匹配

### Q6: 余弦相似度匹配的流程是什么？`⭐⭐⭐`
- **标准回答**：新问题来的时候做两件事：①用 Embedder 把问题转成向量 q_vec；②SCAN 遍历所有 `cache:*` key，对每个缓存条目取 `vec` 字段反序列化为向量 c_vec，算 `cosine_sim = dot(q_vec, c_vec) / (norm(q_vec) * norm(c_vec))`。如果 `max_sim ≥ 0.92`，直接返回对应缓存的 answer；否则继续调 LLM，收到回复后再写入缓存。阈值 0.92 表示语义高度相似但不是字面完全一致
- **知识点**：余弦相似度算法、阈值判断、缓存命中策略

### Q7: 清空缓存的代码怎么理解？`⭐`
- **标准回答**：`clear()` 函数用 `async for key in redis.scan_iter(match="cache:*"):` 遍历所有缓存 key（内部也是 SCAN 机制但封装成异步迭代器），然后 `await redis.delete(*keys_batch)` 分批删除。不能直接 `FLUSHALL`（会清空 Redis 所有数据包括其他业务 key），只删 `cache:*` 前缀的 key。删除后下次聊天重新构建缓存
- **知识点**：Redis 批量删除、scan_iter、key 命名空间

### Q8: 为什么测试要用 ASGITransport 而不是启动 uvicorn？`⭐⭐`
- **标准回答**：ASGITransport 直接调用 FastAPI 的 ASGI 接口，不需要启动 uvicorn 进程，毫秒级响应。如果用 uvicorn 测试需要先启动服务器（`subprocess.Popen`）、等端口监听、再发 HTTP 请求，每个测试用例都要等待服务器启动关闭，慢 100 倍。ASGITransport 是 httpx 提供的测试工具，专门用于 ASGI 框架的单元测试
- **知识点**：ASGI 协议、FastAPI 测试策略、httpx 测试工具

### Q9: dependency_overrides 怎么实现测试数据库隔离？`⭐`
- **标准回答**：`app.dependency_overrides[get_db] = lambda: session` 替换 FastAPI 的数据库依赖。原本 `get_db` 连接 `membrain.db`，测试时替换为连接 `sqlite+aiosqlite://`（内存数据库）的 session。每个测试用例通过 `autouse=True` 的 `db_session` fixture 创建全新的内存 SQLite → 建表 → 覆盖依赖 → 测试执行 → 关闭引擎 → 清除覆盖。实现"互不干扰、用完即弃"，不影响开发数据库
- **知识点**：依赖注入、FastAPI 测试、数据库隔离

### Q10: SSE 流式聊天测试怎么测？`⭐⭐`
- **标准回答**：SSE 是流式响应，不能用常规的 `client.post()`（等全部返回才解析）。用 `client.stream("POST", ...)` 逐行读取：①检查 `resp.status_code == 200`；②逐行遍历 `resp.aiter_lines()`，找到 `data:` 前缀的行；③读到 `data: [DONE]` 标记时 break，说明流正常结束。核心验证点是"流能正常走完并输出内容"，不验证具体返回什么文字（因为 LLM 回答不确定）
- **知识点**：SSE 测试、流式断言、httpx stream

### Q11: 语义缓存怎么调优？`⭐⭐⭐`
- **标准回答**：
  三个方向，按收益排序：

  **① 阈值调优（最关键）**
  相似度阈值 0.92 是经验值，不一定最优。调优方法：收集一批真实问题，人工标注"是否同一问题"的配对数据，画 PR 曲线（精确率-召回率曲线）找到最优阈值。比如在面试问答场景，0.95 可能太严（"LangGraph 用什么写的"和"项目用什么语言"虽然不同但答案都是 Python，应该命中），0.85 可能太松（"怎么部署"和"怎么测试"意思不同，不该命中）。要根据实际数据找到平衡点。

  **② SCAN 性能优化**
  缓存越多 SCAN 越慢——每条都要反序列化向量 + 算余弦相似度，O(n) 复杂度。1000 条缓存时几十毫秒，10000 条就上百毫秒。改进方案：在本地维护一个轻量 FAISS 辅助索引，新缓存写入时向量同时加入 FAISS，查缓存时直接 FAISS search（O(log n)），毫秒级返回。

  **③ 分级 TTL**
  当前所有缓存统一 1 小时。可以差异化：事实类问题（"MemBrain 用了什么框架？"）答案不会变，TTL 放到 1 天；实时类（"今天天气"）5 分钟就过期；问候类（"你好"）不缓存。另外加 LRU 淘汰 + 热点保活——缓存满了淘汰最久未命中的，热点问题每次命中刷新 TTL。

  **一句话总结**：一调阈值（数据驱动找最优值）、二换索引（FAISS 替代 SCAN）、三分级 TTL（按场景定过期时间）。
- **知识点**：缓存调优、PR 曲线、FAISS 索引、TTL 策略

---

## AutoDL 部署

### Q1: 为什么 AutoDL 重启后代码/文件就没了？`⭐`
- **标准回答**：AutoDL 实例有两类存储。①**系统盘**（临时）— conda 环境、pip 包、`/root/` 下的文件都在这，关机后清空。②**`/root/autodl-tmp/`**（持久化）— 挂载的云硬盘，关机重启不丢。所以项目代码一定要放 `/root/autodl-tmp/` 下。conda 环境虽然装一次就能用，但实例销毁后需要重建
- **知识点**：云服务器存储类型、数据持久化

### Q2: conda 环境和"文件夹"有什么关系？`⭐`
- **标准回答**：可以通俗地理解成"独立的 Python 文件夹"。`conda create -n membrain python=3.10` ≈ 新建一个叫 `membrain` 的文件夹，在里面装 Python 3.10 + 独立包管理。`conda activate membrain` ≈ 告诉系统"接下来用这个文件夹里的 Python"。这样做的好处：不影响系统自带的 Python（如 3.8，系统还要用），一个环境装什么包都不会搞乱别的环境，互不干扰
- **知识点**：虚拟环境、conda 原理、环境隔离

### Q3: 为什么项目路径里有两个 membrain（Membrain/membrain）？`⭐`
- **标准回答**：第一个 `Membrain/`（大写）是用户手动创建的文件夹，作为项目容器。第二个 `membrain/`（小写）是 `git clone` 自动生成的，里面才是真正的项目文件（`app/`、`requirements.txt` 等）。正常的目录结构是：`/root/autodl-tmp/Membrain/membrain/`。如果觉得嵌套深，可以把子目录内容移到上层
- **知识点**：git clone 行为、目录结构设计

### Q4: huggingface.co 连不上怎么办？`⭐`
- **标准回答**：AutoDL 实例在国内，huggingface.co 被网络屏蔽。设置镜像环境变量解决：`export HF_ENDPOINT=https://hf-mirror.com`。然后在应用启动前先手动下载模型：`python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('shibing624/text2vec-base-chinese')"`。如果加到 `~/.bashrc` 里就不用每次设了。备用镜像：`https://hf.llm.info`
- **知识点**：国内网络环境、镜像源配置、HuggingFace 模型下载

### Q5: 应用启动时 Neo4j 连接失败、Redis 连不上怎么办？`⭐`
- **标准回答**：设计上 Neo4j 和 Redis 是可选依赖，连接失败只记 warning，不影响应用启动。Noe4j 失败 → 图谱功能不可用，聊天跳过图谱检索。Redis 失败 → 缓存功能不可用，每次聊天都调 LLM。核心聊天功能（认证、对话、RAG）完全正常。因此 AutoDL 上没有 Docker 也能跑，只是少了图数据库和缓存
- **知识点**：可选依赖设计、优雅降级、防御性编程

### Q6: AutoDL 上怎么让外部访问 API？`⭐`
- **标准回答**：`uvicorn app.main:app --host 0.0.0.0 --port 8000` 绑定到所有网卡（0.0.0.0），然后在 AutoDL 控制台 → 实例详情 →「端口映射」添加容器端口 8000，复制生成的外网地址。浏览器访问 `http://<外网地址>/docs` 即可看到 Swagger API 文档。注意：`--host 0.0.0.0` 必须加，默认是 localhost 外部访问不到
- **知识点**：AutoDL 端口映射、网络绑定、外网访问

### Q7: AutoDL 开机自启服务怎么做？不想开了怎么关？`⭐`
- **标准回答**：用 crontab 的 `@reboot` 实现。①创建启动脚本（放 `/root/autodl-tmp/` 持久化目录确保不丢），chmod +x 给执行权限。②`crontab -e` 加一行 `@reboot bash /path/to/script.sh`，保存退出，下次实例重启后自动拉起服务。**不想开了**就 `crontab -e` 删掉或注释那行即可。注意脚本里需要 `source ~/miniconda3/etc/profile.d/conda.sh` 来激活 conda 环境，因为 crontab 不会自动加载 shell 配置
- **知识点**：Linux 开机自启、crontab @reboot、进程守护

---

## Docker 部署

### Q1: Docker Desktop 在国内拉不了镜像怎么办？`⭐`
- **标准回答**：Docker Hub 在国内被墙，需要代理或镜像加速器。方案一：Docker Desktop → Settings → Resources → Proxies → 配置 HTTP/HTTPS 代理（如 `http://127.0.0.1:10810`）→ Apply & Restart。方案二：配置 `~/.docker/daemon.json` 的 `proxies` 字段。方案三：用国内镜像加速器（中科大 `https://docker.mirrors.ustc.edu.cn`、网易 `https://hub-mirror.c.163.com`），配到 Docker Engine 的 `registry-mirrors` 中
- **知识点**：Docker 网络配置、代理、镜像加速

### Q2: WSL 版本太旧导致 Docker Desktop 无法启动怎么办？`⭐`
- **标准回答**：Docker Desktop 依赖 WSL2 运行 Linux 虚拟机。WSL 版本过旧时 Docker 引擎无法启动，表现为鲸鱼图标一直转动。解决方案：管理员终端执行 `wsl --update` 更新 WSL 内核，然后 `wsl --shutdown` 重启 WSL，最后重启 Docker Desktop
- **知识点**：WSL2、Docker Desktop 启动流程、Linux 虚拟机

### Q3: docker compose up -d 一键启动了什么？`⭐`
- **标准回答**：`docker compose up -d` 启动项目依赖的所有服务：①**Neo4j 5-community**（端口 7474 Web 管理 + 7687 Bolt 协议，数据持久化到 `./data/neo4j`）②**Redis 7-alpine**（端口 6379，appendonly 持久化模式）。应用启动时 lifespan 自动连接两者，连接成功日志为 `Neo4j 连接成功` / `Redis 缓存连接成功`，失败只记录 warning 不阻止应用启动
- **知识点**：Docker Compose 编排、服务依赖、优雅降级

### Q4: Docker 容器和 volume 的关系？`⭐`
- **标准回答**：容器是"临时运行的程序"，volume 是"持久化存储"。容器删除后内部数据全丢，volume 独立于容器生命周期存在。Neo4j 数据通过 `./data/neo4j:/data` 绑定挂载到宿主机目录，Redis 通过命名 volume `redis_data:/data` 管理。原则：数据库等有状态服务必须挂 volume，配置写入代码的可以无状态
- **知识点**：Docker 存储、volume 挂载、数据持久化

### Q5: 本地 Docker 和 AutoDL 的环境差异？`⭐`
- **标准回答**：本地有 Docker 可启动 Neo4j + Redis，图谱和缓存功能完整；AutoDL 没有 Docker，Neo4j 和 Redis 自动跳过，核心聊天（认证、RAG）不受影响。代码层面已适配两种环境：lifespan 中 try/except 包住连接逻辑，失败只记 warning。本地开发时所有能力全开，生产部署择需取舍
- **知识点**：开发 vs 生产环境、可选依赖、graceful degradation

### Q6: 作为面试作品，需要掌握 Docker 吗？`⭐⭐`
- **标准回答**：不需要。Docker 在 agent 开发面试中几乎不会作为核心考点。面试更关注 Function Calling / Tool Calling 原理、ReAct 循环、LangGraph 编排、Prompt 工程。Docker 最多被顺带问一句"项目中的 Neo4j 怎么部署的"，回答"用 Docker Compose 编排"就足够了。工作中初/中级 agent 开发也不需要深钻 Docker，能用 `docker compose up` 启动服务就行。时间应该花在 agent 核心能力上
- **知识点**：面试准备、技术选型优先级、学习路径

### Q7: Docker Desktop 界面看不懂、不知道进程在干嘛怎么办？`⭐`
- **标准回答**：不用管。Docker Desktop 里的英文界面、容器列表、日志输出是为运维准备的，agent 开发者不需要看懂。只需要记住三个命令：`docker compose up -d`（启动服务）、`docker compose down`（停服务）、`docker compose ps`（看状态）。把 Docker 想象成家里的路由器——通了就行，不需要懂工作原理。日常使用就是双击 Docker Desktop 等它稳定，然后跑上面那行命令
- **知识点**：Docker 使用边界、工具 vs 原理、学习效率

---

## 部署流程

### Q1: 上传代码到 AutoDL 是通过 git 还是 GitHub？流程和原理是什么？`⭐`
- **标准回答**：两者配合使用。本地代码通过 `git push` 推送到 **GitHub 远程仓库**（中间桥梁），然后 SSH 登录 AutoDL 后 `git pull` 拉取代码。GitHub 在这里充当**两端都能访问的中转站**：本地 PC 和 AutoDL 服务器都能连 GitHub，但无法直接互连。传输链路为 `本地 → git push → GitHub → git pull → AutoDL`。`.env`（密钥）和 `data/`（持久数据）在 `.gitignore` 中不进 git，需要手动复制或重新配置
- **知识点**：Git 工作流、远程仓库、CI/CD 基础、持续部署

### Q2: 日常更新代码到 AutoDL 的完整命令是什么？`⭐`
- **标准回答**：
  ```
  本地：git add . → git commit -m "xxx" → git push
  AutoDL：conda activate membrain → cd /root/autodl-tmp/Membrain → git pull → pip install -r requirements.txt（如有新依赖）→ 杀旧 uvicorn 进程 → 重启 uvicorn
  ```
  核心就三步：本地 push → AutoDL pull → 重启生效
- **知识点**：部署流程、服务重启

### Q3: DEPLOY.md、CHANGELOG.md、CONTRIBUTING.md 是代码规范吗？`⭐`
- **标准回答**：不是。这些是开源社区**约定俗成的习惯**，不是强制规范。README.md（项目介绍）基本都有，DEPLOY.md（部署说明）看项目是否有部署需要，CHANGELOG.md（版本记录）多人协作/发布时用，CONTRIBUTING.md（贡献指南）开源项目才需要。不写不影响项目运行，写了方便协作和查阅
- **知识点**：项目文档规范、约定 vs 强制

### Q4: 本地 git 仓库在哪？git commit 的每一步做了什么？`⭐`
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

### Q5: git 仓库在父目录怎么调整到项目独立仓库？`⭐`
- **标准回答**：当多个项目在同一个 git 仓库下（如 `D:\pythonProject\git\` 下有 `membrain/`、`deepseek_agent/` 等多个项目），需要拆分为独立仓库。

  调整步骤：

  ```bash
  # 第 1 步：备份旧 .git（在 git 根目录操作）
  cd D:/pythonProject/git
  mv .git .git_backup

  # 第 2 步：在项目目录下新建独立仓库
  cd D:/pythonProject/git/membrain
  git init
  git branch -m master main        # 把默认分支名改为 main

  # 第 3 步：更新 .gitignore，排除 data/、.env 等
  # 将 data/faiss_index.bin 和 data/documents/* 改为 data/

  # 第 4 步：暂存 + 首次提交
  git add .
  git commit -m "init: Membrain 独立仓库"

  # 第 5 步：关联 GitHub 并强制推送
  git remote add origin https://github.com/az949527/Membrain.git
  git push -f origin main           # -f 强制覆盖远程历史
  ```

  关键点：
  - `.git/` 现在在 `D:\pythonProject\git\membrain\.git`，可以直接看到
  - GitHub 上文件路径去掉了 `membrain/` 前缀，变成 `app/...` 等
  - `git push -f` 会覆盖远程历史，之前的 commit 记录丢失，但代码不受影响
  - `.gitignore` 中 `data/` 排除了 Neo4j 数据文件和向量索引
- **知识点**：git init、git 仓库拆分、.gitignore、force push

### Q6: AutoDL git pull + 重启的完整流程是什么？遇到异常怎么处理？`⭐`
- **标准回答**：

  **正常流程**：
  ```bash
  # Step 1: SSH 登录
  ssh root@<实例IP> -p <端口>

  # Step 2: 进入项目目录
  cd ~/autodl-tmp/Membrain

  # Step 3: 拉取最新代码
  git pull origin main

  # Step 4: 杀旧进程 + 重启
  ps aux | grep uvicorn        # 找到 PID
  kill <PID>                   # 杀掉旧进程
  export HF_ENDPOINT=https://hf-mirror.com   # 国内镜像
  nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > app.log 2>&1 &
  sleep 5
  cat app.log                   # 确认启动日志

  # Step 5: 验证
  curl http://localhost:8000/
  ```

  **异常及处理方式**：

  | 异常 | 原因 | 处理命令 |
  |------|------|----------|
  | `fatal: refusing to merge unrelated histories` | git 仓库重构后 force push 过，本地和远程历史不兼容 | `git reset --hard origin/main` |
  | `No module named 'app'` | 不在项目目录下执行 uvicorn | `cd ~/autodl-tmp/Membrain` 确认 `app/` 目录存在 |
  | 启动卡在"正在初始化 RAG 组件..." | SentenceTransformer 加载模型到内存，首次可能需要 10-30 秒 | 等 30 秒看日志，二次启动通常 1-2 秒 |
  | `Neo4j 连接失败` | AutoDL 没跑 Docker Neo4j | 不影响核心功能，Warning 级别，跳过即可 |
  | `Redis 连接失败` | Redis 服务未启动 | 检查 `redis-cli ping`，没 Redis 则缓存不可用 |
  | 模型加载报错 `OSError` | `local_files_only=True` 但缓存中没有模型 | 手动下载：`python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('shibing624/text2vec-base-chinese')"` |

  **关键命令速查**：
  ```bash
  git reset --hard origin/main    # 强制对齐远程（丢弃本地历史）
  export HF_ENDPOINT=https://hf-mirror.com  # HuggingFace 国内镜像
  nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > app.log 2>&1 &  # 后台启动
  cat app.log                     # 查看启动日志
  ps aux | grep uvicorn           # 查找进程
  kill -9 <PID>                   # 强制杀掉进程
  curl http://localhost:8000/     # 验证 API 是否正常
  ```
- **知识点**：AutoDL 部署流程、异常处理、git reset、uvicorn 后台运行

## 全链路测试

### Q1: 全链路测试的完整流程是什么？`⭐`
- **标准回答**：

  **测试目标**：验证 登录 → 上传文档 → 聊天（ReAct+RAG）→ 查看追踪 整条链路是否正常。

  **完整流程**（5 步）：

  ```bash
  # === Step 1: 注册 + 登录 ===
  curl -s -X POST http://localhost:8000/api/v1/auth/register \
    -H "Content-Type: application/json" \
    -d '{"email":"test@test.com","username":"test","password":"test123456"}' | python -m json.tool
  # → {"id": 1, "email": "test@test.com", ...}

  TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/token \
    -H "Content-Type: application/json" \
    -d '{"email":"test@test.com","password":"test123456"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
  echo "TOKEN=$TOKEN"
  # → TOKEN=eyJ...

  # === Step 2: 上传文档 ===
  echo "MemBrain是一个基于LangGraph构建的个人知识助手，支持RAG检索、知识图谱查询和网络搜索功能。" > /tmp/test.txt
  curl -s -X POST http://localhost:8000/api/v1/documents/upload \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@/tmp/test.txt" | python -m json.tool
  # → {"id": 1, "filename": "test.txt", "status": "ready", ...}

  # === Step 3: 聊天（验证 ReAct+RAG）===
  curl -N -s --max-time 90 -X POST http://localhost:8000/api/v1/chat \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"messages":[{"role":"user","content":"MemBrain是什么？它用了什么技术？"}]}'
  # → SSE 流式输出，包含 LangGraph、ReAct、RAG 等关键词

  # === Step 4: 查看 Agent 追踪 ===
  curl -s http://localhost:8000/api/v1/agent/traces?limit=5 \
    -H "Authorization: Bearer $TOKEN" | python -m json.tool
  # → 包含 question、sources_selected、rounds、duration_ms 等字段

  # === Step 5: 问候语（验证 __answer__ 直接回答）===
  curl -N -s --max-time 30 -X POST http://localhost:8000/api/v1/chat \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"messages":[{"role":"user","content":"你好"}]}'
  # → SSE 流式输出问候，不走工具检索
  ```

  **关键细节**：
  - 聊天 API 是 SSE 流式响应（`text/event-stream`），不能用 `python -m json.tool` 解析
  - 请求体格式为 `{"messages":[{"role":"user","content":"..."}]}`，不是 `{"content":"..."}`
  - 登录路由是 `/token`，不是 `/login`
  - 用 `--max-time` 设置超时避免 curl 卡死
- **知识点**：全链路测试流程、SSE 流式响应、API 端点格式

### Q2: 全链路测试中遇到的各种异常怎么处理？`⭐`
- **标准回答**：

  | 异常 | 输出特征 | 原因 | 处理方式 |
  |------|---------|------|----------|
  | 邮箱已注册 | `{"detail": "邮箱被注册"}` | 之前测试过，用户已存在 | 换邮箱注册，或直接登录 |
  | 密码错误 | `{"detail": "邮箱或密码错误"}` | 之前的数据库被删除或密码不匹配 | 重新注册新账号 |
  | 路由 404 | `{"detail": "Not Found"}` | 端点路径不对 | 检查路由前缀（`/token` 不是 `/login`） |
  | 请求体格式错误 | `{"detail": [{"msg": "Field required", "loc": ["body","messages"]}]}` | 聊天 API 是 `messages` 数组，不是 `content` | 改为 `{"messages":[{"role":"user","content":"..."}]}` |
  | SQLite 数据库锁 | `sqlite3.OperationalError: database is locked` | 并发写入冲突或进程被杀导致事务中断 | ① 删除锁文件 `rm -f *.db-wal *.db-shm` ② 或删除 db 重建 `rm -f membrain.db` ③ 确保仅 1 个 uvicorn 进程 |
  | Redis 连接失败 | `redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379` | Redis 服务未运行 | 代码中 catch 异常跳过缓存，或启动 Redis 服务 |
  | OpenAI 库报错 | `TypeError: AsyncClient.__init__() got an unexpected keyword argument 'proxies'` | openai 与 httpx 版本不兼容 | `pip install httpx==0.27.2` 降级 httpx |
  | 模型加载报错 | `OSError` 或卡在"正在初始化 RAG 组件..." | embedding 模型不在缓存中 | 手动下载：`python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('shibing624/text2vec-base-chinese')"` |
  | 没找到 uvicorn | `nohup: failed to run command 'uvicorn'` | 不在 conda 环境中 | `conda activate membrain` 后再启动 |
  | curl 卡住无输出 | 终端停住不动 | SSE 流式响应等待 LLM 返回 | 按 Ctrl+C 取消，加 `--max-time` 设超时 |
  | SSE 输出乱码 | `data: ...` 内容不完整 | curl 缓冲问题 | 加 `-N` 参数关闭缓冲 |

  **通用排查思路**：
  1. 先看服务是否正常：`curl http://localhost:8000/`
  2. 再看后端日志：`cat app.log | tail -40`
  3. 日志定位错误类型，对照上表找处理方式
  4. 修完后重启服务：`pkill -f uvicorn` → 等 2s → 重新启动
- **知识点**：异常处理、问题排查方法论、SQLite 并发控制、版本兼容

### Q1: Function Calling / Tool Calling 和 Prompt 路由有什么区别？`⭐⭐⭐`
- **标准回答**：Prompt 路由是让 LLM 输出自由文本（如 `["rag"]`），然后代码手动解析这个文本来决定调用什么工具。Tool Calling 是 API 层面的原生支持：显式传 `tools=tools` 参数给 LLM，LLM 返回结构化的 `tool_calls` JSON，代码直接读取 `tc.function.name` 即可。核心区别：Prompt 路由的 LLM 并不知道"有工具可用"，它只是在回答问题；Tool Calling 的 LLM 主动选择调什么工具，返回格式由 API 保证，不需要手动解析。后者在面试中能体现对 Agent 原理的理解
- **知识点**：Tool Calling vs Prompt 路由、结构化输出、Agent 原语

### Q2: Tool Calling 的 tools 参数怎么定义的？description 为什么重要？`⭐⭐⭐`
- **标准回答**：tools 参数按 OpenAI 的 tool schema 格式定义，每个工具包含 name（工具名，如 `rag_search`）、description（工具能力的描述，如"从本地知识库中搜索用户上传的私有文档内容"）、parameters（参数 schema，用 JSON Schema 格式定义）。description 是 LLM 做路由决策的唯一依据——LLM 看不到工具的实现代码，只能靠 description 判断"这个问题是否应该调用这个工具"。所以 description 要写清楚使用场景，而不是写功能说明
- **知识点**：Tool Schema 设计、LLM 决策依据、面试技巧

### Q3: classify_node 返回 []（空列表）时意味着什么？`⭐⭐⭐`
- **标准回答**：LLM 判断当前问题不需要任何工具（问候语、闲聊等），直接进入 LLM 回答环节，不执行任何检索。这是 Tool Calling 对比"无脑全跑"路线的核心优势——节省 API 额度、减少延迟。面试点：问 LLM 一个问题 → LLM 说不需要工具 → 直接回答。这说明 agent 不是每轮都调工具，而是按需调用
- **知识点**：Agent 按需决策、工具调用策略、效率优化

### Q4: 为什么 "张三和李四是什么关系" 同时触发了 graph_query 和 rag_search？`⭐⭐⭐`
- **标准回答**：LLM 判断这个问题可能需要两种知识源：①graph_query 查询知识图谱中的实体关系（两人之间的关系链）；②rag_search 搜索文档中是否提到这两人的关系。这说明 LLM 具备多工具并行决策能力——不局限于单一工具，而是判断哪些工具可能有用就都调。在代码层面 LangGraph 天然支持 parallel execution，多个工具并行调用互不阻塞。这个现象说明了 Tool Calling 的智能性，也体现了 LangGraph 并行路由的优势
- **知识点**：多工具协同、并行执行、LLM 决策分析

### Q5: 如果 LLM API 超时或报错，classify 节点怎么处理？`⭐⭐⭐`
- **标准回答**：classify_node 的整个 LLM 调用被 try/except 包住，任何异常（超时、API 错误、模型不响应）都返回 ，即所有源全开。这是一个"防御性降级"策略——宁可多跑检索浪费额度，也不能因为路由失败让用户完全得不到回答。与各检索节点的异常处理（单节点失败只跳过自身）配合，形成完整的错误容忍链
- **知识点**：错误处理、降级策略、防御性编程

### Q6: 实现 Tool Calling 后系统架构发生了什么变化？`⭐⭐⭐`
- **标准回答**：路由决策从"写死的 prompt 分类"变成了"LLM 通过 tools 参数自主判断"。其他部分（检索节点、LangGraph 状态机构建、chat.py 集成）完全不变。核心收益是：①路由准确率提升（LLM 知道"有工具可用"）；②结构化输出保证（不用猜 LLM 的文本回复）；③面试价值（Function Calling 是 agent 开发最高频考点）。类似"替换引擎不换车架"——核心替换少、影响小、收益大
- **知识点**：架构演进、最小化改动、增量重构


### Q7: classify_node 的 fallback 策略是什么样的？`⭐⭐⭐`
- **标准回答**：三层兜底。第一层（LLM 调用失败）：API 超时或报错 → `except` 返回全源 `["rag", "graph", "web"]`，宁可多跑不能空手。第二层（工具参数错误或检索为空）：json.loads 解析 tool_calls 失败时跳过该工具；检索节点搜不到内容时返回空字符串，不影响最终 LLM 回答。第三层（整张图全炸）：LangGraph 的 ainvoke 被 try/except 包住 → 降级为纯 LLM 聊天（无检索无缓存），用户至少能正常对话。各层独立保护，单点故障不扩散
- **知识点**：异常隔离、降级策略、防御性编程

### Q8: tool_choice 参数有哪些选项？各用什么场景？`⭐⭐⭐`
- **标准回答**：①`"auto"`（默认）— LLM 自己决定是否调工具，适合多数场景，项目用的就是 auto。②`"none"` — 强制不调工具，适合闲聊场景省 token。③`"required"` — 强制调用工具（传给 parallel_tool_calls），适合必须走工具的管线。④`{"type":"function","function":{"name":"xxx"}}` — 强制调某个特定工具，适合定向测试。面到高级岗位时会问这个，答出来能体现对 API 参数的细致理解
- **知识点**：Tool Calling 参数、LLM API 设计

### Q9: Function Calling 有哪些已知缺陷和边界？`⭐⭐⭐`
- **标准回答**：三个主要缺陷。①**幻觉参数**：LLM 可能构造不存在的工具名或参数格式 → 需要 json.loads try/except + 校验。②**过度调用**：LLM 倾向"用工具比不用好"，不需要时也调用 → 需要下游 fallback（空结果安全）。③**嵌套调用**：一个工具的结果可能触发另一个工具 → 引出了 ReAct 循环。面试中主动指出这些缺陷能体现工程经验
- **知识点**：LLM 幻觉、Agent 边界、ReAct

---

## ReAct 节点

### Q1: nodes.py 里有哪些函数？各自干什么？`⭐⭐⭐`
- **标准回答**：6 个函数。
  - **在用**：`reasoning_node`（ReAct 推理，LLM 用 Tool Calling 决定调工具还是回答）+ `execute_tools_node`（并行执行选中的工具，结果反馈给下一轮推理）
  - **废弃**（旧版 classify 模式残留，不再被 graph.py 引用）：`rag_node` / `graph_node` / `web_node` / `collect_node`
- **知识点**：ReAct 架构、节点职责

### Q2: reasoning_node 的工作流程是什么？`⭐⭐⭐`
- **标准回答**：①从 state 取出 question、history（之前工具调用的记录）、iteration（轮次计数）。②组装 api_messages：system prompt（描述三个工具的能力）+ user question + history。③调 OpenAI LLM，传 tools=TOOLS 参数。④LLM 返回两条路：不选工具（tool_calls 为空）→ `["__answer__"]` 表示可直接回答；选了工具 → 映射为内部源名 `["rag","graph"]`，同时记录 tool_call_record 写入 messages。⑤最多 3 轮强制结束。异常时降级为全源检索
- **知识点**：ReAct 推理、Tool Calling、异常降级

### Q3: execute_tools_node 的工作流程是什么？`⭐⭐⭐`
- **标准回答**：①根据 selected_sources 选中要执行的工具（rag/graph/web）。②用 asyncio.gather 并行执行多个工具，互不阻塞，总耗时≈最慢的那个。③从 state.messages 中提取上一轮 assistant 的 tool_call_id，用于构造合法的 tool role 消息（OpenAI 格式要求：tool 消息必须匹配对应的 tool_call_id）。④遍历结果：更新 response、format 各 context 字段（rag_context/graph_context/web_context），构造 tool role 消息追加到 messages。⑤轮次 iteration +1，回到 reasoning_node 继续推理
- **知识点**：并行执行、消息格式、Tool Calling 协议

### Q4: ReAct 的数据流是怎么走的？`⭐⭐⭐`
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

### Q5: graph.py 的 route_decision 函数做了什么？`⭐⭐⭐`
- **标准回答**：LangGraph 条件边函数。输入 AgentState，检查 selected_sources：含 `__answer__` → 返回 `["__answer__"]` 走向 END（结束）；否则返回 sources 列表（如 `["rag","web"]`）走向 execute_tools 节点。注意返回的是 `sources` 变量（list），不是 state 对象——之前有个 bug 是 `return state` 返回了整个 state 对象，LangGraph 无法匹配条件边导致运行时错误
- **知识点**：LangGraph 条件边、常见 bug

### Q6: `__answer__` 时 LLM 的回答文本怎么处理的？被丢弃了吗？`⭐⭐⭐`
- **标准回答**：丢弃了，但这是**故意设计的**。项目采用了**两层分离架构**：
  - **第一层 — LangGraph ReAct**（`nodes.py` + `graph.py`）：只负责检索决策。reasoning_node 调用 LLM + tools 参数，决定调什么工具。execute_tools_node 并行执行，把结果写入 `rag_context` / `graph_context` / `web_context`。`__answer__` 时 ReAct 结束，choice_msg.content（LLM 推理过程中的"自言自语"）直接丢弃
  - **第二层 — chat.py 单独 LLM 调用**（`services/chat.py` 第 175-200 行）：从 state 取出三个 context 字段，插入到 api_messages 的 system 位置，然后另起一次 `client.chat.completions.create(stream=True)` 流式生成最终回答给用户
  好处：回答质量不依赖 ReAct 的推理质量，两部分可独立优化。代价：每次回答多调一次 LLM API
- **知识点**：两层架构、检索与生成分离、设计权衡

### Q7: 完整的聊天请求数据流是什么？`⭐⭐⭐`
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

### Q1: main.py 里的中间件是什么？做什么的？`⭐⭐`
- **标准回答**：`main.py` 注册了两个中间件。①**CORS Middleware**：跨域处理，开发阶段允许所有来源（`allow_origins=["*"]`），让前端网页能跨域访问 API。②**RequestLogMiddleware**：自定义中间件（`app/core/middleware.py`），每个请求进来时记录方法、路径、状态码、耗时，如 `POST /api/v1/chat → 200 (1.25s)`。中间件像"安检门"，所有请求都会经过，与业务逻辑无关
- **知识点**：FastAPI 中间件、CORS、请求日志

### Q2: 项目完整架构流转图`⭐⭐⭐`
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

---

## Stage 7: RAG 评估

### Q1: 评估体系有什么？如何运行？`⭐⭐`

- **标准回答**：
  两个评估脚本 + 一个测试文档：

  ```
  tests/eval_retrieval.py       # 检索质量评估（直接调 RAGRetriever 组件，不经过 API）
  tests/eval_qa.py              # 端到端 QA 评估（通过 httpx 调 Chat API，走 SSE 流）
  data/eval_doc.txt             # 评估用测试文档（覆盖 MemBrain 项目全部知识点）
  ```

  **运行方式**：
  ```bash
  # 1. 启动服务，上传评估文档
  uvicorn app.main:app --host 0.0.0.0 --port 8000
  curl -X POST /api/v1/documents/upload -F "file=@data/eval_doc.txt"

  # 2. 跑检索评估（不进 API，直接调组件）
  cd D:/pythonProject/git/membrain
  export HF_ENDPOINT=https://hf-mirror.com
  python -m tests.eval_retrieval                # 输出 Recall@3 / MRR / Top-1

  # 3. 跑 QA 评估（走全链路 API）
  python tests/eval_qa.py                       # 输出 Keyword Rate
  python tests/eval_qa.py --resume              # 断点续跑（跳过已完成）
  ```

  **结果目录**：
  ```
  eval_results/
    eval_results.json          # 检索评估明细
    eval_results_qa.json       # QA 评估明细
    REPORT.md                  # 综合报告
    评估流程记录.md              # 流程文档
  ```
- **知识点**：评估体系设计、RAG 评估方法、组件测试 vs 端到端测试

### Q2: eval_retrieval.py 怎么工作的？`⭐⭐`

- **标准回答**：
  ```python
  EVAL_SET = [
      {"query": "MemBrain 用了什么框架？",
       "expected_keywords": ["LangGraph"],
       "topic": "精确匹配"},
      # ... 共 18 条，分 4 类
  ]
  ```

  工作流程：
  1. 初始化 Embedder → VectorStore → RAGRetriever（直接实例化组件，不走 API）
  2. 遍历 18 条查询，每条调 `retriever.retrieve(query, top_k=3)`
  3. 对每个返回结果检测 **expected_keywords 是否出现在 chunk 原文中**
  4. 汇总计算 **Recall@3**（命中数/总数）、**Top-1 命中率**（第一条就命中的比例）、**MRR**（排名倒数均值）

  指标含义：
  - **Recall@3**: top-3 结果中至少有一个包含关键词的比例。衡量"能不能找到"。
  - **MRR**: 第一个命中的排列位置倒数均值。如果排第一得 1，排第三得 0.33。"找到的信息有多靠前"。
  - **Top-1 命中率**: 第一条就是命中的比例。"第一次就中"的体验指标。
- **知识点**：检索评估指标、Recall@k、MRR

### Q3: eval_qa.py 怎么工作的？`⭐⭐`

- **标准回答**：
  与 eval_retrieval 不同，eval_qa 走的是**完整的 Chat API 链路**（httpx + SSE 流式响应），不是直接调组件。

  工作流程：
  1. 登录获取 JWT token
  2. 遍历 18 条查询，每条通过 `client.stream("POST", /api/v1/chat)` 发送聊天请求
  3. 收集完整的 SSE 流式响应（`data:` 事件），拼接成最终回答
  4. 检查回答中是否包含 **expected_keywords**（大小写不敏感）
  5. 每条执行完毕后立即保存到 `eval_results_qa.json`（断点续跑支持）
  6. 汇总输出 **Answer Rate**、**Keyword Rate**、平均回答长度、平均耗时

  关键设计：
  - 用 `asyncio.timeout(90)` 限制单条超时，防止某条 query 卡死整个评估
  - `--resume` 参数跳过已完成的查询，从中断处继续
  - 每条结果含 `answer_preview`（回答前 200 字），方便人工复审

  与检索评估的核心区别：
  - 检索评估测的是 FAISS 能不能找到对的内容
  - QA 评估测的是 LLM 能不能利用找到的内容生成正确回答
  - 检索 100% 命中 ≠ QA 100% 通过（LLM 可能不信任 RAG 上下文）
- **知识点**：端到端评估、SSE 流式测试、断点续跑

### Q4: v1 基线结果如何？关键发现是什么？`⭐⭐⭐`

- **标准回答**：

  **检索评估（eval_retrieval.py）**：
  ```
  Recall@3:   77.8% (14/18)
  Top-1:      61.1% (11/18)
  MRR:         0.9583
  ```

  **QA 评估（eval_qa.py）**：
  ```
  Keyword Rate: 83.3% (15/18)
  平均耗时:       58.1s/条
  ```

  **按场景对比**：

  | 场景 | 检索命中 | QA 命中 | 分析 |
  |------|---------|---------|------|
  | 精确匹配 | 60% (3/5) | 60% (3/5) | ❌ 关键词在文档中但不在 top-3，且 LLM 用自身知识覆盖文档 |
  | 语义相似 | 100% (5/5) | 100% (5/5) | ✅ embedding 语义匹配和 LLM 生成都稳定 |
  | 跨段综合 | 100% (4/4) | 75% (3/4) | ⚠️ 检索全中但 QA 有遗漏，LLM 选择了通用知识 |
  | 边界无关 | 50% (2/4) | 100% (4/4) | ⚠️ 检索有误召回但 LLM 正确回答了问候/闲聊 |

  **关键发现**：
  1. **RAG 检索不是瓶颈** — 语义相似和跨段综合场景检索命中率 100%，embedding + FAISS 管线工作正常
  2. **LLM 覆盖 RAG 上下文** — "分块大小"问题 LLM 回答「512 个字符」而非文档中的「500」；"ReAct 轮数"问题 LLM 说「没有明确限制」而非「最多 3 轮」。文档内容检索到了，但 LLM 不信任，用自身预训练知识覆盖了正确答案
  3. **top_k=3 不足** — 部分精确匹配查询的 chunk 排在 top-3 之外，调到 top_k=5 可改善
  4. **阈值 0.3 偏低** — 无关查询（"讲个笑话"）的 chunk 相似度 0.346，刚好跨过阈值被误召回，提到 0.4 可减少噪声
- **知识点**：评估结果分析、RAG vs LLM 知识冲突、检索与生成的质量差异

### Q5: 如何改进评估体系？`⭐⭐⭐`

- **标准回答**：
  当前 v1 基线已保存到 `eval_results/`，后续分三个层次迭代：

  **短期（2h 可完成）**：
  1. LLM-as-judge 追加打分 — 用 DeepSeek 对每条回答按 accuracy/completeness/faithfulness 打 1-5 分，替代 0/1 keyword match
  2. eval_all.py 一键执行 — 合并清理→启动→上传→评估→存档为一条命令
  3. 版本化存储 + 趋势对比 — `eval_results/v1/` → `v2/`，`history.json` 记录各版本指标

  **中期（1-2 天）**：
  1. 评估数据集扩至 50+ 条，覆盖边界 case 和难例
  2. BERTScore 集成，做语义相似度评估
  3. 根本原因自动分析 — 失败 case 打出"检索到的 chunk 内容 vs LLM 回答"的对比

  **长期（有 CI 需求时）**：
  1. pytest fixture 集成，跑在隔离的内存 DB 上
  2. commit 时自动触发评估，指标下降 >1% 拒绝提交
- **知识点**：评估体系迭代、持续改进、工程化思维

## Stage 9: Agent 健壮性（Guardrails + 记忆管理）

### Q1: 一次完整聊天调了几次 LLM？`⭐⭐⭐`

- **标准回答**：分为两层。第 1 层是 ReAct 循环（graph.ainvoke），`reasoning_node` 每次决策调一次，共 2-3 次，中间每次可能触发 Text2Cypher（额外 1 次）。第 2 层是 chat.py 最终的流式生成（1 次）。所以一次聊天总共 **3-5 次 LLM 调用**，取决于工具调用轮数。每个 `reasoning_node` 只做决策 token 消耗小，最终生成才拼全量上下文。
- **知识点**：LangGraph ReAct 循环、LLM 调用链路、token 预算

### Q2: 为什么需要 Guardrails？LLM 返回的 tool_calls 不都是合法的吗？`⭐⭐⭐`

- **标准回答**：LLM 输出不可信是 Agent 开发的共识。即使模型再强，tool_calls 也可能出现非法工具名、参数格式错误、或内容注入攻击。不做校验，一个非法参数就能让整个 Agent 崩溃。MemBrain 做了三层校验：第 1 层 `validate_tool_calls()` 过滤非法工具名和 JSON 解析失败的参数；第 2 层 `check_empty_result()` 跳过空结果的源；第 3 层系统兜底——全炸就纯 LLM 聊天。面试官会觉得你有生产意识。
- **知识点**：LLM 输出校验、安全编码、防御性编程

### Q3: 历史消息和记忆有什么区别？`⭐⭐⭐`

- **标准回答**：历史消息是原始对话记录（messages 表），逐条存储，50 轮就是 50 条，包含大量无意义填充词。记忆是 LLM 提炼后的摘要和事实（memory_records 表），50 轮对话压缩为 1 条摘要 + 若干事实。历史消息按时间线拼接填充上下文窗口，记忆按信息密度注入 system prompt 后面。两者在 api_messages 中是独立的 system role 消息。
- **知识点**：上下文管理、记忆 vs 历史、token 优化

### Q4: 三层记忆怎么分类？当前实现了哪几层？`⭐⭐⭐`

- **标准回答**：三层分类：情景记忆（Episodic）记录对话时间线，当前已经有的 messages 表就是；语义记忆（Semantic）提取实体和偏好，Stage 9 的 `extract_facts()` 实现；程序记忆（Procedural）记录用户习惯模式，当前预留可扩展。回答框架：先说出三层分类 → 指出当前实现了情景+语义 → 说明程序记忆可以在 fact 积累足够后做模式识别。面试官会觉得你有完整的技术视野。
- **知识点**：记忆分类、Agent 长期记忆

### Q5: 超过 6 轮才触发记忆，6 之前的信息不就丢了吗？`⭐⭐`

- **标准回答**：不会丢。6 轮之前的原始消息仍然在 messages 表中，每次都会作为历史 context 加载。6 轮是指"同步到记忆"的触发阈值，不是"丢弃历史"的阈值。上下文管理分两层：messages 表存全部原始历史（持久不丢），memory_records 存提炼后的记忆（压缩信息量）。选 6 轮是经验值——太早触发信息不够，LLM 提炼不出有价值的事实；太晚触发前面的信息可能已经被上下文窗口挤掉了。这个阈值可以配置。
- **知识点**：触发条件设计、上下文管理、记忆 vs 历史

### Q6: 历史消息和记忆都是全部加载吗？`⭐⭐`

- **标准回答**：对，当前都是全量加载。messages 表：`SELECT * WHERE conversation_id=?` 无 limit，50 轮 = 100 条全塞 api_messages。memory_records：同样 `.all()` 全量，facts 越积越多。这在高轮数时会导致 token 膨胀和"lost in the middle"问题（关键信息夹在中间被 LLM 忽略）。生产级做法会加滑动窗口（messages 只取最近 N 轮）和 fact 数量上限（最多 20 条），用 summary 替换旧轮次。当前 demo 阶段不改，是因为项目定位是面试作品，面试官问起来能说出方案就行。
- **知识点**：全部加载策略、token 预算、滑动窗口、lost in the middle

### Q7: summary、summarize、facts 三者的关系是什么？`⭐⭐`

- **标准回答**：summarize 是方法（动词），负责调 LLM 生成摘要并写入 DB。summary 是产物（名词），存在 memory_records 表里 type='summary' 的记录。facts 也是产物，type='fact'。区别：summary 是"面"，描述对话整体脉络（"上次聊了架构设计"），覆盖写入只留一条。facts 是"点"，记录具体信息（"用户偏好详细回答"），追加写入越积累越多。两者互补——summary 让 LLM 知道对话背景，facts 让 LLM 知道具体信息。谁也不能替代谁。
- **知识点**：方法 vs 产物、记忆粒度、宏观 vs 微观信息

### Q8: 记忆系统和上下文管理是什么关系？`⭐⭐⭐`

- **标准回答**：两者是上下游关系，不是替代关系。记忆系统负责"写"——从对话中提炼 facts 和 summary，存入 memory_records 表。上下文管理负责"读"——决定当前这一轮 api_messages 里放什么、不放什么。记忆系统产出"原材料"（facts + summary），上下文管理决定怎么用这些原材料（滑动窗口、摘要替换旧消息、fact 上限）。记忆系统操作 DB，上下文管理只动内存中的 api_messages，不修改 DB。当前 Stage 9 做了记忆系统，上下文管理是预留优化方向。
- **知识点**：读 vs 写、api_messages 组装策略、DB vs 内存

## Stage 10: RAG 深度优化（Reranker + HyDE + 评估集扩充）

### Q1: 什么是 Reranker？为什么 FAISS 粗排后还要加 Reranker？`⭐⭐⭐`

- **标准回答**：Reranker 是精排环节。FAISS 用 bi-encoder（双编码器），问题和文档各自独立编码成向量，用余弦相似度计算。速度快但语义捕捉有限——"怎么登录"和"认证流程是什么"向量相似度可能不高。Reranker 用 cross-encoder（交叉编码器），问题和文档一起送入 Transformer 计算相关性分数，精度更高但速度慢。MemBrain 的做法是 FAISS 粗排先取 top_k=10（快速筛选候选），再用 CrossEncoder 精排取 top_n=3（精确排序）。这是工业界标准做法：用 bi-encoder 做第一轮召回（快），用 cross-encoder 做第二轮精排（准）。
- **知识点**：bi-encoder vs cross-encoder、粗排+精排两阶段、召回率与精度权衡

### Q2: HyDE 是什么？解决了什么问题？`⭐⭐⭐`

- **标准回答**：HyDE（Hypothetical Document Embeddings，假设文档嵌入）的核心思想是：先用 LLM 根据用户问题生成一段"假设回答"，然后用这个假设回答去做向量检索。解决的问题是短查询的语义稀疏性——用户问"密码怎么存"只有 5 个字，embedding 很难匹配到"bcrypt 哈希加密"相关文档。但如果 LLM 先生成一段假设回答，里面自然包含"bcrypt、哈希、password"等术语，embedding 就能匹配到更相关的文档。注意 HyDE 的假设回答只用来做检索，不是最终答案——它是检索增强手段，不是生成增强手段。
- **知识点**：查询改写、短查询优化、检索增强 vs 生成增强

### Q3: HyDE 的假设回答和最终回答有什么区别？`⭐⭐`

- **标准回答**：假设回答（hypo_answer）只参与检索，不出现在最终 prompt 中。流程是：用户问题 → HyDE 生成假设回答 → 假设回答向量化 → FAISS 检索 → 拿到真实文档块 → 真实文档 + 用户问题送入 LLM → 生成最终回答。假设回答的目的是扩充查询语义，类似"先用小模型写草稿再搜"，草稿写得对不对不重要，重要的是草稿里包含了相关术语，能帮助向量检索定位到正确文档。HyDE 论文的一个核心发现是：即使假设回答是幻觉产物，只要包含了领域相关词汇，检索效果依然提升。
- **知识点**：检索 vs 生成、查询语义扩充、HyDE 论文核心发现

### Q4: Reranker 和 HyDE 是两个独立环节吗？谁先谁后？`⭐⭐`

- **标准回答**：是独立的两个环节，HyDE 在前、Reranker 在后。完整链路：用户问题 → HyDE 生成假设回答 → 假设回答向量化 → FAISS 粗排取 top_k=10 → CrossEncoder 精排取 top_n=3 → 相似度阈值过滤（0.3）→ 返回 LLM。HyDE 解决"能不能搜到对的文档"（召回层），Reranker 解决"搜到的文档哪个最相关"（排序层）。两者互补，不冲突。
- **知识点**：完整检索链路、召回 vs 排序、各环节职责

### Q5: 为什么 FAISS 搜索用 top_k=10 而不是直接 top_k=3？`⭐⭐`

- **标准回答**：给 Reranker 留候选空间。如果 FAISS 只取 top_k=3，Reranker 只能在 3 个候选中重排，几乎没意义。取 top_k=10，Reranker 可以从 10 个候选中挑出最相关的 3 个。这是典型的"粗筛 + 精排"漏斗设计——第一层用高效但粗糙的算法扩大候选集，第二层用精确但慢的算法精排。Top-k 数值没有绝对标准，取决于 FAISS 召回质量和数据规模，一般 10-50 之间，当前 10 对 demo 数据量足够。
- **知识点**：漏斗设计、粗排+精排的比例、超参数选择逻辑

### Q6: 怎么评估 Reranker 和 HyDE 的效果？`⭐⭐⭐`

- **标准回答**：通过 eval_retrieval.py 评估脚本，对比三个指标的变化：Recall@3（top-3 召回率，期望提升）、MRR（平均倒数排名，期望更高）、Top-1 命中率（期望提升）。评估方式分三步：先用旧版评估脚本（无 Reranker/HyDE、top_k=3）跑出基线；然后在新版评估脚本（top_k=10 + Reranker + HyDE）上跑结果；对比两组数据，如果 Reranker 使 Top-1 命中率提升 5-10% 说明有效。注意 HyDE 有随机性（依赖 LLM 生成质量），需要跑多次取平均。面试时能说出这套评估方法，比单纯说"我加了 Reranker"更有说服力。
- **知识点**：A/B 测试、评估指标选择、对比实验设计

### Q7: 评估数据集为什么从 18 条扩充到 59 条？`⭐⭐`

- **标准回答**：18 条不够有统计意义——多了几个或少几个命中，Recall@3 可能波动 5-10 个百分点。59 条覆盖了精确匹配（8）、语义相似（10）、跨段综合（10）、Agent 系统（6）、Guardrails（4）、记忆系统（5）、知识图谱（4）、API 与部署（4）、边界无关（8）九个场景，能更全面反映检索质量。面试官问起来，可以说"评估覆盖了 9 个场景共 59 条查询"，比"18 条"听起来更专业。
- **知识点**：统计显著性、评估覆盖度、数据集设计

### Q8: Reranker 的 CrossEncoder 模型为什么选 bge-reranker-v2-m3？`⭐⭐`

- **标准回答**：bge-reranker-v2-m3 是 BAAI 开源的轻量级 CrossEncoder，支持多语言（中英文），推理速度较快，在 C-MTEB 中文榜单上排名靠前。选型标准是精度-速度平衡——bge-reranker-v2-m3 比更小的模型精度高，比更大的模型（如 bge-reranker-v2-gemma）速度快。对于 demo 数据量（几千条 Chunk），性能影响可忽略。面试官问起模型选型，能说出"多语言支持 + C-MTEB 榜单 + 精度速度平衡"踩点齐全。
- **知识点**：模型选型标准、多语言支持、C-MTEB 榜单、精度-速度权衡

### Q9: 为什么 FAISS 查完还要查 DB？FAISS 里存了什么？`⭐⭐`

- **标准回答**：FAISS 只存向量和 chunk_id，不存原文。FAISS search 返回的是 `[(chunk_id, 分数)]`——只有 ID 和相似度分数，没有实际文本内容。所以必须拿 ID 去 SQLite 查 Chunk 表的 content 字段，才能拿到原文送去 Reranker 精排和 LLM 生成回答。关系型 DB（SQLite）存文本内容，向量库（FAISS）存语义索引，两者是互补关系。
- **知识点**：FAISS 存储边界、向量库 vs 关系型数据库分工

### Q10: HyDE 生成"假设回答"后，这个回答会存到 FAISS 里吗？`⭐⭐`

- **标准回答**：不会。HyDE 只是用假设回答作为"查询向量"去搜 FAISS，FAISS 里始终是文档原始 chunk 的向量。假设回答生成 → 向量化 → 作为 query_vec 搜索 FAISS → 丢弃假设回答。最终只保留 FAISS 返回的真实 chunk 内容。这就好比你先脑补一个答案再查书——脑补的内容不写进书里，只是为了帮你更准确找到书中位置。
- **知识点**：HyDE 流程边界、查询改写 vs 文档更改

### Q11: 什么时候会有粗排结果但最终结果为空？`⭐⭐`

- **标准回答**：分两种情况。第一种是 FAISS 和 DB 数据不一致（bug 场景）：FAISS 索引里还有 chunk_id，但 SQLite 里对应的 chunk 已被删除，导致 candidates 为空 → 直接返回空。第二种是正常场景：FAISS 搜到结果、DB 查到原文、Reranker 也跑了，但所有结果的 faiss_score 都低于 0.3 阈值，valid 列表为空。第二种更常见，比如用户问无关问题，FAISS 硬找了最接近的 chunk，但相似度不够被过滤掉。
- **知识点**：阈值过滤、数据一致性、FAISS-DB 同步

---

## Stage 11: 可观测性与交互体验（中间推理流式输出 + LangSmith）

### Q1: 为什么用 astream 替换 ainvoke？`⭐⭐⭐`

- **标准回答**：ainvoke 是黑箱执行——等到整个 LangGraph 跑完才返回最终 state，期间用户什么都看不到。astream 每执行完一个节点就 yield 一次当前 state，可以实时知道每次 reasoning 决定调什么工具、每个工具返回了什么结果。这不是功能差异，而是**体验差异**：ainvoke 适合后端批处理，astream 适合需要实时反馈的交互场景。
- **知识点**：LangGraph 流式模式、同步 vs 异步迭代器

### Q2: astream 和 astream_events 有什么区别？`⭐⭐⭐`

- **标准回答**：astream 按节点粒度 yield（reasoning_node 执行完 → yield → execute_tools_node 执行完 → yield），每次拿到的是节点返回的 state 片段。astream_events 粒度更细，能拿到节点内部的 LLM token、tool call 参数等，但实现更复杂且对 DeepSeek 这类兼容接口的兼容性不确定。当前项目用 astream 足够展示"正在做什么→检索到什么→生成回答"的完整过程。面试时可以说"我们用了 astream，因为对演示来说节点级粒度已经够用，astream_events 的额外复杂度在当前阶段不值得"。
- **知识点**：LangGraph 流式粒度、复杂度-收益权衡

### Q3: 新的 SSE 协议怎么设计的？`⭐⭐`

- **标准回答**：旧协议只有纯文本 token：`data: <token>\n\n`。新协议改为结构化事件流，每个事件带 type 字段：
  ```
  data: {"type":"status","content":"正在分析问题..."}\n\n
  data: {"type":"reasoning","content":"第1轮推理: 需要 rag, web"}\n\n
  data: {"type":"tool_call","tool":"rag_search","query":"..."}\n\n
  data: {"type":"tool_result","source":"rag","summary":"RAG 检索到 3 条结果"}\n\n
  ```
  三种事件类型：status（状态提示）、reasoning/tool_call/tool_result（推理过程）、answer（最终回答 token）。最终回答的 token 仍保持纯文本格式向后兼容。前端如果只渲染 text/plain 也能正常显示最终回答，只是看不到推理过程。
- **知识点**：SSE 协议设计、向后兼容、事件驱动架构

### Q4: accumulated 累加机制是什么？`⭐⭐`

- **标准回答**：LangGraph 的 astream 每轮只 yield 当前节点的产出（不是全量 state）。比如 reasoning_node 的输出有 `selected_sources` 和 `messages`，execute_tools_node 的输出有 `rag_context`、`graph_context` 等。用 `accumulated.update(output)` 逐轮叠加，最终得到一个包含所有字段的完整 state。这和 ainvoke 返回的 state 是一样的，只是需要手动拼起来。
- **知识点**：状态管理、LangGraph astream 输出格式

### Q5: LangSmith 是怎么集成的？`⭐⭐`

- **标准回答**：LangSmith 是 LangChain 的 LLM 可观测性平台。LangGraph 原生支持——只要设了 `LANGSMITH_TRACING=true` 和 `LANGSMITH_API_KEY`，astream 和 ainvoke 自动上报 traces，不需要改代码。每次请求会生成一条 trace，包含每个节点的 LLM 调用、输入输出、token 消耗。config.py 里声明了配置项，但当前本地环境没配 key，等上线 AutoDL 时再开。面试官问"生产环境怎么做排查"，就可以说"LangSmith 全链路追踪，每次请求都能回溯完整调用链"。
- **知识点**：LLM 可观测性、LangSmith、自动 tracing

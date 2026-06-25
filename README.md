# MemBrain - 个人知识助手

基于 **LangGraph + RAG + 知识图谱** 的智能 Agent，支持对话、文档管理和多源检索。

## 架构总览

```mermaid
flowchart TB
    subgraph Frontend["🎨 前端层"]
        Streamlit["Streamlit UI\n(streamlit_app.py)"]
        Swagger["Swagger Docs\n(/docs)"]
    end

    subgraph API["🚪 API 层 (FastAPI)"]
        direction LR
        Auth["Auth\n/api/v1/auth"]
        Chat["Chat\n/api/v1/chat"]
        Doc["Documents\n/api/v1/documents"]
        Trace["Agent Trace\n/api/v1/agent"]
    end

    subgraph Agent["🧠 Agent 层"]
        ReAct["LangGraph ReAct\n(app/agent/)"]
        Router["路由判断\n(greeting / rag / graph)"]
        Guard["工具校验\n(guardrails.py)"]
        Memory["短期记忆\n(conversations)"]
        Tracer["推理追踪\n(agent_traces)"]
    end

    subgraph RAG["📚 RAG 管线"]
        Chunker["TextChunker\n(app/rag/chunker.py)"]
        Embedder["Embedder\n(app/rag/embedder.py)"]
        VectorStore["FAISS\n向量索引"]
        Reranker["Reranker\n(app/rag/reranker.py)"]
        HyDE["HyDE\n(app/rag/hyde.py)"]
        Retriever["RAGRetriever\n(app/rag/retriever.py)"]
    end

    subgraph Graph["🔗 知识图谱"]
        EntityExt["EntityExtractor\n(app/graph/entity_extractor.py)"]
        Neo4j["Neo4j\n图数据库"]
        GraphRetriever["GraphRetriever\n(app/graph/graph_retriever.py)"]
    end

    subgraph Storage["💾 存储层"]
        DB["SQLite / PostgreSQL\n(app/core/database.py)"]
        FAISS["FAISS Index\n./data/faiss_index.bin"]
        FileStore["文档文件\n./data/documents/"]
        Redis["语义缓存\n(可选)"]
    end

    %% 连接关系
    Frontend -->|HTTP / SSE| API
    API -->|JWT 认证| Auth
    API -->|流式响应| Chat
    API -->|文件上传| Doc

    Chat -->|对话消息| Agent
    Agent -->|路由决策| Router
    Agent -->|工具调用| Guard
    Agent -->|RAG 检索| RAG
    Agent -->|图谱查询| Graph
    Agent -->|记录轨迹| Tracer
    Agent -->|对话记忆| Memory

    RAG --> Retriever
    Retriever -->|分块| Chunker
    Retriever -->|向量化| Embedder
    Retriever -->|重排序| Reranker
    Retriever -->|假设文档| HyDE
    Retriever -->|相似度搜索| VectorStore
    VectorStore --> FAISS

    Graph --> GraphRetriever
    GraphRetriever -->|提取实体| EntityExt
    GraphRetriever -->|查询关系| Neo4j

    Doc -->|文档元数据| DB
    Doc -->|向量索引| FAISS
    Doc -->|文件存储| FileStore

    Embedder -->|模型加载| Storage
    RAG -->|缓存查询| Redis

    style Frontend fill:#e1f5fe
    style API fill:#f3e5f5
    style Agent fill:#fff3e0
    style RAG fill:#e8f5e9
    style Graph fill:#fce4ec
    style Storage fill:#f5f5f5
```

## 功能特性

| 特性 | 说明 |
|------|------|
| **RAG 问答** | 基于文档检索 + LLM 生成，支持中文 embedding |
| **知识图谱** | Neo4j 存储实体关系，图结构辅助推理 |
| **ReAct Agent** | LangGraph 驱动的推理-行动循环，动态选择知识源 |
| **文档管理** | 上传 txt/md/pdf → 自动分块 → 向量化 → 检索 |
| **检索增强** | Reranker 重排序 + HyDE 假设文档检索 |
| **流式对话** | SSE 实时输出，可见 ReAct 推理过程 |
| **前端界面** | Streamlit 可视化聊天 + 文档管理 |
| **推理追踪** | 每一步 Agent 决策都记录，便于调试和展示 |

## 技术栈

- **框架**: FastAPI + LangGraph + Streamlit
- **检索**: FAISS + Sentence-Transformers + Reranker
- **图谱**: Neo4j + 实体关系提取
- **AI**: DeepSeek Chat API + Function Calling
- **存储**: SQLAlchemy (SQLite/PostgreSQL) + Redis 缓存
- **测试**: pytest + pytest-asyncio (30+ tests)

## 快速启动

```bash
pip install -r requirements.txt
cp .env.example .env  # 填入你的 API Key
uvicorn app.main:app --reload --port 8000

# 另一个终端启动前端（可选）
streamlit run streamlit_app.py
```

## 请求示例

```bash
# 注册
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","username":"test","password":"123456"}'

# 登录
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"123456"}'

# 聊天
curl -N -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"messages":[{"role":"user","content":"你好"}],"conversation_id":null}'
```

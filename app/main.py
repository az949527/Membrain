"""
MemBrain 应用入口

使用 FastAPI 框架 + lifespan 生命周期管理。

启动流程：
1. 创建 FastAPI 实例
2. 注册 CORS 中间件（允许跨域请求）
3. 注册请求日志中间件（记录每个请求的方法、路径、耗时）
4. 注册路由模块（auth + chat + documents）
5. 启动时自动初始化数据库（建表）+ RAG 组件
"""
from contextlib import asynccontextmanager  # 将 async 生成器转为异步上下文管理器，用于 lifespan

from fastapi import FastAPI                         # Web 框架主类
from fastapi.middleware.cors import CORSMiddleware   # 跨域中间件，允许前端跨域请求

from app.core.config import settings      # 配置（含 RAG 参数）
from app.core.database import init_db       # 数据库初始化（启动时建表）
from app.core.logger import logger          # 自定义日志工具（带格式/级别）
from app.core.middleware import RequestLogMiddleware  # 请求日志中间件（记录方法/路径/耗时）
from app.routers import auth, chat, document, trace          # 路由模块：认证 + 聊天 + 文档 + 追踪
from app.cache.redis_client import init_redis, close_redis

@asynccontextmanager
async def lifespan(application: FastAPI):
    """应用生命周期管理

    yield 之前的代码在启动时执行：
    - 初始化数据库连接和表结构
    - 初始化 RAG 组件（embedder + vector_store）

    yield 之后的代码在关闭时执行（暂无需要）
    """
    logger.info("正在初始化数据库...")
    await init_db()
    logger.info("数据库初始化完成")

    # 初始化 RAG 组件
    logger.info("正在初始化 RAG 组件...")
    from app.rag.embedder import Embedder
    from app.rag.vector_store import VectorStore
    application.state.embedder = Embedder(settings.EMBEDDING_MODEL)
    application.state.vector_store = VectorStore(settings.FAISS_INDEX_PATH)
    logger.info("RAG 组件初始化完成")

    # 初始化 Neo4j 连接
    # 连接失败不阻止应用启动，没 Docker 时图谱功能不可用
    logger.info("正在初始化 Neo4j 连接...")
    from app.graph.neo4j_conn import Neo4jConnection
    neo4j_conn = Neo4jConnection()
    try:
        await neo4j_conn.initialize()
        application.state.neo4j = neo4j_conn
    except Exception as e:
        logger.warning("Neo4j 连接失败（跳过）: %s", e)
        application.state.neo4j = None

    # Redis 缓存
    application.state.redis = None
    try:
        application.state.redis = await init_redis(settings.REDIS_URL)
        logger.info("Redis 缓存连接成功")
    except Exception as e:
        logger.warning("Redis 连接失败（缓存不可用）: %s", e)

    yield

    # 关闭 Neo4j 连接（只有初始化成功时才关闭）
    if application.state.neo4j:
        await neo4j_conn.close()

    await close_redis(application.state.redis)


app = FastAPI(
    title="MemBrain",
    version="0.1.0",
    lifespan=lifespan,
)

# ==================== 中间件注册（顺序重要） ====================
# CORS 放最外层，确保所有请求都能跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # 开发阶段允许所有来源
    allow_credentials=True,
    allow_methods=["*"],          # 允许所有 HTTP 方法
    allow_headers=["*"],          # 允许所有请求头
)
# 请求日志中间件
app.add_middleware(RequestLogMiddleware)

# ==================== 路由注册 ====================
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(document.router)
app.include_router(trace.router)


@app.get("/")
async def root():
    """健康检查端点"""
    return {"message": "MemBrain API is running"}

import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from unittest.mock import Mock
import numpy as np
from app.main import app
from app.core.database import get_db
from app.core.database import Base


@pytest_asyncio.fixture(autouse=True)
async def db_session():
    # 1. 创建内存 SQLite 引擎（跟开发数据库完全隔离）
    engine = create_async_engine("sqlite+aiosqlite://", echo=True)

    # 2. 建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 3. 创建 session 并注入到 app
    # expire_on_commit=False 避免 ASGITransport 序列化响应时触发
    # ORM 懒加载导致 MissingGreenlet 错误（commit 后会过期所有属性）
    session = AsyncSession(engine, expire_on_commit=False)
    app.dependency_overrides[get_db] = lambda: session

    yield session

    # 4. 清理
    await session.close()
    await engine.dispose()
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(autouse=True)
async def mock_rag_state():
    """为所有测试注入 mock embedder + vector_store（文档端点依赖它们）"""
    # Mock Embedder（不加载真实模型）
    embedder = Mock()
    def mock_embed(texts):
        return np.random.rand(len(texts), 768).astype(np.float32)
    embedder.embed = mock_embed

    # Mock VectorStore（避免创建 FAISS 索引）
    vector_store = Mock()

    app.state.embedder = embedder
    app.state.vector_store = vector_store

    yield

    if hasattr(app.state, "embedder"):
        del app.state.embedder
    if hasattr(app.state, "vector_store"):
        del app.state.vector_store


@pytest_asyncio.fixture
async def client(mock_rag_state, db_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def auth_token(client):
    # 注册
    await client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "testpass123",
        "username": "testuser"
    })
    # 登录拿 token
    resp = await client.post("/api/v1/auth/token", json={
        "email": "test@example.com",
        "password": "testpass123"
    })
    return resp.json()["access_token"]

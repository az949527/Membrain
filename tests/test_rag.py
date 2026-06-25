"""
RAG 检索测试

直接调 RAGRetriever 组件（不经过 API），Mock Embedder / VectorStore / DB，
只测检索逻辑：embed → FAISS search → DB 查原文 → 阈值过滤。

注意：AsyncMock 被 await 时行为复杂（self.return_value 的 __await__），
所以自定义 AwaitableMock 替代，确保 await db.execute() 返回可控对象。
"""
import numpy as np
import pytest
from unittest.mock import Mock, AsyncMock

from app.rag.retriever import RAGRetriever


class _AwaitableResult:
    """可 await 的 mock DB 查询结果

    SQLAlchemy: await db.execute(...) → Result → .scalars() → .all()

    这个类同时模拟 Result 和 Scalars，链式调用：
      await obj → 返回自身（await 消费后仍可调用 scalars）
      obj.scalars() → 返回自身
      obj.all() → 返回预设的 chunks 列表
    """

    def __init__(self, chunks: list):
        self._chunks = chunks

    def __await__(self):
        """await 后返回自身，后续仍可调用 scalars()"""
        async def _inner():
            return self
        return _inner().__await__()

    def scalars(self):
        """返回自身，all() 也在同一对象上"""
        return self

    def all(self):
        return self._chunks


def _make_db_mock(chunks: list[tuple[int, str]]) -> AsyncMock:
    """构造 mock db

    确保 await db.execute(select(...)) 返回的对象能链式调 .scalars().all()
    """
    db = AsyncMock()
    mock_chunks = [Mock(id=cid, content=text) for cid, text in chunks]
    db.execute.return_value = _AwaitableResult(mock_chunks)
    return db


class TestRAGRetrieval:

    @pytest.mark.asyncio
    async def test_retrieve_basic(self):
        """基本检索：embed → search → 返回带原文的 chunks"""
        embedder = Mock()
        embedder.embed_query.return_value = np.random.rand(768).astype(np.float32)

        vector_store = Mock()
        vector_store.search.return_value = [(1, 0.85), (2, 0.72)]

        db = _make_db_mock([(1, "MemBrain 使用 LangGraph 框架"),
                           (2, "FastAPI 作为 Web 框架")])

        retriever = RAGRetriever(embedder, vector_store, db)
        chunks = await retriever.retrieve("MemBrain 用了什么框架？", top_k=3)

        assert len(chunks) == 2
        assert chunks[0]["content"] == "MemBrain 使用 LangGraph 框架"
        assert chunks[0]["score"] == 0.85
        assert chunks[1]["content"] == "FastAPI 作为 Web 框架"
        assert chunks[1]["score"] == 0.72

    @pytest.mark.asyncio
    async def test_retrieve_empty_faiss(self):
        """FAISS 无结果 → 空列表"""
        embedder = Mock()
        embedder.embed_query.return_value = np.random.rand(768).astype(np.float32)

        vector_store = Mock()
        vector_store.search.return_value = []  # FAISS 返回空

        db = AsyncMock()

        retriever = RAGRetriever(embedder, vector_store, db)
        chunks = await retriever.retrieve("无关问题", top_k=3)
        assert chunks == []

    @pytest.mark.asyncio
    async def test_retrieve_below_threshold(self):
        """FAISS 有结果但分数低于 0.3 阈值 → 空列表"""
        embedder = Mock()
        embedder.embed_query.return_value = np.random.rand(768).astype(np.float32)

        vector_store = Mock()
        vector_store.search.return_value = [(1, 0.12)]  # 低于阈值

        db = _make_db_mock([(1, "一些不相关文本")])

        retriever = RAGRetriever(embedder, vector_store, db)
        chunks = await retriever.retrieve("无关问题", top_k=3)
        assert chunks == []

    @pytest.mark.asyncio
    async def test_retrieve_db_missing_chunks(self):
        """FAISS 搜到但 DB 中已删除 → 只返回 DB 存在的"""
        embedder = Mock()
        embedder.embed_query.return_value = np.random.rand(768).astype(np.float32)

        vector_store = Mock()
        vector_store.search.return_value = [(1, 0.85), (2, 0.72), (3, 0.60)]

        db = _make_db_mock([(1, "Chunk 1"), (2, "Chunk 2")])

        retriever = RAGRetriever(embedder, vector_store, db)
        chunks = await retriever.retrieve("test", top_k=3)

        assert len(chunks) == 2  # 只返回 DB 存在的
        assert chunks[0]["content"] == "Chunk 1"
        assert chunks[1]["content"] == "Chunk 2"


class TestBuildRAGContext:
    """RAGRetriever.build_rag_context 静态方法测试"""

    def test_build_context_with_chunks(self):
        chunks = [
            {"content": "块1内容", "score": 0.9},
            {"content": "块2内容", "score": 0.8},
        ]
        context = RAGRetriever.build_rag_context(chunks)
        assert "块1内容" in context
        assert "块2内容" in context
        assert context.startswith("以下是与问题相关的知识库内容")

    def test_build_context_empty(self):
        assert RAGRetriever.build_rag_context([]) == ""

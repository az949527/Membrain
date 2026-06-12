from __future__ import annotations

"""
把前面几步串起来：用户问题 → 向量化 → FAISS搜索 → 从DB取原文 → 组装成prompt上下文
"""

from app.rag.embedder import Embedder
from app.rag.vector_store import VectorStore
from app.models.chunk import Chunk
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


class RAGRetriever:
    def __init__(self, embedder, vector_store: VectorStore, db: AsyncSession):
        self.embedder = embedder
        self.vector_store = vector_store
        self.db = db
    async def retrieve(self, query: str, top_k: int = 3) -> list[dict]:
        """检索与向量查询最相关的知识块"""
        # 1、查询转向量
        query_vec = self.embedder.embed_query(query)
        # 2、FAISS搜索，返回[(chunk_id, similarity), ...]
        results = self.vector_store.search(query_vec, top_k)
        if not results:
            return []
        # 3、相似度阈值过滤（低于0.3的chunk与问题基本无关，不送入LLM）
        SIMILARITY_THRESHOLD = 0.3
        valid_ids = [cid for cid, score in results if score >= SIMILARITY_THRESHOLD]
        if not valid_ids:
            return []
        # 4、从DB查chunk原文
        result = await self.db.execute(
            select(Chunk).where(Chunk.id.in_(valid_ids))
        )
        chunks = result.scalars().all()
        # 5、按相似度降序排序（而不是chunk_index）
        score_map = dict(results)
        chunks.sort(key=lambda c: score_map.get(c.id, 0), reverse=True)
        return [
            {
                "content": c.content,
                "document_id": c.document_id,
                "chunk_index": c.chunk_index,
                "score": score_map.get(c.id, 0.0),  # 附带相似度分数，方便调试
            }
            for c in chunks
        ]

    @staticmethod
    def build_rag_context(chunks: list[dict]) -> str:
        """将检索到的块拼接成prompt上下文"""
        if not chunks:
            return ""
        parts = ["以下是与问题相关的知识库内容（每条可能不完整，请结合你的知识回答）：","---"]
        for i, c in enumerate(chunks, 1):
            parts.append(f"[{i}] {c['content']}")
        parts.append("---")
        return "\n\n".join(parts)

"""
把前面几步串起来：用户问题 → 向量化 → FAISS搜索 → 从DB取原文 → 组装成prompt上下文
"""
from app.rag.embedder import Embedder
from app.rag.vector_store import VectorStore
from app.models.chunk import Chunk
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.rag.reranker import Reranker
from app.rag.hyde import HyDE


class RAGRetriever:
    def __init__(self, embedder, vector_store: VectorStore, db: AsyncSession, use_hyde: bool = False, use_reranker: bool = False):
        self.embedder = embedder
        self.vector_store = vector_store
        self.db = db
        self.use_hyde = use_hyde
        self.reranker = Reranker() if use_reranker else None
        self.hyde = HyDE()

    async def retrieve(self, query: str, top_k: int = 10, top_n: int = 3) -> list[dict]:
        """检索与向量查询最相关的知识块"""
        # 1、查询转向量（可选 HyDE 改写）
        if self.use_hyde:
            hypo_answer = await self.hyde.generate(query)
            query_vec = self.embedder.embed_query(hypo_answer)
        else:
            query_vec = self.embedder.embed_query(query)

        # 2、FAISS搜索，返回[(chunk_id, similarity), ...]
        results = self.vector_store.search(query_vec, top_k)
        if not results:
            return []

        # 3、从DB查chunk原文（拼查询，避免循环查单条）
        chunk_ids = [cid for cid, _ in results]
        db_result = await self.db.execute(
            select(Chunk).where(Chunk.id.in_(chunk_ids))
        )
        chunk_map = {c.id: c for c in db_result.scalars().all()}

        # 4、构建候选列表（只取 DB 存在的数据）
        candidates = [
            (chunk_map[cid].content, score)
            for cid, score in results
            if cid in chunk_map
        ]
        if not candidates:
            return []

        # 5、Reranker 精排（模型不可用时按 FAISS 分数排序）
        if self.reranker:
            reranked = self.reranker.rerank(query, candidates, top_n)
        else:
            reranked = [(c, 0.0) for c in sorted(candidates, key=lambda x: x[1], reverse=True)[:top_n]]

        # 6、相似度阈值过滤 + 构建返回结果
        SIMILARITY_THRESHOLD = 0.3
        valid = []
        for (text, faiss_score), rerank_score in reranked:
            if faiss_score >= SIMILARITY_THRESHOLD:
                valid.append({
                    "content": text,
                    "score": faiss_score,
                    "rerank_score": rerank_score,
                })

        return valid

    @staticmethod
    def build_rag_context(chunks: list[dict]) -> str:
        """将检索到的块拼接成prompt上下文"""
        if not chunks:
            return ""
        parts = ["以下是与问题相关的知识库内容（每条可能不完整，请结合你的知识回答）：", "---"]
        for i, c in enumerate(chunks, 1):
            parts.append(f"[{i}] {c['content']}")
        parts.append("---")
        return "\n\n".join(parts)

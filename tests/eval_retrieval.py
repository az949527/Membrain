"""
检索质量评估脚本

对预定义的 15-18 条测试查询逐一调 RAGRetriever.retrieve()，
检查返回结果是否包含预期关键词，计算 Recall@k 和 MRR。

用法：
  conda activate membrain
  cd ~/autodl-tmp/Membrain
  python -m tests.eval_retrieval

前提：测试文档已通过 API 上传并索引完成。
"""

import asyncio
import json

from app.core.config import settings
from app.core.database import async_session_factory
from app.rag.embedder import Embedder
from app.rag.vector_store import VectorStore
from app.rag.retriever import RAGRetriever

# ======================== 评估数据集 ========================
# 每条包含：
#   query:              用户问题
#   expected_keywords:  期望检索结果中包含的关键词（任意匹配即算命中）
#   topic:              所属场景分类

EVAL_SET = [
    # ---- 精确匹配（5 条） ----
    {
        "query": "MemBrain 用了什么框架？",
        "expected_keywords": ["LangGraph"],
        "topic": "精确匹配",
    },
    {
        "query": "用户认证使用什么方式？",
        "expected_keywords": ["JWT", "JSON Web Token"],
        "topic": "精确匹配",
    },
    {
        "query": "密码用什么算法加密？",
        "expected_keywords": ["bcrypt"],
        "topic": "精确匹配",
    },
    {
        "query": "文档默认分块大小是多少？",
        "expected_keywords": ["500"],
        "topic": "精确匹配",
    },
    {
        "query": "ReAct 循环最多执行几轮？",
        "expected_keywords": ["3"],
        "topic": "精确匹配",
    },

    # ---- 语义相似（5 条） ----
    {
        "query": "项目是用什么语言写的？",
        "expected_keywords": ["Python"],
        "topic": "语义相似",
    },
    {
        "query": "怎么保证安全性？",
        "expected_keywords": ["JWT", "bcrypt", "加密"],
        "topic": "语义相似",
    },
    {
        "query": "检索流程是怎样的？",
        "expected_keywords": ["向量化", "FAISS", "相似度"],
        "topic": "语义相似",
    },
    {
        "query": "LLM 怎么决定要不要查资料？",
        "expected_keywords": ["工具调用", "__answer__", "推理"],
        "topic": "语义相似",
    },
    {
        "query": "服务器上怎么更新代码？",
        "expected_keywords": ["git pull", "SSH"],
        "topic": "语义相似",
    },

    # ---- 跨段综合（4 条） ----
    {
        "query": "上传文档后系统会做什么处理？",
        "expected_keywords": ["分块", "向量化", "FAISS"],
        "topic": "跨段综合",
    },
    {
        "query": "系统有哪些检索方式？",
        "expected_keywords": ["RAG", "知识图谱", "网络搜索"],
        "topic": "跨段综合",
    },
    {
        "query": "项目的技术栈有哪些？",
        "expected_keywords": ["FastAPI", "LangGraph", "DeepSeek"],
        "topic": "跨段综合",
    },
    {
        "query": "数据存在哪里？",
        "expected_keywords": ["SQLite", "FAISS", "Neo4j", "Redis"],
        "topic": "跨段综合",
    },

    # ---- 边界（4 条） ----
    {
        "query": "你好",
        "expected_keywords": [],
        "topic": "边界无关",
    },
    {
        "query": "今天天气怎么样？",
        "expected_keywords": [],
        "topic": "边界无关",
    },
    {
        "query": "讲个笑话",
        "expected_keywords": [],
        "topic": "边界无关",
    },
    {
        "query": "1+1等于几？",
        "expected_keywords": [],
        "topic": "边界无关",
    },
]


def is_match(chunks: list[dict], expected_keywords: list[str]) -> bool:
    """检查返回的 chunks 中是否包含任意一个预期关键词"""
    if not expected_keywords:
        return len(chunks) == 0
    for c in chunks:
        content = c.get("content", "")
        for kw in expected_keywords:
            if kw in content:
                return True
    return False


def first_match_rank(chunks: list[dict], expected_keywords: list[str]) -> int | None:
    """返回第一个匹配结果在 top-k 中的排名（1-indexed），不匹配返回 None"""
    if not expected_keywords:
        return None if chunks else 0  # 0 = 正确拒绝（无结果）
    for i, c in enumerate(chunks, 1):
        content = c.get("content", "")
        for kw in expected_keywords:
            if kw in content:
                return i
    return None


async def evaluate():
    print("=" * 60)
    print("  检索质量评估")
    print("=" * 60)

    # 初始化组件
    embedder = Embedder(settings.EMBEDDING_MODEL)
    vector_store = VectorStore(settings.FAISS_INDEX_PATH)

    async with async_session_factory() as db:
        retriever = RAGRetriever(embedder, vector_store, db)

        results = []
        for item in EVAL_SET:
            query = item["query"]
            keywords = item["expected_keywords"]

            chunks = await retriever.retrieve(query, top_k=3)
            matched = is_match(chunks, keywords)
            rank = first_match_rank(chunks, keywords)

            top_content = chunks[0]["content"][:60] if chunks else "(无结果)"
            top_score = chunks[0].get("score", 0) if chunks else 0

            results.append({
                **item,
                "matched": matched,
                "rank": rank,
                "top_score": top_score,
                "top_content": top_content,
                "n_results": len(chunks),
            })

    # ======================== 输出结果 ========================
    print(f"\n{'查询(前30字)':<30} {'场景':<10} {'命中':>4} {'排名':>4} {'分数':>6} {'结果数':>4}")
    print("-" * 70)
    for r in results:
        short_q = r["query"][:28]
        match_str = "✅" if r["matched"] else "❌"
        rank_str = str(r["rank"]) if r["rank"] is not None else "-"
        print(f"{short_q:<30} {r['topic']:<10} {match_str:>4} {rank_str:>4} {r['top_score']:>6.3f} {r['n_results']:>4}")

    # ======================== 统计指标 ========================
    total = len(results)
    hits = sum(1 for r in results if r["matched"])
    recall_at_3 = hits / total

    # MRR: 只算有匹配结果的（边界无关不算在内）
    rankable = [r for r in results if r["rank"] is not None and r["topic"] != "边界无关"]
    mrr = sum(1.0 / r["rank"] for r in rankable if r["rank"] > 0) / len(rankable) if rankable else 0

    # Top-1 命中率
    top1_hits = sum(1 for r in results if r["rank"] == 1)
    top1_rate = top1_hits / total

    print(f"\n{'=' * 60}")
    print(f"  📊 汇总统计")
    print(f"{'=' * 60}")
    print(f"  总查询数:      {total}")
    print(f"  命中数:        {hits}")
    print(f"  Recall@3:      {hits}/{total} = {recall_at_3:.1%}")
    print(f"  Top-1 命中率:  {top1_hits}/{total} = {top1_rate:.1%}")
    print(f"  MRR:           {mrr:.4f}")

    # 按场景分组
    topics = set(r["topic"] for r in results)
    print(f"\n  {'─' * 40}")
    print(f"  按场景分析")
    print(f"  {'─' * 40}")
    for topic in sorted(topics):
        group = [r for r in results if r["topic"] == topic]
        group_hits = sum(1 for r in group if r["matched"])
        print(f"  {topic:<10} → {group_hits}/{len(group)} = {group_hits/len(group):.1%}")

    print(f"\n{'=' * 60}")

    return results


if __name__ == "__main__":
    results = asyncio.run(evaluate())

    # 输出 JSON 供后续记录
    summary = {
        "total": len(results),
        "recall_at_3": sum(1 for r in results if r["matched"]) / len(results),
        "mrr": sum(1.0 / r["rank"] for r in results if r["rank"] is not None and r["rank"] > 0) / max(
            sum(1 for r in results if r["rank"] is not None and r["topic"] != "边界无关"), 1
        ),
        "details": results,
    }
    with open("eval_results.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("\n详细结果已保存到 eval_results.json")

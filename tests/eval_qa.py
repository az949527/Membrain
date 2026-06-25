"""
端到端 QA 质量评估脚本

对预定义的 18 条测试查询通过 Chat API 发送聊天请求，
收集 SSE 流式响应全文，检查回答是否包含预期关键词。

用法（服务需先启动，且 eval_doc.txt 已上传）：
  conda activate membrain
  cd D:/pythonProject/git/membrain
  python tests/eval_qa.py

或者指定已有 token：
  python tests/eval_qa.py --token YOUR_TOKEN

前提：
  1. uvicorn 服务已在 localhost:8000 运行
  2. eval_doc.txt 已通过 API 上传并索引完成
"""

import argparse
import asyncio
import json
import os
import sys
import time
from urllib.parse import urljoin

import httpx

BASE_URL = os.environ.get("EVAL_BASE_URL", "http://localhost:8000")

# ======================== 评估数据集 ========================
# 与 eval_retrieval.py 保持一致，但 expected_keywords 改为预期出现在最终回答中的关键词
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
        "expected_keywords": ["git pull", "SSH", "git"],
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
        "expected_keywords": ["SQLite", "FAISS", "Neo4j"],
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


def check_keywords(text: str, keywords: list[str]) -> bool:
    """检查文本中是否包含任意一个预期关键词"""
    if not keywords:
        return True  # 无预期关键词时视为通过
    for kw in keywords:
        if kw.lower() in text.lower():
            return True
    return False


def count_matched_keywords(text: str, keywords: list[str]) -> tuple[int, int]:
    """返回 (命中数, 总数)"""
    if not keywords:
        return (0, 0)
    matched = sum(1 for kw in keywords if kw.lower() in text.lower())
    return (matched, len(keywords))


async def login(email: str = "eval@test.com", password: str = "eval123456") -> str:
    """登录获取 token"""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            urljoin(BASE_URL, "/api/v1/auth/token"),
            json={"email": email, "password": password},
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


SAVE_PATH = "eval_results/v2/eval_results_qa.json"


async def chat_query(token: str, query: str, timeout: int = 90) -> str:
    """发送聊天请求并收集完整 SSE 响应"""
    try:
        async with asyncio.timeout(timeout):
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
                collected = []
                async with client.stream(
                    "POST",
                    urljoin(BASE_URL, "/api/v1/chat"),
                    json={"messages": [{"role": "user", "content": query}]},
                    headers={"Authorization": f"Bearer {token}"},
                ) as resp:
                    if resp.status_code != 200:
                        error_body = await resp.aread()
                        return f"[ERROR {resp.status_code}] {error_body.decode('utf-8', errors='replace')}"

                    async for line in resp.aiter_lines():
                        line = line.strip()
                        if line.startswith("data:"):
                            data = line[5:].strip()
                            if data == "[DONE]":
                                break
                            collected.append(data)

                return "".join(collected)
    except asyncio.TimeoutError:
        return "[ERROR TIMEOUT]"
    except Exception as e:
        return f"[ERROR {type(e).__name__}: {e}]"


def save_partial(results: list):
    """保存当前进度到 JSON 文件"""
    output = {
        "total": len(results),
        "hits": sum(1 for r in results if r.get("matched") and not r.get("error")),
        "errors": sum(1 for r in results if r.get("error")),
        "details": results,
    }
    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)


def load_previous() -> list:
    """从已有结果文件中加载，返回已完成查询的 index 集合"""
    if not os.path.exists(SAVE_PATH):
        return []
    with open(SAVE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("details", [])


async def evaluate():
    print("=" * 60)
    print("  端到端 QA 质量评估")
    print("=" * 60)

    # 登录
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", help="已有 token（跳过登录）")
    parser.add_argument("--resume", action="store_true", help="从上次中断处继续")
    args = parser.parse_args()
    token = args.token or await login()
    print(f"[登录成功] token={'***' + token[-8:] if token else 'N/A'}")

    # 健康检查
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            resp = await client.get(BASE_URL + "/")
            print(f"[服务检查] {BASE_URL} → {resp.status_code}")
        except Exception as e:
            print(f"[服务检查失败] {e}")
            print("请确保 uvicorn 服务已启动（port 8000），且 eval_doc.txt 已上传。")
            sys.exit(1)

    # 断点续跑
    previous = load_previous() if args.resume else []
    done_queries = {r["query"] for r in previous}
    if done_queries:
        print(f"[断点续跑] 跳过 {len(done_queries)} 条已完成的查询")

    results = list(previous)

    for i, item in enumerate(EVAL_SET):
        query = item["query"]

        # 跳过已完成
        if query in done_queries:
            r = next(r for r in previous if r["query"] == query)
            kw_str = f"{r['keyword_match']}/{r['keyword_total']}" if r.get("keyword_total", 0) > 0 else "-"
            print(f"  [{i+1}/{len(EVAL_SET)}] ⏭️ {query[:35]:<35} kw={kw_str} len={r.get('answer_len', 0)} (跳过)")
            continue

        keywords = item["expected_keywords"]
        topic = item["topic"]

        print(f"\n  [{i+1}/{len(EVAL_SET)}] ▶ {query[:35]}...", end=" ", flush=True)

        t0 = time.time()
        answer = await chat_query(token, query)
        elapsed = time.time() - t0

        # 检查错误
        if answer.startswith("[ERROR"):
            print(f"❌ {answer}")
            results.append({
                **item, "matched": False,
                "keyword_match": 0, "keyword_total": len(keywords),
                "answer_len": 0, "answer_preview": answer[:80],
                "duration": round(elapsed, 2), "error": True,
            })
            save_partial(results)
            continue

        has_keywords = check_keywords(answer, keywords)
        kw_matched, kw_total = count_matched_keywords(answer, keywords)
        answer_len = len(answer)

        status = "✅" if has_keywords else "❌"
        kw_str = f"{kw_matched}/{kw_total}" if kw_total > 0 else "-"
        preview = answer[:60].replace("\n", " ")
        print(f"{status} kw={kw_str} len={answer_len} t={elapsed:.1f}s")
        print(f"      预览: \"{preview}...\"")

        results.append({
            **item,
            "matched": has_keywords,
            "keyword_match": kw_matched,
            "keyword_total": kw_total,
            "answer_len": answer_len,
            "answer_preview": answer[:200],
            "duration": round(elapsed, 2),
            "error": False,
        })

        # 每条结束后立即保存
        save_partial(results)

    # ======================== 汇总统计 ========================
    total = len(results)
    hits = sum(1 for r in results if r.get("matched") and not r.get("error"))
    errors = sum(1 for r in results if r.get("error"))

    print(f"\n{'=' * 60}")
    print(f"  📊 汇总统计")
    print(f"{'=' * 60}")
    print(f"  总查询数:      {total}")
    print(f"  命中数:        {hits}")
    print(f"  错误数:        {errors}")
    print(f"  Answer Rate:   {total - errors}/{total} = {(total - errors) / total:.1%}" if total else "  N/A")
    print(f"  Keyword Rate:  {hits}/{total} = {hits / total:.1%}" if total else "  N/A")
    print(f"  平均回答长度:  {sum(r['answer_len'] for r in results if not r.get('error')) / max(total - errors, 1):.0f} 字")
    print(f"  平均耗时:      {sum(r['duration'] for r in results) / total:.1f}s")

    # 按场景分组
    topics = set(r["topic"] for r in results)
    print(f"\n  {'─' * 40}")
    print(f"  按场景分析")
    print(f"  {'─' * 40}")
    for topic in sorted(topics):
        group = [r for r in results if r["topic"] == topic]
        group_hits = sum(1 for r in group if r.get("matched") and not r.get("error"))
        print(f"  {topic:<10} → {group_hits}/{len(group)} = {group_hits / len(group):.1%}")

    print(f"\n{'=' * 60}")

    return results


if __name__ == "__main__":
    results = asyncio.run(evaluate())

    # 保存结果
    output = {
        "total": len(results),
        "hits": sum(1 for r in results if r.get("matched") and not r.get("error")),
        "errors": sum(1 for r in results if r.get("error")),
        "details": results,
    }
    output_path = "eval_results/v2/eval_results_qa.json"
    os.makedirs("eval_results/v2", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n详细结果已保存到 {output_path}")

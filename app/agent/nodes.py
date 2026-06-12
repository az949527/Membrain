"""
LangGraph 节点函数

每个节点接收 AgentState，返回 dict（部分更新）。
依赖（embedder, db, neo4j 等）通过 functools.partial 从外部注入。
"""
import asyncio

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.logger import logger
from app.rag.retriever import RAGRetriever
from app.graph.graph_retriever import GraphRetriever
from app.tools.web_search import WebSearchTool
from app.agent.tools import TOOLS, TOOL_SOURCE_MAP


async def reasoning_node(
    state: dict,
) -> dict:
    """ReAct推理节点，LLM决定下一步调工具还是回答"""
    question = state.get("question", "")
    history = state.get("messages", [])
    iteration = state.get("iteration", 0)

    if not question:
        return {"selected_sources": ["__answer__"]}

    # 超过最多轮数 -> 强制结束
    MAX_ITERATIONS = 3
    if iteration >= MAX_ITERATIONS:
        logger.info("[ReAct] 强制结束，已超过最大轮数 %s", MAX_ITERATIONS)
        return {"selected_sources": ["__answer__"]}

    try:
        client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
        )

        # 组装message：把历史tool结果传给LLM
        # 让LLM能看到之前调用什么工具，返回什么
        api_messages = [
            {"role": "system",
             "content": (
                 "你是一个智能助手。你可以使用以下工具来获取信息：\n"
                 "- rag_search: 从本地知识库搜索用户上传的文档内容\n"
                 "- graph_query: 查询知识图谱中的实体关系\n"
                 "- web_search: 搜索网络实时信息\n\n"
                 "根据当前信息和问题，决定下一步：\n"
                 "1. 如果已有足够信息可以回答 → 选择 __answer__\n"
                 "2. 如果需要更多信息 → 选择合适的工具"
                ),
             },
            {"role": "user", "content": question},
        ]
        # 把之前tool执行的结果追加进去，让LLM看到上下文
        api_messages.extend(history)

        response = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=api_messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.1,
            timeout=15,
        )

        choice_msg = response.choices[0].message
        tool_calls = choice_msg.tool_calls or []

        # 没选工具 → 认为可以回答了
        if not tool_calls:
            return {"selected_sources": ["__answer__"]}

        # 映射工具名为知识源
        sources = []
        for tc in tool_calls:
            source = TOOL_SOURCE_MAP.get(tc.function.name)
            if source:
                sources.append(source)

        # 把LLM的tool_calls请求记录下来
        # 这样execute_tools下一轮reasoning会知道这轮调了什么
        tool_call_record = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in tool_calls
            ],
        }
        logger.info(
            "【ReAct推理】第%s轮 问题='%s' → 工具=%s → 源=%s",
            iteration + 1, question[:30],
            [tc.function.name for tc in tool_calls],
            sources,
        )

        return {
            "selected_sources": sources,
            "messages": history + [tool_call_record],  # 把本次调用记入历史
        }
    except Exception as e:
        logger.warning("【ReAct推理失败】%s，降级为全源检索", e)
        return {"selected_sources": ["rag", "graph", "web"]}

async def execute_tools_node(state: dict, embedder, vector_store, db, neo4j) -> dict:
    """执行选中的工具，结果追加到messages"""
    question = state.get("question", "")
    sources = state.get("selected_sources", [])
    messages = state.get("messages", [])

    rag_context = state.get("rag_context")
    graph_context = state.get("graph_context")
    web_context = state.get("web_context")

    async def run_rag():
        if "rag" in sources:
            try:
                retriever = RAGRetriever(embedder, vector_store, db)
                chunks = await  retriever.retrieve(question, top_k=settings.TOP_K_RETRIEVAL)
                if chunks:
                    ctx = RAGRetriever.build_rag_context(chunks)
                    return ("rag", ctx, f"RAG检索到 {len(chunks)} 条结果")
            except Exception as e:
                logger.warning("【RAG节点失败】%s", e)
        return ("rag", None, "RAG未检索到内容")

    async def run_graph():
        if "graph" in sources and neo4j:
            try:
                ctx = await GraphRetriever.retrieve(neo4j, question)
                if ctx:
                    return ("graph", ctx, "图谱查询返回关系数据")
            except Exception as e:
                logger.warning("【图谱节点失败】%s", e)
        return ("graph", None, "图谱无结果")

    async def run_web():
        if "web" in sources:
            try:
                results = await WebSearchTool.search(question)
                if results:
                    lines = ["【网络搜索结果】"]
                    for i, r in enumerate(results[:5], 1):
                        lines.append(f"{i}. {r['title']}\n  {r['snippet']}\n  {r['link']}")
                    ctx = "\n\n".join(lines)
                    return ("web", ctx, f"搜索到{len(results)}条结果")
            except Exception as e:
                logger.warning("【搜索节点失败】%s", e)
        return ("web", None, "搜索无结果")

    # 并行执行选中的工具
    tasks = []
    if "rag" in sources:
        tasks.append(run_rag())
    if "graph" in sources:
        tasks.append(run_graph())
    if "web" in sources:
        tasks.append(run_web())

    results = await asyncio.gather(*tasks) if tasks else []

    # 获取上一轮 assistant 消息中的 tool_call_id，用于匹配 tool result
    tool_call_ids = []
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            tool_call_ids = [tc["id"] for tc in msg["tool_calls"]]
            break

    # 更新context字段 + 追加tool结果到messages
    new_tool_msgs = []
    for i, (source, ctx, summary) in enumerate(results):
        if source == "rag":
            rag_context = ctx
        elif source == "graph":
            graph_context = ctx
        elif source == "web":
            web_context = ctx

        # 格式化为tool role 消息（OpenAI格式）
        new_tool_msgs.append({
            "role": "tool",
            "content": ctx if ctx else "未找到相关内容",
            "tool_call_id": tool_call_ids[i] if i < len(tool_call_ids) else "",
        })

    logger.info(
        "【工具执行】第%s轮 执行=%s → %s",
        state.get("iteration", 0) + 1,
        sources,
        {s: "有结果" if ctx else "无结果" for s, ctx, _ in results},
    )

    return {
        "rag_context": rag_context,
        "graph_context": graph_context,
        "web_context": web_context,
        "messages": messages + new_tool_msgs,   # 追加tool结果到历史
        "iteration": state.get("iteration", 0) + 1, # 轮次+1
    }


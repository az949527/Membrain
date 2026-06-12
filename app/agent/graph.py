"""
构建 LangGraph StateGraph

将 reasoning / execute_tools 节点串起来，
reasoning 根据 selected_sources 条件分发到 execute_tools 或 END，
循环最多 3 轮。
"""
from functools import partial

from langgraph.graph import StateGraph, END

from app.agent.state import AgentState
from app.agent.nodes import (
    reasoning_node, execute_tools_node,     #替换原来的导入
)


def route_decision(state: AgentState) -> list[str]:
    """条件边：如果selected_sources含__answer__ → END，否则路由到工具节点"""
    sources = state.get("selected_sources", [])
    if "__answer__" in sources:
        return ["__answer__"]
    return sources


def build_router(embedder, vector_store, db, neo4j):
    builder = StateGraph(AgentState)

    # 注册节点（注册reasoning_node和execute_tools_node）
    builder.add_node("reasoning", reasoning_node)
    builder.add_node("execute_tools", partial(
        execute_tools_node,
        embedder=embedder, vector_store=vector_store, db=db, neo4j=neo4j,
    ))

    # 入口
    builder.set_entry_point("reasoning")

    # 条件边：reasoning根据selected_sources分发
    # __answer__ → END，否则 → execute_tools
    builder.add_conditional_edges(
        "reasoning",
        route_decision,
        {
            "__answer__": END,
            "rag": "execute_tools",
            "graph": "execute_tools",
            "web": "execute_tools",
        },
    )

    # 固定边：各检索节点 → collect → END
    # 改成循环边：tools执行完回答reasoning（继续推理）
    builder.add_edge("execute_tools", "reasoning")

    return builder.compile()

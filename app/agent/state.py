"""
LangGraph AgentState 定义

路由过程中传递的状态：
- question: 用户问题
- rag/graph/web_context: 各知识源的检索结果
- selected_sources: classify 节点选中的知识源列表
"""
from typing import TypedDict, Optional, List


class AgentState(TypedDict):
    """LangGraph 路由状态"""
    question: str                        # 用户当前问题
    rag_context: Optional[str]           # RAG 检索结果（None=未检索）
    graph_context: Optional[str]         # 知识图谱检索结果
    web_context: Optional[str]           # 网络搜索结果
    selected_sources: List[str]          # classify 节点选择的源 ["rag","graph","web"]
    messages: List[dict]                 # 记录每轮tool调用和结果，LLM靠这个知道前面做了什么
    iteration:  int                      # 计数，最多3轮，防止死循环

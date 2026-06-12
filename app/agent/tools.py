"""
OpenAI Tool Calling 工具定义

每个工具按 OpenAI 的 tool schema 格式定义。
LLM 收到 tools 参数后会根据 description 判断何时调用哪个工具。

设计要点：
- description 写清楚"什么场景用这个工具"，LLM 靠这个做决策
- 每个工具都接受 query 参数（从用户问题中提取关键词）
- TOOL_SOURCE_MAP 将工具名映射回内部源名，保持 graph.py 路由逻辑不变
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "rag_search",
            "description": "从本地知识库中搜索用户上传的私有文档内容。当问题涉及项目文档、私有知识、文件内容等需要查看具体文档资料时使用",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，从用户问题中提取核心实体或主题"
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "graph_query",
            "description": "查询知识图谱中的实体关系。当问题涉及人物关系、公司与人的关联、职位归属、概念分类等关系型知识时使用",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "要查询的实体或关系描述"
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "搜索网络上的实时信息。当问题涉及新闻、天气、股价、政策、最新动态、外部数据等需要时效性或联网查询的内容时使用",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词"
                    }
                },
                "required": ["query"],
            },
        },
    },
]

# 工具名到内部源名的映射
TOOL_SOURCE_MAP = {
    "rag_search": "rag",
    "graph_query": "graph",
    "web_search": "web",
}

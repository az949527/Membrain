"""
Agent（ReAct）核心流程测试

测试LangGraph路由逻辑，问候、工具调用、超时降级、循环终止
OpenAI用mock替代，不发起真实调用
"""
import pytest
from unittest.mock import patch, AsyncMock
from app.agent.graph import build_router


@pytest.fixture
def router():
    """构建不含真实依赖的路由器"""
    # 传入mock对象，只测路由逻辑，不测检索
    return build_router(
        embedder=AsyncMock(),
        vector_store=AsyncMock(),
        db=AsyncMock(),
        neo4j=AsyncMock(),
    )

@pytest.mark.asyncio
class TestReActRouting:

    @patch("app.agent.nodes.AsyncOpenAI")
    async def test_greeting_no_tool_call(self, mock_openai, router):
        """问候语 → LLM不调工具 → __answer__"""
        # ---- Arrange ----
        # mock LLM返回：不选任何工具（tool_calls为空）
        mock_instance = AsyncMock()
        mock_instance.chat.completions.create.return_value = AsyncMock(
            choices=[AsyncMock(message=AsyncMock(tool_calls=None, content="你好！"))]
        )
        mock_openai.return_value = mock_instance

        # ----  Act  ----
        result = await router.ainvoke({
            "question": "你好",
            "rag_context": None,
            "graph_context": None,
            "web_context": None,
            "selected_sources": [],
        })

        # ----  Assert  ----
        assert "__answer__" in result.get("selected_sources", []), \
            "问候语不应调用任何工具"

    @patch("app.agent.nodes.AsyncOpenAI")
    async def test_max_iterations_force_end(self, mock_openai, router):
        """LLM 一直选工具 → 3 轮后强制结束"""
        mock_tool_call = AsyncMock()
        mock_tool_call.id = "call_1"
        mock_tool_call.function.name = "rag_search"
        mock_tool_call.function.arguments = '{"query":"test"}'

        mock_instance = AsyncMock()
        mock_instance.chat.completions.create.return_value = AsyncMock(
            choices=[AsyncMock(message=AsyncMock(
                tool_calls=[mock_tool_call],
                content=None,
            ))]
        )
        mock_openai.return_value = mock_instance

        result = await router.ainvoke({
            "question": "test",
            "rag_context": None,
            "graph_context": None,
            "web_context": None,
            "selected_sources": [],
        })

        # 3 轮后强制结束，最终 selected_sources 是 __answer__
        assert "__answer__" in result.get("selected_sources", [])


class TestReActFallback:
    """降级逻辑：直接测 reasoning_node 节点，不跑整张图"""

    @patch("app.agent.nodes.AsyncOpenAI")
    async def test_api_timeout_returns_fallback(self, mock_openai):
        """reasoning_node 单节点：API超时 → 返回全源"""
        from app.agent.nodes import reasoning_node
        mock_openai.side_effect = Exception("API Timeout")

        result = await reasoning_node({
            "question": "今天天气怎么样",
            "messages": [],
            "iteration": 0,
        })

        assert result["selected_sources"] == ["rag", "graph", "web"], \
            "API超时时应降级为全源检索"
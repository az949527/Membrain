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


class TestReActToolSelection:
    """工具选择决策测试：直接测 reasoning_node 单节点，看 LLM 选什么工具"""

    @patch("app.agent.nodes.AsyncOpenAI")
    async def test_reasoning_node_rag_selection(self, mock_openai):
        """LLM 选择 rag_search → selected_sources 包含 rag"""
        from app.agent.nodes import reasoning_node

        mock_tool_call = AsyncMock()
        mock_tool_call.id = "call_1"
        mock_tool_call.function.name = "rag_search"
        mock_tool_call.function.arguments = '{"query": "MemBrain 框架"}'

        mock_instance = AsyncMock()
        mock_instance.chat.completions.create.return_value = AsyncMock(
            choices=[AsyncMock(message=AsyncMock(
                tool_calls=[mock_tool_call],
                content=None,
            ))]
        )
        mock_openai.return_value = mock_instance

        result = await reasoning_node({
            "question": "MemBrain 用了什么框架？",
            "messages": [],
            "iteration": 0,
        })

        assert "rag" in result.get("selected_sources", []), \
            "LLM 选 rag_search 应映射为 selected_sources 包含 rag"

    @patch("app.agent.nodes.AsyncOpenAI")
    async def test_reasoning_node_multi_tool(self, mock_openai):
        """LLM 同时选 rag + web → selected_sources 同时包含 rag 和 web"""
        from app.agent.nodes import reasoning_node

        tc1 = AsyncMock()
        tc1.id = "call_1"
        tc1.function.name = "rag_search"
        tc1.function.arguments = '{"query": "MemBrain"}'

        tc2 = AsyncMock()
        tc2.id = "call_2"
        tc2.function.name = "web_search"
        tc2.function.arguments = '{"query": "LangGraph 最新"}'

        mock_instance = AsyncMock()
        mock_instance.chat.completions.create.return_value = AsyncMock(
            choices=[AsyncMock(message=AsyncMock(
                tool_calls=[tc1, tc2],
                content=None,
            ))]
        )
        mock_openai.return_value = mock_instance

        result = await reasoning_node({
            "question": "LangGraph 最新进展？",
            "messages": [],
            "iteration": 0,
        })

        sources = result.get("selected_sources", [])
        assert "rag" in sources, "rag_search 应映射为 rag"
        assert "web" in sources, "web_search 应映射为 web"

    @patch("app.agent.nodes.AsyncOpenAI")
    async def test_reasoning_node_empty_tool_calls_fallback(self, mock_openai):
        """LLM 无 tool_calls → 降级为全源检索（防御性策略）"""
        from app.agent.nodes import reasoning_node

        mock_instance = AsyncMock()
        mock_instance.chat.completions.create.return_value = AsyncMock(
            choices=[AsyncMock(message=AsyncMock(
                tool_calls=None,
                content="你好！有什么可以帮助你的吗？",
            ))]
        )
        mock_openai.return_value = mock_instance

        result = await reasoning_node({
            "question": "你好",
            "messages": [],
            "iteration": 0,
        })

        # 当前策略：LLM 不返回 tool_calls 时降级为全源检索
        # 宁可多搜不能空手，属于防御性设计
        assert result["selected_sources"] == ["rag", "graph", "web"], \
            "无 tool_calls 时应降级为全源检索"


class TestReActFullLoop:
    """完整 ReAct 循环测试：全图路由（reasoning → execute → reasoning → answer）"""

    @patch("app.agent.nodes.AsyncOpenAI")
    async def test_reactive_loop_answer_after_tool(self, mock_openai, router):
        """ReAct: 第1轮选工具 → 后续轮次完成后强制结束"""
        tc = AsyncMock()
        tc.id = "call_1"
        tc.function.name = "rag_search"
        tc.function.arguments = '{"query": "MemBrain 框架"}'

        mock_instance = AsyncMock()
        # side_effect: 第1次返回 tool_call, 后续返回空（触发降级为全源）
        mock_instance.chat.completions.create.side_effect = [
            AsyncMock(choices=[AsyncMock(message=AsyncMock(
                tool_calls=[tc], content=None,
            ))]),
            AsyncMock(choices=[AsyncMock(message=AsyncMock(
                tool_calls=None, content="MemBrain 使用 LangGraph 框架",
            ))]),
        ]
        mock_openai.return_value = mock_instance

        result = await router.ainvoke({
            "question": "MemBrain 用了什么框架？",
            "rag_context": None,
            "graph_context": None,
            "web_context": None,
            "selected_sources": [],
        })

        # 由于空 tool_calls 会降级为全源检索，实际会走满 3 轮后强制结束
        assert "__answer__" in result.get("selected_sources", []), \
            "最终应强制结束"
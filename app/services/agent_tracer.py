"""
Agent 追踪服务

封装追踪记录的创建逻辑，供 chat.py 在每次 LangGraph 路由后调用。
"""
import time
import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.models.agent_trace import AgentTrace


class AgentTracer:
    """Agent 行为追踪器"""

    @staticmethod
    async def record(
        db: AsyncSession,
        question: str,
        result: dict,
        duration_ms: int,
    ) -> AgentTrace | None:
        """记录一次 Agent 路由追踪

        参数:
            db: 数据库会话
            question: 用户问题
            result: LangGraph 路由返回结果（含 selected_sources / rag_context 等）
            duration_ms: 路由总耗时（毫秒）

        返回:
            AgentTrace: 创建的追踪记录
        """
        try:
            sources = result.get("selected_sources", [])

            # 判断各知识源是否有返回内容
            context_used = {
                "rag": bool(result.get("rag_context")),
                "graph": bool(result.get("graph_context")),
                "web": bool(result.get("web_context")),
            }

            trace = AgentTrace(
                question=question[:200],  # 截断长问题
                sources_selected=json.dumps(sources, ensure_ascii=False),
                rounds=result.get("iteration", 0),
                duration_ms=duration_ms,
                context_used=json.dumps(context_used, ensure_ascii=False),
            )
            db.add(trace)
            await db.flush()

            logger.info(
                "【Agent追踪】问题='%s' 源=%s 轮数=%s 耗时=%sms 使用=%s",
                question[:30], sources, result.get("iteration", 0),
                duration_ms, context_used,
            )
            return trace

        except Exception as e:
            logger.warning("【Agent追踪记录失败】%s", e)
            return None

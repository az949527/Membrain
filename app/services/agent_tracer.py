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

        使用独立会话提交，避免被 SSE 流式响应的事务回滚影响。
        """
        try:
            from app.core.database import async_session_factory

            sources = result.get("selected_sources", [])

            # 判断各知识源是否有返回内容
            context_used = {
                "rag": bool(result.get("rag_context")),
                "graph": bool(result.get("graph_context")),
                "web": bool(result.get("web_context")),
            }

            trace = AgentTrace(
                question=question[:200],
                sources_selected=json.dumps(sources, ensure_ascii=False),
                rounds=result.get("iteration", 0),
                duration_ms=duration_ms,
                context_used=json.dumps(context_used, ensure_ascii=False),
            )

            # 使用独立会话提交，不依赖上游 SSE 的事务
            async with async_session_factory() as tracer_session:
                tracer_session.add(trace)
                await tracer_session.commit()

            logger.info(
                "【Agent追踪】问题='%s' 源=%s 轮数=%s 耗时=%sms 使用=%s",
                question[:30], sources, result.get("iteration", 0),
                duration_ms, context_used,
            )
            return trace

            logger.info(
                "【Agent追踪】问题='%s' 源=%s 轮数=%s 耗时=%sms 使用=%s",
                question[:30], sources, result.get("iteration", 0),
                duration_ms, context_used,
            )
            return trace

        except Exception as e:
            logger.warning("【Agent追踪记录失败】%s", e)
            return None

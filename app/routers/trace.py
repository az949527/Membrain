"""
Agent 追踪记录路由

提供查看追踪记录列表的 API 端点。
"""
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.agent_trace import AgentTrace
from app.schemas.trace import AgentTraceResponse

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


@router.get("/traces", response_model=List[AgentTraceResponse])
async def list_traces(
    limit: int = Query(20, ge=1, le=100, description="返回条数"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取最近的 Agent 追踪记录，按时间倒序排列"""
    result = await db.execute(
        select(AgentTrace)
        .order_by(AgentTrace.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())

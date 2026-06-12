"""
Agent 追踪记录 Pydantic 模型

定义追踪记录的 API 响应格式。
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AgentTraceResponse(BaseModel):
    """追踪记录响应

    from_attributes=True 支持从 ORM 模型直接转换
    """
    id: int
    question: str
    sources_selected: Optional[str] = None
    rounds: int
    duration_ms: int
    context_used: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}

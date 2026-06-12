"""
Agent 追踪记录模型

每次 LangGraph 路由完成后记录一条追踪日志，
用于评估 Agent 决策质量和排查问题。
"""
from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AgentTrace(Base):
    """Agent 追踪记录表

    存储每次聊天请求的 Agent 执行轨迹，包括：
    - 用户问题
    - ReAct 选中的知识源
    - 执行轮数
    - 耗时
    - 各源是否有返回结果
    """
    __tablename__ = "agent_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(Text, nullable=False, comment="用户问题")
    sources_selected: Mapped[str] = mapped_column(
        String(128), nullable=True, comment="选中的知识源，JSON 列表"
    )
    rounds: Mapped[int] = mapped_column(Integer, default=0, comment="ReAct 执行轮数")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, comment="路由耗时（毫秒）")
    context_used: Mapped[str] = mapped_column(
        String(128), nullable=True, comment="各源是否有结果，JSON 对象"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        comment="记录时间",
    )

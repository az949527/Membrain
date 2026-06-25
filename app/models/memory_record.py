"""
记忆记录模型

存储 Agent 从对话中提取的语义记忆（facts）和对话摘要（summaries）。
对应三层记忆中的语义记忆和情景记忆压缩。
"""
from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MemoryRecord(Base):
    """记忆记录表

    memory_type 支持两种：
    - "fact"：从对话中提取的事实/偏好（语义记忆）
    - "summary"：对话摘要（情景记忆的压缩）
    """
    __tablename__ = "memory_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 关联到对话（每条记忆属于一个对话）
    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("conversations.id"), nullable=False
    )

    # 记忆类型：fact / summary
    memory_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # 记忆内容（事实描述或摘要文本）
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 创建时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<MemoryRecord {self.memory_type}:{self.content[:20]}>"

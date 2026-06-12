"""
消息模型

定义对话中的单条消息，对应数据库 messages 表。
每条消息属于某个对话，记录角色（用户/助手/系统）和内容。

=== 业务模块：需根据项目需求重新设计 ===

说明：
- 消息模型是这个聊天应用特有的，换项目时重新设计
- 模式固定：外键关联 Conversation + 业务字段 + 时间戳
"""
from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Message(Base):
    """消息表

    存储对话历史中的每一条消息。
    角色（role）支持三种取值：user（用户）、assistant（AI助手）、system（系统提示）。
    内容（content）使用 Text 类型，支持长文本。
    """
    __tablename__ = "messages"

    # 主键，自增整数
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 外键：关联到 conversations 表
    conversation_id: Mapped[int] = mapped_column(Integer, ForeignKey("conversations.id"), nullable=False)

    # 消息角色：user / assistant / system
    role: Mapped[str] = mapped_column(String(16), nullable=False)

    # 消息正文：使用 Text 支持长文本
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 消息发送时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    # 多对一关联：反向关联到 Conversation
    conversation = relationship("Conversation", back_populates="messages")

    def __repr__(self) -> str:
        return f"<Message {self.id}: {self.role}>"

"""
对话模型

定义用户与 AI 之间的一次对话会话，对应数据库 conversations 表。
一个对话包含多条消息（一对多关系），属于某个用户。

=== 业务模块：需根据项目需求重新设计 ===

说明：
- 对话模型是这个聊天应用特有的，换项目时重新设计
- 模式固定：外键关联 User + 业务字段 + 时间戳 + relationship
"""
from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Conversation(Base):
    """对话表

    将一组相关的消息归为一个对话，方便用户回顾和继续之前的交流。
    对话标题默认取第一条用户消息，可在后续手动修改。
    """
    __tablename__ = "conversations"

    # 主键，自增整数
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 外键：关联到 users 表，标记这个对话属于哪个用户
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # 对话标题：自动从首条用户消息截取，默认值为"新对话"
    title: Mapped[str] = mapped_column(String(255), default="新对话")

    # 记录创建时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    # 记录最后更新时间（有新消息时更新）
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    # 多对一关联：反向关联到 User
    user = relationship("User", back_populates="conversations")

    # 一对多关联：一个对话有多条消息
    # cascade 确保删除对话时同时删除其所有消息
    # order_by 保证消息按创建时间排序返回
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan",
                            order_by="Message.created_at")

    def __repr__(self) -> str:
        return f"<Conversation {self.id}: {self.title}>"

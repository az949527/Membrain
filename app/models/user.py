"""
用户模型

定义系统中的用户实体，对应数据库 users 表。
每个用户可以有多个对话（一对多关系）。

=== 业务模块：需根据项目需求重新设计 ===

说明：
- 模型定义是本项目特有的（用户 + 对话 + 消息），换项目就完全不一样了
- 但写法模式是固定的：继承 Base → 定义 __tablename__ → Mapped 字段 → relationship 关联

使用时：
    1. 想清楚你的业务有哪些实体
    2. 每个实体建一个文件，参考这里的模式来写
    3. 确定实体之间的关系（1对多？多对多？）

通用参考：
    from app.core.database import Base
    class Xxx(Base):
        __tablename__ = "xxxes"
        id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
        ...
"""
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    """用户表

    存储用户的认证信息和基本资料。
    密码不存明文，只存 bcrypt 哈希值。
    """
    __tablename__ = "users"

    # 主键，自增整数
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 邮箱：唯一、有索引，用于登录
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    # 用户名：唯一，用于展示和标识
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    # bcrypt 哈希后的密码，长度 60，预留到 128 确保兼容性
    hashed_password: Mapped[str] = mapped_column(String(128), nullable=False)

    # 记录创建时间，带时区，使用 UTC
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    # 记录最后更新时间，每次更新时自动刷新
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    # 一对多关联：一个用户有多个对话
    # cascade="all, delete-orphan" 表示删除用户时自动删除其所有对话
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User {self.id}: {self.username}>"

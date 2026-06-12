"""
用户认证服务

封装注册、登录、用户查询的业务逻辑。
这些方法被 routers/auth.py 调用，与 HTTP 层解耦。

=== 核心业务逻辑：每个项目需自行实现 ===

说明：
- 业务逻辑是每个产品的核心，必须自己写
- 但模式固定：
    class XxxService:
        @staticmethod
        async def do_something(db, params...) -> Result:
            # 1. 校验/查重
            # 2. 业务处理
            # 3. 写库
            return result

设计原因：
- 将业务逻辑从路由层抽离，方便单元测试
- 如果以后要加邮箱验证、OAuth 等，只需在这里扩展
"""
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.hashing import hash_password, verify_password
from app.core.security import create_access_token
from app.models.user import User


class AuthService:
    """用户认证相关业务逻辑（全部使用静态方法，无状态服务）"""

    @staticmethod
    async def register(db: AsyncSession, email: str, username: str, password: str) -> User:
        """注册新用户

        流程：
        1. 检查邮箱是否已被注册 → 是则抛 409
        2. 检查用户名是否已被使用 → 是则抛 409
        3. bcrypt 哈希密码（绝不存明文）
        4. 写入数据库并返回新用户对象

        为什么先检查再写入：
        - 利用数据库 unique 约束兜底，但提前检查能返回友好的中文错误信息
        """
        # 检查邮箱是否已存在
        result = await db.execute(select(User).where(User.email == email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="邮箱已被注册")

        # 检查用户名是否已存在
        result = await db.execute(select(User).where(User.username == username))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已被使用")

        # 创建用户（密码已经哈希处理）
        user = User(
            email=email,
            username=username,
            hashed_password=hash_password(password),
        )
        db.add(user)
        await db.flush()   # 刷入数据库以获取自增 ID
        await db.refresh(user)  # 刷新以获取数据库生成的默认值
        return user

    @staticmethod
    async def authenticate(db: AsyncSession, email: str, password: str) -> User:
        """验证用户登录

        流程：
        1. 按邮箱查找用户
        2. 用户不存在或密码不匹配 → 抛 401（不告知具体哪个错了，防止枚举攻击）

        为什么返回 User 而不是 Token：
        - 将 token 生成放在路由层，服务层只负责认证逻辑
        """
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
        return user

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
        """按 ID 查询用户（供其他服务内部调用）"""
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

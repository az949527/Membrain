"""
认证路由

提供三个认证相关端点：
- POST /register — 注册新用户
- POST /token   — 登录获取 JWT
- GET  /me      — 获取当前用户信息（需登录）

=== API 接口层：每增一个 API 端点需对应增加 ===

说明：
- 路由层只做"传话筒"，不做业务判断
- 模式固定（三段式）：
    1. 定义 APIRouter + prefix
    2. 写 @router.xxx("/path") 装饰器
    3. 函数体：取出参数 → 调用 Service → 返回结果

使用时：
    1. 在 schemas/ 中定义好请求/响应格式
    2. 在 services/ 中实现业务逻辑
    3. 在这里写 3-5 行代码串起来
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token, get_current_user
from app.models.user import User
from app.schemas.auth import (
    RegisterRequest,
    TokenRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth import AuthService

# APIRouter 创建路由分组
# prefix: 所有路由自动添加 /api/v1/auth 前缀
# tags:   在 OpenAPI 文档中分组显示
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """用户注册

    请求体中的 password 是明文，服务端不会存储明文。
    注册成功后返回用户基本信息（不含密码）。
    """
    user = await AuthService.register(db, body.email, body.username, body.password)
    return user


@router.post("/token", response_model=TokenResponse)
async def login(body: TokenRequest, db: AsyncSession = Depends(get_db)):
    """用户登录

    验证邮箱和密码，验证通过后返回 JWT access_token。
    客户端应在后续请求的 Authorization 头中携带此 token。
    """
    user = await AuthService.authenticate(db, body.email, body.password)
    token = create_access_token(user.id)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息

    依赖 get_current_user 中间件：
    1. 从请求头提取 Authorization: Bearer <token>
    2. 解码 JWT 获取 user_id
    3. 从数据库查询并返回 User 对象
    如果 token 无效或已过期 → 返回 401
    """
    return current_user

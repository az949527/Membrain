"""
认证相关 Pydantic 模型

定义注册、登录接口的请求体和响应体格式。
使用 Pydantic 的 EmailStr 做邮箱格式校验，
使用 field_validator 做自定义字段规则校验。

=== 业务模块：每增一个 API 端点需对应增加 ===

说明：
- 这些 Schema 是项目业务的一部分，需要自己定义
- 但模式固定：继承 BaseModel → 定义字段类型 + 可选校验器 + model_config

使用时：
    1. 先想好 API 需要什么请求参数和返回字段
    2. 在这里定义对应的 Request / Response 类
    3. 定义好之后，在 routers 和 services 里直接用
"""
from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    """注册请求体

    email:     邮箱地址（自动校验格式）
    username:  用户名（2-32 字符）
    password:  密码明文（最少 6 位，服务端不存明文）
    """
    email: EmailStr
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """校验用户名长度"""
        if len(v) < 2 or len(v) > 32:
            raise ValueError("用户名长度需在 2-32 字符之间")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """校验密码长度，最短 6 位"""
        if len(v) < 6:
            raise ValueError("密码长度至少 6 位")
        return v


class TokenRequest(BaseModel):
    """登录请求体：邮箱 + 密码"""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """登录成功后的响应

    access_token: JWT 令牌字符串
    token_type:   令牌类型，固定为 "bearer"
    """
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """用户信息响应体

    model_config 中的 from_attributes=True 表示可从 ORM 模型直接转换
    """
    id: int
    email: str
    username: str
    created_at: datetime

    model_config = {"from_attributes": True}

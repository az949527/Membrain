"""
聊天相关 Pydantic 模型

定义聊天接口的请求体和响应体格式。
使用嵌套模型 MessageItem 来描述消息结构。

=== 业务模块：每增一个 API 端点需对应增加 ===

说明：
- 聊天相关的 Schema 是这个项目特有的
- 模式固定：BaseModel 定义字段 → 组合成嵌套结构
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class MessageItem(BaseModel):
    """单条消息结构

    role:    消息角色，user / assistant / system
    content: 消息文本内容
    """
    role: str
    content: str


class ChatRequest(BaseModel):
    """聊天请求体

    messages:        消息列表（通常以 user 消息结尾）
    conversation_id: 对话 ID，留空则自动创建新对话
    """
    messages: List[MessageItem]
    conversation_id: Optional[int] = None


class ChatResponse(BaseModel):
    """聊天响应体（用于非流式场景，当前未使用）"""
    content: str
    conversation_id: int


class ConversationResponse(BaseModel):
    """对话列表中的单条对话信息

    from_attributes=True 支持从 ORM 模型直接转换
    """
    id: int
    title: str
    created_at: datetime

    model_config = {"from_attributes": True}

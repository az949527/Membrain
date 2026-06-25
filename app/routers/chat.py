"""
聊天路由

提供两个聊天相关端点：
- POST /chat          — 流式聊天（SSE，需登录）
- GET  /conversations — 获取对话列表（需登录）

=== API 接口层：每增一个 API 端点需对应增加 ===

说明：
- 路由层只做"传话筒"，不做业务判断
- 模式固定（三段式）：
    1. 定义 APIRouter + prefix
    2. 写 @router.xxx("/path") 装饰器
    3. 函数体：取出参数 → 调用 Service → 返回结果

为什么使用 SSE 而不是 WebSocket：
- SSE 基于 HTTP，兼容性好，代理友好
- 只需要服务端→客户端的单向流，SSE 天然适合
- 实现简单，不需要升级握手等复杂逻辑
"""
import json
from typing import List, Union

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logger import logger
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.chat import ChatRequest, ConversationResponse
from app.services.chat import ChatService

router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post("/chat")
async def chat(
    body: ChatRequest,
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """流式聊天

    请求体：
    - messages: 消息列表，最后一条通常是用户新输入
    - conversation_id: 可选，留空则新建对话

    返回 SSE (Server-Sent Events) 流：
    - data: <文本token>\n\n    — 逐 token 的回复内容
    - data: {"done": true, "conversation_id": 1}\n\n  — 结束标记

    使用 StreamingResponse 实现流式响应：
    不加这个的话 FastAPI 会等整个生成器跑完才返回，
    那就失去流式的意义了。

    注意：Pydantic 模型转 dict 后用 model_dump() (v2 语法)
    """
    from app.core.logger import logger

    logger.info("========== 收到聊天请求 ==========")
    logger.info("用户ID: %s, 对话ID: %s, 消息数: %s",
                 current_user.id, body.conversation_id, len(body.messages))
    from fastapi.responses import StreamingResponse

    # 将 Pydantic 模型转为普通 dict，方便服务层处理
    messages_dict = [m.model_dump() for m in body.messages]

    # 创建异步生成器
    generator = ChatService.chat(
        db,
        user_id=current_user.id,
        conversation_id=body.conversation_id,
        messages=messages_dict,
        request=request,
    )

    # 包装为 SSE 流式响应
    return StreamingResponse(
        _sse_wrap(generator, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",       # 禁止缓存
            "Connection": "keep-alive",        # 保持长连接
            "X-Accel-Buffering": "no",         # 禁用 nginx 缓冲
        },
    )


async def _sse_wrap(generator, db: AsyncSession):
    """将 ChatService.chat 生成器包装为标准 SSE 格式

    SSE 格式要求：每条消息以 "data: " 开头，以 "\n\n" 结尾。

    特殊消息处理：
    - __conversation_id__: 从流中提取但不发送给客户端
    - done 事件：流结束标记，携带 conversation_id
    """
    conv_id = None
    sse_count = 0
    async for chunk in generator:
        # dict → 结构化事件，JSON 序列化后发送
        if isinstance(chunk, dict):
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            continue
        # 拦截特殊消息：对话 ID 通知（不发送给客户端）
        if chunk.startswith("__conversation_id__:"):
            conv_id = chunk.split(":")[1].strip()
            logger.info("[SSE包装器] 捕获到对话ID: %s（不发送给客户端）", conv_id)
            continue
        # 正常 token 内容：包装为 SSE 格式
        sse_count += 1
        yield f"data: {chunk}\n\n"

    # 流结束后发送完成标记
    done_data = {"done": True}
    if conv_id:
        done_data["conversation_id"] = int(conv_id)
    done_json = json.dumps(done_data)
    logger.info("[SSE包装器] 完成标记: total_tokens=%s, sending=%s", sse_count, done_json)
    yield f"data: {done_json}\n\n"


@router.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取用户的对话历史列表

    按最后更新时间倒序排列，方便用户看到最近的对话。
    供前端侧边栏或对话切换功能使用。
    """
    return await ChatService.get_conversations(db, current_user.id)

"""
聊天服务

处理对话生命周期管理和 LLM API 调用。

=== 核心业务逻辑：每个项目需自行实现 ===

说明：
- 聊天服务是这个项目的核心业务，完全定制
- 但设计模式固定：静态方法 + 异步数据库操作 + 调用外部 API

核心流程（chat 方法）：
1. 获取或创建对话（由 conversation_id 决定）
2. 将用户输入保存到数据库
3. 从数据库加载完整对话历史
4. 调用 DeepSeek API 流式生成回复
5. 逐 token 返回给客户端
6. 流结束后保存完整回复到数据库

设计原因：
- 消息先存再调 API，保证即使后续调用失败，用户输入也不会丢失
- 每次都从 DB 加载完整历史而不是依赖客户端传，
  避免客户端篡改历史
"""
from typing import AsyncGenerator, List, Optional

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logger import logger
from app.models.conversation import Conversation
from app.models.message import Message


class ChatService:
    """聊天业务逻辑（管理对话和消息持久化，调用 LLM API）"""

    @staticmethod
    async def _get_or_create_conversation(
        db: AsyncSession, user_id: int, conversation_id: Optional[int]
    ) -> Conversation:
        """获取已有对话或创建新对话

        如果提供了 conversation_id 且属于该用户 → 复用
        否则 → 创建新对话

        参数:
            conversation_id: None 或不属于当前用户时都会创建新的
        """
        if conversation_id is not None:
            # 查找指定 ID 且属于当前用户的对话
            result = await db.execute(
                select(Conversation).where(
                    Conversation.id == conversation_id, Conversation.user_id == user_id
                )
            )
            conv = result.scalar_one_or_none()
            if conv:
                return conv

        # 没找到或没提供 → 创建新对话
        conv = Conversation(user_id=user_id)
        db.add(conv)
        await db.flush()
        await db.refresh(conv)
        return conv

    @staticmethod
    async def _save_message(
        db: AsyncSession, conversation_id: int, role: str, content: str
    ) -> Message:
        """保存单条消息到数据库并返回"""
        msg = Message(conversation_id=conversation_id, role=role, content=content)
        db.add(msg)
        await db.flush()
        await db.refresh(msg)
        return msg

    @classmethod
    async def chat(
        cls,
        db: AsyncSession,
        user_id: int,
        conversation_id: Optional[int],
        messages: List[dict],
        request=None,
    ) -> AsyncGenerator[str, None]:
        """流式聊天核心方法

        这是一个异步生成器，逐 token 产出文本。
        首条产出是 "__conversation_id__:{id}" 的特殊消息，
        让客户端知道当前的对话 ID（新建对话时特别重要）。

        参数:
            db:              数据库会话
            user_id:         当前用户 ID
            conversation_id: 对话 ID（None 则新建）
            messages:        本轮用户消息列表 [{"role":"user","content":"..."}]

        Yields:
            str: 逐 token 的回复内容
        """
        # ==================== 第 1 步：获取或创建对话 ====================
        logger.info("【第1步】获取或创建对话 conversation_id=%s, user_id=%s",
                     conversation_id, user_id)
        conv = await cls._get_or_create_conversation(db, user_id, conversation_id)
        conv_id = conv.id
        logger.info("【第1步完成】使用对话 ID=%s (标题: %s)", conv_id, conv.title)

        # ==================== 第 2 步：保存用户消息 ====================
        user_msg_count = 0
        for msg in messages:
            if msg.get("role") == "user":
                await cls._save_message(db, conv_id, "user", msg["content"])
                user_msg_count += 1
        logger.info("【第2步完成】已保存 %s 条用户消息到对话 %s", user_msg_count, conv_id)

        # ==================== 第 3 步：构建 API 请求 ====================
        # 从数据库加载完整历史（确保不会被客户端篡改）
        history_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(Message.created_at)
        )
        history = history_result.scalars().all()
        logger.info("【第3步】从数据库加载了 %s 条历史消息", len(history))

        # 组装给 LLM 的消息列表：system 提示 + 历史对话
        api_messages = [
            {"role": "system", "content": "你是一个智能助手，请用中文回答问题。"}
        ]
        for m in history:
            api_messages.append({"role": m.role, "content": m.content})
        logger.info("【第3步完成】组装了 %s 条消息发给 LLM（含 system 提示）", len(api_messages))

        user_query = messages[-1]["content"] if messages else ""

        # ==================== 第 3.5 步：语义缓存查询 ====================
        from app.cache import semantic_cache

        redis = getattr(request.app.state, "redis", None)
        if redis and user_query:
            try:
                cached = await semantic_cache.get(redis, user_query, request.app.state.embedder)
                if cached:
                    logger.info("【缓存命中】直接返回缓存回答")
                    yield f"__conversation_id__:{conv_id}\n"
                    yield cached
                    await cls._save_message(db, conv_id, "assistant", cached)
                    return
                logger.info("【缓存未命中】继续正常流程")
            except Exception as e:
                logger.warning("【缓存查询失败】Redis 不可用，跳过缓存: %s", e)

        # ==================== LangGraph 路由检索 ====================
        import time
        from app.services.agent_tracer import AgentTracer

        try:
            # 懒加载 router（只在首次聊天时构建一次）
            if not hasattr(request.app.state, "router"):
                from app.agent.graph import build_router
                request.app.state.router = build_router(
                    embedder=request.app.state.embedder,
                    vector_store=request.app.state.vector_store,
                    db=db,
                    neo4j=getattr(request.app.state, "neo4j", None),
                )

            if user_query:
                t0 = time.time()
                result = await request.app.state.router.ainvoke({
                    "question": user_query,
                    "rag_context": None,
                    "graph_context": None,
                    "web_context": None,
                    "selected_sources": [],
                })
                duration_ms = int((time.time() - t0) * 1000)

                # 记录 Agent 追踪（异步，不影响主流程）
                await AgentTracer.record(db, user_query, result, duration_ms)

                if result.get("rag_context"):
                    api_messages.insert(1, {"role": "system", "content": result["rag_context"]})
                if result.get("graph_context"):
                    api_messages.insert(2, {"role": "system", "content": result["graph_context"]})
                if result.get("web_context"):
                    api_messages.insert(3, {"role": "system", "content": result["web_context"]})
        except Exception as e:
            logger.warning("【LangGraph 路由跳过】%s", e)


        # ==================== 第 4 步：流式调用 LLM API ====================
        logger.info("【第4步】开始调用 LLM API (base_url=%s, model=%s)",
                     settings.LLM_BASE_URL, settings.LLM_MODEL)
        full_response = ""

        # 先发送 conversation_id 给客户端
        yield f"__conversation_id__:{conv_id}\n"

        # 初始化 OpenAI 客户端（DeepSeek 兼容 OpenAI 接口）
        client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
        )

        try:
            stream = await client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=api_messages,
                stream=True,
                timeout=120,
            )

            logger.info("【第4步】LLM 连接成功，开始接收流式 token...")
            token_count = 0

            async for chunk in stream:
                content = chunk.choices[0].delta.content or ""
                if content:
                    full_response += content
                    token_count += 1
                    yield content

            logger.info("【第4步完成】共接收 %s 个 token，累计 %s 字",
                        token_count, len(full_response))

        except Exception as e:
            logger.error("【第4步异常】Chat stream error: %s", str(e))
            yield f"\n\n[连接错误: {str(e)}]"
            return

        # ==================== 第 5 步：保存完整回复 ====================
        if full_response:
            await cls._save_message(db, conv_id, "assistant", full_response)
            logger.info("【第5步】已保存 AI 回复到对话 %s（%s 字）", conv_id, len(full_response))

            # 自动更新对话标题（取第一条用户消息的前 30 个字）
            if conv.title == "新对话" and messages:
                first_user_msg = next(
                    (m["content"] for m in messages if m.get("role") == "user"), ""
                )
                if first_user_msg:
                    conv.title = first_user_msg[:30]
                    db.add(conv)
                    logger.info("【第5步】自动更新对话标题为: %s", conv.title)
        else:
            logger.warning("【第5步跳过】AI 没有返回任何内容，无需保存")

        logger.info("========== 聊天请求处理完成 ==========")

        # ==================== 第 6 步：写入语义缓存 ====================
        if full_response and redis and user_query:
            await semantic_cache.set(redis, user_query, full_response, request.app.state.embedder)
            logger.info("【缓存写入】已回答缓存")

    @staticmethod
    async def get_conversations(db: AsyncSession, user_id: int) -> List[Conversation]:
        """获取用户的所有对话列表，按最后更新时间倒序"""
        result = await db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
        )
        return list(result.scalars().all())

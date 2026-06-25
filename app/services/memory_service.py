import json
import re
from openai import AsyncOpenAI
from sqlalchemy import select

from app.core.config import settings
from app.core.logger import logger
from app.core.prompts import FACTS_EXTRACT_PROMPT, CONVERSATION_SUMMARY_PROMPT
from app.models.memory_record import MemoryRecord


class MemoryService:
    """Agent 记忆服务

    管理三层记忆：
    - 语义记忆：extract_facts() 提取事实/偏好
    - 情景记忆：summarize() 压缩对话摘要
    - 检索注入：get_memory() 格式化输出
    """

    def __init__(self, db):
        self.db = db
        self.client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
        )

    async def extract_facts(self, conversation_id: int, messages: list) -> list[str]:
        """从对话中提取事实/偏好，存为语义记忆

        调用 LLM 分析对话，提取用户提到的实体、偏好、关键信息。
        结果逐条写入 memory_records 表，type='fact'。
        """
        # 1. 取最近的消息（最新的 6 轮）
        recent = self._get_recent_messages(messages, rounds=6)

        # 2. 调 LLM 提取事实
        prompt = FACTS_EXTRACT_PROMPT.format(
            conversation="\n".join(
                f"{m.role}: {m.content[:200]}" for m in recent
            )
        )

        response = await self.client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )

        # 3. 解析返回的 JSON 列表
        facts = self._parse_facts(response.choices[0].message.content or "[]")

        # 4. 写入数据库
        for fact in facts:
            record = MemoryRecord(
                conversation_id=conversation_id,
                memory_type="fact",
                content=fact,
            )
            self.db.add(record)
        await self.db.commit()

        return facts

    async def summarize(self, conversation_id: int, messages: list) -> str:
        """压缩对话历史为一句话摘要，存为情景记忆"""
        # 1. 取全部消息的概要
        conversation_text = "\n".join(
            f"{m.role}: {m.content[:300]}" for m in messages[-10:]
        )

        # 2. 调 LLM 生成摘要
        response = await self.client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{"role": "user", "content": CONVERSATION_SUMMARY_PROMPT.format(
                conversation=conversation_text
            )}],
            temperature=0.1,
        )

        summary = response.choices[0].message.content or ""

        # 3. 写入数据库（覆盖旧的 summary，只保留最新一条）
        # 先删旧的 summary
        old = await self.db.execute(
            select(MemoryRecord).where(
                MemoryRecord.conversation_id == conversation_id,
                MemoryRecord.memory_type == "summary",
            )
        )
        for record in old.scalars().all():
            await self.db.delete(record)

        # 再写入新的
        record = MemoryRecord(
            conversation_id=conversation_id,
            memory_type="summary",
            content=summary,
        )
        self.db.add(record)
        await self.db.commit()

        return summary

    async def get_memory(self, conversation_id: int) -> str:
        """获取当前对话的已有记忆，格式化为文本注入到 system prompt 之后

        返回格式：
            [记忆摘要]
            （summary 内容）

            [已知事实]
            - fact 1
            - fact 2
        """
        records = await self.db.execute(
            select(MemoryRecord).where(
                MemoryRecord.conversation_id == conversation_id,
            ).order_by(MemoryRecord.created_at.desc())
        )
        records = records.scalars().all()

        if not records:
            return ""

        summary = ""
        facts = []
        for r in records:
            if r.memory_type == "summary":
                summary = r.content
            elif r.memory_type == "fact":
                facts.append(r.content)

        parts = []
        if summary:
            parts.append(f"[记忆摘要]\n{summary}")
        if facts:
            parts.append("[已知事实]\n- " + "\n- ".join(facts))

        return "\n\n".join(parts)

    @staticmethod
    def _get_recent_messages(messages: list, rounds: int = 6) -> list:
        """取最近 N 轮对话（过滤 tool 消息）"""
        result = []
        for m in messages:
            if hasattr(m, "role") and m.role in ("user", "assistant"):
                result.append(m)
        return result[-rounds * 2:]  # user + assistant = 1 轮

    @staticmethod
    def _parse_facts(content: str) -> list:
        """解析 LLM 返回的事实列表 JSON"""
        # 尝试从 ```json ... ``` 中提取
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
        if match:
            content = match.group(1).strip()
        try:
            facts = json.loads(content)
            if isinstance(facts, list):
                return [f for f in facts if isinstance(f, str) and len(f) > 3]
        except json.JSONDecodeError:
            pass
        return []




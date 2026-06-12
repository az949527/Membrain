"""
=== 实体关系提取器 ===

用 LLM（DeepSeek）从文档文本中提取 (实体, 关系, 实体) 三元组。

流程：
    文本 → LLM 提取 JSON 数组 → 解析 → 去重 → 返回可用三元组

设计原因：
    - 用 LLM 而非 NLP 库：泛化能力更强，准确率更高
    - 低温度（0.1）：提取需要确定性，不需要创造性
    - JSON 格式输出：方便后续处理和存入 Neo4j
"""

import json
import re
from openai import AsyncOpenAI
from app.core.config import settings
from app.core.logger import logger


class EntityExtractor:
    """从文本中提取实体关系三元组"""

    @staticmethod
    async def extract_triples(text: str) -> list[dict]:
        """从文本中提取实体关系三元组

        参数:
            text: 原始文本（文档片段或整篇文档）

        返回:
            list[dict]: 三元组列表，格式:
                [{"subject": "实体1", "relation": "关系", "object": "实体2"}, ...]

        注意:
            - 如果 LLM 返回非标准 JSON，会尝试从 ```json ``` 代码块中提取
            - 提取失败时返回空列表，不阻塞调用方
        """
        # 文本过长时截断，避免超出 LLM 上下文
        # entity_extractor 是按文档粒度提取的，最大 8000 字符
        max_chars = 8000
        truncated = text[:max_chars]

        prompt = f"""从以下文本中提取实体关系三元组 (实体, 关系, 实体)。

要求：
- 实体必须是具体的人名、地名、组织名、概念、技术名、产品名等
- 关系必须简洁明确（如"任职于"、"开发了"、"属于"、"位于"）
- 每个三元组单独一条，不要合并
- 只返回 JSON 数组，不要任何额外文字和 markdown 格式

文本：
{truncated}

返回格式：
[{{"subject": "实体1", "relation": "关系", "object": "实体2"}}]"""

        try:
            client = AsyncOpenAI(
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_BASE_URL,
            )

            response = await client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,  # 低温度确保确定性输出
                timeout=30,
            )

            content = response.choices[0].message.content or ""

            # 尝试解析 JSON：先直接解析，失败则尝试从 ```json ``` 代码块提取
            triples = EntityExtractor._parse_json_response(content)

            logger.info(
                "实体提取完成: 输入 %s 字符 → 提取 %s 个三元组",
                len(truncated),
                len(triples),
            )
            return triples

        except Exception as e:
            logger.warning("实体提取失败: %s", e)
            return []

    @staticmethod
    def _parse_json_response(content: str) -> list[dict]:
        """解析 LLM 返回的 JSON，兼容可能的 markdown 代码块格式

        参数:
            content: LLM 返回的原始字符串

        返回:
            list[dict]: 解析后的三元组列表，解析失败返回空列表
        """
        # 先尝试直接解析
        try:
            result = json.loads(content)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

        # 尝试从 ```json ... ``` 代码块中提取
        json_match = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", content)
        if json_match:
            try:
                result = json.loads(json_match.group(1))
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass

        # 尝试提取数组部分（从第一个 [ 到最后一个 ]）
        array_match = re.search(r"(\[[\s\S]*\])", content)
        if array_match:
            try:
                result = json.loads(array_match.group(1))
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass

        return []

    @staticmethod
    def deduplicate(triples: list[dict]) -> list[dict]:
        """去重：基于 (subject, relation, object) 三元组完全匹配

        参数:
            triples: 原始三元组列表

        返回:
            list[dict]: 去重后的三元组列表
        """
        seen = set()
        unique = []
        for t in triples:
            key = (t.get("subject", ""), t.get("relation", ""), t.get("object", ""))
            if key not in seen:
                seen.add(key)
                unique.append(t)
        return unique

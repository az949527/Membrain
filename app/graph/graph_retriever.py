"""
=== 知识图谱检索器 (Text2Cypher) ===

将用户的自然语言问题转为 Cypher 查询，从 Neo4j 中检索相关信息。

流程：
    用户问题 → 获取图结构 → LLM 转 Cypher → 执行查询 → 格式化为上下文

设计原因：
    - Text2Cypher 比直接让 LLM 回答更准确：查询结果是确定的，LLM 只需翻译
    - 先获取 schema 再生成 Cypher：让 LLM 知道图里有啥，生成更准确的查询
    - Neo4j 不可用时返回空字符串：不阻塞聊天流程
"""

import json
from openai import AsyncOpenAI
from app.core.config import settings
from app.core.logger import logger
from app.core.prompts import TEXT2CYPHER_PROMPT


class GraphRetriever:
    """知识图谱检索器"""

    @staticmethod
    async def retrieve(neo4j, question: str) -> str:
        """检索知识图谱，返回格式化上下文

        参数:
            neo4j: Neo4jConnection 实例（可能为 None）
            question: 用户问题

        返回:
            str: 格式化后的图谱上下文，无可查内容时返回空字符串
        """
        if not neo4j:
            return ""

        try:
            # 1. 获取图结构描述（节点标签和关系类型）
            schema = await GraphRetriever._get_schema(neo4j)

            # 2. 用 LLM 将问题转为 Cypher 查询
            cypher = await GraphRetriever._question_to_cypher(question, schema)
            if not cypher:
                return ""

            # 3. 执行查询
            results = await neo4j.query(cypher)

            # 4. 格式化为文本
            if not results:
                return ""

            return GraphRetriever._format_results(results)

        except Exception as e:
            logger.warning("图谱检索失败: %s", e)
            return ""

    @staticmethod
    async def _get_schema(neo4j) -> str:
        """获取 Neo4j 图数据库的结构描述

        返回节点标签、属性、关系类型的可读文本。
        """
        try:
            # 获取节点标签和关系类型
            labels_result = await neo4j.query(
                "CALL db.labels() YIELD label RETURN label"
            )
            rels_result = await neo4j.query(
                "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType"
            )

            labels = [r["label"] for r in labels_result]
            rels = [r["relationshipType"] for r in rels_result]

            schema_parts = ["图数据库结构："]
            if labels:
                schema_parts.append(f"节点类型: {', '.join(labels)}")
            if rels:
                schema_parts.append(f"关系类型: {', '.join(rels)}")

            return "\n".join(schema_parts)
        except Exception as e:
            logger.warning("获取图 schema 失败: %s", e)
            return "图数据库结构未知"

    @staticmethod
    async def _question_to_cypher(question: str, schema: str) -> str:
        """用 LLM 将用户问题转为 Cypher 查询

        参数:
            question: 用户自然语言问题
            schema: 图数据库结构描述

        返回:
            str: Cypher 查询语句，生成失败返回空字符串
        """
        prompt = TEXT2CYPHER_PROMPT.format(schema=schema, question=question)
        try:
            client = AsyncOpenAI(
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_BASE_URL,
            )

            response = await client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                timeout=30,
            )

            cypher = response.choices[0].message.content or ""
            cypher = cypher.strip().strip("```").strip()

            # 移除可能的 cypher 代码块标记
            if cypher.startswith("cypher"):
                cypher = cypher[6:].strip()

            if cypher == "SKIP":
                return ""

            # 安全检查：只允许 SELECT 类查询（MATCH / CALL）
            if not cypher.upper().startswith(("MATCH", "CALL")):
                logger.warning("生成的 Cypher 不是查询语句，已跳过: %s", cypher[:50])
                return ""

            logger.info("Text2Cypher: %s", cypher[:100])
            return cypher

        except Exception as e:
            logger.warning("生成 Cypher 失败: %s", e)
            return ""

    @staticmethod
    def _format_results(results: list[dict]) -> str:
        """将 Neo4j 查询结果格式化为可读文本

        参数:
            results: Neo4j 查询结果列表

        返回:
            str: 格式化文本，格式为 "[知识图谱] key: value\\n"
        """
        lines = ["[知识图谱查询结果]"]
        for record in results:
            parts = []
            for key, value in record.items():
                parts.append(f"{key}: {value}")
            lines.append("  " + " | ".join(parts))

        return "\n".join(lines)

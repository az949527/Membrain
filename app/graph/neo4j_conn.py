"""
=== Neo4j 图数据库连接管理 ===

封装 neo4j 异步驱动，提供初始化、查询、关闭功能。

使用方式：
    conn = Neo4jConnection()
    await conn.initialize()
    result = await conn.query("MATCH (n) RETURN n")
    await conn.close()

设计原因：
- 用 neo4j 驱动而非 langchain_neo4j：langchain_neo4j 封装太多不需要的功能
- 异步驱动：不阻塞事件循环，和 FastAPI 异步架构一致
- 连接失败时不抛异常：没开 Docker 时服务照常运行，仅图谱功能不可用
"""

from neo4j import AsyncGraphDatabase
from app.core.config import settings
from app.core.logger import logger


class Neo4jConnection:
    """Neo4j 图数据库连接管理

    管理驱动生命周期，提供统一的查询接口。
    """

    def __init__(self):
        self.driver = None

    async def initialize(self):
        """初始化驱动并验证连接是否可用

        如果 Neo4j 未启动（如没开 Docker），捕获异常并记录警告，
        不阻止应用启动。
        """
        try:
            self.driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URL,
                auth=(
                    settings.NEO4J_USERNAME,
                    settings.NEO4J_PASSWORD,
                ),
            )
            await self.driver.verify_connectivity()
            logger.info("Neo4j 连接成功: %s", settings.NEO4J_URL)
        except Exception as e:
            logger.warning("Neo4j 连接失败（跳过）: %s", e)
            self.driver = None

    async def close(self):
        """关闭驱动，释放连接资源"""
        if self.driver:
            await self.driver.close()
            logger.info("Neo4j 连接已关闭")

    async def query(self, cypher: str, params: dict = None) -> list:
        """执行 Cypher 查询并返回结果列表

        参数:
            cypher: Cypher 查询语句（如 "MATCH (n:Entity {name: $name}) RETURN n"）
            params: 查询参数字典（如 {"name": "张三"}）

        返回:
            list[dict]: 查询结果列表，每个元素是一条记录的 dict

        注意:
            如果 driver 为 None（连接失败时），直接返回空列表
        """
        if not self.driver:
            logger.warning("Neo4j 未连接，跳过查询: %s", cypher[:50])
            return []

        async with self.driver.session(
            database=settings.NEO4J_DATABASE
        ) as session:
            result = await session.run(cypher, params or {})
            records = [record.data() for record in await result.fetch()]
            return records

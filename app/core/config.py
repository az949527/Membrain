"""
=== 通用模块（可复用到其他项目）===

说明：
- 这个文件的结构（继承 BaseSettings + Config 读 .env）是通用的，每个项目都能用
- 字段本身是项目特定的，换项目时按需增删

使用时：
1. 复制整个文件到新项目
2. 修改或删减字段即可
3. 敏感信息放 .env，不要在代码里写死

@see: https://docs.pydantic.dev/latest/api/pydantic_settings/
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # ==================== 应用基础配置 ====================
    # 【跨项目通用】只要有 Web 服务都需要
    APP_NAME: str = "MemBrain"
    DEBUG: bool = False

    # ==================== 数据库配置 ====================
    # 【跨项目通用】只需改连接串即可切换数据库
    DATABASE_URL: str = "sqlite+aiosqlite:///./membrain.db"

    # ==================== JWT 认证配置 ====================
    # 【跨项目通用】密钥必须改，其他保持默认即可
    SECRET_KEY: str = "change-this-to-a-random-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # ==================== LLM 配置（项目特定）====================
    # 【业务相关】这个项目用 DeepSeek，换别的 LLM 就改这里
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_MODEL: str = "deepseek-chat"

    # RAG / Embedding
    EMBEDDING_MODEL: str = "shibing624/text2vec-base-chinese"  # 中文 embedding 模型
    FAISS_INDEX_PATH: str = "./data/faiss_index.bin"  # FAISS 索引文件路径
    DOCUMENTS_DIR: str = "./data/documents"  # 上传文档存储目录
    CHUNK_SIZE: int = 500  # 分块大小（字符数）
    CHUNK_OVERLAP: int = 50  # 分块重叠（字符数）
    TOP_K_RETRIEVAL: int = 3  # 检索返回的最相似块数
    REDIS_URL: str = "redis://localhost:6379/0"

    # ==================== Neo4j 知识图谱配置 ====================
    # 【项目特定】Neo4j 图数据库连接参数
    NEO4J_URL: str = "bolt://localhost:7687"
    NEO4J_USERNAME: str = "neo4j"
    NEO4J_PASSWORD: str = "password123"
    NEO4J_DATABASE: str = "neo4j"

    # ==================== 搜索工具配置 ====================
    SERPAPI_API_KEY: str = ""

    # ==================== 日志配置 ====================
    # 【跨项目通用】
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

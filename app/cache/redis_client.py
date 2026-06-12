"""
Redis 连接管理

提供 init_redis / close_redis 两个函数，
在 main.py 的 lifespan 中调用。
"""
from redis.asyncio import Redis


async def init_redis(redis_url: str) -> Redis:
    """创建 Redis 连接，返回客户端实例"""
    return Redis.from_url(redis_url, decode_responses=True)


async def close_redis(redis: Redis):
    """关闭 Redis 连接"""
    if redis:
        await redis.close()

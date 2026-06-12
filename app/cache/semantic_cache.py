"""
语义缓存：相同/相似问题不重复调 LLM

查询流程：
1. 新问题 → embedder 转向量
2. Redis SCAN 遍历所有 cache:* 记录
3. 逐一比余弦相似度
4. 最高分 >= 阈值 → 命中返回
5. 否则 → 未命中返回 None

写入流程：
1. 问题向量化
2. pickle 序列化向量
3. 存入 Redis Hash + 设过期时间
"""

import base64
import pickle
import time

from numpy import dot
from numpy.linalg import norm

# 相似度阈值：高于此值视为同一问题
# 0.92 是一个经验值，可根据实际使用调整
SIMILARITY_THRESHOLD = 0.92

# 缓存默认过期时间（秒）
DEFAULT_TTL = 3600

async def get(redis, question: str, embedder) -> str | None:
    """查缓存，命中返回answer，未命中返回None"""
    # 1、问题向量化
    vec = embedder.embed([question])[0]

    # 2、SCAN遍历所有缓存记录
    cursor = 0
    best_sim = 0
    best_answer = None
    while True:
        cursor, keys = await redis.scan(cursor, match="cache:*", count=100)
        for key in keys:
            data = await redis.hgetall(key)
            if not data:
                continue
            # decode_responses=True 时 Redis 返回字符串 key，用字符串取值
            vec_raw = data.get("vec") or data.get(b"vec")
            if not vec_raw:
                continue
            cache_vec = pickle.loads(base64.b64decode(vec_raw))
            # 3、余弦相似度
            sim = float(dot(vec, cache_vec) / (norm(vec) * norm(cache_vec)))
            if sim > best_sim:
                best_sim = sim
                best_answer = data.get("answer") or data.get(b"answer")
        if cursor == 0:
            break

    # 4、高于阈值才命中
    if best_sim >= SIMILARITY_THRESHOLD:
        return best_answer
    return None


async def set(redis, question: str, answer: str, embedder,
              ttl: int = DEFAULT_TTL):
    """写入缓存"""
    vec = embedder.embed([question])[0]
    key = f"cache:{hash(question)}"
    data = {
        "vec": base64.b64encode(pickle.dumps(vec)).decode(),
        "question": question,
        "answer": answer,
        "ts": time.time(),
    }
    await redis.hset(key, mapping=data)
    await redis.expire(key, ttl)


async def clear(redis):
    """清空所有缓存"""
    cursor = 0
    while True:
        cursor, keys = await redis.scan(cursor, match="cache:*", count=100)
        if keys:
            await redis.delete(*keys)
        if cursor == 0:
            break
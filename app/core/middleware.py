"""
=== 通用模块（可复用到其他项目）===

说明：
- 请求日志中间件是纯基础设施，跟业务无关
- 直接复制到新项目即可使用

使用时：
    在 main.py 里 app.add_middleware(RequestLogMiddleware) 注册即可
"""
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.logger import logger


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        elapsed = time.time() - start
        logger.info(
            "%s %s → %s (%.2fs)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
        )
        return response

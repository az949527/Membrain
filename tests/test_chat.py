"""聊天接口测试"""

import pytest


@pytest.mark.asyncio
async def test_chat_sse_stream(client, auth_token):
    """聊天返回 SSE 流"""
    async with client.stream(
        "POST", "/api/v1/chat",
        json={"messages": [{"role": "user", "content": "你好"}]},
        headers={"Authorization": f"Bearer {auth_token}"}
    ) as resp:
        assert resp.status_code == 200
        async for line in resp.aiter_lines():
            if line.startswith("data:") and "done" in line:
                break


@pytest.mark.asyncio
async def test_chat_greeting(client, auth_token):
    """问候语正常响应"""
    async with client.stream(
        "POST", "/api/v1/chat",
        json={"messages": [{"role": "user", "content": "你好"}]},
        headers={"Authorization": f"Bearer {auth_token}"}
    ) as resp:
        assert resp.status_code == 200
        received_data = False
        async for line in resp.aiter_lines():
            if line.startswith("data:"):
                received_data = True
        assert received_data, "应该收到至少一条 data 事件"


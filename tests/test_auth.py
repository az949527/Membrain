"""认证相关接口测试"""

import pytest


@pytest.mark.asyncio
async def test_register_success(client):
    resp = await client.post("/api/v1/auth/register", json={
        "email": "newuser@example.com",
        "password": "testpass123",
        "username": "newuser"
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "newuser@example.com"


@pytest.mark.asyncio
async def test_register_duplicate(client, auth_token):
    """用已注册的邮箱重复注册"""
    resp = await client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "testpass123",
        "username": "testuser"
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_token_valid(client):
    """正确密码获取 token"""
    # 先注册
    await client.post("/api/v1/auth/register", json={
        "email": "token@example.com",
        "password": "testpass123",
        "username": "tokenuser"
    })
    # 再登录
    resp = await client.post("/api/v1/auth/token", json={
        "email": "token@example.com",
        "password": "testpass123"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_token_invalid(client):
    """错误密码返回 401"""
    await client.post("/api/v1/auth/register", json={
        "email": "badpw@example.com",
        "password": "testpass123",
        "username": "badpwuser"
    })
    resp = await client.post("/api/v1/auth/token", json={
        "email": "badpw@example.com",
        "password": "wrongpassword"
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_success(client, auth_token):
    """有效 token 可获取用户信息"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "email" in data
    assert "username" in data


@pytest.mark.asyncio
async def test_me_no_token(client):
    """不带 token 返回 401"""
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_bad_token(client):
    """错误格式 token 返回 401"""
    headers = {"Authorization": "Bearer invalidtoken123"}
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 401

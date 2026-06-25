"""
文档上传/列表/删除测试

使用 conftest.py 中的 mock_rag_state 注入的 mock embedder + vector_store，
这样真实的 DocumentService 可以执行完整的管道（除向量化外），
同时避免生命周期冲突。
"""

import os
import tempfile
from unittest.mock import patch

import pytest

from app.core.config import settings

TEST_CONTENT = (
    "MemBrain 是一个基于 LangGraph 构建的个人知识助手。\n"
    "它支持 RAG 检索、知识图谱查询和网络搜索功能。\n"
).encode()


# ======================== 上传 ========================


class TestDocumentUpload:
    @pytest.mark.asyncio
    async def test_upload_txt(self, client, auth_token):
        """上传 .txt 文件 → status=ready，返回文件信息"""
        with tempfile.TemporaryDirectory() as tmp_docs:
            with patch.object(settings, "DOCUMENTS_DIR", tmp_docs):
                resp = await client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("test.txt", TEST_CONTENT, "text/plain")},
                    headers={"Authorization": f"Bearer {auth_token}"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["filename"] == "test.txt"
                assert data["status"] == "ready"
                assert data["file_size"] == len(TEST_CONTENT)

    @pytest.mark.asyncio
    async def test_upload_invalid_type(self, client, auth_token):
        """上传不支持的文件类型 → 400"""
        with tempfile.TemporaryDirectory() as tmp_docs:
            with patch.object(settings, "DOCUMENTS_DIR", tmp_docs):
                resp = await client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("test.exe", b"fake", "application/x-msdownload")},
                    headers={"Authorization": f"Bearer {auth_token}"},
                )
                assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_upload_unauthorized(self, client):
        """未认证上传 → 401"""
        resp = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 401


# ======================== 列表 ========================


class TestDocumentList:
    @pytest.mark.asyncio
    async def test_list_documents(self, client, auth_token):
        """上传 2 个文档 → 列表返回 2 条，按创建时间倒序"""
        with tempfile.TemporaryDirectory() as tmp_docs:
            with patch.object(settings, "DOCUMENTS_DIR", tmp_docs):
                for name in ["doc1.txt", "doc2.txt"]:
                    resp = await client.post(
                        "/api/v1/documents/upload",
                        files={"file": (name, TEST_CONTENT, "text/plain")},
                        headers={"Authorization": f"Bearer {auth_token}"},
                    )
                    assert resp.status_code == 200

                resp = await client.get(
                    "/api/v1/documents/",
                    headers={"Authorization": f"Bearer {auth_token}"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert len(data) == 2
                assert data[0]["filename"] == "doc2.txt"  # 最新的在前

    @pytest.mark.asyncio
    async def test_list_empty(self, client, auth_token):
        """无文档 → 空列表"""
        resp = await client.get(
            "/api/v1/documents/",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == []


# ======================== 删除 ========================


class TestDocumentDelete:
    @pytest.mark.asyncio
    async def test_delete_document(self, client, auth_token):
        """上传 → 删除 → 列表为空"""
        with tempfile.TemporaryDirectory() as tmp_docs:
            with patch.object(settings, "DOCUMENTS_DIR", tmp_docs):
                resp = await client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("test.txt", TEST_CONTENT, "text/plain")},
                    headers={"Authorization": f"Bearer {auth_token}"},
                )
                doc_id = resp.json()["id"]

                resp = await client.delete(
                    f"/api/v1/documents/{doc_id}",
                    headers={"Authorization": f"Bearer {auth_token}"},
                )
                assert resp.status_code == 204

                resp = await client.get(
                    "/api/v1/documents/",
                    headers={"Authorization": f"Bearer {auth_token}"},
                )
                assert resp.json() == []

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, client, auth_token):
        """删除不存在的文档 → 404"""
        resp = await client.delete(
            "/api/v1/documents/999",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_unauthorized(self, client):
        """未认证删除 → 401"""
        resp = await client.delete("/api/v1/documents/1")
        assert resp.status_code == 401

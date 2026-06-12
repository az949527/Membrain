from __future__ import annotations

from typing import Optional, List

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class DocumentUploadResponse(BaseModel):
    """上传文档返回"""
    id: int
    filename: str
    file_size: int
    status: str     #processing/ ready/ failed
    created_at: datetime

class DocumentResponse(BaseModel):
    """文档详情"""
    id: int
    filename: str
    file_path: str
    file_size: int
    file_type: Optional[str] = None
    chunk_count: int
    status: str
    created_at: datetime
    updated_at: datetime

class DocumentListResponse(BaseModel):
    """文档列表（不含content，减少传输量）"""
    id: int
    filename: str
    file_size: int
    file_type: Optional[str] = None
    chunk_count: int
    status: str
    created_at: datetime

class RAGQueryRequest(BaseModel):
    """RAG问答请求"""
    conversation_id: int
    query: str = Field(..., min_length=1,description="用户问题")

class RAGQueryResponse(BaseModel):
    """RAG问答响应"""
    answer: str
    sources: List[dict] = []    # 引用的知识块 [{content, document_id, chunk_index}]

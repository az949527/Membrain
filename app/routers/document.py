from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, UploadFile, File, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.document import (
    DocumentUploadResponse,
    DocumentResponse,
    DocumentListResponse,
    RAGQueryRequest,
    RAGQueryResponse,
)
from app.services.document_service import DocumentService

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传文档"""
    return await DocumentService.upload(
        db, current_user.id, file,
        embedder=request.app.state.embedder,
        vector_store=request.app.state.vector_store,
        neo4j=getattr(request.app.state, "neo4j", None),
    )

@router.get("/", response_model=List[DocumentListResponse])
async def list_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取文档列表"""
    return await DocumentService.list_documents(db, current_user.id)

@router.delete("/{doc_id}", status_code=204)
async def delete_document(
    doc_id: int,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除文档"""
    await DocumentService.delete_document(
        db, current_user.id, doc_id,
        vector_store=request.app.state.vector_store,
    )

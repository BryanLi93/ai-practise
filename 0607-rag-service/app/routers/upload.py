"""
文件上传端点。
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, UploadFile, HTTPException, status, Depends, File
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.db import get_db
from app.schemas import UploadResponse
from app.services.ingest import ingest_text_file, EmptyContentError
from app.parsing import parse_file

router = APIRouter(prefix="/upload", tags=["upload"])

# ---------- 常量 ----------

MAX_FILE_SIZE = 30 * 1024 * 1024  # 30 MB

ALLOWED_CONTENT_TYPES = {
    "text/plain",
    "text/markdown",
    "text/x-markdown",        # 部分浏览器/客户端用这个
    "application/octet-stream",  # 兜底:有时浏览器识别不出 .md
    "application/pdf",
}

ALLOWED_EXTENSIONS = {".txt", ".md", ".markdown", ".pdf"}

# ---------- 工具 ----------
def _validate_file(file: UploadFile):
    """校验文件类型。不通过抛 HTTPException。"""
    if file.filename and "." in file.filename:
        ext = "." + file.filename.rsplit(".", 1)[-1].lower()
        if ext in ALLOWED_EXTENSIONS:
            return
    if file.content_type in ALLOWED_CONTENT_TYPES:
        return
    
    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail=f"Only .txt and .md files supported. Got filename={file.filename}, "
               f"content_type={file.content_type}",
    )

# ---------- 路由 ----------
@router.post(
    "",
    response_model=UploadResponse, # response_model 不只是文档——FastAPI 会用它过滤返回值。即使你返回的对象有额外字段（比如不小心返回了 ORM 对象），也只会输出 schema 里声明的字段。
    status_code=status.HTTP_201_CREATED,
    summary="Upload a text file for RAG ingestion",
)
async def upload_file(
    file: UploadFile = File(..., description="Text file (.txt or .md), max 10 MB"),
    db: AsyncSession = Depends(get_db)
) -> UploadResponse:
    """
    上传文件 → 切块 → embedding → 入库。

    返回 document_id,后续可用于 query。
    """
    _validate_file(file)

    # 读取文件内容
    raw_bytes = await file.read()
    byte_size = len(raw_bytes)

    if byte_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file",
        )
    if byte_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large ({byte_size} bytes), max {MAX_FILE_SIZE}",
        )        

    # 解析(根据文件类型派发到对应 parser)
    try:
        content = parse_file(
            raw_bytes,
            content_type=file.content_type or "",
            filename=file.filename or "",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception("file parsing failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse file: {type(e).__name__}",
        )

    # 入库
    try:
        result = await ingest_text_file(
            db,
            filename=file.filename or "unnamed",
            content_type=file.content_type or "text/plain",
            content=content,
            byte_size=byte_size,
        )
    # 已知业务异常 → 友好提示 + 4xx 状态码
    except EmptyContentError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    # 未知异常 → 记日志 + 5xx 状态码 + 不暴露内部细节给客户端
    except Exception as e:
        # logger.exception(...) 自动把完整 traceback 写到日志，方便后端排查。
        logger.exception("ingest failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ingest failed: {type(e).__name__}",
        )
    

    return UploadResponse(
        document_id=result.document.id,
        filename=result.document.filename,
        chunk_count=result.chunk_count,
        created_at=result.document.create_at
    )

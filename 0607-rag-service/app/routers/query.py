"""
查询端点。
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas import QueryRequest, QueryResponse
from app.services.chat import handle_chat, ConversationNotFound

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["query"])


# ---------- 路由 ----------
@router.post(
    "",
    response_model=QueryResponse,  # FastAPI 会用它过滤返回值,只输出 schema 声明的字段
    status_code=status.HTTP_201_CREATED,
    summary="Ask a question against the knowledge base",
)
async def query_endpoint(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db),
) -> QueryResponse:
    """
    薄路由:把编排交给 chat service,这里只负责把领域异常翻译成 HTTP 状态码。
    """
    try:
        return await handle_chat(
            db,
            req_conversation_id=request.conversation_id,
            req_question=request.question,
            req_top_k=request.top_k,
        )
    except ConversationNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    except Exception as e:
        logger.exception("query failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Query failed: {type(e).__name__}",
        )

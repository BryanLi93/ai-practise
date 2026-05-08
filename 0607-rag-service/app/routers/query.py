"""
查询端点。
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.db import get_db
from app.schemas import QueryRequest, QueryResponse
from app.services.retrieval import query as run_query

router = APIRouter(prefix="/query", tags=["query"])

# ---------- 路由 ----------
@router.post(
    "",
    response_model=QueryResponse, # response_model 不只是文档——FastAPI 会用它过滤返回值。即使你返回的对象有额外字段（比如不小心返回了 ORM 对象），也只会输出 schema 里声明的字段。
    status_code=status.HTTP_201_CREATED,
    summary="Ask a question against the knowledge base",
)
async def query_endpoint(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db)
) -> QueryResponse:
    """
    用户提问 → 检索 → 生成答案。
    """
    try:
        answer = await run_query(db, question=request.question, top_k=request.top_k)
    except Exception as e:
        logger.exception("query failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Query failed: {type(e).__name__}",
        )

    return QueryResponse(answer=answer)

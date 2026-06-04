"""
查询端点。
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.db import get_db
from app.schemas import QueryRequest, QueryResponse, Source
from app.services.retrieval import query as run_query
from app.services import conversation as conv_service

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
    # 1. 解析/创建会话
    if request.conversation_id is None:
        # 新会话
        conv = await conv_service.create_conversation(db, title=request.question[:50])
        conversation_id = conv.id
    else:
        if not await conv_service.conversation_exists(db, request.conversation_id):
            raise HTTPException(status_code=404, detail="Conversation not found")
        else:
            conversation_id = request.conversation_id

    # 2. 跑 RAG(Day 1 还是单轮,Day 2 才加历史)
    try:
        result = await run_query(db, question=request.question, top_k=request.top_k)
    except Exception as e:
        logger.exception("query failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Query failed: {type(e).__name__}",
        )

    # 3. 构造 sources(沿用你原有逻辑)
    sources = [
        Source(
            id=i,
            chunk_id=rc.chunk.id,
            document_id=rc.document.id,
            document_filename=rc.document.filename,
            chunk_index=rc.chunk.chunk_index,
            content=rc.chunk.content,
            similarity=round(rc.similarity, 4),
            vector_rank=rc.vector_rank,
            keyword_rank=rc.keyword_rank,
            rerank_score=rc.rerank_score
        )
        for i, rc in enumerate(result.sources, start=1)
    ]

    # 4. 持久化两条消息(同一事务)
    await conv_service.add_message(
        db,
        conversation_id=conversation_id,
        role="user",
        content=request.question,
        commit=False
    )
    await conv_service.add_message(
        db,
        conversation_id=conversation_id,
        role="assistant",
        content=result.answer,
        sources=[s.model_dump() for s in sources],
        commit=True
    )

    # 5. 返回(带 conversation_id)
    return QueryResponse(answer=result.answer, sources=sources, conversation_id=conversation_id)

"""
检索 + 生成服务。
"""
from __future__ import annotations

import logging

from google import genai
from google.genai import types
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.embedding import embed_query, get_client as get_genai_client
from app.models import Chunk
from app.config import settings

logger = logging.getLogger(__name__)

# ---------- 常量 ----------

DEFAULT_TOP_K = 5

# 检索结果不足时,直接告诉用户
NO_CONTEXT_ANSWER = "根据现有知识库,我没有找到能回答这个问题的相关内容。"

SYSTEM_PROMPT = """你是一个严格基于上下文回答问题的助手。

规则:
1. 只能使用下方"上下文"中提供的信息回答问题。
2. 如果上下文中没有足够信息回答问题,直接回答"根据现有知识库,我没有找到能回答这个问题的相关内容。不要编造,不要使用上下文以外的常识。
3. 回答简洁、准确,不要重复问题。
4. 如果上下文里只有部分信息,可以基于部分信息回答,但要说明哪部分无法回答。
"""

USER_PROMPT_TEMPLATE = """上下文:
---
{context}
---

问题: {question}

请基于上下文回答。"""

# ---------- 内部:检索 ----------
async def _retrieve_chunks(
    db: AsyncSession,
    query_vector: list[float],
    top_k: int,
) -> list[Chunk]:
    """按余弦距离查 top-k 最相似的 chunks。"""
    stmt = (
        select(Chunk)
        .order_by(Chunk.embedding.cosine_distance(query_vector))
        .limit(top_k)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())

# ---------- 内部:生成 ----------
async def _generate_answer(question: str, context: str) -> str:
    client = get_genai_client()

    user_prompt = USER_PROMPT_TEMPLATE.format(context=context, question=question)

    response = await client.aio.models.generate_content(
        model=settings.chat_model,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.1,
            max_output_tokens=1024,
        )
    )

    if not response.text:
        raise RuntimeError("LLM returned empty response")

    return response.text.strip()

# ---------- 对外 API ----------
async def query(
    db: AsyncSession,
    *,
    question: str,
    top_k: int = DEFAULT_TOP_K
) -> str:
    """
    完整的 RAG 查询流程。

    Args:
        db: 数据库 session
        question: 用户问题
        top_k: 检索返回的 chunk 数量

    Returns:
        基于检索内容生成的答案字符串
    """
    logger.info("query: %s (top_k=%d)", question, top_k)

    # 1. 把 question embed 成向量
    query_vector = await embed_query(question)

    # 2. 检索 top-k chunks
    chunks = await _retrieve_chunks(db, query_vector=query_vector, top_k=top_k)

    if not chunks:
        logger.info("no chunks found,returning fallback")
        return NO_CONTEXT_ANSWER
    
    logger.info("retrieved %d chunks", len(chunks))
    for i, c in enumerate(chunks):
        logger.debug("  [%d] doc=%d chunk=%d preview=%s",
                     i, c.document_id, c.chunk_index, c.content[:50])

    # 3. 组装 context(把多个 chunk 用分隔符拼接)
    content = "\n\n---\n\n".join(c.content for c in chunks)
    # logger.info(content)

    # 4. 调 LLM 生成答案
    answer = await _generate_answer(question, content)
    return answer
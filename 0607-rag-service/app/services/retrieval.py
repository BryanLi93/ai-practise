"""
检索 + 生成服务。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from google import genai
from google.genai import types
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.embedding import embed_query, get_client as get_genai_client
from app.models import Chunk, Document
from app.config import settings

logger = logging.getLogger(__name__)

# ---------- 常量 ----------

DEFAULT_TOP_K = 5

# 检索结果不足时,直接告诉用户
NO_CONTEXT_ANSWER = "根据现有知识库,我没有找到能回答这个问题的相关内容。"

SYSTEM_PROMPT = """你是一个严格基于上下文回答问题的助手。

你必须遵守的规则:

1. 只能使用下方"上下文"中提供的信息回答问题。每条上下文都有编号 [1]、[2]、[3] 等。
2. 在回答中引用具体信息时,必须在引用内容后立刻标注来源编号,格式为 [n] 或 [n][m]。例如:
   - 正确:"FastAPI 是一个现代 Python web 框架 [1],由 Sebastian 开发 [2]。"
   - 错误:"FastAPI 是一个现代 Python web 框架,由 Sebastian 开发。"(没标注)
3. 一句话可以引用多个来源:"RAG 包含检索和生成两个阶段 [1][3]。"
4. 如果上下文中没有足够信息回答问题,直接回答"根据现有知识库,我没有找到能回答这个问题的相关内容。"——不要标注任何编号,不要编造,不要使用上下文以外的常识。
5. 回答简洁、准确,不要重复问题本身。

请严格遵守以上规则,特别是引用标注。"""

USER_PROMPT_TEMPLATE = """上下文:
---
{context}
---

问题: {question}

请基于上下文回答，并标注引用编号 [n]。"""

# ---------- 内部数据结构 ----------
@dataclass
class RetrievedChunk:
    """检索到的 chunk + 元数据。"""
    chunk: Chunk
    document: Document
    distance: float       # cosine distance (0-2,越小越相似)

    @property
    def similarity(self) -> float:
        """转成 similarity 分数(0-1,越高越相似)。"""
        return max(0.0, 1.0 - self.distance)
    
@dataclass
class QueryResult:
    """完整查询结果。"""
    answer: str
    sources: list[RetrievedChunk]


# ---------- 内部:检索 ----------
async def _retrieve_chunks(
    db: AsyncSession,
    query_vector: list[float],
    top_k: int,
) -> list[RetrievedChunk]:
    """按余弦距离查 top-k chunks,同时取出距离分数和 document 信息。"""
    distance_expr = Chunk.embedding.cosine_distance(query_vector)

    stmt = (
        select(Chunk, distance_expr.label("distance"))
        .options(selectinload(Chunk.document))    # 同时加载关联的 document
        .order_by(distance_expr)
        .limit(top_k)
    )
    result = await db.execute(stmt)


    retrieved = []
    for chunk, distance in result.all():
        retrieved.append(RetrievedChunk(
            chunk=chunk,
            document=chunk.document,
            distance=float(distance)
        ))
    return retrieved

# ---------- 内部:Prompt 组装 ----------
def _format_context(retrieved: list[RetrievedChunk]) -> str:
    parts = []
    for i, rc in enumerate(retrieved, start=1):
        parts.append(f"[{i}] {rc.chunk.content}")
    return "\n\n".join(parts)

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
) -> QueryResult:
    """
    完整的 RAG 查询流程。

    Args:
        db: 数据库 session
        question: 用户问题
        top_k: 检索返回的 chunk 数量

    Returns:
        答案 + 引用源
    """
    logger.info("query: %s (top_k=%d)", question, top_k)

    # 1. 把 question embed 成向量
    query_vector = await embed_query(question)

    # 2. 检索 top-k chunks
    retrieved = await _retrieve_chunks(db, query_vector=query_vector, top_k=top_k)

    if not retrieved:
        return QueryResult(answer=NO_CONTEXT_ANSWER, sources=[])
    
    logger.info("retrieved %d chunks", len(retrieved))
    for i, rc in enumerate(retrieved, start=1):
        logger.debug("  [%d] sim=%.3f doc=%s chunk=%d",
                     i, rc.similarity, rc.document.filename, rc.chunk.chunk_index)


    # 3. 组装 context(把多个 chunk 用分隔符拼接)
    content = _format_context(retrieved)
    # logger.info(content)

    # 4. 调 LLM 生成答案
    answer = await _generate_answer(question, content)
    return QueryResult(answer=answer, sources=retrieved)
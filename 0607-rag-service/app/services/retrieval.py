"""
检索 + 生成服务。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
import asyncio

from google import genai
from google.genai import types
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text as sql_text
from sqlalchemy.orm import selectinload

from app.embedding import embed_query, get_client as get_genai_client
from app.models import Chunk, Document
from app.config import settings
from app.rerank import rerank as do_rerank

logger = logging.getLogger(__name__)

# ---------- 常量 ----------

DEFAULT_TOP_K = 5

# 新增:
CANDIDATES_MULTIPLIER = 4   # 每路检索召回 top_k * 4 个候选,留出 RRF 融合空间
RRF_K = 60                  # RRF 平滑常数,标准取值

# 新增:
RERANK_CANDIDATES = 20      # 送给 reranker 的候选数(从 RRF 融合后取这么多)
ENABLE_RERANK = False        # 开关,方便对比测试

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
    # distance: float       # cosine distance (0-2,越小越相似)

    # @property
    # def similarity(self) -> float:
    #     """转成 similarity 分数(0-1,越高越相似)。"""
    #     return max(0.0, 1.0 - self.distance)

    score: float                # RRF 融合分数
    vector_rank: int | None     # 在向量路径里的名次(1-based),没召回到则 None
    keyword_rank: int | None    # 在关键词路径里的名次,没召回到则 None
    rerank_score: float | None = None

    @property
    def similarity(self) -> float:
        """UI 友好的相关度分数(0-1,从 RRF score 派生)。"""
        # RRF 单路第一名 ≈ 0.0164,两路都命中第一名 ≈ 0.0328
        # 乘以 30 放大到 UI 友好的 0-1 区间
        return min(1.0, self.score * 30)
    
@dataclass
class QueryResult:
    """完整查询结果。"""
    answer: str
    sources: list[RetrievedChunk]


# ---------- 内部:检索 ----------
# async def _retrieve_chunks(
#     db: AsyncSession,
#     query_vector: list[float],
#     top_k: int,
# ) -> list[RetrievedChunk]:
#     """按余弦距离查 top-k chunks,同时取出距离分数和 document 信息。"""
#     distance_expr = Chunk.embedding.cosine_distance(query_vector)

#     stmt = (
#         select(Chunk, distance_expr.label("distance"))
#         .options(selectinload(Chunk.document))    # 同时加载关联的 document
#         .order_by(distance_expr)
#         .limit(top_k)
#     )
#     result = await db.execute(stmt)


#     retrieved = []
#     for chunk, distance in result.all():
#         retrieved.append(RetrievedChunk(
#             chunk=chunk,
#             document=chunk.document,
#             distance=float(distance)
#         ))
#     return retrieved

async def _retrieve_by_vector(
    db: AsyncSession,
    query_vector: list[float],
    limit: int
) -> dict[int, int]:
    """向量检索：返回 {chunk_id: rank},rank 从 1 开始。"""
    stmt = (
        select(Chunk.id)
        .order_by(Chunk.embedding.cosine_distance(query_vector))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return {
        chunk_id: rank
        for rank, (chunk_id,) in enumerate(result.all(), start=1)
    }


async def _retrieve_by_keyword(
    db: AsyncSession,
    question: str,
    limit: int
) -> dict[int, int]:
    """关键词检索：全文搜索,返回 {chunk_id: rank}。"""
    sql = sql_text("""
        WITH parsed AS (
            SELECT NULLIF(
                array_to_string(
                    tsvector_to_array(to_tsvector('chinese_zh', :q)),
                    ' | '
                ),
                ''
            ) AS or_query
        )
        SELECT chunks.id
        FROM chunks, parsed
        WHERE parsed.or_query IS NOT NULL
          AND chunks.content_tsv @@ to_tsquery('chinese_zh', parsed.or_query)
        ORDER BY ts_rank_cd(
            chunks.content_tsv,
            to_tsquery('chinese_zh', parsed.or_query)
        ) DESC
        LIMIT :k
    """)
    result = await db.execute(sql, { "q": question, "k": limit })
    return {
        row[0]: rank
        for rank, row in enumerate(result.all(), start=1)
    }

async def _rrf_fuse(
    vector_rankings: dict[int, int],
    keyword_rankings: dict[int, int],
    top_k: int
) -> list[tuple[int, float, int | None, int | None]]:
    """
    RRF 融合：RRF 算法融合两路排名。
    返回 [(chunk_id, rrf_score, vector_rank, keyword_rank), ...],按分数降序。
    """
    all_ids = set(vector_rankings) | set(keyword_rankings)
    scored = []
    for chunk_id in all_ids:
        v_rank = vector_rankings.get(chunk_id)
        k_rank = keyword_rankings.get(chunk_id)
        score = 0.0
        if v_rank is not None:
            score += 1.0 / (RRF_K + v_rank)
        if k_rank is not None:
            score += 1.0 / (RRF_K + k_rank)
        scored.append((chunk_id, score, v_rank, k_rank))
    scored.sort(key=lambda x: -x[1])
    return scored[:top_k]

async def _load_chunks(
    db: AsyncSession,
    fused: list[tuple[int, float, int | None, int | None]]
) -> list[RetrievedChunk]:
    """
    按融合顺序批量加载完整数据
    根据 RRF 融合结果加载完整 Chunk(带 document),保持 RRF 顺序。
    """

    if not fused:
        return []
    chunk_ids = [f[0] for f in fused]
    stmt = (
        select(Chunk)
        .options(selectinload(Chunk.document))
        .where(Chunk.id.in_(chunk_ids))
    )
    result = await db.execute(stmt)
    chunks_by_id = {
        c.id: c
        for c in result.scalars().all()
    }

    retrieved = []
    for chunk_id, score, v_rank, k_rank, in fused:
        chunk = chunks_by_id.get(chunk_id)
        if chunk is None:
            continue
        retrieved.append(
            RetrievedChunk(
                chunk=chunk,
                document=chunk.document,
                score=score,
                vector_rank=v_rank,
                keyword_rank=k_rank
            )
        )
    return retrieved

async def _hybrid_retrieve(
    db: AsyncSession,
    question: str,
    query_vector: list[float],
    candidates: int, # 改:不是 top_k,是要召回多少候选
) -> list[RetrievedChunk]:
    """向量 + 关键词并行检索,RRF 融合,返回 top_k 结果。"""
    per_path = candidates * CANDIDATES_MULTIPLIER

    vector_rankings = await _retrieve_by_vector(db, query_vector, per_path)
    keyword_rankings = await _retrieve_by_keyword(db, question, per_path)

    logger.info(
        "hybrid candidates: vector=%d, keyword=%d, overlap=%d",
        len(vector_rankings),
        len(keyword_rankings),
        len(set(vector_rankings) & set(keyword_rankings)),
    )

    fused = await _rrf_fuse(vector_rankings, keyword_rankings, candidates)

    return await _load_chunks(db, fused)

async def _rerank_chunks(
    question: str,
    candidates: list[RetrievedChunk],
    top_k: int
) -> list[RetrievedChunk]:
    """对 candidates 做 cross-encoder rerank,返回 top_k。"""
    if not candidates:
        return []
    
    # 在线程池里跑同步推理,不阻塞事件循环
    docs = [rc.chunk.content for rc in candidates]
    scores = await asyncio.to_thread(do_rerank, question, docs)

    # 用 rerank 分数排序
    for rc, score in zip(candidates, scores):
        rc.rerank_score = score

    reranked = sorted(candidates, key = lambda rc: rc.rerank_score or 0.0, reverse=True)
    return reranked[:top_k]

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
    # retrieved = await _retrieve_chunks(db, query_vector=query_vector, top_k=top_k)
    # 召回(混合检索)
    candidates = await _hybrid_retrieve(
        db, question=question, query_vector=query_vector,
        candidates=RERANK_CANDIDATES
    )

    if not candidates:
        return QueryResult(answer=NO_CONTEXT_ANSWER, sources=[])
    
    # Rerank
    if ENABLE_RERANK:
        retrieved = await _rerank_chunks(question, candidates, top_k)
    else:
        retrieved = candidates[:top_k]
    
    for i, rc in enumerate(retrieved, start=1):
        logger.debug(
            "  [%d] rrf=%.4f rerank=%s v=%s k=%s doc=%s chunk=%d",
            i, rc.score,
            f"{rc.rerank_score:.4f}" if rc.rerank_score else "N/A",
            rc.vector_rank, rc.keyword_rank,
            rc.document.filename, rc.chunk.chunk_index,
        )


    # 3. 组装 context(把多个 chunk 用分隔符拼接)
    content = _format_context(retrieved)
    # logger.info(content)

    # 4. 调 LLM 生成答案
    answer = await _generate_answer(question, content)
    return QueryResult(answer=answer, sources=retrieved)
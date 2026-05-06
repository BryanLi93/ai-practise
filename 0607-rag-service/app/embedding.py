from google import genai
from google.genai import types, errors as genai_errors
from app.config import settings
from typing import Literal
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)
import asyncio
import logging
logger = logging.getLogger(__name__)

# ---------- 常量 ----------

# Free tier 保守批量大小：单次请求最多 100 条文本
# 主要受 TPM 和单请求 token 数约束，100 条 × 平均 200 tokens = 20K，远低于 TPM 上限
BATCH_SIZE = 100

# Free tier 主动节流：~5 RPM 意味着 12 秒/请求,留点余量给 13 秒
# Tier 1 升级后可以改成 0.5
THROTTLE_SECONDS = 13.0

# 任务类型字面量,避免拼错
TaskType = Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]

# ---------- 客户端单例 ----------

_client: genai.Client | None = None

def get_client() -> genai.Client:
    """懒加载 Gemini 客户端单例。"""
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.google_api_key)
    return _client

# ---------- 内部:单次 API 调用(带重试) ----------

async def _embed_batch_once(texts: list[str], task_type: TaskType) -> list[list[float]]:
    client = get_client()
    
    result = await client.aio.models.embed_content(
        model="gemini-embedding-001",
        contents= texts,
        config=types.EmbedContentConfig(
            output_dimensionality=1536,
            task_type=task_type,
        ),
    )
    embeddings = []
    if result.embeddings:
        embeddings = [eb.values for eb in result.embeddings if eb.values]
    return embeddings

async def _embed_batch_with_retry(
    texts: list[str],
    task_type: TaskType,
) -> list[list[float]]:
    """带 tenacity 重试的批量 embedding。"""
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(6),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type(genai_errors.APIError),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    ):
        with attempt:
            return await _embed_batch_once(texts, task_type)
    # tenacity 保证 reraise=True 时这里不会被执行
    raise RuntimeError("unreachable")

# ---------- 对外接口 ----------

async def embed_documents(texts: list[str]) -> list[list[float]]:
    """
    文档入库时调用。会自动:
    - 设置 task_type=RETRIEVAL_DOCUMENT
    - 按 BATCH_SIZE 切批
    - 批之间主动节流(避免撞 RPM 上限)
    - 失败重试

    返回与输入顺序一一对应的 embedding 列表。
    """
    if not texts:
        return []

    all_embeddings: list[list[float]] = []
    total_batches = (len(texts) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(texts), BATCH_SIZE):
        batch_idx = i // BATCH_SIZE + 1
        batch = texts[i : i + BATCH_SIZE]
        logger.info(
            "embedding batch %d/%d (size=%d)", batch_idx, total_batches, len(batch)
        )

        embeddings = await _embed_batch_with_retry(batch, "RETRIEVAL_DOCUMENT")
        all_embeddings.extend(embeddings)

        # 主动节流(最后一批不用等)
        if batch_idx < total_batches:
            await asyncio.sleep(THROTTLE_SECONDS)

    return all_embeddings


async def embed_query(text: str) -> list[float]:
    """
    用户查询时调用。task_type=RETRIEVAL_QUERY,单条调用。
    """
    embeddings = await _embed_batch_with_retry([text], "RETRIEVAL_QUERY")
    return embeddings[0]


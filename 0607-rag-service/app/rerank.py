"""
Rerank 层:用 BGE-reranker-v2-m3 对召回候选做精排。
"""
from __future__ import annotations

import logging
from typing import Sequence

from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)

# ---------- 模型加载 ----------
_RERANKER_MODEL_ID = "BAAI/bge-reranker-v2-m3"
_reranker: CrossEncoder | None = None

def get_reranker() -> CrossEncoder:
    """懒加载 reranker 模型(进程内单例)。"""
    global _reranker
    if _reranker is None:
        logger.info("loading reranker model: %s", _RERANKER_MODEL_ID)
        _reranker = CrossEncoder(
            _RERANKER_MODEL_ID,
            max_length=512,        # query+chunk 拼接后的 token 上限
            device=_pick_device(),
        )
        logger.info("reranker loaded on %s", _reranker.model.device)
    return _reranker

def _pick_device() -> str:
    """自动选择最佳设备:MPS(M 系列 Mac) > CUDA > CPU。"""
    import torch
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


# ---------- 对外 API ----------
def rerank(
    query: str,
    documents: Sequence[str]
) -> list[float]:
    """
    对一组候选文档按相关性打分。

    Args:
        query: 用户问题
        documents: 候选 chunks 的文本列表

    Returns:
        和 documents 等长的相关性分数列表。
        分数越高越相关。BGE-reranker 的分数是 logit,不归一化。
    """
    if not documents:
        return []

    reranker = get_reranker()
    pairs = [(query, doc) for doc in documents]
    scores = reranker.predict(pairs, show_progress_bar=False)
    return [float(s) for s in scores]

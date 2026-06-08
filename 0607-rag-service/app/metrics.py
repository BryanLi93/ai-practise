"""
Prometheus 指标定义(Day 6 基础监控)。

集中在这里定义指标对象,业务代码 import 后调用 .inc() / .observe()。
/metrics 端点由 main.py 用 prometheus_client.make_asgi_app() 挂载,
Prometheus 走拉取(pull)模型定时来抓这个端点。

三种类型对照:
  - Counter   只增不减的累加器(QPS 由 rate(counter) 查询时算出,不直接存)
  - Histogram 分桶统计,用来估算 p50/p95/p99 这类分位数
  - Gauge     可上可下的瞬时值(本项目暂未用到)
"""
from __future__ import annotations

from prometheus_client import Counter, Histogram

# ---------- 请求级(在中间件记录)----------
REQUEST_COUNT = Counter(
    "rag_http_requests_total",
    "HTTP 请求总数",
    labelnames=("method", "path", "status"),
)

REQUEST_LATENCY = Histogram(
    "rag_http_request_duration_seconds",
    "HTTP 请求耗时(秒)",
    labelnames=("method", "path"),
    # 默认桶偏 web 短请求;RAG 带 LLM 生成会到几秒,补几个大桶
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
)

# ---------- 业务级(在 service 记录)----------
LLM_TOKENS = Counter(
    "rag_llm_tokens_total",
    "LLM token 消耗累计",
    labelnames=("model", "type"),   # type = prompt / completion
)

RETRIEVAL_CANDIDATES = Histogram(
    "rag_retrieval_candidates",
    "每次检索 RRF 融合后的候选 chunk 数",
    buckets=(0, 1, 2, 5, 10, 20, 50),
)

RERANK_SCORE = Histogram(
    "rag_rerank_score",
    "rerank cross-encoder 打分分布",
    buckets=(-10, -5, -2, 0, 2, 5, 10),  # bge-reranker logits 大致范围
)

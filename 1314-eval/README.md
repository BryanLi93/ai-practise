# 1314-eval — RAG 评测体系(Week 13-14)

给 `0607-rag-service`(手写 RAG)做质量评测。黑盒:脚本调跑起来的 RAG 服务 `/query`,拿回答 + 检索片段,用 Ragas 打分。

## 交付物(对应学习计划 📅 2026-06-28)

1. **Golden Dataset**:20-50 条「问题 → 标准答案(reference)」对,grounded 在 4 篇真实文档
2. **自动化评测脚本**:检索层 `Context Recall` / `Context Precision` + 生成层 `Faithfulness` / `Response Relevancy`(框架 Ragas)
3. **token / latency / cost 监控面板**
4. **Prompt 版本管理**(版本化 JSON,评测分数挂到 prompt 版本)

## ⚠️ 版本基线与陷阱速查(2026-06-24 实测)

**基线**:`ragas 0.4.3`(最新)+ `langchain 0.3.x 线`(**手动降级**)+ `openai 2.43.0`。

| 坑 | 现象 | 解法 |
|---|---|---|
| **ragas 裸依赖 langchain** | `Requires-Dist: langchain`(无版本上限)→ pip 抓 1.x → ragas 顶层 `import langchain_community.chat_models.vertexai` 报 `ModuleNotFoundError`(1.x 删了该路径) | 钉回 0.3.x:`pip install "langchain<1.0" "langchain-core<1.0" "langchain-community<1.0" "langchain-openai<1.0"` |
| **collections 路径不配 evaluate()** | 0.4.3 弃用 `ragas.metrics.X`,推 `ragas.metrics.collections.X`;但后者**不是 `Metric` 子类**(基类 `BaseMetric/SimpleBaseMetric`),塞不进 `evaluate()` | 仍用经典 `from ragas.metrics import ...` + `evaluate()`,吞 DeprecationWarning |
| langgraph/langchain-classic 冲突告警 | 降级后 pip 报这俩需 core 1.x | 无害:评测不 import 它们(1.x 误带进来的传递依赖) |

## 规范 import(经 0.4.3 实测可用)

```python
from ragas import SingleTurnSample, EvaluationDataset, evaluate
from ragas.llms import LangchainLLMWrapper          # 包 ChatOpenAI(接硅基流动)
from ragas.embeddings import LangchainEmbeddingsWrapper  # 包 OpenAIEmbeddings(Response Relevancy 要)
from ragas.metrics import (
    Faithfulness, LLMContextRecall,
    LLMContextPrecisionWithReference, ResponseRelevancy,
)
```

## 4 指标 × 需要的字段(决定评测集要造什么)

| 指标 | 层 | 测什么 | 需要字段 |
|---|---|---|---|
| `Faithfulness` | 生成 | 答案有没有编造(忠于 context) | `response` + `retrieved_contexts` |
| `ResponseRelevancy` | 生成 | 答案切不切题(不管对错) | `user_input` + `response` + **embeddings** |
| `LLMContextRecall` | 检索 | 该检索的有没有漏 | `user_input` + `retrieved_contexts` + **`reference`** |
| `LLMContextPrecisionWithReference` | 检索 | 相关 chunk 有没有排前面 | `user_input` + `retrieved_contexts` + **`reference`** |

→ 4 个里 2 个需要 `reference`(参考答案),1 个需要 embeddings → 所以必须先造带答案的 golden 集 + 接通 embeddings。

## 环境 / 命令

```bash
# venv: pyenv 3.12.13
.venv/bin/python xxx.py          # 非交互一律用 .venv 解释器
.venv/bin/pip freeze > requirements.txt

# 前置:RAG 服务要先起(黑盒评测靠它)
# cd ../0607-rag-service && docker compose up -d && fastapi dev app/main.py
```

## 目录

```
1314-eval/
├── data/        # golden.json(问题+reference) / eval_dataset.json(采集到的 response+contexts)
├── scripts/     # 评测脚本(自写练习)
├── prompts/     # prompt 版本化 JSON(交付物 4)
├── reports/     # 评测报告 + 面板
└── requirements.txt
```

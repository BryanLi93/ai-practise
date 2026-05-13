# RAG Service

最小可用的 RAG 问答服务。

## 技术栈

- FastAPI + SQLAlchemy 2.0 (async)
- PostgreSQL + pgvector (halfvec 1536 维)
- Gemini Embedding 001 + Gemini 2.5 Flash

## 快速开始

启动数据库:
docker compose up -d
python -m scripts.init_db

启动服务:
fastapi dev app/main.py

打开 http://127.0.0.1:8000/docs 测试。

## 已知限制 (Day 1-2 范围)

- 仅支持 .txt / .md (PDF 见 Day 6-7)
- 仅向量检索 (混合检索见 Day 4)
- 无引用溯源 (见 Day 3)
- 无 rerank (见 Day 5)

## 问题

用户问一个问题，端到端发生了什么？请按时间顺序写出每一步。
为什么 chunks 表的 embedding 列要用 halfvec(1536) 而不是 vector(3072)？
为什么 embed_documents 和 embed_query 要用不同的 task_type？
db.flush() 和 db.commit() 的差别是什么？为什么 ingest 服务里要 flush 而不直接 commit？
RAG 的"幻觉"是怎么产生的？我们的 prompt 是怎么约束的？

为什么不只用向量？盲区
为什么不只用关键词？语义
为什么要 RRF？两路量纲不同
为什么还要 Rerank？召回阶段精度有上限
为什么不只用 Rerank？算不动那么多候选

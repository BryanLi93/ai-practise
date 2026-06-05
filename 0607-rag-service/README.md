# RAG Service

一个生产级 RAG 问答服务,使用 FastAPI + PostgreSQL + OpenAI 兼容中转站。

## 架构特点

- **混合检索**: pgvector 余弦距离 + tsvector + zhparser 中文分词,RRF 融合
- **三段式 pipeline**: 召回(混合) → 精排(BGE-reranker-v2-m3) → 生成(gpt-5.4)
- **引用溯源**: 答案带 [n] 标注,sources 数组返回完整 chunk 元数据
- **中文友好**: zhparser 中文分词,embedding 维度 1536(text-embedding-3-small 原生)

## 技术栈

- FastAPI + SQLAlchemy 2.0 (async)
- PostgreSQL 16 + pgvector 0.7 (halfvec) + zhparser
- OpenAI text-embedding-3-small (1536d) + gpt-5.4(均经 OpenAI 兼容中转站)
- BGE-reranker-v2-m3 (sentence-transformers)

## 快速开始

依赖:

- Docker / Docker Compose
- Python 3.11+

### 1. 启动数据库

```bash
docker compose up -d --build
```

第一次构建会编译 zhparser,需要 3-5 分钟。

### 2. 安装 Python 依赖

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env,填入 OPENAI_API_KEY 和 OPENAI_BASE_URL(中转站,通常以 /v1 结尾)
```

### 4. 初始化数据库 schema

```bash
python -m scripts.init_db
```

### 5. 启动服务

```bash
fastapi dev app/main.py
```

打开 http://127.0.0.1:8000/docs 试用。

## API

- `POST /upload`: 上传 txt / md / pdf
- `POST /query`: 问问题,返回答案 + 引用源

## 已知限制

- PDF 解析对扫描件(无文本层)无效,需要 OCR
- 中转站限流取决于服务商,大文档入库受其约束;chat 长生成偶有断连
- 知识库小于 100 chunks 时混合检索的优势不明显
- Rerank 模型首次加载需要 ~500MB 磁盘

## 后续路线

- 评测体系(Ragas,Week 13-14)
- LangGraph Agent 化(Week 9-10)
- 前端产品化(Vercel AI SDK,Week 11-12)

## For 面试

用户问一个问题，端到端发生了什么？请按时间顺序写出每一步。
为什么 chunks 表的 embedding 列要用 halfvec(1536) 而不是 vector(3072)？
为什么从 Gemini 迁到 OpenAI 兼容中转站？换 embedding 模型为什么必须清库重新入库？
db.flush() 和 db.commit() 的差别是什么？为什么 ingest 服务里要 flush 而不直接 commit？
RAG 的"幻觉"是怎么产生的？我们的 prompt 是怎么约束的？

为什么不只用向量？盲区
为什么不只用关键词？语义
为什么要 RRF？两路量纲不同
为什么还要 Rerank？召回阶段精度有上限
为什么不只用 Rerank？算不动那么多候选

做过一个完整的 RAG service。技术栈是 FastAPI + PostgreSQL/pgvector,LLM 走 OpenAI 兼容中转站(chat gpt-5.4 + embedding text-embedding-3-small)。
检索是三段式:召回用 pgvector 余弦距离 + zhparser 中文分词的 tsvector 混合检索,RRF 融合(因为两路分数量纲不同);精排用 BGE-reranker-v2-m3 cross-encoder 对 top 20 重排;生成用 gpt-5.4,prompt 强约束基于 context 回答并要求 [n] 引用标注。
几个工程细节:embedding 维度选 1536(text-embedding-3-small 原生,正好在 pgvector HNSW 2000 维上限内);PDF 解析用 PyMuPDF 加启发式去重复页眉页脚;限流用 tenacity 退避 + 主动节流处理。还做过一次 provider 迁移(Gemini 原生 → OpenAI 中转站),踩过"换 embedding 模型必须清库重灌"的坑。

# RAG Service

一个生产级 RAG 问答服务,使用 FastAPI + PostgreSQL + Gemini。

## 架构特点

- **混合检索**: pgvector 余弦距离 + tsvector + zhparser 中文分词,RRF 融合
- **三段式 pipeline**: 召回(混合) → 精排(BGE-reranker-v2-m3) → 生成(Gemini)
- **引用溯源**: 答案带 [n] 标注,sources 数组返回完整 chunk 元数据
- **中文友好**: zhparser 中文分词,Matryoshka 维度截断(3072→1536)

## 技术栈

- FastAPI + SQLAlchemy 2.0 (async)
- PostgreSQL 16 + pgvector 0.7 (halfvec) + zhparser
- Gemini Embedding 001 (1536d) + Gemini 2.5 Flash
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
# 编辑 .env,填入 GOOGLE_API_KEY
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
- Free tier Gemini 限流 ~5 RPM,大文档入库较慢
- 知识库小于 100 chunks 时混合检索的优势不明显
- Rerank 模型首次加载需要 ~500MB 磁盘

## 后续路线

- 评测体系(Ragas,Week 13-14)
- LangGraph Agent 化(Week 9-10)
- 前端产品化(Vercel AI SDK,Week 11-12)

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

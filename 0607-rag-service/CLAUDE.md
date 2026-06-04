# RAG Service — 项目上下文（交接自 PROJECT_CONTEXT.md）

> 本文件由长期对话的交接文档迁移而来,Claude Code 启动时自动读取为项目上下文。
> **状态已于 2026-06-04 核对**:Week 7 Day 1 刚完成,准备进 Day 2。
> 注意:git 仓库根在**上一级** `~/Documents/my-code/ai-practise`,本项目是其子目录;`.gitignore` 在上级。

---

## 0. 一句话定位

这是一个**从零手写的生产级 RAG 问答服务**,作为前端工程师转型 AI 应用工程师的核心练习项目。
重点不是"用框架快速搭一个能跑的 RAG",而是**手动实现每一层、理解每个技术决策的 trade-off**,以便求职面试时能讲清原理。

项目路径:`/Users/bryan/Documents/my-code/ai-practise/0607-rag-service`

---

## 1. 学习者背景与协作偏好(重要,影响回答方式)

**背景**
- 约 10 年前端经验(React / Vue / TypeScript / Next.js),有丰富生产部署经验
- 无 Python 基础起步,AI/ML 是全新领域,正在 6 个月全职转型
- 目标:中国大陆 AI 应用工程师岗位;前端背景是竞争优势(能做产品级 AI 应用界面)

**回答偏好(请严格遵守)**
- **语言**:默认中文。仅库名/协议名/无公认中文译法的术语保留英文(React、FastAPI、embedding、prompt、RRF 等);其余用自然中文,不强行中英混用。
- **类比**:解释新概念优先用前端/JS/TS 世界的类比。**但不要用 zod 举例**——学习者没用过 zod,换其他熟悉的前端概念。
- **代码改造**:已有文件用**增量 diff**(只列要改的部分),不要整文件重写。学习者写过的代码应被尊重和改进,不是推翻。新文件才给全量。
- **风格**:简洁,不铺垫,不用 emoji。判断和建议各配一句理由,不展开成穷举式分析。
- **讲解顺序**:先把概念剥离 jargon 讲直觉,再上技术细节。学习者会直接说"看不懂"或"还是没理解",此时换更浅的类比重讲,不要堆术语。
- **纠错**:理解有偏差直接指出并纠正,不委婉。
- **决策**:涉及选型给明确推荐 + 理由,不回避判断。信息不足直接问,不要猜。
- **深度**:有经验工程师视角,跳过基础语法,直接讲核心。涉及选型说 trade-off 和生产考量。
- **学习节奏**:按 Day 拆解,小步快跑,每步可独立验证。学习者独立提交代码后再请求 review。code review 用 summary 格式,只讲弱点和改进点,不逐行走读。
- **方法论**:框架抽象前先手写实现(例如先手写 chaining 再用 LangGraph),建立对比理解。

---

## 2. 技术栈(已确定)

| 层 | 选型 | 版本/备注 |
|---|---|---|
| 语言 | Python | 3.12.13(pyenv 管理) |
| Web 框架 | FastAPI | `fastapi[standard]` |
| ORM | SQLAlchemy 2.0 | async 风格,需要 `greenlet` |
| 校验/序列化 | Pydantic v2 + pydantic-settings | |
| DB 驱动 | psycopg v3 | `psycopg[binary]`,原生 async |
| 数据库 | PostgreSQL 16 | Docker,端口 **5433**(避开 ai_registry 项目的 5432) |
| 向量扩展 | pgvector | `halfvec(1536)` + HNSW 索引 |
| 中文分词 | zhparser(基于 SCWS) | 自编译进 pgvector 镜像 |
| Embedding | Gemini `gemini-embedding-001` | 1536 维(MRL 截断),Free tier |
| Chat | Gemini `gemini-2.5-flash` | Free tier |
| LLM SDK | `google-genai`(原生) | embedding 必须用原生,不能用 OpenAI 兼容层 |
| Rerank | `BAAI/bge-reranker-v2-m3` | 经 `sentence-transformers` 加载,本地推理 |
| 限流重试 | `tenacity` | 指数退避 |
| 分块 | `langchain-text-splitters` | RecursiveCharacterTextSplitter |
| token 估算 | `tiktoken` | cl100k_base(对 Gemini 是近似值) |
| PDF 解析 | `pymupdf`(fitz) | |
| 容器 | Docker Compose + OrbStack | |

**环境备忘**
- pip 用清华镜像:`pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple`
- HuggingFace 模型下载用国内镜像:`.env` 里设 `HF_ENDPOINT=https://hf-mirror.com`
- 两个 Postgres 实例:`ai_registry` 项目在 5432,本 RAG 项目在 5433
- 没有 OpenAI key,chat 走 Gemini;Free tier embedding 限流约 **5 RPM**

---

## 3. 已确定的技术决策(标题索引)

> 完整理由在 `docs/DECISIONS.md`(项目核心知识点 + 面试考点)。这里只列标题,用到某条按编号去查。

- **向量与存储**:1 Matryoshka 截断 3072→1536 / 2 halfvec 而非 vector / 3 维度是数据库的契约
- **Embedding 调用**:4 必须用 google-genai 原生 SDK(task_type)/ 5 Asymmetric embedding / 6 Free tier 限流(批量+节流+退避)/ 7 阻塞调用 await、ML 推理用 asyncio.to_thread
- **检索(三段式)**:8 pgvector 而非 ChromaDB / 9 tsvector+GIN 而非 rank_bm25 / 10 中文分词 zhparser / 11 content_tsv 用 Generated Column / 12 OR 风格+ts_rank_cd / 13 RRF 而非加权求和 / 14 召回候选=top_k×4 / 15 三段式架构 / 16 Rerank 用 BGE 本地而非 Cohere / 17 Bi-encoder vs Cross-encoder / 18 三个常量的漏斗
- **生成**:19 system_instruction 参数 / 20 temperature=0.1 / 21 强 prompt+few-shot / 22 chunks 用 `---` 分隔
- **引用溯源**:23 `[n]`+sources 数组 / 24 难点是引用正确性(faithfulness)
- **多轮对话**:25 服务端持有历史 / 26 Conversation UUID、Message int / 27 按 id 排序不按 created_at / 28 sources_json 用 JSONB / 29 存取闭环 / 30 Query Rewriting(Day 2)/ 31 历史滑动窗口
- **通用 Python/工程**:32 pydantic-settings 配置 / 33 flush vs commit / 34 selectinload 避免 N+1 / 35 外键显式 index=True / 36 Text vs String(n) / 37 service/router 分层 / 38 全局异常处理器

---

## 4. 项目结构

> 已按 2026-06-04 实际文件核对。与旧交接文档的差异见本节末「校准说明」。

```
0607-rag-service/                # 注意:git 根在上一级 ai-practise
├── .env / .env.example          # GOOGLE_API_KEY, DATABASE_URL, EMBEDDING_DIM, HF_ENDPOINT 等
├── CLAUDE.md                    # 本文件
├── README.md
├── docker-compose.yml           # postgres 服务(build 自定义镜像)
├── docker/postgres/
│   ├── Dockerfile               # pgvector:pg16 基础上编译 SCWS + zhparser
│   └── init-extensions.sql      # CREATE EXTENSION vector/zhparser + chinese_zh 配置
├── requirements.txt
├── app/
│   ├── main.py                  # FastAPI 入口,lifespan,CORS,全局异常,注册路由
│   ├── config.py                # pydantic-settings Settings 单例
│   ├── db.py                    # async engine + AsyncSessionLocal + get_db 依赖
│   ├── models.py                # Document, Chunk, Conversation, Message(4 张表都已建)
│   ├── schemas.py               # 所有 Pydantic 请求/响应模型
│   ├── embedding.py             # Gemini embedding 封装(批量+节流+重试+task_type)
│   ├── chunking.py              # RecursiveCharacterTextSplitter + token 估算
│   ├── parsing.py               # 文件解析层(PDF / txt / md → str)
│   ├── rerank.py                # BGE-reranker 加载与打分(CrossEncoder)
│   ├── routers/
│   │   ├── upload.py            # POST /upload
│   │   ├── query.py            # POST /query(已接入 conversation)
│   │   └── conversation.py      # /conversations CRUD
│   └── services/
│       ├── ingest.py            # 切块 → embedding → 事务写入
│       ├── retrieval.py         # 混合检索 + RRF + rerank + 生成
│       └── conversation.py      # 会话 CRUD + add_message
├── docs/                        # 学习者自建的复习材料
│   ├── ARCHITECTURE.md          # 分层架构图 + 时序图(Mermaid)
│   └── INTERVIEW.md             # 面试问答标准答案稿(⚠️ 标注"当前代码状态"诚实提醒)
└── scripts/
    ├── init_db.py               # create_all 建表
    ├── test_embedding.py / test_chunking.py / test_ingest.py / test_retrieval.py  # 手动验证脚本
    └── test_data/
        ├── documents/           # 4 个 md(FastAPI / RAG / pgvector / Java 并发)
        └── retrieval_questions.json   # 10 个 golden questions(5 主题域 + 1 知识库外)
```

**校准说明(相对旧交接文档)**
- 旧文档列的 `scripts/seed_test_data.py` 和 `scripts/test_e2e.py` **目前不存在**,需要时再建。
- 旧文档提到的顶层 `tests/`(pytest e2e)**尚未创建**,当前验证靠 `scripts/test_*.py` 手动脚本。
- `docs/ARCHITECTURE.md`、`docs/INTERVIEW.md` 是新增的学习材料,旧文档未收录。

### 数据模型概要
- `documents`(id, filename, content_type, byte_size, created_at)→ 1:N → `chunks`
- `chunks`(id, document_id FK CASCADE, chunk_index, content, token_count, embedding HALFVEC(1536), content_tsv GENERATED)
- `conversations`(id UUID, title, created_at)→ 1:N → `messages`
- `messages`(id int, conversation_id FK CASCADE, role, content, sources_json JSONB, created_at)

### 检索三个核心常量(retrieval.py)
- `CANDIDATES_MULTIPLIER = 4`(每路召回宽度)
- `RERANK_CANDIDATES = 20`(RRF 出口 = rerank 入口)
- `RRF_K = 60`、`DEFAULT_TOP_K = 5`、`ENABLE_RERANK = True`(A/B 开关)

---

## 5. 当前进度

### Week 6 — RAG MVP(已完成)
- Step 1-12:项目骨架、Postgres+pgvector、数据模型、embedding 模块、分块、schemas、ingest、upload、retrieval、query、main.py、端到端验证
- Day 3:引用溯源(`[n]` + sources)
- Day 4:混合检索(向量 + tsvector/zhparser + RRF)
- Day 5:Rerank 层(BGE-reranker-v2-m3,asyncio.to_thread)
- Day 6-7:PDF 解析(pymupdf + 启发式去页眉页脚)、README、Docker、git

### Week 7 — 多轮对话 + 工程化(进行中)
- **Day 1(数据层)— 已完成**:
  - models 加 `Conversation` / `Message`(已修正 `ForeignKey` 误传 `index` 的 bug)
  - schemas 加会话相关 + `QueryRequest.conversation_id` / `QueryResponse.conversation_id`
  - 新增 `services/conversation.py`(CRUD + add_message)
  - 新增 `routers/conversation.py`(创建/列表/详情/删除)
  - 改 `routers/query.py` 接入会话(创建/校验 conversation,持久化 user+assistant 两条消息)
  - main.py 注册 conversation 路由
  - `python -m scripts.init_db` 已建好 4 张表
  - **此时仍是单轮**:历史已存,但 RAG 还没用历史

---

## 6. 下一步(Week 7 剩余)

| Day | 任务 | 关键点 |
|---|---|---|
| **Day 2(下一步)** | Query Rewriting + 历史注入 | 让多轮对话"活"起来:加载最近 N 轮 → LLM 改写当前问题为独立问题 → 检索 → 历史拼进生成 prompt → 存历史。建议把会话编排从 router 抽到 chat service,顺便修"RAG 失败留空会话"的事务瑕疵 |
| Day 3 | 简单前端 | 纯 HTML + vanilla JS(用上前端强项),文件上传 + 对话气泡 + Markdown 渲染 + 引用侧栏。Week 11-12 才用 Next.js 做产品级 |
| Day 4 | 流式输出 | SSE + FastAPI StreamingResponse + Gemini generate_content_stream + 前端 EventSource。建议单独做,涉及前后端两层 |
| Day 5 | 结构化日志 | JSON 日志 + trace_id 中间件 + 异常分层(401/403/404/422/429/500/502/503)+ 关键路径 timing |
| Day 6 | 基础监控 | /metrics 端点:QPS/延迟/错误率、token 用量、召回数分布、rerank score 分布。可选接 prometheus_client |
| Day 7 | Docker 整合 | FastAPI 也容器化,compose 编排两服务,HF 模型缓存 volume 持久化,一键 `docker compose up` |

### 之后的 Week(24 周课程)

> 完整路线图(Week 8–24)+ 博客选题见 `docs/ROADMAP.md`。
> 紧接 Week 7 的是:Week 8 RAG 工程化 → Week 9-10 LangGraph Agent → Week 11-12 Next.js 产品级前端(开始投简历)→ Week 13-14 Ragas 评测。

---

## 7. 已知限制与技术债

- **PDF 解析对扫描件无效**:无文本层需 OCR,超出当前范围
- **Free tier 限流**:embedding ~5 RPM,大文档入库慢;长对话多一次 query rewrite 调用,更吃配额
- **`similarity` 字段语义模糊**:经 RRF 后是 `min(1.0, rrf_score*30)`,既非 cosine 也非纯 RRF;生产建议改用 rank
- **RAG 失败留空会话**:query 路由先建会话再跑 RAG,失败会留空会话(Day 2 抽 chat service 时修)
- **标题孤儿问题**:Markdown 标题可能被单独切成一个无信息 chunk(如 `## 检索流程`);未处理,Week 13-14 评测暴露后再优化(可选 MarkdownHeaderTextSplitter)
- **chunk 策略是"凑合能用"**:chunk_size=500/overlap=50 是起步值,未调优;overlap 仅在"切碎超长段落"时生效,纯段落合并不加 overlap
- **小知识库混合检索优势不明显**:当前测试集 Gemini embedding 已很强,混合检索主要起"补强"而非"救场"作用;但多语言/长尾场景仍需要
- **无用户系统**:用 conversation_id 隔离,未绑定用户(学习阶段有意跳过)
- **无 DB 迁移工具**:用 `create_all`,生产应上 Alembic

---

## 8. 可写的技术博客选题(已识别,Week 23 用)

> 6 个选题见 `docs/ROADMAP.md`。

---

## 9. 常用命令速查

```bash
# 启动数据库(首次或改了 Dockerfile 加 --build)
docker compose up -d              # 改了现有表结构才需要 down -v 清数据
docker compose up -d --build

# 建表(只创建不存在的表,不动现有数据)
python -m scripts.init_db

# 启动服务
fastapi dev app/main.py           # 或 uvicorn app.main:app --reload

# 手动验证脚本(无 pytest,直接跑)
python -m scripts.test_embedding
python -m scripts.test_chunking
python -m scripts.test_ingest
python -m scripts.test_retrieval

# 进 psql
docker exec -it rag-postgres psql -U rag -d rag

# 验证中文分词
docker exec -it rag-postgres psql -U rag -d rag -c "SELECT to_tsvector('chinese_zh', '向量数据库支持相似度检索');"

# 看表
docker exec -it rag-postgres psql -U rag -d rag -c "\dt"

# 学习阶段重置(谨慎,生产禁用)
docker exec -it rag-postgres psql -U rag -d rag -c "TRUNCATE documents, conversations RESTART IDENTITY CASCADE;"
```

API 文档:`http://127.0.0.1:8000/docs`

---

## 10. 给 Claude Code 的协作提示

1. 接手时先确认当前 Day(本文档写于 **Week 7 Day 1 已完成、准备进 Day 2**)。
2. 改已有文件给 diff,不要整文件重写。
3. 每个 Day 拆成小步,每步可独立验证(import 不报错 / 跑 `scripts/test_*.py` / Swagger 测端点)。
4. 学习者会贴报错和代码片段请求 review;review 只讲弱点和改进,不逐行走读。
5. 遇到"看不懂",换更浅的前端类比重讲,不堆术语;不要用 zod 类比。
6. 选型给明确推荐 + 一句理由;信息不足直接问。
7. 优先让学习者自己实现,再对照讲框架封装(如 Week 9 LangGraph)。
8. 涉及 Anthropic/Gemini 产品的具体参数(限流、模型名、API 形态)可能过时,需要时联网核实而非凭记忆。

# RAG Service — 项目上下文（交接自 PROJECT_CONTEXT.md）

> 本文件由长期对话的交接文档迁移而来,Claude Code 启动时自动读取为项目上下文。
> **状态已于 2026-06-09 核对**:**Week 8(后端工程化)已完成** —— Redis 缓存(embedding + 首轮答案 + 流式重放 + best-effort 降级)、成本指标(token×单价)+ rewrite token 计入、README 收尾。下一步进 **Week 9-10(LangGraph Agent)**。
> 总规划 source of truth 在 Obsidian:`0_Focus/projects/求职AI工作/【Plan】24周细化学习清单.md`。Week 8 详情见第 5 节、技术债见第 7 节。
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
- **讲解方式(经验证最有效,优先用)**:讲新概念时,用**一个贯穿始终的真实例子 + 逐字追踪真实数据**,而不是抽象类比或表格。具体做法:举一段真实输入(如真实的两轮对话原话),一步步展示"此刻代码/数据库手里攥着的到底是哪几个字""哪里出了问题""修完后这几个字变成了什么"。先用具体例子让他看懂*发生了什么*,概念名最后才点(甚至说"名字不用记")。抽象类比(纯函数、状态机、表格罗列)对他反而隔靴搔痒——只在具体例子讲完后做辅助补充,不作主线。讲代码思路同理:拿同一个例子的数据,追踪它流过每个函数时的形态变化。
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
| 向量扩展 | pgvector | `halfvec(1024)` + HNSW 索引 |
| 中文分词 | zhparser(基于 SCWS) | 自编译进 pgvector 镜像 |
| Embedding | `BAAI/bge-m3` | 1024 维(固定,无 dimensions 参数);经硅基流动(SiliconFlow) |
| Chat | `Qwen/Qwen3.5-4B` | 思考模型,生成/改写时 `enable_thinking=False`;经硅基流动 |
| LLM SDK | `openai`(AsyncOpenAI) | chat + embedding 都走硅基流动(自定义 `base_url`) |
| Rerank | `BAAI/bge-reranker-v2-m3` | 经硅基流动 `/v1/rerank` API(httpx 裸调,非本地推理) |
| 限流重试 | `tenacity` | 指数退避 |
| 日志 | `structlog` | 结构化 JSON 管道 + 桥接 stdlib;contextvars 注入 trace_id |
| 监控 | `prometheus-client` | Counter/Histogram + `/metrics` 端点(pull 模型);含 token/延迟/成本 |
| 缓存 | `redis`(`redis.asyncio`) | embedding + 首轮答案缓存,best-effort 降级;host 6380→容器 6379 |
| 分块 | `langchain-text-splitters` | RecursiveCharacterTextSplitter |
| token 估算 | `tiktoken` | cl100k_base(对 Qwen3.5 是近似值) |
| PDF 解析 | `pymupdf`(fitz) | |
| 容器 | Docker Compose + OrbStack | |

**环境备忘**
- ⚠️ **依赖装在项目内 `.venv`,不是 pyenv 全局 3.12.13**:脚本化/非交互式跑服务必须显式用 `.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`。直接敲 `uvicorn`/`fastapi` 会命中系统 Python 3.9(报 `ModuleNotFoundError: sqlalchemy`);`~/.pyenv/versions/3.12.13/bin/python` 全局也没装 psycopg(报 `No module named 'psycopg'`)。平时 `fastapi dev` 能跑,是因为终端已激活 `.venv`。注意 `python -m py_compile` 不导入依赖,过了≠能起服务。
- pip 用清华镜像:`pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple`
- HuggingFace 模型下载用国内镜像:`.env` 里设 `HF_ENDPOINT=https://hf-mirror.com`
- 两个 Postgres 实例:`ai_registry` 项目在 5432,本 RAG 项目在 5433
- chat / embedding / rerank 都走 **硅基流动(SiliconFlow)OpenAI 兼容接口**:`.env` 配 `OPENAI_API_KEY` + `OPENAI_BASE_URL`(`https://api.siliconflow.cn/v1`)+ `CHAT_MODEL` / `EMBEDDING_MODEL` / `RERANK_MODEL`;限流比原 Gemini free tier 宽松
- ⚠️ **Qwen3.5-4B 是思考模型**:默认会先输出一大段 `reasoning_content` 再给 `content`,在有 `max_tokens` 上限的 RAG 生成里会把额度耗光导致 `content` 为空。chat 三处调用(生成/流式生成/查询改写)都传 `extra_body={"enable_thinking": False}` 关掉思考
- 改 `.env` 后**必须手动重启服务**:`settings = Settings()` 进程启动只读一次,reload 只监听 `.py` 不监听 `.env`(踩过坑)
- ⚠️ 换 embedding 模型 = 旧向量作废,**必须清库重新入库**(向量跨模型不可比)

---

## 3. 已确定的技术决策(标题索引)

> 完整理由在 `docs/DECISIONS.md`(项目核心知识点 + 面试考点)。这里只列标题,用到某条按编号去查。

- **向量与存储**:1 维度 1024(bge-m3 固定输出,无 MRL / dimensions 参数)/ 2 halfvec 而非 vector / 3 维度是数据库的契约
- **Embedding 调用**:4 用硅基流动 OpenAI 兼容接口(见 41)/ 5 bge-m3 当前对称使用,未加 query/passage 前缀(对称 vs 非对称仍是考点)/ 6 限流处理(批量 ≤32+节流 0.5s+退避)/ 7 chat/embedding 阻塞调用 await;rerank 改走 API 后是异步网络调用直接 await(不再 asyncio.to_thread)
- **Provider**:41 走硅基流动 OpenAI 兼容接口(chat=Qwen/Qwen3.5-4B / embedding=BAAI/bge-m3 / rerank=BAAI/bge-reranker-v2-m3;chat+embedding 用 openai SDK,rerank 用 httpx)
- **检索(三段式)**:8 pgvector 而非 ChromaDB / 9 tsvector+GIN 而非 rank_bm25 / 10 中文分词 zhparser / 11 content_tsv 用 Generated Column / 12 OR 风格+ts_rank_cd / 13 RRF 而非加权求和 / 14 召回候选=top_k×4 / 15 三段式架构 / 16 Rerank 用 BGE(经 SiliconFlow /v1/rerank API)而非 Cohere / 17 Bi-encoder vs Cross-encoder / 18 三个常量的漏斗
- **生成**:19 system_instruction 参数 / 20 temperature=0.1 / 21 强 prompt+few-shot / 22 chunks 用 `---` 分隔
- **引用溯源**:23 `[n]`+sources 数组 / 24 难点是引用正确性(faithfulness)
- **多轮对话**:25 服务端持有历史 / 26 Conversation UUID、Message int / 27 按 id 排序不按 created_at / 28 sources_json 用 JSONB / 29 存取闭环 / 30 Query Rewriting(Day 2 已完成)/ 31 历史滑动窗口 / 39 检索用改写句·生成用原话 / 40 写库放 RAG 之后·单事务
- **通用 Python/工程**:32 pydantic-settings 配置 / 33 flush vs commit / 34 selectinload 避免 N+1 / 35 外键显式 index=True / 36 Text vs String(n) / 37 service/router 分层 / 38 全局异常处理器

---

## 4. 项目结构

> 已按 2026-06-04 实际文件核对。与旧交接文档的差异见本节末「校准说明」。

```
0607-rag-service/                # 注意:git 根在上一级 ai-practise
├── .env / .env.example          # OPENAI_API_KEY, OPENAI_BASE_URL, CHAT_MODEL, EMBEDDING_MODEL, DATABASE_URL, HF_ENDPOINT 等
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
│   ├── llm.py                   # get_openai_client():AsyncOpenAI 单例(硅基流动,chat+embedding 共用)
│   ├── embedding.py             # bge-m3 embedding 封装(批量 ≤32+节流+重试)
│   ├── chunking.py              # RecursiveCharacterTextSplitter + token 估算
│   ├── parsing.py               # 文件解析层(PDF / txt / md → str)
│   ├── rerank.py                # 调硅基流动 /v1/rerank 打分(httpx,按输入顺序对齐分数)
│   ├── routers/
│   │   ├── upload.py            # POST /upload
│   │   ├── query.py            # POST /query(已接入 conversation)
│   │   └── conversation.py      # /conversations CRUD
│   └── services/
│       ├── ingest.py            # 切块 → embedding → 事务写入
│       ├── retrieval.py         # 混合检索 + RRF + rerank + 生成
│       ├── chat.py              # handle_chat 多轮编排 + rewrite_query + 单事务落库
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
- `chunks`(id, document_id FK CASCADE, chunk_index, content, token_count, embedding HALFVEC(1024), content_tsv GENERATED)
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
- Day 5:Rerank 层(BGE-reranker-v2-m3,经硅基流动 /v1/rerank API)
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
- **Day 2(多轮对话)— 已完成**:
  - `services/conversation.py` 加 `get_recent_messages`(DESC 取最新 N 条再 reversed 成正序)
  - `services/chat.py` 加 `rewrite_query`(LLM 改写指代/省略为独立问题,有历史才调)+ `handle_chat` 总编排 + `ConversationNotFound` 领域异常
  - `services/retrieval.py` 的 `query()` 解耦:`search_query`(改写句)走检索,`question`(原话)+ `recent_messages` 走生成;`_generate_answer` 拼历史进 prompt(`re.sub` 去旧引用编号),`SYSTEM_PROMPT` 加规则 6 声明历史非引用源
  - `routers/query.py` 瘦身成"调 handle_chat + 翻译异常(404/502)"
  - 单事务:写库全部移到 RAG 成功之后,`create_conversation(commit=False)` 只 flush 拿 id,末尾一次 `db.commit()`;修掉"RAG 失败留空会话"
  - 易错点记录见 `docs/PITFALLS.md`(P1–P9)
- **Day 3(简单前端)— 已完成**:
  - 新增 `web/index.html`(纯 HTML + vanilla JS,无构建/无框架):三栏布局 = 上传+会话列表 / 对话气泡+输入 / 引用侧栏
  - 内置极简 Markdown 渲染器(不依赖 CDN);答案 `[n]` 可点击联动右侧来源高亮
  - `app/main.py` 用 `StaticFiles(html=True)` 把 `web/` 挂到 `/ui`(与 API 同源,无 CORS);访问 `http://127.0.0.1:8000/ui/`
  - "新对话"只清前端状态,服务端在首次 `/query` 才建会话(复用 Day 2 单事务,不留空会话)
- **Provider(走硅基流动)— 已完成**:chat / embedding / rerank 全部走 **硅基流动(SiliconFlow)OpenAI 兼容接口**(`app/llm.py` 的 `get_openai_client()` 单例供 chat+embedding;rerank 走 `app/rerank.py` 的 httpx 调 `/v1/rerank`)。chat=`Qwen/Qwen3.5-4B`(思考模型,三处调用均 `enable_thinking=False`)、embedding=`BAAI/bge-m3`(1024 维)、rerank=`BAAI/bge-reranker-v2-m3`,均 .env 配。换 embedding 模型已清库重灌。
- **Day 4(流式输出)— 已完成**:
  - `services/retrieval.py`:`query()` 拆成 `retrieve()`(只检索)+ `generate_stream()`(只流式生成);`_generate_answer_stream` 用 `chat.completions.create(stream=True)` 逐 token `yield`(guard `choices` 空帧 / `delta.content` 为 None);`_build_user_prompt` 抽出供流式/非流式共用。
  - `services/chat.py`:抽 `_prepare`(会话+历史+改写)/ `_build_sources` / `_persist`(单事务写库)三个共用件;`handle_chat`(非流式,保留 `run_query`)与 `handle_chat_stream`(流式,产出语义帧 dict)各走各的生成,**未强行合并**(讨论后定:非流式不绕道流式)。
  - `routers/query.py`:新增 `POST /query/stream`,`_sse()` 把帧编码成 `data: {json}\n\n`;**先手动 `await agen.__anext__()` 取第一帧**,把"开流前错误"(会话不存在→404 / 检索失败→502)与"开流后错误"(生成中途→error 帧)分开——开流后 HTTP 200 已发,状态码改不了。
  - `web/index.html`:`streamQuery()` 用 `fetch` + `ReadableStream` 读流(POST 带 body 不能用 EventSource),`TextDecoder({stream:true})` + 按 `\n\n` 缓冲切帧;`sendMessage` 改成 sources 先渲染、token 累积重渲染 markdown。
  - 帧协议:`sources`(1)→ `token`(N)→ `done`(带 conversation_id)。语义帧(dict)与 SSE 编码**分层**:chat 层产 dict,router 层编码字节。
  - 验证:`curl -N /query/stream` 见三段逐步到达;库里 user+assistant 两条消息确认写入(流式单事务闭环成立)。易错点见 `docs/PITFALLS.md`(P10–P14)。
- **Day 5(结构化日志)— 已完成(最小实现)**:
  - 新增 `app/logging_config.py`:structlog processor 管道(`merge_contextvars` → `add_logger_name` → `add_log_level` → `TimeStamper` → 渲染器);用 `ProcessorFormatter` 桥接标准库 logging,sqlalchemy/openai 等第三方库日志并入同一管道;`settings.log_json` 切 dev 彩色(`ConsoleRenderer`)/ prod JSON(`JSONRenderer`)。
  - `config.py` 加 `log_json: bool=False`;`requirements.txt` 加 `structlog`;`main.py` 把 `logging.basicConfig` 换成 `configure_logging()` + `logger=structlog.get_logger()`,日志调用改 event+字段风格。
  - `main.py` 加 `trace_context_middleware`:入口 `bind_contextvars(trace_id=上游 X-Trace-Id or uuid4().hex[:12])`,出口打 `request_completed`(method/path/status/elapsed_ms)+ 响应头 `X-Trace-Id`,`finally` `clear_contextvars`;全局异常响应体带 `trace_id`。
  - 新增 `scripts/test_logging.py`(一次运行展示桥接前后对比);trace_id 注入/清理已验证。
  - ⚠️ **取舍(最小实现)**:uvicorn 自带 logging 未统一(强行收编与 `--reload` 时序冲突导致日志重复,故放弃,用中间件请求日志替代 access log);只做请求级 timing,**service 内分段 timing 与细粒度异常状态码映射未做**。面试稿见 `docs/INTERVIEW.md` 条目 G。
- **Day 6(基础监控)— 已完成(最小实现)**:
  - 新增 `app/metrics.py`:`prometheus_client` 定义 5 个指标 —— `rag_http_requests_total`(Counter,method/path/status)、`rag_http_request_duration_seconds`(Histogram,桶到 30s)、`rag_llm_tokens_total`(Counter,model/type)、`rag_retrieval_candidates`(Histogram)、`rag_rerank_score`(Histogram)。
  - `main.py`:`trace_context_middleware` 内接请求指标(用 `scope["route"].path` 当 label 避免高基数,early-return 跳过 /metrics 自身);`app.mount("/metrics", make_asgi_app())` 暴露端点(pull 模型)。
  - `retrieval.py`:`retrieve` 记召回候选数;`_rerank_chunks` 记 rerank 分数;`_record_token_usage` 在非流式 `_generate_answer` 与流式尾帧(`stream_options={"include_usage": True}`)记 prompt/completion token。`requirements.txt` 加 `prometheus-client`。
  - 验证:`generate_latest()` 快照见全部 5 个指标(Histogram 分桶 + _count/_sum 正确)。
  - ⚠️ **取舍**:`rag_rerank_score` 因 `ENABLE_RERANK=False` 暂无数据;`rewrite_query` 的 token 未计入(只统计主生成);未接真实 Prometheus/Grafana,本地 `curl /metrics` 验证为准。
- **Day 7(Docker 整合)— 已完成**(提交 `1bed96a`):
  - 新增根目录 `Dockerfile`(app 镜像,`python:3.12-slim`):依赖层与代码层分离复用缓存;`tiktoken` 的 cl100k_base 词表烤进镜像(`TIKTOKEN_CACHE_DIR`,运行时容器内常下载失败)。rerank 改走 SiliconFlow API 后,镜像不再需要 torch / sentence-transformers / libgomp1(瘦约 4GB)。
  - 新增 `entrypoint.sh`:先 `python -m scripts.init_db` 幂等建表 → `exec uvicorn ... --host 0.0.0.0`(exec 让 uvicorn 占 PID 1,`docker stop` 的 SIGTERM 才能直达优雅退出)。
  - 新增 `.dockerignore`:排 `.venv`/`__pycache__`/`.env`/`.git` 等(secrets 不进镜像,运行时由 compose `env_file` 注入)。
  - `docker-compose.yml` 加 `app` 服务:`depends_on: postgres(service_healthy)`、覆盖 `DATABASE_URL` 走服务名 `postgres:5432`、`HF_HOME=/models` 挂 `hf_cache` volume;一键 `docker compose up`。

### Week 8 — 后端工程化(压缩版,已完成)
- **Day 1(Redis 缓存)— 已完成**:
  - 新增 `app/cache.py`:`get_redis()` 单例(`redis.asyncio.from_url`,`decode_responses=True`)+ 通用 `cache_get_json` / `cache_set_json`(封装序列化 + **best-effort 降级**:吞 `RedisError` 当未命中/不写,绝不拖垮主流程)。
  - **Embedding 缓存**(`embedding.py` 的 `embed_query`):key=`emb:{model}:{dim}:{sha256(text)}`(带 model/dim 防换模型读脏向量),纯函数,TTL 7 天(纯内存策略)。
  - **答案缓存**(`chat.py` 的 `handle_chat` + `handle_chat_stream`):key=`ans:{chat_model}:{top_k}:{sha256(question)}`,**只缓存无历史首轮**(`not recent_messages`;带历史非纯函数会串味);TTL 1 小时(正确性折中,知识库更新后过时)。命中即落库后早返回。**流式命中按同一帧协议重放**(sources → 整段答案一帧 token → done),前端无感知。
  - 易错点:漏 `await` 导致 SET 静默失效;命中分支误把缓存 dict 当 `QueryResult` 对象用(`result.answer` 崩——dict 只认 `["..."]`、dataclass 只认 `.`),靠"命中分支早 return、dict 不流到下游"解决。
  - compose 加 `redis` 服务(host 6380→容器 6379,避让本机已占的 6379)+ `rag_redis_data` volume;app 加 `REDIS_URL=redis://redis:6379/0` 覆盖。验证脚本:`scripts/test_redis.py` / `test_embed_cache.py` / `bench_cache.py`。
- **Day 2(成本计算 + 收尾)— 已完成**:
  - `metrics.py` 加 `MODEL_PRICES` 单价表 + `rag_llm_cost_total` Counter + 统一入口 `record_usage(model, usage)`(记 token + 按单价累加成本;embedding 的 usage 无 `completion_tokens`,用 `getattr` 兜底)。
  - `retrieval.py` 的 `_record_token_usage` 改为委托 `record_usage`;`chat.py` 的 `_rewrite_query` 补 `record_usage`——**补上原先漏计的 rewrite token**(Day 6 缺口)。
  - README 重写:架构图(mermaid 请求流 + compose 编排)、两种运行方式(全栈一键 / 本地开发)、API 表、缓存与成本的已知限制 + 面试题。`docker compose config` 校验三服务编排合法。
  - ⚠️ 待本机冒烟:`docker compose up --build` 全栈起通 + `/metrics` 见非 0 `rag_llm_cost_total`(需先把 `MODEL_PRICES` 换成硅基流动实际单价)。

---

## 6. 下一步(Week 9-10 — LangGraph Agent)

> 总规划(source of truth)在 Obsidian:`0_Focus/projects/求职AI工作/【Plan】24周细化学习清单.md` 第 8 周。下表 Week 7 各 Day 已全部完成,留作索引。

### Week 7(已全部完成)

| Day | 任务 | 关键点 |
|---|---|---|
| ~~Day 2~~(已完成) | Query Rewriting + 历史注入 | ✅ 已实现:`get_recent_messages` → `rewrite_query` → 解耦 search_query/question → 历史进生成 prompt → `handle_chat` 编排 + 单事务。详见第 5 节与 `docs/PITFALLS.md` |
| ~~Day 3~~(已完成) | 简单前端 | ✅ `web/index.html` 三栏(上传/对话/引用),内置 Markdown 渲染,挂在 `/ui`。详见第 5 节 |
| ~~Day 4~~(已完成) | 流式输出 | ✅ SSE + `StreamingResponse` + `chat.completions.create(stream=True)` + 前端 `fetch` ReadableStream。拆 `retrieve`/`generate_stream`,先拉一帧分段错误处理。详见第 5 节与 `docs/PITFALLS.md`(P10–P14) |
| ~~Day 5~~(已完成) | 结构化日志 | ✅ structlog JSON 管道 + 桥接 stdlib + `trace_context_middleware`(trace_id/contextvars)+ 请求级 timing。⚠️ 最小实现:uvicorn 未统一、无分段 timing、无细粒度异常映射。详见第 5 节与 `docs/INTERVIEW.md` 条目 G |
| ~~Day 6~~(已完成) | 基础监控 | ✅ `prometheus_client` 5 指标(请求数/延迟/token/召回数/rerank 分数)+ `/metrics` 端点。⚠️ rerank 指标因开关关着无数据、rewrite token 未计、未接 Prometheus/Grafana。详见第 5 节 |
| ~~Day 7~~(已完成) | Docker 整合 | ✅ 提交 `1bed96a`:`Dockerfile`(app 镜像,tiktoken 词表烤进镜像 / 依赖分层缓存,rerank 走 API 后无需 torch)+ `entrypoint.sh`(建表 → `exec uvicorn` 占 PID 1)+ compose 编排两服务 + HF 缓存 volume + `.dockerignore`,一键 `docker compose up` |

### Week 8 — 后端工程化(压缩版,已全部完成)

> 原 Week 8 的「日志 / Docker 多服务 / 基础监控」已在 Week 7 Day 5-7 提前完成,本周实际只做了 Redis 缓存 + 成本 + README。详情见第 5 节。技术债(chat 重试 / service 分段 timing / 语义缓存 / 答案缓存精确失效)**后置**,见第 7 节。

| 步骤 | 任务 | 关键点 |
|---|---|---|
| ~~Day 1~~(已完成) | Redis 缓存 | ✅ `cache.py`(单例 + best-effort JSON helper);embedding 缓存(纯函数,7 天)+ 首轮答案缓存(1 小时,流式重放);compose 加 redis(6380→6379)。详见第 5 节 |
| ~~Day 2~~(已完成) | 成本计算 + 收尾 | ✅ `rag_llm_cost_total`(token×单价)+ 统一 `record_usage` 把 rewrite token 计入;README 重写(架构图/运行方式/API);compose config 校验。详见第 5 节 |

### Week 9-10 — LangGraph Agent(下一步)

> ⚠️ Week 7 的多轮对话 ≠ Agent;Agent 是 LLM 自己决定调用工具的多步任务。方法论:先手写一个最简 chaining 再上 LangGraph(建立对比理解)。详见 Obsidian 总规划第 9-10 周 + `docs/ROADMAP.md`。

### 之后的 Week(24 周课程)

> 完整路线图(Week 8–24)+ 博客选题见 `docs/ROADMAP.md`。
> 紧接 Week 7 的是:Week 8 RAG 工程化 → Week 9-10 LangGraph Agent → Week 11-12 Next.js 产品级前端(开始投简历)→ Week 13-14 Ragas 评测。

---

## 7. 已知限制与技术债

- **PDF 解析对扫描件无效**:无文本层需 OCR,超出当前范围
- **硅基流动限流/稳定性**:限流取决于服务商;chat 长生成仍可能断连,大文档入库受其约束;长对话多一次 query rewrite 调用,更吃用量
- **`similarity` 字段语义模糊**:经 RRF 后是 `min(1.0, rrf_score*30)`,既非 cosine 也非纯 RRF;生产建议改用 rank
- ~~**RAG 失败留空会话**~~:**已于 Day 2 修复**——写库全部移到 RAG 成功之后,`handle_chat` 单事务一次 commit,失败回滚不留空会话
- **chat / rerank 调用无重试**:`rewrite_query` / `_generate_answer` / `_generate_answer_stream` 的 `chat.completions.create` 与 `rerank.py` 的 httpx 调用都是裸调,不像 `embedding.py` 有 tenacity 退避;硅基流动撞 429/断连直接 502(流式则在开流后变成 error 帧)。生产需补(复用 embedding 的退避思路,异常类型:chat 用 `openai.APIError`、rerank 用 `httpx.HTTPError`)
- **`ENABLE_RERANK` 当前为 `False`**:`retrieval.py` 的 A/B 开关现在关着,rerank 未生效,召回排序质量打折(流式不受影响)。要测召回质量记得改回 `True`
- **日志可观测性是最小实现(Day 5)**:uvicorn 自带 logging 未并入统一管道(原生格式、无 trace_id);只有请求级 timing,无 service 内分段 timing(rewrite/retrieve/generate);异常仅全局 500 兜底 + query.py 的 404/502,无细粒度状态码映射(401/403/429/503)。生产需补,详见 `docs/INTERVIEW.md` 条目 G
- **监控是最小实现(Day 6/8)**:`rag_rerank_score` 因 `ENABLE_RERANK=False` 无数据;只暴露 `/metrics`,未接 Prometheus 抓取 + Grafana 看板。生产需补。(rewrite token 已于 Week 8 补计;成本 `rag_llm_cost_total` 已加,但 `MODEL_PRICES` 是**占位单价**,需按硅基流动实际计费改才有意义,currency 单位也取决于硅基流动)
- **答案缓存无精确失效(Week 8)**:`ans:*` 只靠 TTL(1 小时)容忍过时,上传新文档后不会主动清相关缓存,旧答案最长存活 1 小时。生产应在 `/upload` 成功后清 `ans:*`(或更细粒度)。另:embedding 缓存未做"惊群"防护(同一冷 key 并发全部 miss 各打一次 API)、未做二进制紧凑序列化(现 JSON ~20-30KB/条);**语义缓存**(按相似度命中近义问)未做
- **标题孤儿问题**:Markdown 标题可能被单独切成一个无信息 chunk(如 `## 检索流程`);未处理,Week 13-14 评测暴露后再优化(可选 MarkdownHeaderTextSplitter)
- **chunk 策略是"凑合能用"**:chunk_size=500/overlap=50 是起步值,未调优;overlap 仅在"切碎超长段落"时生效,纯段落合并不加 overlap
- **小知识库混合检索优势不明显**:当前测试集 embedding 已很强,混合检索主要起"补强"而非"救场"作用;但多语言/长尾场景仍需要
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

# 启动服务(交互式开发,终端已激活 .venv)
fastapi dev app/main.py           # 或 uvicorn app.main:app --reload
# 脚本化/非交互式:必须显式用 .venv 解释器(裸 uvicorn 会命中系统 py3.9)
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 测流式端点(-N 关 curl 缓冲;逐字到达 = 成功)
curl -N -X POST http://127.0.0.1:8000/query/stream \
  -H "Content-Type: application/json" \
  -d '{"question":"什么是 RAG?","top_k":5}'

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
8. 涉及第三方模型/服务(硅基流动 / Qwen / Anthropic 等)的具体参数(限流、模型名、API 形态)可能过时,需要时联网核实而非凭记忆。

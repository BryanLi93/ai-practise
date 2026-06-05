# 面试问答标准答案稿

> 每题结构:**一句话核心** → **展开** → **对应代码**。
> 标 ⚠️ 的是"当前代码状态"的诚实提醒,被追问时别说成已经做了。

---

## 0. 电梯陈述(开场 30 秒)

> 我做了一个完整的 RAG 问答服务,技术栈是 FastAPI + PostgreSQL/pgvector,LLM 走 **OpenAI 兼容中转站**(chat 用 gpt-5.4,embedding 用 text-embedding-3-small)。
> 检索是**三段式**:召回用 pgvector 余弦距离加 zhparser 中文分词的 tsvector 做**混合检索**,用 **RRF** 融合两路(因为两路分数量纲不可比);精排用 **BGE-reranker-v2-m3** 这个 cross-encoder 对 top 20 重排;生成用 gpt-5.4,prompt 强约束"只基于 context 回答"并要求 `[n]` 引用标注做溯源。
> 几个工程细节:embedding 维度选 1536(text-embedding-3-small 原生,正好压在 pgvector HNSW 2000 维上限内);PDF 解析用 PyMuPDF 加启发式去重复页眉页脚;限流用 **tenacity 退避 + 主动节流** 处理。

---

## 1. 端到端:用户问一个问题,发生了什么?(必背)

**核心**:向量化问题 → 混合召回 → RRF 融合 → 精排 → 拼 context → LLM 生成带引用的答案。

**展开(按时间顺序 6 步)**:
1. **问题向量化** —— `embed_query` 调 OpenAI `embeddings.create`(text-embedding-3-small),得到 1536 维向量。OpenAI 是对称 embedding,query 和 document 用同一模型,没有 task_type(早期 Gemini 才区分 RETRIEVAL_QUERY/DOCUMENT)。
2. **两路召回** —— 向量路按 `cosine_distance` 排序取 top 80;关键词路用 zhparser 把问题分词成 `词A | 词B` 的 OR 查询,按 `ts_rank_cd` 排序取 top 80。各自返回 `{chunk_id: 名次}`。
3. **RRF 融合** —— 对两路并集里每个 chunk 算 `score = Σ 1/(60+rank)`,降序取前 20。
4. **精排** —— (开启时)BGE cross-encoder 把 query 和每个 chunk 拼一起打分,重排取 top_k;放在 `asyncio.to_thread` 里跑,不阻塞事件循环。
5. **拼 context** —— 把 chunk 编号成 `[1] ... [2] ...`。
6. **生成** —— gpt-5.4(`chat.completions.create`),system 消息强约束只用 context、强制 `[n]` 标注、找不到就明说;`temperature=0.1` 降低发挥。最后路由层把 chunks 组装成带 `similarity` 和引用编号的 `sources` 数组一起返回。

**对应代码**:`app/services/retrieval.py` 的 `query()` 函数。

---

## 2. 为什么 embedding 列用 halfvec(1536) 而不是 vector(3072)?

**核心**:为了能建 HNSW 索引(维度上限 2000),同时省一半存储。

**展开**:
- pgvector 的 HNSW 索引维度上限是 2000,超了就建不了近似索引、只能全表暴力扫。所以目标维度要 ≤2000。
- 现用 `text-embedding-3-small`,**原生就是 1536**,天然落在上限内、不用截断。若换 `text-embedding-3-large`(原生 3072),OpenAI `text-embedding-3` 系列是 **Matryoshka(MRL)** 模型,前面的维度承载最重要语义,可用 `dimensions=1536` **截断**而语义损失很小(早期用 Gemini 的 3072→1536 也是这招)。
- `halfvec` 用 16 位半精度存,比 `vector`(32 位)**省一半空间和内存带宽**,对召回精度几乎无影响。

**对应代码**:`app/models.py` `HALFVEC(settings.embedding_dim)`;`app/embedding.py` `embeddings.create(dimensions=settings.embedding_dim)`。

⚠️ **诚实提醒**:1536 维是**为了能建 HNSW 而选的**,但当前代码里 `init_db` 只建了 tsvector 的 GIN 索引,**embedding 列还没有真正建 HNSW**,所以现在向量检索其实是暴力精确 KNN(小知识库够用)。被追问"那你建索引了吗",就说:"维度是预留给 HNSW 的,目前数据量小走的精确 KNN,加索引是一行 `Index(..., postgresql_using='hnsw', ...)` 的事。"

---

## 3. Asymmetric vs Symmetric embedding(原 task_type 问题)

**核心**:**非对称** embedding 给"文档"和"查询"分别优化向量空间(更易匹配,召回略升);**对称** 两边同一编码。**我现在用 OpenAI `text-embedding-3`,是对称的、无 task_type**,所以 `embed_documents` 和 `embed_query` 只差"批量 vs 单条"。

**展开**:非对称是不少检索模型的设计——Gemini 的 `task_type=RETRIEVAL_DOCUMENT/QUERY`、BGE 的 query/passage、E5 的 `"query:"/"passage:"` 前缀。被追问"你区分 query 和 doc 吗":现在不区分;若换 BGE-M3 等支持的模型可加角色前缀再榨点召回。

**对应代码**:`app/embedding.py` 的 `embed_documents` vs `embed_query`。

---

## 4. db.flush() 和 db.commit() 的差别?为什么 ingest 里用 flush?

**核心**:`flush` 把 SQL 发给数据库但**不结束事务**,`commit` 才真正提交并结束事务。

**展开**:
- ingest 里先 `add(document)` 再 `flush()`,目的是**触发 INSERT 拿到自增主键 `document.id`**,因为后面建 chunks 需要这个外键。
- 但此时**不能 commit** —— 如果接下来插入 chunks 失败,整个事务(document + chunks)要**一起回滚**,不能留一个没有任何 chunk 的孤儿 document。
- 所以流程是:`add(doc)` → `flush()`(拿 id)→ `add_all(chunks)` → `commit()`(一次性提交)。

**对应代码**:`app/services/ingest.py:77` flush,`:90` commit。

---

## 5. RAG 的"幻觉"怎么产生的?prompt 怎么约束?

**核心**:幻觉来自 LLM 用**参数里的记忆**而非 context 回答;我们用强约束 system prompt 把它"焊死"在 context 上。

**展开 —— prompt 的四道闸**:
1. **只许用 context** —— "只能使用下方上下文中的信息回答"。
2. **强制引用标注** —— 每个事实后面必须跟 `[n]`,给了正反例。这既是溯源,也**反向迫使模型逐句回到原文**对照,减少编造。
3. **兜底拒答** —— 找不到就回固定话术"没有找到相关内容",不许用常识。
4. **低温度** —— `temperature=0.1` 减少自由发挥。

另外召回层也在防幻觉:召回不到任何 chunk 时直接返回 `NO_CONTEXT_ANSWER`,根本不调 LLM。

**对应代码**:`app/services/retrieval.py:38` SYSTEM_PROMPT;`:334` 空召回兜底。

---

## 6~10. 检索策略五连问(混合检索的核心逻辑)

这五题是一条逻辑链,**连起来背**最有说服力:

### 6. 为什么不只用向量?——**关键词盲区**
向量擅长语义,但对**精确词、专有名词、型号、缩写、代码符号**不敏感。比如问 "halfvec",向量可能召回一堆"向量存储"的泛泛内容,却漏掉真正写 `halfvec` 那段。

### 7. 为什么不只用关键词?——**语义盲区**
关键词(tsvector)只能字面匹配,**换个说法就召不回**。问"怎么防止模型乱编",正文写的是"缓解幻觉",字面不重合,关键词路直接漏掉,而向量能命中。

### 8. 为什么要 RRF,不直接把两路分数相加?——**量纲不可比**
向量路是**余弦距离**,关键词路是 **ts_rank_cd**,两个分数的尺度、分布完全不同,直接相加是"拿苹果加橘子"。RRF 只用**名次**:`score = Σ 1/(60+rank)`,把两路统一到同一标准,既鲁棒又不需要调参归一化。那个 `+60`(RRF_K)是平滑常数,削弱头部名次的过度主导。

### 9. 既然混合检索了,为什么还要 Rerank?——**召回精度有上限**
召回用的是**双塔(bi-encoder)**:query 和 doc **分开**编码,牺牲精度换速度,只能算"大致相关"。**cross-encoder** 把 query 和 doc **拼在一起**送进模型做交叉注意力,能判断细粒度相关性,精度高得多。所以用它对召回出来的 20 个做精排。

### 10. 那为什么不直接全用 Rerank?——**算不动**
cross-encoder 每个 (query, doc) 对都要跑一次完整前向,**没法预先建索引**,全库几万 chunk 每次查询都重算根本不现实。所以是**漏斗**:便宜的召回从全库筛到 20,贵的精排只处理这 20 个。

**对应代码**:`_hybrid_retrieve` / `_rrf_fuse` / `_rerank_chunks` 在 `app/services/retrieval.py`。

⚠️ **诚实提醒**:`ENABLE_RERANK` 当前是 `False`(retrieval.py:34),默认走 RRF 后直接截断。演示前改成 `True`,或者大方说"这是个可开关的对比实验,默认关掉是为了省本地推理"。

---

## 附加高频追问(面试官大概率会问)

### A. chunk_size 500、overlap 50 怎么定的?
单位是**字符数**不是 token。500 字符中英混合大约 100~700 token,远低于 embedding 模型 2048 上限,语义也够完整。overlap 50 防止**句子在 chunk 边界被切断**导致语义丢失。用 `RecursiveCharacterTextSplitter`,分隔符从粗到细(段落→行→中英句末标点→…),优先在自然边界切。
⚠️ 注意:overlap 只在"单个超长段落被迫切碎"时才生效;原始段落都小于 chunk_size 时走纯合并路径,相邻块之间没有 overlap(chunking.py:82 注释)。

### B. 中文检索怎么处理的?
PostgreSQL 默认不分中文词。我在 Docker 镜像里**自己编译了 SCWS + zhparser**,建了 `chinese_zh` 文本搜索配置,把名词/动词/形容词等词性映射成可检索词。`chunks.content_tsv` 是 `Computed` 列,DB 自动用 `to_tsvector('chinese_zh', content)` 生成,配 GIN 索引。
**对应**:`docker/postgres/Dockerfile` + `init-extensions.sql` + `models.py:45`。

### C. 限流怎么扛的?两层
1. **主动节流**:`embed_documents` 批之间 `sleep`,节流值随 provider 变——Gemini free tier 要 13s(~5 RPM),现在走 OpenAI 中转站宽松,降到 0.5s。
2. **被动重试**:`tenacity` 指数退避,`wait_exponential(min=4,max=60)`,最多 6 次,只重试 `openai.APIError` / HTTP 错误。
**对应**:`app/embedding.py` `THROTTLE_SECONDS` + `_embed_batch_with_retry`。
⚠️ chat 路径(`rewrite_query` / `_generate_answer`)目前**没接这层重试**,是裸调,撞 429/断连直接 502——技术债,生产要补。

### D. 为什么全程 async?
RAG 是**重 IO**的:embedding、检索、LLM 生成全是网络/磁盘等待。async 让单进程在等待时切去处理别的请求,**并发吞吐高**。SQLAlchemy 用 async engine,LLM 用 `AsyncOpenAI`(`await client.chat.completions.create` / `client.embeddings.create`),本地 rerank 是 CPU 同步任务所以丢进 `asyncio.to_thread` 避免阻塞事件循环。

### E. 引用溯源怎么实现的?
两端配合:**prompt 强制** LLM 在答案里写 `[n]`;**路由层**把检索到的 chunks 按相同顺序组装成 `sources` 数组,每个带 `chunk_id / document_filename / chunk_index / similarity / vector_rank / keyword_rank / rerank_score`。前端用 `[n]` 编号对回 `sources[n-1]`。
⚠️ `similarity` 是从 RRF score 派生的 UI 友好分(`min(1, score*30)`,retrieval.py:84),不是真正的余弦相似度,被问到要讲清楚。

### F. 异常处理 / 安全?
- 全局异常 handler 兜底,**不把 stacktrace 泄露**给客户端,只回类型名(main.py:55)。
- 上传做白名单校验 + 大小限制(30MB)。
- 已知业务异常(空内容)→ 4xx,未知异常 → 5xx + 记完整日志。

---

## 当前状态待办(改进项,主动说反而加分)

| 项 | 现状 | 一句话改进 |
|---|---|---|
| HNSW 索引 | 未建,向量走暴力 KNN | `models.py` 给 embedding 加 HNSW Index |
| Rerank | `ENABLE_RERANK=False` | 默认开启或做成请求参数 |
| 两路召回 | 顺序 await(注释写"并行") | `asyncio.gather` + 各自独立 session 真并发 |
| ~~embedding 模型硬编码~~ | ✅ 已改读 `settings.embedding_model/_dim`(迁 OpenAI 时一并做了) | — |
| chat 无重试 | `rewrite_query`/`_generate_answer` 裸调 | 仿 embedding 接 tenacity 退避(`openai.APIError`) |
| 评测 | 无 | 接 Ragas 做召回率/忠实度评测 |

> 面试时**主动讲这些**比被问出来强:说明你 review 过自己的代码、知道生产级和当前版本的差距在哪。

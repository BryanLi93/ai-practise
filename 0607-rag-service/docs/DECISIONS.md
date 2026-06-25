# 技术决策与理由（42 条）

> 项目的核心知识点,也是面试高频考点。每条都是"踩过/讨论过"才定下来的。
> CLAUDE.md 第 3 节只保留标题索引,完整理由在这里;用到某条时按编号查。

## 向量与存储
1. **目标维度 1024**:现用 `BAAI/bge-m3`,**固定输出 1024 维**,不支持 `dimensions` 参数(硅基流动的 dimensions 只对 Qwen3 系列生效),也没有 MRL 截断的余地——维度由模型定死。pgvector 的 HNSW/IVFFlat 索引上限是 2000 维(`halfvec` 半精度把上限提到 4000),1024 远在其内。
2. **`halfvec` 而非 `vector`**:float16 半精度,存储减半,索引性能更好;在 1024 维下质量损失可忽略。
3. **维度是数据库的契约**:模型和维度一旦定死,改动需要全量重新 embed。入库时把 `embedding_model` 和 `dim` 记进 metadata,便于未来迁移。

## Embedding 调用
4. **chat + embedding 统一用 `openai` SDK**(指向硅基流动 base_url):OpenAI 兼容接口,换 provider/模型只改 .env,见 #41。
5. **Asymmetric vs Symmetric embedding(概念仍是考点)**:有些模型**非对称**——给"文档"和"问题"分别优化向量空间(如 Gemini 的 `task_type=RETRIEVAL_DOCUMENT/QUERY`、E5 的 `query:/passage:` 前缀),几乎免费的召回提升。`bge-m3` 本身支持 query/passage 用法,但当前经硅基流动 embeddings 接口是**对称**调用(不加前缀),`embed_documents` 和 `embed_query` 只差"批量 vs 单条"。被问到要能讲清两者区别和取舍——以及"想再榨召回可加 query/passage 前缀"。
6. **限流处理**:批量调用(单批 ≤32,硅基流动 embeddings 硬上限就是 32 条/请求)+ 批间主动节流 + tenacity 指数退避双保险。批量是必须而非优化——单条串行会卡几十秒。节流值随 provider 变:Gemini free tier 要 13s(~5 RPM),硅基流动宽松,降到 0.5s,主要靠退避兜底;重试异常类型用 `openai.APIError`。
7. **embedding / chat 是异步网络调用,直接 await**。rerank 改走硅基流动 `/v1/rerank` 后也是异步网络调用(httpx),直接 `await`,不再像本地 cross-encoder 那样用 `asyncio.to_thread` 推线程池(那是给阻塞型本地推理用的)。

## 检索(三段式:召回 → 精排 → 生成)
8. **pgvector 而非 ChromaDB**:更贴近国内生产栈;一次 SQL 同时做向量 + 全文检索。ChromaDB 仅作 Week 5 学习对比。
9. **全文检索用 tsvector + GIN,而非 `rank_bm25` 库**:可扩展、单 SQL、与向量检索共用一个库。`rank_bm25` 要全量载入内存。
10. **中文分词用 zhparser**:PG 内置分词器对中文无效(整句一个 token)。zhparser 比 pg_jieba 安装稍简单(虽然两者都要从源码编译)。
11. **`content_tsv` 用 Generated Column**:`Computed("to_tsvector('chinese_zh', content)", persisted=True)`,DB 自动维护,ingest 代码无感。
12. **关键词查询用 OR 风格 + `ts_rank_cd`**:OR 宽召回(AND 太严,长问题召不到);`ts_rank_cd`(cover density)比 `ts_rank` 更接近 BM25 思想。
13. **RRF 融合而非加权求和**:RRF 只用排名,与分数量纲无关(cosine 在 [0,1],BM25 不限上界);超参 `k=60` 是社区共识值。微软/ES/Vespa 默认都用 RRF。
14. **召回候选 = top_k × 4**:让 RRF 能发现"两路都召回但单路名次靠后"的跨路共识 chunk。
15. **三段式检索**:召回(混合,快/宽)→ 精排(cross-encoder,慢/精)→ 生成。这是 RAG 工业标准架构。
16. **Rerank 用 BGE-reranker-v2-m3,经硅基流动 `/v1/rerank` API**:模型选 BGE(开源、中英 SOTA);不走 Cohere 是因为国内访问境外服务不稳(面试考点)。早期在本地用 `sentence-transformers` 跑 cross-encoder,后改走硅基流动同款模型的 API——省掉 torch / sentence-transformers 依赖(镜像瘦约 4GB),代价是多一次网络往返、分数从未归一化 logit 变 0-1。
17. **Bi-encoder vs Cross-encoder 的本质区别**:召回是 bi-encoder(query 和 doc 独立编码,可预先建索引,快);rerank 是 cross-encoder(query+doc 拼一起进模型,token 互相 attention,精度高但不可索引)。这是"必须分两段"的信息论根因,不是 trick。
18. **`RERANK_CANDIDATES=20` 是 rerank 入口宽度**;`top_k` 是 rerank 出口/LLM 入口宽度。三个常量是逐级缩小的漏斗:`top_k×4`(每路召回)→ 20(RRF 出口)→ 5(rerank 出口)。

## 生成
19. **system prompt 走独立的 system 角色**,不拼进用户内容:缓存友好、模型对齐、服从度更高。当前用 OpenAI 接口,即 `messages=[{"role":"system",...},{"role":"user",...}]`(早期 Gemini 是 `system_instruction` 参数,同一思想的不同写法)。
20. **temperature=0.1**:RAG 要忠实不要创意,低温减少幻觉。不写 0.0 因为完全确定性偶尔陷入局部模式。
21. **强 prompt 约束 + few-shot**:小模型(如 Qwen3.5-4B)服从度不如大模型,必须用"必须""禁止"级指令 + 示例,才能稳定输出 `[n]` 引用标注。
22. **chunks 用 `---` 分隔拼 context**:防止 LLM 把不同来源误认为连续段落。

## 引用溯源
23. **答案内嵌 `[n]` + sources 数组**:prompt 要求 LLM 在引用处标注 `[n]`,sources 返回完整 chunk 元数据。Day 1-2 全返回(透明、好调试),拒答时 sources 可能非空但答案是兜底语。
24. **真正难点是"引用正确性"**:LLM 可能标对编号但内容是编的(faithfulness 问题),需 Week 13-14 用 Ragas 评测。

## 多轮对话(Week 7)
25. **服务端持有历史**(非客户端):持久化、刷新不丢,对标所有真实产品。
26. **`Conversation.id` 用 UUID,`Message.id` 用自增 int**:UUID 对外暴露不泄露规模;message int 正好用来做可靠的时间排序。
27. **消息按 `id` 排序,不按 `created_at`**:PG 的 `func.now()` 返回**事务开始时间**,同一事务内插入的多条消息时间戳相同,按 id 才可靠。
28. **`sources_json` 用 JSONB,不建关联表**:展示用、不查询的数据;强结构+高频查询才建表。
29. **存取闭环**:存时 `Source.model_dump()` → dict → JSONB;取时 JSONB → dict,靠 Pydantic 类型声明 `list[Source]` 自动转回对象。
30. **Query Rewriting(Day 2 已完成)**:多轮对话中,先让 LLM 把含指代/省略的当前问题改写成独立问题,再检索。LangChain ConversationalRetrievalChain 默认做法。第一轮无历史则跳过(省一次 LLM 调用)。
31. **历史滑动窗口**:保留最近约 10 轮(当前实现 `get_recent_messages(limit=6)`,DESC 取最新再 reversed 成正序)。摘要压缩留到长对话场景再加,不预先优化。
39. **检索用改写句、生成用原话(Day 2)**:`search_query`(改写后)只喂给 embedding/检索/rerank;`question`(用户原话)+ 历史喂给生成。理由:改写是为补偿"检索器无状态"打的补丁,是有损机器转写;生成阶段有历史可看,不需要补丁,用原话能避免改写错误烙进答案、保持对用户原意的忠实。两个变量全程并存。
40. **写库放在 RAG 成功之后 + 单事务一次 commit(Day 2)**:`handle_chat` 先只读(取历史)→ 改写 → 检索生成(均不写库)→ 成功后才 `create_conversation(commit=False)` + 两条 `add_message(commit=False)` + 一次 `db.commit()`。避免"RAG 失败留空会话",也避免把 DB 事务挂在慢 LLM 调用上。service 抛 `ConversationNotFound` 领域异常,由 router 翻译成 404(状态码不进 service)。

## 通用 Python/工程
32. **pydantic-settings 类型安全配置**:`Settings()` import 即校验,缺必填值 fail fast。Pylance 对 `Settings()` 误报 `reportCallIssue`,用 `# type: ignore[call-arg]` 抑制单行。
33. **`db.flush()` vs `db.commit()`**:flush 推改动到 DB 拿自增主键但不提交;commit 才持久化。ingest 里先 flush 拿 document.id 再 commit,保证"全或无"。
34. **`selectinload`** 避免 N+1:加载 chunk 时一并批量加载关联 document。
35. **外键列必须显式加 `index=True`**:PostgreSQL 不像 MySQL 自动给外键建索引,不加会导致 JOIN 和级联删除全表扫描。注意 `index` 是 `mapped_column` 的参数,不是 `ForeignKey` 的参数。
36. **`Text` vs `String(n)`**:PG 中两者性能无差,预期长/不确定上限用 `Text`,有业务上限用 `String(n)`。
37. **service / router 分层**:router 只管 HTTP 协议,业务逻辑在 service;内部用 dataclass 传递,对外用 Pydantic schema。
38. **全局异常处理器**:兜底未捕获异常,只暴露异常类型名给客户端,完整 traceback 进日志(防信息泄露)。

## Provider
41. **走硅基流动(SiliconFlow)OpenAI 兼容接口**:chat=`Qwen/Qwen3.5-4B` / embedding=`BAAI/bge-m3` / rerank=`BAAI/bge-reranker-v2-m3`;chat+embedding 用 `openai` SDK,rerank 用 httpx 调 `/v1/rerank`,换 provider/模型只改 .env。唯一值得记的技术点:换 embedding 模型会让旧向量作废(跨模型不可比),必须清库重灌——即 #3"维度是契约"的延伸。

## 思考模型
42. **Qwen3.5-4B 是思考模型,生成 / 改写都关掉 `enable_thinking`**:它默认先输出一大段 `reasoning_content` 再给 `content`。在有 `max_tokens` 上限的 RAG 生成里,思考链会把额度耗光,`content` 直接为空(`finish_reason=length`)。三处 chat 调用(`_generate_answer` / `_generate_answer_stream` / `_rewrite_query`)都传 `extra_body={"enable_thinking": False}`:RAG 要的是基于 context 的直接答案,思考既浪费 token / 延迟又触发空响应 bug。

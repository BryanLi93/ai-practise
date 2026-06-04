# 技术决策与理由（38 条）

> 项目的核心知识点,也是面试高频考点。每条都是"踩过/讨论过"才定下来的。
> CLAUDE.md 第 3 节只保留标题索引,完整理由在这里;用到某条时按编号查。

## 向量与存储
1. **Matryoshka 截断 3072 → 1536**:`gemini-embedding-001` 默认 3072 维,但 pgvector 的 HNSW/IVFFlat 索引上限是 2000 维。`halfvec` 半精度类型把索引上限提到 4000,1536 是"存储成本 / 质量 / 索引约束 / 行业惯例"的交集。该模型是 MRL 模型,截断到 1536 质量损失极小。
2. **`halfvec` 而非 `vector`**:float16 半精度,存储减半,索引性能更好;在 1536 维下质量损失可忽略。
3. **维度是数据库的契约**:模型和维度一旦定死,改动需要全量重新 embed。入库时把 `embedding_model` 和 `dim` 记进 metadata,便于未来迁移。

## Embedding 调用
4. **embedding 必须用 `google-genai` 原生 SDK**:OpenAI 兼容层缺 `task_type` 参数。
5. **Asymmetric embedding**:入库 chunk 用 `task_type=RETRIEVAL_DOCUMENT`,查询用 `RETRIEVAL_QUERY`。同模型针对"文档"和"问题"两种角色生成更适合检索的向量,是几乎免费的召回质量提升(OpenAI text-embedding-3 没有)。
6. **Free tier 限流处理**:批量调用(单批 ≤100)+ 批间主动节流(13s)+ tenacity 指数退避双保险。批量是必须而非优化——单条串行会卡几十秒。
7. **embedding 是同步阻塞调用要 await**;chat 同理。ML 本地推理(rerank)用 `asyncio.to_thread` 推到线程池,避免阻塞事件循环。

## 检索(三段式:召回 → 精排 → 生成)
8. **pgvector 而非 ChromaDB**:更贴近国内生产栈;一次 SQL 同时做向量 + 全文检索。ChromaDB 仅作 Week 5 学习对比。
9. **全文检索用 tsvector + GIN,而非 `rank_bm25` 库**:可扩展、单 SQL、与向量检索共用一个库。`rank_bm25` 要全量载入内存。
10. **中文分词用 zhparser**:PG 内置分词器对中文无效(整句一个 token)。zhparser 比 pg_jieba 安装稍简单(虽然两者都要从源码编译)。
11. **`content_tsv` 用 Generated Column**:`Computed("to_tsvector('chinese_zh', content)", persisted=True)`,DB 自动维护,ingest 代码无感。
12. **关键词查询用 OR 风格 + `ts_rank_cd`**:OR 宽召回(AND 太严,长问题召不到);`ts_rank_cd`(cover density)比 `ts_rank` 更接近 BM25 思想。
13. **RRF 融合而非加权求和**:RRF 只用排名,与分数量纲无关(cosine 在 [0,1],BM25 不限上界);超参 `k=60` 是社区共识值。微软/ES/Vespa 默认都用 RRF。
14. **召回候选 = top_k × 4**:让 RRF 能发现"两路都召回但单路名次靠后"的跨路共识 chunk。
15. **三段式检索**:召回(混合,快/宽)→ 精排(cross-encoder,慢/精)→ 生成。这是 RAG 工业标准架构。
16. **Rerank 用 BGE-reranker-v2-m3 本地模型,而非 Cohere API**:Cohere 国内访问不稳,生产不能依赖境外服务(面试考点);BGE 开源、中英 SOTA。
17. **Bi-encoder vs Cross-encoder 的本质区别**:召回是 bi-encoder(query 和 doc 独立编码,可预先建索引,快);rerank 是 cross-encoder(query+doc 拼一起进模型,token 互相 attention,精度高但不可索引)。这是"必须分两段"的信息论根因,不是 trick。
18. **`RERANK_CANDIDATES=20` 是 rerank 入口宽度**;`top_k` 是 rerank 出口/LLM 入口宽度。三个常量是逐级缩小的漏斗:`top_k×4`(每路召回)→ 20(RRF 出口)→ 5(rerank 出口)。

## 生成
19. **system prompt 用 `system_instruction` 参数**,不拼进 contents:缓存友好、模型对齐、服从度更高。
20. **temperature=0.1**:RAG 要忠实不要创意,低温减少幻觉。不写 0.0 因为完全确定性偶尔陷入局部模式。
21. **强 prompt 约束 + few-shot**:Free tier 的 Flash 服从度不如 Pro,必须用"必须""禁止"级指令 + 示例,才能稳定输出 `[n]` 引用标注。
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
30. **Query Rewriting(Day 2 待做)**:多轮对话中,先让 LLM 把含指代/省略的当前问题改写成独立问题,再检索。LangChain ConversationalRetrievalChain 默认做法。第一轮无历史则跳过。
31. **历史滑动窗口**:保留最近约 10 轮。摘要压缩留到长对话场景再加,不预先优化。

## 通用 Python/工程
32. **pydantic-settings 类型安全配置**:`Settings()` import 即校验,缺必填值 fail fast。Pylance 对 `Settings()` 误报 `reportCallIssue`,用 `# type: ignore[call-arg]` 抑制单行。
33. **`db.flush()` vs `db.commit()`**:flush 推改动到 DB 拿自增主键但不提交;commit 才持久化。ingest 里先 flush 拿 document.id 再 commit,保证"全或无"。
34. **`selectinload`** 避免 N+1:加载 chunk 时一并批量加载关联 document。
35. **外键列必须显式加 `index=True`**:PostgreSQL 不像 MySQL 自动给外键建索引,不加会导致 JOIN 和级联删除全表扫描。注意 `index` 是 `mapped_column` 的参数,不是 `ForeignKey` 的参数。
36. **`Text` vs `String(n)`**:PG 中两者性能无差,预期长/不确定上限用 `Text`,有业务上限用 `String(n)`。
37. **service / router 分层**:router 只管 HTTP 协议,业务逻辑在 service;内部用 dataclass 传递,对外用 Pydantic schema。
38. **全局异常处理器**:兜底未捕获异常,只暴露异常类型名给客户端,完整 traceback 进日志(防信息泄露)。

# 架构图 & 时序图

> 配合 `INTERVIEW.md` 一起看。所有图用 Mermaid 编写,GitHub / VSCode 预览可直接渲染。

## 1. 分层架构图

```mermaid
graph TD
    Client[客户端 / Swagger UI]

    subgraph HTTP["HTTP 层 (app/main.py)"]
        FastAPI[FastAPI 实例<br/>CORS · 全局异常 · lifespan]
    end

    subgraph Router["路由层 (app/routers)"]
        Upload[upload.py<br/>POST /upload]
        Query[query.py<br/>POST /query]
    end

    subgraph Service["服务层 (app/services)"]
        Ingest[ingest.py<br/>切块→向量化→事务写库]
        Retrieval[retrieval.py<br/>混合检索→RRF→精排→生成]
    end

    subgraph Capability["能力层 (app)"]
        Parsing[parsing.py<br/>PDF/txt/md→文本]
        Chunking[chunking.py<br/>递归字符切分]
        Embedding[embedding.py<br/>OpenAI embedding]
        Rerank[rerank.py<br/>BGE cross-encoder]
    end

    subgraph Data["数据层"]
        Models[models.py<br/>Document / Chunk]
        DB[db.py<br/>async engine]
    end

    subgraph Infra["基础设施"]
        PG[(PostgreSQL 16<br/>pgvector + zhparser)]
        Gemini[硅基流动 SiliconFlow<br/>OpenAI 兼容 · Qwen3.5-4B / bge-m3]
        BGE[BGE-reranker-v2-m3<br/>经硅基流动 /v1/rerank]
    end

    Client --> FastAPI --> Upload & Query
    Upload --> Parsing --> Chunking --> Ingest
    Query --> Retrieval
    Ingest --> Embedding & Models
    Retrieval --> Embedding & Rerank & Models
    Embedding --> Gemini
    Rerank --> BGE
    Models --> DB --> PG
    Retrieval --> Gemini
```

## 2. 技术方案作用图（复习版）

这张图按真实请求链路组织。方框写“做什么”，连线写“为什么需要这项技术”；虚线表示日志和指标，不参与业务数据处理。

```mermaid
flowchart LR
    User["用户<br/>Web UI / Swagger"]
    SiliconFlow["SiliconFlow<br/>bge-m3：embedding<br/>BGE reranker：精排<br/>Qwen3.5-4B：生成 / 改写"]
    Observe["可观测性<br/>structlog + trace_id：串联请求日志<br/>Prometheus /metrics：请求、延迟、token、召回、估算成本（单价待核对）"]

    subgraph Compose["Docker Compose：统一启动和连接 app、PostgreSQL、Redis"]
        subgraph App["FastAPI App"]
            Router["HTTP / Router<br/>参数校验、异常转状态码、依赖注入"]

            subgraph Ingest["文档入库"]
                Parse["PyMuPDF / 文本解码<br/>PDF、txt、md → 纯文本"]
                Split["RecursiveCharacterTextSplitter<br/>500 字符 / overlap 50"]
                EmbedDoc["批量 embedding<br/>每批 ≤32 + 0.5s 节流 + 退避重试"]
            end

            subgraph Query["问答链路"]
                Chat["对话编排<br/>最近 6 条历史、问题改写<br/>成功后一次事务保存"]
                EmbedQuery["问题 embedding"]
                Hybrid["混合召回<br/>向量 top 80 + 中文关键词 top 80"]
                RRF["RRF 融合<br/>只比较名次，保留 20"]
                Rerank["BGE rerank<br/>可选；当前默认关闭"]
                TopK["最终 top_k<br/>默认 5"]
                Generate["Qwen 生成<br/>只用 context + [n] 引用<br/>enable_thinking=False"]
                Stream["SSE<br/>sources → token → done<br/>开流前先拉第一帧"]
            end
        end

        PG[("PostgreSQL 16<br/>业务数据：documents / chunks / conversations / messages<br/>向量：pgvector halfvec(1024)，当前精确 KNN<br/>关键词：zhparser + tsvector + GIN")]
        Redis[("Redis 7（best-effort）<br/>问题 embedding：TTL 7 天<br/>无历史首轮答案：TTL 1 小时<br/>故障时降级为未命中")]
    end

    User --> Router

    Router -->|"POST /upload"| Parse
    Parse --> Split --> EmbedDoc
    EmbedDoc -->|"bge-m3"| SiliconFlow
    EmbedDoc -->|"Document + Chunks<br/>flush 后一次 commit"| PG

    Router -->|"POST /query<br/>POST /query/stream"| Chat
    Chat <-->|"首轮答案缓存"| Redis
    Chat -->|"改写后的 search_query"| EmbedQuery
    EmbedQuery <-->|"问题向量缓存"| Redis
    EmbedQuery -->|"未命中时调用 bge-m3"| SiliconFlow
    EmbedQuery --> Hybrid
    Hybrid <-->|"余弦距离 + ts_rank_cd"| PG
    Hybrid --> RRF
    RRF -->|"ENABLE_RERANK=True"| Rerank
    Rerank -->|"远程 /v1/rerank"| SiliconFlow
    Rerank --> TopK
    RRF -->|"当前默认 False"| TopK
    TopK --> Generate
    Generate <-->|"Qwen chat completion"| SiliconFlow
    Generate --> Chat
    Chat -->|"user + assistant + sources"| PG
    Chat --> Stream --> User

    Router -.-> Observe
    Chat -.-> Observe
    Hybrid -.-> Observe

    classDef external fill:#f5f5f5,stroke:#666,color:#222;
    classDef data fill:#e8f4ff,stroke:#2878b5,color:#123;
    classDef warning fill:#fff4d6,stroke:#c58a00,color:#432;
    class SiliconFlow,Observe external;
    class PG,Redis data;
    class Rerank warning;
```

读图时重点记住：

- PostgreSQL 不只是存数据，还同时负责向量检索和中文全文检索。
- Redis 只减少重复调用，坏了可以绕过，不能拖垮主链路。
- SiliconFlow 提供三个不同模型能力：embedding、rerank、生成/改写。
- rerank 代码已经接好，但当前默认关闭；embedding 也还没有 HNSW 索引。
- structlog 和 Prometheus 负责发现问题，不参与答案生成。

## 3. 文档入库时序图 (POST /upload)

```mermaid
sequenceDiagram
    autonumber
    actor U as 客户端
    participant R as upload.py
    participant P as parsing.py
    participant I as ingest.py
    participant C as chunking.py
    participant E as embedding.py
    participant G as 硅基流动
    participant DB as PostgreSQL

    U->>R: POST /upload (file)
    R->>R: _validate_file 扩展名/MIME/大小校验
    R->>R: await file.read() 读字节
    R->>P: parse_file(bytes)
    alt PDF
        P->>P: parse_pdf (PyMuPDF + 去页眉页脚)
    else txt/md
        P->>P: _decode_text (utf-8/gbk 多编码)
    end
    P-->>R: 纯文本
    R->>I: ingest_text_file(content)
    I->>C: split_text(content)
    C-->>I: List[Chunk] (500字符/块, 50重叠)
    I->>E: embed_documents(texts)
    loop 每批 ≤32 条
        E->>G: embeddings.create(model=bge-m3)
        G-->>E: embeddings
        E->>E: sleep 0.5s 主动节流 (除最后一批)
    end
    E-->>I: List[vector]
    I->>DB: add(Document) + flush() 拿自增 id
    I->>DB: add_all(Chunks) + commit()
    Note over DB: content_tsv 由 DB 自动<br/>Computed 生成 (zhparser 分词)
    I-->>R: IngestResult(document, chunk_count)
    R-->>U: 201 UploadResponse
```

## 4. 提问检索时序图 (POST /query)

```mermaid
sequenceDiagram
    autonumber
    actor U as 客户端
    participant R as query.py
    participant S as retrieval.py
    participant E as embedding.py
    participant G as 硅基流动
    participant DB as PostgreSQL
    participant K as rerank.py / 硅基流动 rerank

    U->>R: POST /query (question, top_k)
    R->>S: run_query(question, top_k)

    S->>E: embed_query(question)
    E->>G: embeddings.create(model=bge-m3)
    G-->>E: query_vector
    E-->>S: query_vector

    rect rgb(235,245,255)
        Note over S,DB: 混合召回 (_hybrid_retrieve)
        S->>DB: _retrieve_by_vector (cosine_distance 排序)
        DB-->>S: {chunk_id: rank}
        S->>DB: _retrieve_by_keyword (zhparser OR + ts_rank_cd)
        DB-->>S: {chunk_id: rank}
        S->>S: _rrf_fuse  score=Σ 1/(60+rank)
        S->>DB: _load_chunks (批量取完整 Chunk+Document)
        DB-->>S: List[RetrievedChunk]
    end

    alt ENABLE_RERANK = True
        S->>K: rerank(question, docs)  [await /v1/rerank]
        K-->>S: scores → 重排取 top_k
    else 当前默认 False
        S->>S: candidates[:top_k] 直接截断
    end

    S->>S: _format_context  "[1] ... [2] ..."
    S->>G: chat.completions.create(system 强约束 + user: context)
    G-->>S: answer (带 [n] 引用)
    S-->>R: QueryResult(answer, sources)
    R->>R: 组装 List[Source]
    R-->>U: 201 QueryResponse
```

## 5. 三段式检索漏斗 (数据量收敛)

```mermaid
graph LR
    A[全库 chunks] -->|向量路 top 80| B[向量候选]
    A -->|关键词路 top 80| C[关键词候选]
    B --> D{RRF 融合}
    C --> D
    D -->|取 20| E[精排候选]
    E -->|开启时 cross-encoder| F[Rerank top 5]
    E -->|当前默认关闭| F2[直接取 top 5]
    F --> G[送入 LLM 的 context]
    F2 --> G
```

> 数字来源:`RERANK_CANDIDATES=20`,`CANDIDATES_MULTIPLIER=4` → 每路召回 20×4=80,RRF 后取 20。`ENABLE_RERANK=True` 时精排后取 `top_k`;当前默认是 `False`,直接从 RRF 结果取 `top_k`(默认 5)。

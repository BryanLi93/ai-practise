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
        Gemini[LLM 中转站<br/>OpenAI 兼容 · gpt-5.4 / text-embedding-3-small]
        BGE[BGE-reranker-v2-m3<br/>本地模型]
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

## 2. 文档入库时序图 (POST /upload)

```mermaid
sequenceDiagram
    autonumber
    actor U as 客户端
    participant R as upload.py
    participant P as parsing.py
    participant I as ingest.py
    participant C as chunking.py
    participant E as embedding.py
    participant G as LLM 中转站
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
    loop 每批 100 条
        E->>G: embeddings.create(model=text-embedding-3-small, dimensions=1536)
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

## 3. 提问检索时序图 (POST /query)

```mermaid
sequenceDiagram
    autonumber
    actor U as 客户端
    participant R as query.py
    participant S as retrieval.py
    participant E as embedding.py
    participant G as LLM 中转站
    participant DB as PostgreSQL
    participant K as rerank.py / BGE

    U->>R: POST /query (question, top_k)
    R->>S: run_query(question, top_k)

    S->>E: embed_query(question)
    E->>G: embeddings.create(model=text-embedding-3-small)
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
        S->>K: rerank(question, docs)  [asyncio.to_thread]
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

## 4. 三段式检索漏斗 (数据量收敛)

```mermaid
graph LR
    A[全库 chunks] -->|向量路 top 80| B[向量候选]
    A -->|关键词路 top 80| C[关键词候选]
    B --> D{RRF 融合}
    C --> D
    D -->|取 20| E[精排候选]
    E -->|cross-encoder| F[Rerank top 5]
    F --> G[送入 LLM 的 context]
```

> 数字来源:`RERANK_CANDIDATES=20`,`CANDIDATES_MULTIPLIER=4` → 每路召回 20×4=80,RRF 后取 20,精排后取 `top_k`(默认 5)。

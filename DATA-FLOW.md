# RAG · Agent · 前端 —— 三个项目怎么串起来(数据流总览)

> 这份笔记串起仓库里三个互相调用的项目,讲清**一个问题的数据格式从后端到屏幕经历了什么变化**,以及 **RAG 模式和 Agent 模式的本质区别**。
> 单个项目内部的细节各自有文档(如 `1112-frontend/docs/ARCHITECTURE.md`),这里只画跨项目的全景。

---

## 1. 三个项目分别是谁

| 目录 | 角色 | 端口 | 对外端点 |
|---|---|---|---|
| `0607-rag-service` | FastAPI RAG 服务(检索 + 生成,pgvector) | :8000 | `/query`(非流式)、`/query/stream`(流式) |
| `0910-langgraph-agent` | LangGraph Agent 服务(`15_agent_server.py`) | :8100 | `/agent/stream`;**内部把 RAG `/query` 当一个工具调** |
| `1112-frontend` | Next.js BFF(透传)+ 前端 | :3000 | `/api/chat`(RAG 模式)、`/api/agent`(Agent 模式) |

两条调用链:

```
RAG 模式:    浏览器 → /api/chat  → RAG :8000 /query/stream
Agent 模式:  浏览器 → /api/agent → LangGraph :8100 /agent/stream →(工具)RAG :8000 /query
```

---

## 2. RAG 模式 vs Agent 模式:功能区别

| | **RAG 模式** | **Agent 模式** |
|---|---|---|
| 要不要检索 | **每个问题都先检索**再生成(固定管道) | **LLM 自己决定**:知识库问题才调工具,通用问题直接答 |
| 检索次数 | 固定一次 | 0 次 / 1 次 / 多次,由 LLM 判断 |
| 结构化来源 | **有** —— `sources` 帧带完整 `Source[]`(id、similarity、原文) | **无** —— 工具把 sources 拍平成纯字符串(见 §4) |
| `[n]` 引用溯源 | ✅ 有,侧栏点击高亮 | ❌ 没有(结构被拍平丢了) |
| 可视化重点 | 答案 + 引用侧栏 | 答案 + **工具时间线**(它查了什么、查到什么) |
| 多轮会话 | ✅ `conversation_id` 持久化 | ❌ 单轮 |

一句话:**RAG 是一条固定流水线(必检索 → 生成);Agent 是让 LLM 自主决策(它自己决定调不调工具、调几次)。**

Agent 的 system prompt 印证了这点:

> `知识库问题用工具查、查到再答;通用问题直接答,别瞎调工具`

---

## 3. 数据格式之旅(以 Agent 模式为主线)

例子:在 Agent 模式问「**pgvector 用什么距离度量?**」,跟着数据走一遍。每一跳数据**长什么样**、**发生了什么变化**:

### ① RAG 服务 :8000 `/query` 返回 —— Pydantic JSON(结构化)

被 agent 当工具调用,拿到完整结构:

```json
{
  "answer": "...",
  "sources": [
    { "id": 1, "document_filename": "pgvector.md",
      "content": "pgvector 支持 L2 / 内积 / 余弦…",
      "similarity": 0.82, "chunk_id": 51, "...": "..." }
  ],
  "conversation_id": "c-abc"
}
```

⬇ **工具 `search_knowledge_base` 只取 `sources`,拼成一段纯文本喂给 LLM**

### ② Agent 工具的返回值 —— 纯字符串 ⚠️ 结构丢失

```
"文档名：pgvector.md / 内容：pgvector 支持 L2 / 内积 / 余弦…

文档名：index.md / 内容：…"
```

> **关键岔口**:`id`、`similarity`、`chunk_id` 全没了,只剩文档名 + 内容。这就是 **Agent 模式拿不到 `[n]` 引用溯源的根因**——结构在这一步被拍平。

⬇ **LLM 读这段文本生成答案;服务端把「工具事件 + 答案 token」翻成自定义语义帧**

### ③ LangGraph 服务 :8100 `/agent/stream` —— 自定义 SSE 语义帧

```
data: {"type":"step","id":"call_x","tool":"search_knowledge_base","status":"running","input":{"query":"pgvector 距离度量"}}
data: {"type":"step","id":"call_x",...,"status":"done","output":"文档名：…"}
data: {"type":"token","content":"pgvector "}
data: {"type":"token","content":"支持 L2、内积、余弦距离。"}
data: {"type":"done"}
```

⬇ **Next.js BFF 原样透传**:`return new Response(upstream.body, …)`

### ④ Next.js BFF :3000 `/api/agent` —— 和 ③ 逐字节相同

BFF 只做安全收口(藏后端地址)+ 错误兜底(后端没起返干净 502),SSE 帧原样转给浏览器。所以这一跳数据 = ③。

⬇ **客户端 `parseSSE` 逐帧解出 → `agentReduce(frame, draft)` 累积进一条扁平消息**

### ⑤ 客户端 `ChatMessage` —— 扁平 JS 对象(渲染源)

```js
{ id, role: "assistant",
  text: "pgvector 支持 L2、内积、余弦距离。",   // token.content 累积(已剥 <think>)
  toolSteps: [                                  // step 帧累积,同 id 原地 running→done
    { id: "call_x", data: { tool, status: "done", input, output } }
  ] }
// RAG 模式则是 { text, sources: [完整 Source[]], conversationId }
```

每种信息各占一个字段,reducer 直接往上累积,渲染端直接取字段。

---

## 4. RAG 模式链路(对比)

Agent 链有 4 跳、中间多一步「拍平」。**RAG 模式的链更短、且不拍平**,这正是它能做引用溯源的原因:

```
RAG :8000 /query/stream            Next.js /api/chat(透传)          client
──────────────────────────         ──────────────────────────         ──────────────────────
语义帧(直接带结构):          →   逐字节相同(原样转发):       →   parseSSE + ragReduce
 {type:sources, sources:[完整]}      {type:sources, sources:[完整]}       累积成 ChatMessage:
 {type:token, text:"…"}              {type:token, text:"…"}                { text,
 {type:done, conversation_id}        {type:done, conversation_id}            sources:[结构完整],
                                                                            conversationId }
```

注意 RAG 帧的 token 字段是 **`text`**,Agent 是 **`content`**;RAG 的 `done` 带 `conversation_id`(多轮用),Agent 不带。两个模式各自一个 reducer(`ragReduce` / `agentReduce`)处理这点差异。

---

## 5. 一句话收口

两条链格式经历的**本质变化是同一套**:

> **结构化 JSON / 帧 → 自定义语义帧(SSE)→ BFF 原样透传 → 客户端 reducer 累积成扁平 ChatMessage**

唯一的岔口在 **Agent 多了一步「sources 拍平成字符串」**——它决定了两个模式前端能力的全部差异(有没有 `[n]` 溯源)。

> 相关文档:前端 BFF 透传 + 客户端流式 hook(`useStreamChat`)+ reducer 的细节见 [`1112-frontend/docs/ARCHITECTURE.md`](1112-frontend/docs/ARCHITECTURE.md)。

# 1112-frontend — 项目架构 Plan(Week 11-12 产品级前端)

> 24 周路线里的位置:Week 9-10 LangGraph Agent 之后、Week 13-14 评测之前。
> 目标:把 `0607-rag-service`(以及后续的 LangGraph Agent)包装成一个**可演示、可投简历**的产品级前端。
> 后端契约状态:已于 2026-06-16 对照 `0607-rag-service` 源码核对(见第 2 节)。
> 架构主线与实现细节以 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) 为准,本文是项目概览 + 后端契约 + 功能路线图。

---

## 0. 一句话定位

一个 **Next.js(App Router)** 的 RAG / Agent 聊天前端,核心不是"再写一个 ChatGPT 壳",而是把后端**已经产出但当前 `web/index.html` 没充分展示**的能力(流式、引用溯源 `[n]`、多轮会话、工具调用可视化)用产品级 UI 呈现出来。

定位差异(相对后端自带的 `0607-rag-service/web/index.html`):那个是 vanilla JS 单文件、用来验证后端通不通;本项目是带构建、带组件化、带类型安全的正式前端,**面试时作为"前端背景 + AI 应用"的作品**。

---

## 1. 这个前端到底连谁(关键前提)

| 后端 | 现状 | 本项目怎么用 |
|---|---|---|
| `0607-rag-service` | ✅ 真实 HTTP 服务(`:8000`),有 `/query/stream` SSE、`/upload`、`/conversations` | **Week 11 的主后端**。流式问答、引用、上传、多轮全都连它 |
| `0910-langgraph-agent` | ✅ 已加 `15_agent_server.py`,暴露 `/agent/stream`(`:8100`);内部把 RAG `/query` 包成 agent 工具 | **Week 12 工具可视化的目标后端** |

两条调用链:

```
RAG 模式:    浏览器 → /api/chat  → RAG :8000 /query/stream
Agent 模式:  浏览器 → /api/agent → LangGraph :8100 /agent/stream →(工具)RAG :8000 /query
```

---

## 2. 后端契约现状(已核对源码,前端按这个写)

来自 `0607-rag-service/app/routers/*.py` 与 `app/schemas.py`。

### 2.1 端点

| 方法 | 路径 | 入参 | 出参 |
|---|---|---|---|
| POST | `/upload` | `multipart/form-data`,字段名 `file`;允许 `.txt/.md/.markdown/.pdf`,≤ 30MB | `{document_id, filename, chunk_count, created_at}`(201) |
| POST | `/query` | `{question, top_k=5, conversation_id?}` | `{answer, sources[], conversation_id}`(201) |
| POST | `/query/stream` | 同上 | **SSE**,见 2.2 |
| POST | `/conversations` | `{title?}` | `{id, title, created_at}` |
| GET | `/conversations` | — | `ConversationSummary[]` |
| GET | `/conversations/{id}` | — | `{id, title, created_at, messages[]}`,每条消息可带 `sources` |
| DELETE | `/conversations/{id}` | — | 204 |
| GET | `/health` `/metrics` | — | 健康检查 / Prometheus 文本 |

CORS:`allow_origins=["*"]`(学习阶段宽松),所以浏览器**可以**直连后端;但本项目默认走 BFF(见第 4 节),不依赖这个宽松配置。

### 2.2 流式帧协议(`/query/stream`,前端 reducer 直接消费)

后端是**自定义 SSE**。每帧编码为 `data: {json}\n\n`,顺序固定:

```
sources 帧 (1 条)  → { "type":"sources", "sources":[ Source, ... ] }
token   帧 (N 条)  → { "type":"token", "text":"..." }     // ⚠️ 字段是 text,不是 content
done    帧 (1 条)  → { "type":"done", "conversation_id":"..." }
error   帧 (开流后中途失败) → { "type":"error", "message":"..." }
```

错误分两段(后端已这样设计,前端要对齐):
- **开流前**(会话不存在 / 检索失败):返回 HTTP 404 / 502,能正常映射状态码。
- **开流后**(生成中途失败):HTTP 200 已发出,只能塞一条 `error` 帧。

> ✅ 已实测确认(2026-06-17,`curl /query/stream`):token 帧字段是 **`text`**(不是 content)。另一个坑:token 文本里会**先夹一段 `<think>...</think>` 推理**(中转站模型 gpt-5.4 会吐思考),前端要把 think 段从答案正文里剥掉(`lib/think.ts`),别当正文渲染。

Agent `/agent/stream`(`0910/15_agent_server.py`)的帧与 RAG 的差异:token 字段是 **`content`**(不是 text);多了 `step` 帧(工具 running/done,同 `id` 配对);`done` 不带 `conversation_id`;无 `sources` 帧。

### 2.3 Source 结构(引用溯源 UI 直接消费)

```
Source {
  id: int                 // 引用编号,对应 answer 里的 [n] 标记 —— 这是 [n] ↔ 卡片联动的钥匙
  chunk_id: int
  document_id: int
  document_filename: str   // 侧栏卡片标题
  chunk_index: int
  content: str             // 卡片正文 / 点击 [n] 展开的原文片段
  similarity: float        // 0-1,可做相关度标签/排序
  vector_rank / keyword_rank / rerank_score: 可选
}
```

后端**已经**在答案里输出 `[n]` 并保证与 `sources[].id` 对齐(RAG 决策 23)。前端不需要自己造引用编号,只要解析 `[n]` 并连到对应 `Source` 即可。

---

## 3. 技术栈选型

| 层 | 选型 | 一句话理由 |
|---|---|---|
| 框架 | **Next.js 16 App Router + React 19 + TypeScript** | 你的主场;App Router 的 Route Handler 天然就是 BFF 透传层 |
| 流式 | **自写 `useStreamChat`(`fetch` + `ReadableStream` + `parseSSE`)** | 后端已是干净的自定义 SSE,客户端直接读、逐帧累积成扁平消息;不引第三方对话 SDK,逻辑全在自己掌控(约 70 行) |
| Markdown | `react-markdown` + `remark-gfm` | gfm 负责表格/任务列表/删除线的正确渲染 |
| 代码高亮 | **`rehype-highlight`(流式期)** + 可选 `shiki`(终态) | 见 D3:流式逐 token 重渲染时 shiki 太重,先用同步的 rehype-highlight |
| 样式 | **Tailwind CSS**(不引 shadcn/ui) | 核心组件裸写,需要时再说 |
| 上传进度 | `XMLHttpRequest` | `fetch` 原生不报上传进度,拖拽进度条用 XHR 的 `upload.onprogress` 最省事 |

不引入的:状态管理库(`useStreamChat` + React state 够用)、tRPC(BFF 直接写 Route Handler)、重型 UI kit、第三方对话 SDK。

---

## 4. 核心架构决策

### D1 — BFF 用 Next.js Route Handler 做**透传代理**

`app/api/{chat,agent}/route.ts` 收到浏览器请求 → `fetch` 后端 `/query/stream` 或 `/agent/stream` → `return new Response(upstream.body, { SSE 头 })` 把流原样转回浏览器。BFF **不翻译协议**,只做:

- **安全收口**:后端地址 / `top_k` / 上传转发收在服务端环境变量(`RAG_API_BASE` / `AGENT_API_BASE`),前端只暴露 `/api/*`。
- **错误兜底**:`try/catch` upstream fetch,后端没起 / 4xx / 5xx 时返回干净的 502,而不是把裸网络错误甩给浏览器。
- **将来扩展**:鉴权 / 限流 / 多后端路由都在这一层加。

为什么不让浏览器直连后端(虽然 CORS=`*` 允许):关注点分离 + 安全收口 + 错误兜底(同上)。

### D2 — 客户端流式:`useStreamChat` + reducer,把语义帧累积成扁平消息

浏览器端 `lib/useStreamChat.ts` 用 `fetch` 拿到 SSE 响应体,`lib/sse.ts` 的 `parseSSE` 逐帧切出,交给按 mode 选定的 reducer(`lib/reducers.ts` 的 `ragReduce` / `agentReduce`)累积进一条扁平 `ChatMessage`:

| 后端帧 | reducer 改写 | 客户端用途 |
|---|---|---|
| `token`(N) | `draft.text += strip(frame.text)`(先剥 `<think>`) | Markdown 正文 |
| `sources`(1) | `draft.sources = frame.sources` | 引用侧栏(完整 `Source[]`) |
| `done` | `draft.conversationId = frame.conversation_id` | 下一轮请求带上(多轮) |
| `step`(agent) | 增 / 改 `draft.toolSteps`(同 `id` 原地 running→done) | 工具时间线 |
| `error`(开流后) | `throw` → hook 的 `catch` 设 error 态 | UI 错误条 + 重试 |

`useStreamChat` 还管对话状态:`status`(streaming/ready/error)、`stop`(`AbortController`)、`regenerate`、`reset`(切模式清空)。细节见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) 第 3-4 节。

### D3 — Week 12 工具可视化:LangGraph Agent 的 `/agent/stream`【后端前置依赖,已就绪】

工具执行可视化的数据源是 agent 的"它现在调了哪个工具、入参、返回"。`0910-langgraph-agent/15_agent_server.py` 已暴露 `POST /agent/stream`,把 LangGraph 的工具/步骤事件吐成 SSE:

```
step    帧 → { type:"step", id, tool:"search_knowledge_base", status:"running", input:{...} }
step    帧 → { type:"step", id, ..., status:"done", output:"..." }  // 同 id,前端按 id 原地更新
token   帧 → 最终答案逐 token(字段 content)
done    帧 → 结束(不带 conversation_id)
```

前端 `agentReduce` 把 `step` 帧累积进 `draft.toolSteps`(带稳定 `id`,running→done 靠同 id 重渲染),`ToolTimeline` 渲染成时间线。

### D4 — 流式下的 Markdown 渲染与代码高亮(踩坑预案)

逐 token 流式意味着 markdown **每来一个 token 就要重渲染整段**,有两个真实坑:
1. **性能**:每 token 重新 parse markdown + 高亮很贵。对策:`memo` 包 `Markdown`(消息引用稳定就不重算,只有正在流的那条重渲)+ 稳定 props(`useMemo`/`useCallback`);高亮选**同步、轻量**的 `rehype-highlight`,别在流式期用 `shiki`(异步、重)。长答案若仍卡,在 hook 的 `commit` 上加 ~50ms 节流。可选:消息**流完后**再用 shiki 升级终态高亮质量。
2. **半截 markdown**:流到一半时 ```` ```python ```` 代码块还没闭合、表格只有半行,渲染器会短暂渲染出残缺结构。对策:接受这个抖动(流完即正确)。

**打字机效果澄清**:后端已经是真 token 流,"打字机"不需要再造——直接渲染到达的增量即可。

---

## 5. 目录结构

```
1112-frontend/
├── PLAN.md / docs/ARCHITECTURE.md   # 本文(概览+契约+路线)/ 架构主线与实现细节
├── .env.local                       # RAG_API_BASE / AGENT_API_BASE(服务端用,不暴露给浏览器)
├── src/
│   ├── app/
│   │   ├── layout.tsx / page.tsx
│   │   └── api/
│   │       ├── chat/route.ts        # BFF 透传:RAG /query/stream → 原样转 SSE(+502 兜底)
│   │       ├── agent/route.ts       # BFF 透传:Agent /agent/stream → 原样转 SSE
│   │       └── upload/route.ts       # 透传 multipart 到 RAG /upload
│   ├── lib/
│   │   ├── sse.ts                   # 自定义 SSE 帧解析(按 \n\n 切帧 + TextDecoder stream)
│   │   ├── think.ts                 # <think> 流式剥离状态机
│   │   ├── useStreamChat.ts         # ★ 流式 hook:fetch+ReadableStream+parseSSE+reduce;管 messages/状态/stop/重试
│   │   ├── reducers.ts              # ★ ragReduce / agentReduce:语义帧 → 扁平 ChatMessage 字段(可单测)
│   │   ├── rehype-citations.ts      # [n] → <cite> 的 rehype 插件
│   │   ├── upload.ts                # XHR 上传(onprogress 进度)+ 前端校验
│   │   └── types.ts                 # Source / 帧类型(BackendFrame/AgentFrame)/ ChatMessage
│   └── components/chat/             # Chat / MessageItem / Markdown / ToolTimeline / SourcesPanel / message-utils
└── ...(next.config / tailwind / tsconfig)
```

`★` = 本项目的"真正难点 + 学习重点"所在,其余是常规前端活。

---

## 6. 数据流时序

### Week 11(RAG 流式问答)
```
用户输入 → useStreamChat.send(q, {conversation_id}) → POST /api/chat
   → route.ts(透传):fetch 后端 /query/stream(带 conversation_id)→ return upstream.body
   → 浏览器 for await (parseSSE(res.body)) 逐帧 ragReduce:
        sources 帧 ⇒ draft.sources = [...]
        token 帧   ⇒ draft.text += strip(text)
        done 帧    ⇒ draft.conversationId = ...
        每帧 setMessages
   → MessageItem → Markdown(getText) 渲染气泡;sources 喂引用侧栏
   → 下一轮 send 时从最近 assistant 的 conversationId 带上(多轮)
```

### Week 12(Agent + 工具可视化)
```
useStreamChat(/api/agent, agentReduce) → 后端 /agent/stream(透传)
   step(running) ⇒ draft.toolSteps 增一条(id, status:running, tool, input)
   step(done)    ⇒ 按同 id 原地补 output、status:done
   token(content)⇒ draft.text += strip(content)
客户端:ToolTimeline 渲染 toolSteps;MessageItem 固定「工具在上、答案在下」
```

---

## 7. Week 11 逐 Day 拆解(每步可独立验证)

| Day | 任务 | 关键点 / 验证 |
|---|---|---|
| **D1** | 项目脚手架 + 摸清后端真实帧 | `create-next-app`(TS/Tailwind);`curl -N` 实测 `/query/stream`,把 `sources`/`token`/`done` 的**真实字段名**记进 `lib/types.ts`。验证:`curl` 看到三段;`next dev` 起得来 |
| **D2** | SSE 帧解析 `lib/sse.ts` | `ReadableStream` + `TextDecoder({stream:true})` 按 `\n\n` 缓冲切帧(`parseSSE<T>`)。验证:喂一段录制的 SSE,能切出正确帧序列 |
| **D3** | BFF 透传 route + 客户端 hook | `/api/chat` 透传后端流;`useStreamChat` + `ragReduce` 逐帧累积。验证:浏览器问一句,答案逐 token 出现 |
| **D4** | 基础 Chat UI + 多轮 | 消息列表 + 输入框 + 流式渲染。验证:`conversation_id` 回填、第二轮多轮生效 |
| **D5** | 完整 Markdown 渲染 | `react-markdown` + `remark-gfm`;表格/列表/代码块正确;memo 兜重渲染(D4 坑 1)。验证:答一段带表格+代码的内容,渲染正确不抖死 |
| **D6** | 代码高亮 | `rehype-highlight`;主题样式。验证:多语言代码块高亮;流式期不卡 |

⚡ Week 11 验收:基础 Chat UI 连上 RAG 后端,流式 + 完整 Markdown + 代码高亮 + 多轮会话。

## 8. Week 12 逐 Day 拆解

| Day | 任务 | 关键点 / 验证 |
|---|---|---|
| **D1**(后端,前置) | 给 LangGraph Agent 加 `/agent/stream` | 把 `astream(stream_mode="updates")` 的工具/步骤事件 + token 吐成 SSE。验证:`curl -N /agent/stream` 看到 step + token 帧 |
| **D2** | 引用溯源 UI | 解析 answer 里的 `[n]`(`rehype-citations`)→ 连 `sources`;侧栏卡片;点 `[n]` 滚动+高亮对应卡片;点卡片展开 `content` 原文片段。验证:点 `[1]` 精确定位到来源 |
| **D3** | 工具执行可视化 | `/api/agent` 透传 step 帧;`agentReduce` 累积进 `toolSteps`;`ToolTimeline` 时间线;展示工具名、入参、返回;running→done(按 id 重渲染)。验证:问一个会触发 `search_knowledge_base` 的问题,看到"正在检索→完成 + 入参/结果" |
| **D4** | 文件上传 | 拖拽区 + XHR `upload.onprogress` 进度条 → `/upload`;成功显示 `chunk_count`。验证:拖一个 .md/.pdf 进度到 100% 并可立刻提问该文档内容 |
| **D5** | 交互体验完善 | Loading / Retry / Error 三态(对齐 2.2 的开流前/后两段错误);👍👎 反馈按钮;移动端适配。验证:断开后端看到错误态 + Retry 可重发;窄屏布局可用 |

⚡ Week 12 验收:产品级 UI(引用溯源 + 工具可视化 + 上传 + 完整交互态 + 移动端),可直接做演示 / 进作品集。

---

## 9. 风险、依赖与取舍

- **R1(依赖)**:Week 12 工具可视化依赖 LangGraph Agent 的 `/agent/stream`(决策 D3)。**已就绪**(`15_agent_server.py`)。
- **R2(取舍)**:上传/会话列表这类非流式调用,因后端 CORS=`*`,理论上浏览器可直连后端。默认仍走 BFF 透传以保持一致 + 为将来鉴权留口。
- **R3(已确认)**:`/query/stream` token 字段是 `text`、agent 是 `content`,以 `curl` 实测为准(2.2)。
- **R4(性能)**:流式 markdown 逐 token 重渲染 + 高亮的开销(决策 D4);用 memo + 轻量高亮兜住,必要时给 `commit` 加节流。
- **R5(无鉴权/无用户系统)**:后端用 `conversation_id` 隔离、无用户体系。前端同样不做登录,会话存浏览器 + 后端。作品演示足够,简历上诚实标注。

---

## 10. 决策点(已定)

1. **后端范围**:✅ 不用 mock —— `0910` 已补 agent `/agent/stream`(R1/D3)。
2. **样式**:✅ Tailwind 裸写,不引 shadcn/ui。
3. **流式方案**:✅ 客户端 `fetch + ReadableStream` 自写 `useStreamChat`,BFF 只透传,不引第三方对话 SDK。
4. **上传走 BFF 还是直传**(R2):统一走 BFF。

---

## 11. 参考

- 后端契约源:`0607-rag-service/app/routers/{upload,query,conversation}.py`、`app/schemas.py`、`web/index.html`(`streamQuery` 的 SSE 读法可直接参考)
- Agent 服务:`0910-langgraph-agent/15_agent_server.py`(`/agent/stream`)、`11_demo_rag_agent.py`(RAG 作为工具)
- 前端架构主线与实现细节:[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

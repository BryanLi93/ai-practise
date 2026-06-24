# 1112-frontend — 项目架构 Plan(Week 11-12 产品级前端)

> 24 周路线里的位置:Week 9-10 LangGraph Agent 之后、Week 13-14 评测之前。
> 目标:把 `0607-rag-service`(以及后续的 LangGraph Agent)包装成一个**可演示、可投简历**的产品级前端。
> 后端契约状态:已于 2026-06-16 对照 `0607-rag-service` 源码核对(见第 2 节)。本文是动工前的架构决策稿,逐 Day 拆解在第 7、8 节。

> ⚠️ **2026-06-24 架构已变更,本文是历史决策稿,保留以记录当初的取舍。**
> 当初选了 **D1/D2:Next BFF 适配器把后端自定义 SSE 翻译成 Vercel AI SDK 协议、前端用 `useChat` 消费**。落地后发现这层翻译纯粹为了迁就 `useChat`,遂**弃用 AI SDK**:BFF 改为**原样透传** SSE,浏览器用自写的 `useStreamChat`(`fetch` + `ReadableStream` + `parseSSE`)直接读、用 reducer 累积成扁平 `ChatMessage`。`lib/adapter.ts` 已删,`ai` / `@ai-sdk/react` 依赖已移除。
> 凡本文提到 `useChat` / `createUIMessageStream` / `adapter.ts` / AI SDK「部件 parts」之处,均为**旧设计**;当前架构以 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) 为准。

---

## 0. 一句话定位

一个 **Next.js(App Router)+ Vercel AI SDK** 的 RAG / Agent 聊天前端,核心不是"再写一个 ChatGPT 壳",而是把后端**已经产出但当前 `web/index.html` 没充分展示**的能力(流式、引用溯源 `[n]`、多轮会话、将来的工具调用)用产品级 UI 呈现出来。

定位差异(相对后端自带的 `0607-rag-service/web/index.html`):那个是 vanilla JS 单文件、用来验证后端通不通;本项目是带构建、带组件化、带类型安全的正式前端,**面试时作为"前端背景 + AI 应用"的作品**。

---

## 1. 这个前端到底连谁(关键前提)

| 后端 | 现状 | 本项目怎么用 |
|---|---|---|
| `0607-rag-service` | ✅ 真实 HTTP 服务(`:8000`),有 `/query/stream` SSE、`/upload`、`/conversations` | **Week 11 的主后端**。流式问答、引用、上传、多轮全都连它 |
| `0910-langgraph-agent` | ⚠️ 当前是一组学习脚本(`01`~`13`.py),**没有 HTTP 服务**;`11_demo_rag_agent.py` 已把 RAG `/query` 包成 agent 工具 | **Week 12 工具可视化的目标**,但需要先给它加一个 SSE 端点(见决策 D3 / 风险 R1) |

**结论**:Week 11 完全可以现在就开工(后端 ready)。Week 12 的"工具执行可视化"有一个**后端前置依赖**——LangGraph Agent 必须先暴露一个流式端点,把它的 `astream(stream_mode="updates")` 工具/步骤事件吐出来。这件事不在前端项目代码里,但必须在 Week 12 之前完成,本文按"它会被补上"来规划。

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

CORS:`allow_origins=["*"]`(学习阶段宽松),所以浏览器**可以**直连后端;但本项目默认走 BFF(见 D1),不依赖这个宽松配置。

### 2.2 流式帧协议(`/query/stream`,这是适配层的核心)

后端是**自定义 SSE**,不是 Vercel AI SDK 协议。每帧编码为 `data: {json}\n\n`,顺序固定:

```
sources 帧 (1 条)  → { "type":"sources", "sources":[ Source, ... ] }
token   帧 (N 条)  → { "type":"token", "text":"..." }     // ⚠️ 字段是 text,不是 content
done    帧 (1 条)  → { "type":"done", "conversation_id":"..." }
error   帧 (开流后中途失败) → { "type":"error", "message":"..." }
```

错误分两段(后端已这样设计,前端要对齐):
- **开流前**(会话不存在 / 检索失败):返回 HTTP 404 / 502,能正常映射状态码。
- **开流后**(生成中途失败):HTTP 200 已发出,只能塞一条 `error` 帧。

> ✅ 已实测确认(2026-06-17,`curl /query/stream`):token 帧字段是 **`text`**(不是 content)。另一个坑:token 文本里会**先夹一段 `<think>...</think>` 推理**(中转站模型 gpt-5.4 会吐思考),前端要把 think 段从答案正文里剥掉,或单独折叠展示,别当正文渲染。

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
| 框架 | **Next.js 15 App Router + React 19 + TypeScript** | 你的主场;App Router 的 Route Handler 天然就是 BFF 适配层(D1) |
| AI 集成 | **Vercel AI SDK v5(`ai`)** + `@ai-sdk/openai` | `useChat` 管对话状态 + 流式;`createUIMessageStream` 做协议适配。⚠️ 安装时确认主版本(2026 年可能已到 v6,API 名一致但需核对) |
| Markdown | `react-markdown` + `remark-gfm` | gfm 负责表格/任务列表/删除线的正确渲染 |
| 代码高亮 | **`rehype-highlight`(流式期)** + 可选 `shiki`(终态) | 见 D4:流式逐 token 重渲染时 shiki 太重,先用同步的 rehype-highlight |
| 样式 | **Tailwind CSS**(不引 shadcn/ui,见决策点 2) | 核心组件裸写,需要时再说 |
| 上传进度 | `XMLHttpRequest` 或 fetch + `ReadableStream` 读上传进度 | `fetch` 原生不报上传进度,拖拽进度条用 XHR 的 `upload.onprogress` 最省事 |

不引入的:状态管理库(useChat + React state 够用)、tRPC(BFF 直接写 Route Handler)、重型 UI kit。

---

## 4. 核心架构决策

### D1 — 用 Next.js Route Handler 做 BFF 适配层(把自定义 SSE 翻译成 AI SDK 协议)【推荐】

> ⚠️ 已变更(2026-06-24):当初选了 A(BFF 适配器),后来弃用 AI SDK,BFF 改为纯透传、翻译挪到浏览器端 reducer。下面的取舍分析作为当初的决策记录保留。

**问题**:`useChat` 期望 AI SDK 的 **UI Message Stream** 协议;后端吐的是自定义 `sources/token/done` SSE。两者不兼容。

**三个选项**:
- **A(推荐)BFF Route Handler**:`app/api/chat/route.ts` 收到 `useChat` 请求 → 调后端 `/query/stream` → 解析自定义 SSE → 用 `createUIMessageStream` 重新吐成 AI SDK 协议(文本 + 自定义 data 部件)。
- B 客户端自定义 transport:`useChat` 配自定义 `fetch`/transport 直连后端、客户端翻译帧。少一跳,但放弃了 SDK 的大部分能力,浏览器直连后端(将来加鉴权/限流难)。
- C 改后端协议:让 FastAPI 直接吐 AI SDK 协议。**不选**——会把后端绑死到某个前端 SDK,违背后端解耦原则。

**选 A**。理由:这是 Next.js + AI SDK 的标准生产形态,后端保持解耦;后端密钥/地址藏在服务端;将来加鉴权/限流/多后端路由都在这一层;而**写这个适配器本身就是本项目最有价值的学习内容**(协议翻译、流的合并、错误分段)。代价是多一跳 + 要手写适配器,但这正是要练的东西。

### D2 — 后端帧 ↔ AI SDK 部件的映射(适配器具体怎么翻)

AI SDK v5 服务端用 `createUIMessageStream({ execute({ writer }) {...} })` + `createUIMessageStreamResponse()`;`writer.write({ type, ... })` 写部件;客户端 `useChat` 用 `message.parts`(持久部件)和 `onData`(瞬时部件)消费。映射如下:

| 后端帧 | 适配器动作 | 客户端消费 |
|---|---|---|
| `token`(N) | 累积成文本流,`writer` 写文本增量(或 `writer.merge` 一个文本流) | 自动进 `message.parts` 的 text 部件 → 渲染气泡 |
| `sources`(1) | 写一个**自定义** `data-citations` 持久部件(承载完整 `Source[]`) | `message.parts.filter(p => p.type==='data-citations')` → 引用侧栏 |
| `done` | 写 `data-meta`(可设 `transient:true`)带 `conversation_id` | `onData` 里存下 `conversation_id`,下一轮请求带上(多轮) |
| `error`(开流后) | `writer` 写错误 / 抛出 | UI 显示错误态 + Retry |

为什么引用用**自定义** `data-citations` 而不是 AI SDK 原生 `source` 部件:原生 `source` 偏向 URL 来源,而我们要带 `chunk content / similarity / chunk_index / [n] 的 id`,自定义部件能完整承载、且支持按 `id` 重渲染(reconciliation)。

> AI SDK v5 自定义数据部件 / `createUIMessageStream` 用法见官方文档(第 11 节链接)。

### D3 — Week 12 工具可视化:先给 LangGraph Agent 加一个流式端点【前置依赖】

工具执行可视化的数据源是 agent 的"它现在调了哪个工具、入参、返回"。`0910` 里这些信息存在于 `agent.astream(stream_mode="updates")` / `astream_events`,但没有 HTTP 出口。

**方案**:在 `0910-langgraph-agent` 加一个最小 FastAPI 端点(例如 `POST /agent/stream`),把 LangGraph 的工具/步骤事件吐成 SSE:
```
step    帧 → { type:"step", tool:"search_knowledge_base", status:"running", input:{...} }
step    帧 → { type:"step", tool:"search_knowledge_base", status:"done", output:{...} }  // 同一 step,带 id,前端按 id 更新
token   帧 → 最终答案逐 token
sources / done → 复用 RAG 那套
```
前端适配器把 `step` 帧映射成**自定义 `data-tool-step` 部件**(带稳定 `id`,running→done 靠同 id 重渲染),客户端渲染成时间线 / 进度条。

这一端点是**后端工作**,不在本前端项目里;但 Week 12 开工前必须存在。它本身是 Week 9-10 agent 的自然延伸(把脚本变服务),工作量不大。

### D4 — 流式下的 Markdown 渲染与代码高亮(踩坑预案)

逐 token 流式意味着 markdown **每来一个 token 就要重渲染整段**,有两个真实坑:
1. **性能**:每 token 重新 parse markdown + 高亮很贵。对策:用 AI SDK 的 `experimental_throttle`(或自己节流到 ~30-60ms)合并重渲染;高亮选**同步、轻量**的 `rehype-highlight`,别在流式期用 `shiki`(异步、重)。可选:消息**流完后**再用 shiki 升级终态高亮质量。
2. **半截 markdown**:流到一半时 ```` ```python ```` 代码块还没闭合、表格只有半行,渲染器会短暂渲染出残缺结构。对策:接受这个抖动(流完即正确),或对未闭合代码块做容错补全。

**打字机效果澄清**:后端已经是真 token 流,"打字机"不需要再造——直接渲染到达的增量即可。若想更顺滑,用 AI SDK 的平滑/节流,**不要**在真流之上再叠一个假打字机(会双重缓冲、延迟翻倍)。

---

## 5. 目录结构(规划)

```
1112-frontend/
├── PLAN.md                      # 本文件
├── .env.local                   # RAG_API_BASE=http://127.0.0.1:8000  AGENT_API_BASE=...  (服务端用,不暴露给浏览器)
├── app/
│   ├── layout.tsx / page.tsx    # 聊天主界面
│   ├── api/
│   │   ├── chat/route.ts        # ★ BFF 适配器:RAG /query/stream → AI SDK UI Message Stream(D1/D2)
│   │   ├── agent/route.ts       # ★ Week 12:Agent /agent/stream → AI SDK + 工具步骤部件(D3)
│   │   ├── upload/route.ts      # 透传到 /upload(或前端直传,见 R2)
│   │   └── conversations/...    # 会话列表/详情/删除的透传
│   └── components/
│       ├── chat/                # 消息列表、气泡、输入框(useChat 驱动)
│       ├── markdown/            # react-markdown + remark-gfm + rehype-highlight 封装 + [n] 自定义渲染
│       ├── citations/           # 引用侧栏卡片 + [n] 点击联动
│       ├── tools/               # Week 12:工具调用时间线 / 进度条
│       └── upload/              # 拖拽上传 + 进度条
├── lib/
│   ├── sse.ts                   # 自定义 SSE 帧解析(按 \n\n 切帧 + TextDecoder stream)
│   ├── adapter.ts               # 【已删 2026-06-24】帧 → AI SDK 部件映射;现由客户端 useStreamChat + reducers.ts 取代
│   └── types.ts                 # Source / 帧类型 / UIMessage 泛型(与后端 schema 对齐)
└── ...(next.config / tailwind / tsconfig)
```

`★` = 本项目的"真正难点 + 学习重点"所在,其余是常规前端活。

---

## 6. 数据流时序

### Week 11(RAG 流式问答)
```
用户输入 → useChat 发到 /api/chat/route.ts (BFF)
   → BFF fetch 后端 /query/stream (带 conversation_id)
   → 读自定义 SSE:sources → token×N → done
   → createUIMessageStream:
        sources 帧  ⇒ writer.write(data-citations)
        token 帧    ⇒ writer 写文本增量
        done 帧     ⇒ writer.write(data-meta: conversation_id, transient)
   → createUIMessageStreamResponse() 回给浏览器
客户端 useChat:
   message.parts 里 text 部件 → markdown 气泡(节流重渲染)
   data-citations 部件 → 引用侧栏;answer 里的 [n] 点击 → 高亮/滚动到对应卡片
   onData 拿 conversation_id → 存起来,下一轮带上
```

### Week 12(Agent + 工具可视化)
```
/api/agent/route.ts → 后端 /agent/stream
   step(running) ⇒ data-tool-step(id, status:running, tool, input)
   step(done)    ⇒ data-tool-step(同 id, status:done, output)   // 按 id 原地更新
   token / sources / done ⇒ 同 Week 11
客户端:data-tool-step 部件按到达顺序渲染成时间线;running→done 切状态;最终答案与引用照旧
```

---

## 7. Week 11 逐 Day 拆解(每步可独立验证)

| Day | 任务 | 关键点 / 验证 |
|---|---|---|
| **D1** | 项目脚手架 + 摸清后端真实帧 | `create-next-app`(TS/Tailwind);`curl -N` 实测 `/query/stream`,把 `sources`/`token`/`done` 的**真实字段名**记进 `lib/types.ts`(对齐 2.2 的待确认项)。验证:`curl` 看到三段;`next dev` 起得来 |
| **D2** | SSE 帧解析 `lib/sse.ts` | `fetch` + `ReadableStream` + `TextDecoder({stream:true})` 按 `\n\n` 缓冲切帧(参考后端 `web/index.html` 的 `streamQuery`)。验证:Node 脚本 / 单测喂一段录制的 SSE,能切出正确帧序列 |
| **D3** | BFF 适配器 `/api/chat/route.ts` + `lib/adapter.ts` | D1/D2 落地:帧 → `createUIMessageStream` 部件(D2 映射表)。验证:浏览器直接打 `/api/chat` 看到 AI SDK 协议输出 |
| **D4** | 接 `useChat`,基础 Chat UI | 消息列表 + 输入框 + 流式渲染(纯文本先)。验证:问一句,答案逐 token 出现;`conversation_id` 回填、第二轮多轮生效 |
| **D5** | 完整 Markdown 渲染 | `react-markdown` + `remark-gfm`;表格/列表/代码块正确;节流重渲染(D4 坑 1)。验证:让后端答一段带表格+代码的内容,渲染正确不抖死 |
| **D6** | 代码高亮 | `rehype-highlight`;主题样式。验证:多语言代码块高亮;流式期不卡 |

⚡ Week 11 验收:基础 Chat UI 连上 RAG 后端,流式 + 完整 Markdown + 代码高亮 + 多轮会话。

## 8. Week 12 逐 Day 拆解

| Day | 任务 | 关键点 / 验证 |
|---|---|---|
| **D1**(后端,前置) | 给 LangGraph Agent 加 `/agent/stream`(决策 D3) | 把 `astream(stream_mode="updates")` 的工具/步骤事件 + token 吐成 SSE。验证:`curl -N /agent/stream` 看到 step + token 帧 |
| **D2** | 引用溯源 UI | 解析 answer 里的 `[n]`(react-markdown 自定义组件/rehype 插件)→ 连 `data-citations`;侧栏卡片;点 `[n]` 滚动+高亮对应卡片;点卡片展开 `content` 原文片段。验证:点 `[1]` 精确定位到来源 |
| **D3** | 工具执行可视化 | `/api/agent/route.ts` 适配 step 帧 → `data-tool-step`;时间线/进度条组件;展示工具名、入参、返回;running→done 状态切换(按 id 重渲染)。验证:问一个会触发 `search_knowledge_base` 的问题,看到"正在检索→完成 + 入参/结果" |
| **D4** | 文件上传 | 拖拽区 + XHR `upload.onprogress` 进度条 → `/upload`;成功显示 `chunk_count`。验证:拖一个 .md/.pdf 进度到 100% 并可立刻提问该文档内容 |
| **D5** | 交互体验完善 | Loading / Retry / Error 三态(对齐 2.2 的开流前/后两段错误);👍👎 反馈按钮;移动端适配。验证:断开后端看到错误态 + Retry 可重发;窄屏布局可用 |

⚡ Week 12 验收:产品级 UI(引用溯源 + 工具可视化 + 上传 + 完整交互态 + 移动端),可直接做演示 / 进作品集。

---

## 9. 风险、依赖与取舍

- **R1(依赖,最关键)**:Week 12 工具可视化依赖 LangGraph Agent 先有 `/agent/stream`(决策 D3)。**不属于本前端项目代码**,但 Week 12 前必须就绪。Week 11 不受影响,可立即开工。
- **R2(取舍)**:上传/会话列表这类非流式调用,因后端 CORS=`*`,理论上浏览器可直连后端。默认仍走 BFF 透传以保持一致 + 为将来鉴权留口;若想省事,上传可前端直传(评估后定)。
- **R3(待确认)**:`/query/stream` 帧的内层字段名以 `curl` 实测为准(2.2 末尾标注),不要凭后端 schema 猜——`handle_chat_stream` 产出的是语义帧 dict。
- **R4(性能)**:流式 markdown 逐 token 重渲染 + 高亮的开销(决策 D4);用节流 + 轻量高亮兜住。
- **R5(无鉴权/无用户系统)**:后端用 `conversation_id` 隔离、无用户体系(后端有意跳过)。前端同样不做登录,会话存浏览器 + 后端。作品演示足够,简历上诚实标注。
- **R6(版本漂移)**:Vercel AI SDK 在 v4→v5→v6 之间 API 名有变动(`useChat` 的部件模型、transport)。安装时核对当前主版本与本文 D2 的 API 名,以官方文档为准,别凭记忆。

---

## 10. 决策点(已定,2026-06-17)

1. **后端范围**:✅ 不用 mock —— 直接在 `0910` 里补 agent `/agent/stream`(R1/D3)。落地顺序:① `curl` 实测 RAG `/query/stream` 帧字段(R3)→ ② 写 agent `/agent/stream` → ③ 前端 BFF 适配器(D1/D2)对着两个真协议写。
2. **样式**:✅ Tailwind 裸写,不引 shadcn/ui。
3. **上传走 BFF 还是直传**(R2):暂定统一走 BFF。

> 提醒:D1/D2(BFF 适配器)是**前端项目**里的 Next.js Route Handler 服务端代码;R1/D3(`/agent/stream`)才是**后端项目** `0910` 里的 FastAPI 端点。两者分属两边,别混。

Week 11 可立即开工(D1~D3 与 RAG 后端直接相关)。

---

## 11. 参考

- 后端契约源:`0607-rag-service/app/routers/{upload,query,conversation}.py`、`app/schemas.py`、`web/index.html`(`streamQuery` 的 SSE 读法可直接参考)
- Agent 工具样例:`0910-langgraph-agent/11_demo_rag_agent.py`(RAG 作为工具)、`12_streaming_by_claude.py`(`astream` 流式)
- AI SDK 自定义数据流:<https://ai-sdk.dev/docs/ai-sdk-ui/streaming-data>
- AI SDK 5 发布说明:<https://vercel.com/blog/ai-sdk-5>
</content>
</invoke>

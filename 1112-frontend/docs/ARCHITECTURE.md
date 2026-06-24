# 前端流式问答 —— 架构与设计笔记(Week 11 + 12)

> 这份文档用于面试讲解,也是给自己理清逻辑用的。
> **第一部分(1–6 节)是主干**:严格按依赖顺序往下读,读完就能在白板上把整条数据流讲清楚。
> **第二部分(7–11 节)是难点深挖**:被追问时再展开。
> **第三部分(12–13 节)是速查**:文件地图 + 速答卡。
> 全程跟着同一个例子走:用户问「什么是 RAG?」,答案里带一个引用 `[2]`。
>
> 📌 2026-06-24 架构变更:**弃用 Vercel AI SDK / `useChat`**。原方案是一层 BFF 适配器,把后端自定义 SSE 翻译成 AI SDK 协议再喂 `useChat`;后来意识到这层翻译纯粹是为了迁就 `useChat`,去掉它后整层适配器一起删。现在 BFF 只做**透传**,浏览器用自写的 `useStreamChat`(fetch + ReadableStream)直接读后端 SSE。本文已按新架构重写。

---

# 第一部分 · 架构主干

## 1. 一句话定位

这是一个 Next.js(App Router)前端,加一层**薄 BFF 透传代理**。Python 后端(RAG / Agent)吐自定义 SSE 流,BFF 原样转给浏览器;浏览器用自写的 `useStreamChat` Hook(`fetch` + `ReadableStream`)直接读这串 SSE,把每一帧**累积进一条扁平消息对象**,再渲染成流式答案、引用卡片、工具时间线。

技术栈:Next.js 16(App Router、`src/` 布局)· React 19 · Tailwind v4 · react-markdown + remark-gfm + rehype-highlight。**不依赖 Vercel AI SDK**(`ai` / `@ai-sdk/react` 已移除)。

> 为什么没用现成的 `useChat`?它要求后端按 AI SDK 自己的 **UI Message Stream** 协议说话。我的后端吐的是干净的自定义 SSE(`sources/token/done`),为了喂 `useChat` 得先在服务端写一层适配器把它翻成 AI SDK 协议——等于**翻译两次**(后端 SSE → AI SDK 协议 → `useChat` 解回对象)。既然 SSE 解析我自己用 `parseSSE` 就能做,索性去掉 `useChat`,那层适配器也随之消失。代价是 `messages` 状态、`stop`、重试这些 `useChat` 白送的东西要自己实现(约 70 行),换来的是**少一整层协议 + 代码全在自己掌控**。

---

## 2. 三个进程,以及为什么还要 BFF 这一层

```
┌──────────────────────┐   /api/chat      ┌────────────────────┐  /query/stream   ┌──────────────┐
│  浏览器               │  ─────────────►  │  Next.js BFF        │  ─────────────►  │ RAG 服务      │
│  fetch+useStreamChat  │                  │  :3000              │                  │ FastAPI :8000 │
│                       │  ◄─────────────  │  (透传代理)         │  ◄─────────────  │ pgvector/LLM │
└──────────────────────┘   自定义 SSE(原样) │                    │   自定义 SSE      └──────────────┘
                                           │                    │   /agent/stream  ┌──────────────┐
                                           │  /api/agent ───────┼────────────────► │ Agent 服务    │
                                           │  /api/upload ──────┤                  │ LangGraph     │
                                           └────────────────────┘                  │ :8100         │
                                                                                   └──────────────┘
```

- **浏览器**:只跟 `/api/*` 通信,不知道后端地址,也不直接调模型。
- **Next BFF(本项目)**:**透传** SSE + 请求裁剪 + 错误兜底。不再做协议翻译。
- **RAG :8000 / Agent :8100**:真正干活的 Python 后端,负责检索、LLM、会话持久化、工具调用。

**既然 BFF 不翻译了,为什么不让浏览器直连后端?** 三点:

1. **关注点分离**:LLM、检索、会话持久化、Agent 工具循环都在 Python 后端,前端不重复实现。
2. **安全收口**:后端地址、`top_k`、上传转发都收在服务端环境变量里(`RAG_API_BASE` / `AGENT_API_BASE`),前端只暴露 `/api/*`;将来加鉴权 / 限流 / 多后端路由都在这一层。
3. **错误兜底**:后端没起 / 连不上时,route 里 `try/catch` 返回一个干净的 502,而不是把裸网络错误甩给浏览器(见 [11])。

> 前端类比:这层就是 BFF / API 网关——前端不直连微服务,中间过一层 gateway 做转发、收口、裁剪。区别于旧版的是:它现在**只转发,不做业务翻译**,翻译挪到了浏览器端的 reducer。

---

## 3. 核心模型:把「后端语义帧」累积成「一条扁平消息」

整个项目就这一件事。先把两边的数据长什么样摆出来,再看 reducer 怎么把左边累积成右边。

### 3.1 后端给的:一串「语义帧」

后端用 SSE 流式返回,每帧是一行 `data: {json}\n\n`,描述「刚发生了什么」。RAG 模式的帧,顺序固定是 `sources(1) → token(N) → done(1)`:

```
data: {"type":"sources","sources":[{"id":1,...},{"id":2,...},{"id":3,...}]}
data: {"type":"token","text":"RAG "}
data: {"type":"token","text":"指检索增强生成,"}
data: {"type":"token","text":"先检索[2]再生成。"}
data: {"type":"done","conversation_id":"c-abc"}
```

帧的语义:`sources` = 这次检索到哪些来源;`token` = 答案的一小段文字(逐 token 来);`done` = 结束,附带这轮的会话 id。中途出错会插一条 `{"type":"error"}`。

(Agent 模式的帧略有不同,见 [8],但累积思路完全一样。)

### 3.2 前端要的:一条消息 = 一个扁平字段对象

旧版这里是 AI SDK 的「有序 `parts[]` 数组」。新版换成一个**字段扁平**的 `ChatMessage`(`lib/types.ts`):

```ts
interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;                 // 答案正文(已剥 <think>)
  sources?: Source[];           // RAG 引用来源
  toolSteps?: { id; data }[];   // Agent 工具时间线
  conversationId?: string;      // RAG 多轮:下一轮带上
}
```

每种信息各占一个字段,渲染端直接取字段——不用再遍历/过滤一个混放各种部件的数组。

### 3.3 reducer 做的:把左边逐帧累积进右边

对着同一个例子,reducer 消费完所有帧后,那条 assistant 消息长这样:

```ts
{
  role: "assistant",
  text: "RAG 指检索增强生成,先检索[2]再生成。",  // 3 个 token 累积
  sources: [ /* 3 条来源 */ ],                     // sources 帧
  conversationId: "c-abc",                         // done 帧
}
```

把 3.1 和 3.3 并排看,reducer(`ragReduce`,在 `lib/reducers.ts`)的全部工作就是这张映射表:

| 后端帧 | reducer 改写 | 前端用途 |
|---|---|---|
| `sources` | `draft.sources = frame.sources` | 来源侧栏 |
| `token` × N | `draft.text += strip(frame.text)` | Markdown 正文 |
| `step`(agent) | 增 / 改 `draft.toolSteps`(同 id) | 工具时间线 |
| `done.conversation_id` | `draft.conversationId = …` | 下一轮带上 |
| `error` | `throw` → hook 的 catch | 顶部错误条 |

记住这张表,后面所有细节都是它的展开。对比旧版那张「映射成 `data-citations` / `text-start/delta/end` / transient」的表——少了一整套 AI SDK 协议词汇,剩下的就是「这一帧改消息的哪个字段」。

### 3.4 没有 transient 了:conversation_id 直接挂消息上

旧版 `conversation_id` 是个「不进正文、走旁路 `onData` 回调、存进 ref」的 transient 事件。新版直接把它写进消息的 `conversationId` 字段。下一轮发请求时,从「最近一条 assistant 消息」读它带上(见 [10])——删掉了 ref 和旁路回调。

> 一句话抓住本质:**后端流 = 一串「发生了什么」的语义事件;前端消息 = 一个「该渲染什么」的扁平对象;reducer 就是把事件逐帧累积进这个对象的纯函数。**

---

## 4. 流式管道:通用 hook + 每模式 reducer 两层

旧版这里是「适配器的三条翻译规则」(文本分段开关 `text-start/end`、data part 按 id 更新、transient 不进 parts)。前两条是 AI SDK 协议的仪式,去掉协议后**只剩一条规则活下来**(工具按 id 原地更新),其余都化简成普通字段赋值。现在分两层:

**第一层:通用流式管道 `useStreamChat`(`lib/useStreamChat.ts`)。** 不关心帧的语义,只管 fetch、读流、把每帧交给 reducer、触发重渲染:

```ts
const res = await fetch(api, { method: "POST", body: JSON.stringify({ question, ...body }), signal });
for await (const frame of parseSSE(res.body)) {
  reduce(frame, draft, strip.push);                  // 这一帧改写草稿的哪个字段
  commit(messages.map(m => m.id === draft.id ? { ...draft } : m));  // 每帧 setMessages → 流式刷新
}
```

它还顺手管了 `useChat` 白送的那些:`status`(ready/streaming/error)、`stop`(`AbortController.abort`)、`regenerate`(回退到最后一条 user 重发)、`reset`(切模式清空)。`<think>` 剥离器作为 `strip` 注入给 reducer。

**第二层:每模式的 reducer(`lib/reducers.ts`)。** 纯函数,`switch` 帧 type 改 `draft` 字段,就是 3.3 那张表:

```ts
function ragReduce(frame, draft, strip) {
  switch (frame.type) {
    case "sources": draft.sources = frame.sources; break;
    case "token":   draft.text += strip(frame.text); break;
    case "done":    draft.conversationId = frame.conversation_id; break;
    case "error":   throw new Error(frame.message);
  }
}
```

**唯一活下来的「规则」:工具步骤按 id 原地更新。** Agent 的工具 `running` 和 `done` 两帧用**同一个 id**:`agentReduce` 在 `running` 时往 `draft.toolSteps` push 一条,在 `done` 时按 id `map` 找到那条、原地补上 `output`。卡片就从「⏳ 调用中」变成「✅ 完成」。这叫按 id 协调(reconciliation),心智模型就是 React 的 `key`——只是现在它是一次普通的数组 `map`,不再是协议指令。

> hook 那层的 `reduce` 形参是 `frame: unknown`(后端 JSON 的动态边界),进了具体 reducer 才精确成 `BackendFrame` / `AgentFrame`;Chat 按 mode 选定 reducer 时 `as Reduce` 跨过这个边界。

---

## 5. 端到端走一遍:一个 token 从后端到屏幕

有了模型,现在把 `"先检索[2]再生成。"` 这一段 token 的完整旅程串起来:

```
① 用户回车
   Chat.tsx send() → useStreamChat.send(q, { conversation_id })   // 从最近 assistant 取 conversationId

② hook POST /api/chat
   body = { question: q, conversation_id }

③ route.ts(POST):
   - fetch 后端 /query/stream(try/catch:连不上就返回干净的 502)
   - 拿到响应体后:return new Response(upstream.body, { SSE 头 })   ← 透传,不翻译

④ 浏览器 hook 的 for await (parseSSE(res.body)) 逐帧 reduce:
   sources → draft.sources = [...]
   token   → 先剥 <think>,再 draft.text += "先检索[2]再生成。"
   done    → draft.conversationId = "c-abc"
   每帧 commit → setMessages

⑤ React 重渲染:MessageItem → MessageContent → <Markdown> 把累积文本渲染成 Markdown,
   sources 喂给右侧来源栏
```

一句话:**后端语义帧 →(BFF 透传)→ 浏览器 parseSSE 逐帧 → reducer 累积进扁平消息 → React 渲染**。和旧版比,中间那跳从「适配器翻译成 AI SDK 协议、再由 useChat 解回 parts」缩成了「原样透传、浏览器自己读」。

---

## 6. 前端怎么消费这条消息

组件做的事就是「按字段各取所需」。三个工具函数(`message-utils.ts`)把消息解读成视图要的东西——**它们的签名和旧版一模一样**(只是内部从「过滤 parts 数组」改成「读字段」),所以 `MessageItem` / `ToolTimeline` / `SourcesPanel` 这些消费方**一行没改**:

```ts
getText(m)      // m.text                  → 答案正文
getSources(m)   // m.sources ?? []         → Source[]
getToolSteps(m) // m.toolSteps ?? []       → 工具步骤列表
```

`MessageItem` 据此渲染:工具时间线在上(它是为产出答案做的前置工作),答案正文在下,底部是「来源 N」按钮和反馈。整条链是:

```
useStreamChat(messages)
  → Chat.tsx 遍历 messages
    → MessageItem(单条消息)
      → ToolTimeline(getToolSteps)            工具卡片
      → MessageContent → Markdown(getText)    答案正文
      → 「📚 来源」按钮(getSources)          点开右侧来源栏
```

来源栏 `SourcesPanel` 是**全局唯一一个**,但要显示**某条消息**的来源,所以它的状态被提升到了 `Chat`(见 [9])。

> 这个「签名不变的 message-utils」是这次重构的接缝:消息模型从 `parts[]` 换成扁平对象,改动被挡在 `message-utils.ts` 这一层里,下游组件无感。

---

# 第二部分 · 难点深挖

## 7. `<think>` 流式剥离状态机

**问题**:中转模型会在正文前输出一段 `<think>...</think>` 推理,要剥掉(旧版在服务端适配器里做,新版挪到客户端 hook 里做,逻辑一字未改)。难点是 token 逐段到达,`</think>` 这个标记可能被切在两个 token 里(先到 `</thi`,再到 `nk>`)。

**为什么不能 `String.replace`**:replace 只能处理完整字符串;流式场景下手上的标记是残缺的。

**做法**(`lib/think.ts`):一个跨 chunk 的状态机,有 `text` / `think` 两个状态。核心是「保守消费长度」函数 `safeLen`——只消费能确定的部分,把可能是半截标记的尾巴留到下次:

```ts
function safeLen(buf: string, tag: string): number {
  const max = Math.min(buf.length, tag.length - 1);
  for (let k = max; k > 0; k--) {
    if (tag.startsWith(buf.slice(buf.length - k))) return buf.length - k; // 末尾是 tag 前缀,留住
  }
  return buf.length;
}
```

**逐字符走一遍**(状态 = text,buf = `"答案<thi"`,tag = `"<think>"` 长 7):

- `max = min(6, 6) = 6`
- k=6:`"答案<thi"`,`"<think>".startsWith("答案<thi")`? 否
- k=5:`"案<thi"`? 否
- k=4:`"<thi"`,`"<think>".startsWith("<thi")`? **是** → 返回 `6-4 = 2`

于是输出前 2 个字 `"答案"`,把 `"<thi"` 留到下一段(carry)。下段来 `"nk>正文"`,拼成 `"<think>正文"`,命中完整 `<think>`,进入 think 状态丢弃内容,直到 `</think>` 才切回 text。流结束时 `flush()`:text 状态下 carry 是真实正文要补出,think 状态下未闭合就丢弃。

> 这是经典的流式解析 / 拆包问题,和「解析 TCP 字节流、chunked 传输里一条消息被拆成多包」同一类。在 hook 里,它是 `const strip = createThinkStripper()`,`strip.push` 注入给 reducer 逐帧调用,`strip.flush()` 在流结束补尾。

---

## 8. Agent:token 与工具交替,扁平字段天然保住顺序

**现象**:Agent 的帧是交替来的——先 `token`(前导:「我先查一下知识库…」)→ `step`(工具)→ 再 `token`(最终答案)。它的 token 字段叫 `content`(不是 RAG 的 `text`),done 不带 conversation_id,也没有 sources 帧。

**旧版的纠结**:它用「有序 `parts[]` 数组」,所以得费劲保住数组顺序——遇到 `step` 就 `text-end` 收掉当前文本段、下个 token 再开新段(「分段 text part」),好让 parts 是 `[前导, 工具, 答案]`。

**新版直接没有这个问题**:token 全累积进一个 `draft.text`,step 全累积进 `draft.toolSteps`,两个字段互不干扰。阅读顺序不靠数组,而靠 `MessageItem` 的**固定渲染顺序**:工具时间线永远在上、答案正文永远在下。

```ts
function agentReduce(frame, draft, strip) {
  switch (frame.type) {
    case "token": draft.text += strip(frame.content); break;          // ⚠️ 字段是 content
    case "step":
      if (frame.status === "running")
        draft.toolSteps = [...(draft.toolSteps ?? []), { id: frame.id, data: { tool: frame.tool, status: "running", input: frame.input } }];
      else  // done 帧只带 output,按 id 找到那条 running 原地补
        draft.toolSteps = (draft.toolSteps ?? []).map(s =>
          s.id === frame.id ? { id: s.id, data: { ...s.data, status: "done", output: frame.output } } : s);
      break;
    case "done": break;   // agent 无 conversation_id / 无 sources
  }
}
```

> 其实旧版可见效果也一样是「工具在上、前导+答案拼在一起在下」——因为旧版 `getText` 本来就把所有 text part 拼起来、`MessageItem` 本来就把工具渲在上面。所以「分段 text part」只是为了满足协议合法性,对最终画面没影响。新版把这个事实直接表达成两个扁平字段,省掉了分段仪式。**唯一保留的是「同 id 原地更新」**(running→done),现在就是上面那次普通的数组 `map`。

---

## 9. 引用溯源:从 `[2]` 文本到侧边栏高亮

> 这一节与流式架构无关(纯前端渲染),重构没动它。

### 9.1 完整链路

```
答案 text 里的 "[2]"
  │  rehype-citations.ts:Markdown 解析阶段,把【编号有效】的 [n] 换成 <cite data-ref=2>
  ▼
react-markdown 渲染 <cite> → <CiteRef refNum={2}>,点击时经 React Context 调 onCite(2)
  ▼
MessageItem.onCite(2) = onActivateSources(本条消息的 sources, 2)   ← 数据往上传到 Chat
  ▼
Chat.activateSources:setActive({sources, ref:2, key++}) + 打开抽屉(移动端)
  ▼
<SourcesPanel sources activeRef=2>   ← 数据往下传
  │  派生:card[2] 高亮 + 展开;useEffect 只做 scrollIntoView
  ▼
侧边栏 card[2] 滚到中央 + 蓝框高亮 + 展开原文
```

### 9.2 为什么把状态提升到 Chat(lifting state up)

侧边栏全局只有一个,却要显示**某一条消息**的来源。消息列表和侧边栏是两个兄弟组件、要共享数据,所以把状态提升到最近的公共父组件 `Chat`。

> 这是 React 经典题「状态放哪」。细节:`active.key` 每次点击自增,是为了重复点同一个 `[n]` 也能重新触发定位——否则 `ref` 没变,effect 不会重跑。

### 9.3 派生状态优先于在 effect 里 setState

卡片是否高亮 / 展开,直接从 props 算,不另存 state(最初在 `useEffect` 里 setState 被 eslint `set-state-in-effect` 拦了):

```tsx
open={openCards.has(s.id) || s.id === activeRef}   // 当前定位的那张自动展开
highlighted={s.id === activeRef}
```

`useEffect` 里只留一个真正的副作用:`scrollIntoView`(DOM 操作,不是 setState)。

> 要点:能从现有 props/state 算出来的,就不要再存一份 state(React 官方《You Might Not Need an Effect》)。少一份 state,少一类「状态不同步」的 bug。

### 9.4 rehype 插件为什么自己手写

要把 `[n]` 变可点击,得在 Markdown 解析阶段改节点。手写遍历 hast(没引 `unist-util-visit`):只动 `text` 节点,把编号**有效**(在该消息 sources 里)的 `[n]` 拆成 `<cite>`;无效编号(如 `[99]`)原样留作文本;跳过 `code` / `pre`,代码块里的 `[0]` 不算引用。

---

## 10. 多轮会话 与 RAG / Agent 模式切换

- **多轮**:RAG 后端按 `conversation_id` 在库里重建历史。客户端 `send` 时,从「最近一条 assistant 消息」的 `conversationId` 字段(`done` 帧写进去的)取出来,作为 body 带上;Agent 不带。
  > 旧版这个 id 走 `done` 的 transient 事件 → `onData` 回调 → 存进 ref;新版直接挂在消息字段上,从 `messages` 里读,删掉了 ref 和回调。
- **模式切换**:`Chat` 的 `mode` state 决定 `useStreamChat` 的 `api`(`/api/chat` vs `/api/agent`)和 `reduce`(`ragReduce` vs `agentReduce`);切换时调 hook 的 `reset()` 清空当前会话。
  > 行为变化:旧版用 `useChat({ id: mode })`,切回某模式还能看到该模式之前的历史;新版**切换即清空**(更简单,两模式各自独立)。要保留各模式历史的话,把 `messages` 提成 `Record<mode, ChatMessage[]>` 即可,当前没做。

---

## 11. 其余横切关注点

**文件上传(`lib/upload.ts`)**:用 `XMLHttpRequest` 不用 `fetch`,因为只有 `xhr.upload.onprogress` 能拿到上传进度做进度条。走 BFF:`/api/upload` 读 formData 里的 file,以 multipart 转发给 RAG `/upload`,原样回传。拖拽:消息区 `onDragOver`/`onDrop` + 虚线遮罩;成功显示 `chunk_count`,传完即可直接提问该文档(RAG 和 Agent 查同一个库)。

**错误处理(分两段)**:① 开流**前**(连不上 / 4xx / 5xx)在 route 里 `try/catch`,返回干净的 502——否则 fetch 抛错会变成 500;hook 里 `res.ok` 为假时把 body 文案抛出。② 开流**后**中途失败,后端塞一条 `error` 帧,reducer `throw`,被 hook 的 `catch` 接住设 `status="error"`。两者都汇到顶部错误条 +「重试」(`regenerate()`)。

**Loading / 停止**:首 token 前显示「思考中…」;流式中「发送」变「停止」(hook 的 `stop()` = `AbortController.abort()`,fetch 循环抛 AbortError 被识别为「用户主动停」而非错误)。

**性能(引用稳定性 + memo)**:去掉了旧版 `useChat` 的 `experimental_throttle`,现在**每帧 `setMessages`**。靠 `memo` 兜:`useMemo(() => getSources(message), [message])` + `useCallback` 稳定 `onCite` + `memo` 包 `Markdown`。消息定型后 `message` 引用稳定 → 派生值稳定 → memo 生效 → **只有正在流的那条重算**。长答案若觉得卡,在 hook 里给 `commit` 加个 ~50ms 节流即可。关键认知:memo 是否生效取决于传进去的引用稳不稳;每次渲染传新对象/新函数,memo 就失效了。

**响应式侧边栏**:同一个 `<aside>` 靠 Tailwind 断点切形态,不写两套组件。桌面 `lg:static` 常驻右栏;移动端 `fixed ... translate-x-full`(关)/`translate-x-0`(开)从右侧滑入,配 `lg:hidden` 遮罩。

---

# 第三部分 · 速查

## 12. 文件地图(谁负责什么)

```
src/
├─ app/
│  ├─ page.tsx                 渲染 <Chat/>
│  ├─ layout.tsx, globals.css  字体、Tailwind、highlight.js 主题、代码块样式
│  └─ api/
│     ├─ chat/route.ts         BFF 透传:fetch RAG /query/stream,原样转 SSE(+ try/catch 502 兜底)
│     ├─ agent/route.ts        BFF 透传:fetch Agent /agent/stream,原样转 SSE
│     └─ upload/route.ts       BFF 透传:multipart 转发到 RAG /upload
├─ lib/
│  ├─ types.ts                 Source / 后端帧类型(BackendFrame/AgentFrame)/ ChatMessage(扁平消息模型)
│  ├─ sse.ts                   解析 SSE(按 \n\n 跨 chunk 切帧),parseSSE<T> —— 现在客户端用
│  ├─ think.ts                 <think> 流式剥离状态机
│  ├─ useStreamChat.ts         ★ 流式 hook:fetch+ReadableStream+parseSSE+reduce;管 messages/status/stop/regenerate/reset
│  ├─ reducers.ts              ★ ragReduce / agentReduce:语义帧 → 扁平消息字段(核心,可单测)
│  ├─ rehype-citations.ts      [n] → <cite> 的 rehype 插件
│  └─ upload.ts                XHR 上传(onprogress 进度)+ 前端校验
└─ components/chat/
   ├─ Chat.tsx                 useStreamChat、模式切换(选 api+reducer)、上传、错误/重试/停止、状态提升
   ├─ MessageItem.tsx          单条消息:工具时间线 + 答案 + 来源/反馈
   ├─ MessageContent.tsx       薄封装,转发给 Markdown
   ├─ Markdown.tsx             react-markdown + remark-gfm + rehype-highlight + cite 组件
   ├─ ToolTimeline.tsx         Agent 工具时间线(running→done)
   ├─ SourcesPanel.tsx         引用侧边栏(桌面常驻 / 移动抽屉)+ SourceCard
   └─ message-utils.ts         getText / getSources / getToolSteps(从扁平字段读视图数据,签名同旧版)
```

后端前置(在 `0910-langgraph-agent`):`15_agent_server.py` 暴露 `/agent/stream`(:8100)。
（旧版的 `lib/adapter.ts` —— 帧→AI SDK 部件的适配器 —— 已于 2026-06-24 删除。)

---

## 13. 面试速答卡

**Q:整体架构一句话?**
A:Next BFF 透传 + 自写 `useStreamChat`(fetch + ReadableStream)直接读后端自定义 SSE,reducer 把语义帧逐帧累积成一条扁平消息。

**Q:为什么放弃 Vercel AI SDK / `useChat`?**
A:`useChat` 要求后端按 AI SDK 的 UI Message Stream 协议说话,为了喂它得在服务端写一层适配器把干净的后端 SSE 翻成协议——翻译两次。SSE 解析我自己用 `parseSSE` 就能做,去掉 `useChat` 后那层适配器一起删,代码更短、状态全在自己 hook 里可控。代价是 `messages` 状态 / `stop` / 重试要自己实现(约 70 行)。

**Q:核心逻辑到底做什么?**
A:后端给的是一串「发生了什么」的事件(sources/token/done);前端要的是一条「该渲染什么」的扁平消息。reducer 逐帧把事件累积进消息的对应字段(text / sources / toolSteps / conversationId)。

**Q:为什么不前端直接调模型 / 直连后端?**
A:LLM/检索/会话都在后端,前端不重复造;BFF 做安全收口(藏地址)+ 错误兜底 + 将来鉴权/限流的口子。它只转发,不翻译。

**Q:流式状态怎么管的?**
A:发送时挂一条空 assistant 草稿,`for await (parseSSE(res.body))` 每帧 `reduce` 改写草稿、`setMessages` 触发渲染;`status` 跟踪 streaming/ready/error;`stop` 用 `AbortController.abort()`。

**Q:工具卡片 running→done 怎么原地更新?**
A:两帧用同一个 `tool_call_id` 当 id,`agentReduce` 在 running 时 push、done 时按 id `map` 原地补 output(像 React 的 key 那套 reconciliation,现在是普通数组操作)。

**Q:token 和工具交替时,阅读顺序怎么保证?**
A:不靠数组顺序了。token 累积进 `text`、step 累积进 `toolSteps`,两字段独立;`MessageItem` 固定「工具时间线在上、答案正文在下」。

**Q:引用 `[n]` 点击联动?**
A:rehype 把有效 `[n]` 变 `<cite>` → 经 Context 调 onCite → 把该消息 sources 提升到 Chat → 下传侧边栏 → 派生高亮/展开 + effect 里 scrollIntoView。

**Q:`<think>` 怎么剥?为什么不能 replace?**
A:标记会被切在两个 token 里,用跨 chunk 状态机 + 留住半截前缀;replace 只能处理完整字符串。(现在在客户端 hook 里调。)

**Q:错误处理?**
A:开流前(连不上/4xx/5xx)route 里 try/catch 映射成干净 502;开流后中途失败后端塞 error 帧、reducer 抛异常被 hook catch;前端统一错误条 + 重试。

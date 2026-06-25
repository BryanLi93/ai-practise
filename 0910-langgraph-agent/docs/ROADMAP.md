# LangGraph Agent — 学习计划

> 参照 `0607-rag-service` 的学习节奏(逐步任务 + 方法论 + 博客选题)。
> 本项目对应 rag-service 24 周课程的 **Week 9-10(LangGraph Agent)**,单独立项深入。
> 环境已就绪:`.venv`(pyenv 3.12.13)+ `hello_graph.py` 已跑通(Week 9 Step 1)。
> **Step = 学习步骤序号**,不绑死自然日;每周以 deadline 为准(W9 截 2026-06-12 / W10 截 2026-06-18)。

## ⚠️ 版本基线与陷阱速查(2026-06 联网核实)

**基线:LangGraph 1.2.4**(1.0 于 **2025-10-22 GA**,zero breaking changes)。
网上大量 2024 年教程是 0.x 写法,以下 API 已变。**照老教程抄会走弯路**:

| 你会在老教程看到(0.x) | 1.x 现行写法 | 说明 |
|---|---|---|
| `from langgraph.prebuilt import create_react_agent` | `from langchain.agents import create_agent` | v1.0 弃用前者,后者底层仍跑 langgraph 引擎。需要拦截中间状态/人类审核/多 agent 时再退回手写 StateGraph |
| `interrupt_before` / `interrupt_after`(compile 时静态中断) | `interrupt()` 函数 + `Command(resume=...)` 恢复(runtime 动态) | 老写法仍有效、更简单,但 1.x 主推动态写法,更灵活 |
| `from langgraph.checkpoint.sqlite import SqliteSaver` 直接 import | **先单独装包**:`pip install langgraph-checkpoint-sqlite`(或 `-postgres`),再 import | 1.0 起 checkpointer 拆成独立包,不装会 ImportError。内存版 `MemorySaver` 在 base 包,无需额外装 |
| `.stream()` 默认单一格式 | `stream_mode=` 五选:`values`/`updates`/`messages`/`custom`/`debug`;1.0 新增 `stream_version="v2"` | 见可选机动 Step 11 |
| **稳定没变(放心用)**:`StateGraph` / `add_node` / `add_edge` / `add_conditional_edges` / reducer / `compile` / `invoke` | | 核心 graph API 跨版本稳定 |

> 来源:LangChain 官方 changelog(LangGraph 1.0 GA / checkpoint 独立包)、LangChain v1 迁移文档、Interrupts/Streaming/Visualization 官方文档。

## 方法论(沿用 rag-service)

1. **先手写最简版,再上封装** —— 建立对比理解。例:先手写 `LLM → tool → LLM` 循环,再用 `create_agent` 一行替换,体会封装替你做了什么。
2. **真实数据逐字追踪** —— 每个新概念跑一个最小 `.py`,打印 state 看数据怎么流(`hello_graph.py` 已示范 reducer 累加)。
3. **小步验证** —— 每个 Step 产出一个能独立跑通的 `.py`,不贪多。
4. **对照已学的 rag-service** —— 多处概念能对照(多轮历史 ↔ checkpointer、SSE ↔ astream、structlog ↔ 步骤日志、检索 ↔ RAG-as-tool)。

---

## Week 9 — 图 / 状态 / 工具调用 / 持久化(截止 📅 2026-06-12)

> 主线:从"图怎么搭"到"LLM 自己决定调工具",再到"状态能存能恢复"。
> **Week 7 的多轮对话 ≠ Agent**;Agent 的分水岭是 Step 4(LLM 返回 `tool_calls`)。

| Step | 主题 | 内容 | 练习 / 产出 |
|---|---|---|---|
| **1** ✅ | 最小图 | `State`(TypedDict)/ 节点 / 边 / reducer(`Annotated[list, operator.add]`)/ `compile` / `invoke` | **练习:两节点直线图,逐字追踪 reducer 累加**(用户自写,已跑通)→ `01_graph.py` |
| **2** ✅ | 条件分支 + START/END | `add_conditional_edges`:路由函数读 state 决定走哪条边;`START`/`END` 锚点 | **练习:带分支的"问题 → 思考 → 回答"**(判类型:闲聊→chat / 含数字→calc)。用户自写,已跑通;用了 `Literal` 注解约束标签,判断放 route 直读 query → `02_conditional.py` |
| **3** ✅ | 接 LLM 节点 + 多轮 | `ChatOpenAI` 接硅基流动(复用 rag-service 的 `.env`);`MessagesState` + `add_messages` | 全部完成:`llm.py` 单例封装(SecretStr)+ `02_conditional.py` 的 `node_chat` 接真 LLM;`03_chatbot.py` 用 `MessagesState` 做多轮,亲手验证"带历史 vs 不带历史"——LLM 无状态,记忆靠每轮传历史 |
| **4** ✅ | 工具调用 | `@tool` → `bind_tools` → 观察 `tool_calls`;`ToolNode`(必须在图里跑)执行工具。**Agent vs 多轮对话的分水岭** | `04_tools.py`(看 tool_calls)+ `04_tool_agent.py`(LLM→ToolNode→LLM 一次往返,线性版)。踩了死循环坑(回头边)+ 学了 `print_ascii()`/`draw_mermaid()` 可视化。条件路由的循环版留 Step 5 |
| **5** ✅ | Agent loop | 手写 `LLM ⇄ ToolNode` 循环(`should_continue` 条件边判断有无 tool_call);再用 `create_agent`(`langchain.agents`,1.0)一行替换,对比 | `05_agent_loop.py`:add+multiply 双工具,链式问题逼出循环 2 轮;手写版与 `create_agent` 内部图同构(`model ⇄ tools`+条件边)、结果一致。学了 `isinstance` 类型收窄 |
| **6** ✅ | 持久化 Checkpointer | `InMemorySaver`(免装)验证自动记忆 + `thread_id` 会话隔离;再换 `SqliteSaver`(装 `langgraph-checkpoint-sqlite`)落盘、**重启不丢** | `06_checkpoint.py`:同 thread_id 只传新消息也记得、换 thread_id 隔离;SqliteSaver 跨进程持久化已验证(全新进程读 db 仍答出"小明")。撞上硅基流动偶发返回非标准格式→引出 Step 8 重试 |

## Week 10 — 人类介入 / 容错 / 可观测(截止 📅 2026-06-18)

> 主线:让 agent 能被人打断、能扛住失败、能看清每步在干什么。多处对照 rag-service 已实现的工程能力。

| Step | 主题 | 内容 | 练习 / 产出 |
|---|---|---|---|
| **7** ✅ | Human-in-the-loop | `interrupt()` 暂停 + `Command(resume=...)` 恢复(**1.x 动态写法**,需配 checkpointer);审批节点设计 | `07_hitl.py`:最小 interrupt/resume + 审批流程(批准→execute / 拒绝→cancel,条件边路由)。学到:Literal 不适合"过程填充"字段;interrupt 前别放副作用(resume 会重跑) |
| **8** ✅ | 失败重试 + Fallback | 节点级重试 `add_node(..., retry_policy=RetryPolicy(...))`(参数名 `retry_policy`);模型降级 `主.with_fallbacks([备选])` | `08_retry.py`(节点重试)+ `09_fallback.py`(模型降级)。**两层容错**:retry=重跑同节点 / fallback=换 Runnable。踩坑:`max_attempts`=总执行次数(容忍 n-1 个异常);默认 `default_retry_on` **不重试** `ValueError`/`RuntimeError`/`TypeError` 等确定性错误,只重试 `ConnectionError`/5xx/未知异常(`retry_on` 接单类/元组/callable);重试从节点顶部**重跑**→副作用要幂等(同 HITL resume 规律);`with_fallbacks` 返回 `RunnableWithFallbacks`(非 `BaseChatModel`)→ 传给 `create_agent` 报类型(`reportCallIssue`+`reportArgumentType`),运行时能跑(对 model 调 `.bind_tools()`、`__getattr__` 代理到主+备选)但要 `# pyright: ignore`;生产 fallback 三法:**网关层**(LiteLLM/OpenRouter,最干净)/代码内压类型/手写图。顺带重构 `llm.py`:单槽单例+model 参数矛盾→**按 model 名分桶缓存**,删 `is_singleton` |
| **9** ✅ | 步骤日志 + 可视化 | 记录每节点的输入/输出/耗时(JSON);`draw_mermaid_png()` 导出执行流程图 | `10_log_visual.py`。**可视化**:`draw_mermaid()` 出源码(无依赖)/`draw_mermaid_png(output_file_path=...)` 默认**联网** mermaid.ink 渲染落盘(`pyppeteer` 才本地渲染;`pygraphviz` 是 `draw_png()` 用的,这里不需要)。**手写日志**:装饰器 `log_node` 包节点函数,`time.perf_counter()` 计时 + `json.dumps(..., default=str)`;`input`=进来的 state,`output`=节点返回的**局部更新 dict**(印证"节点只返回要更新字段")。`functools.wraps`:装饰器把函数换成 `wrapper`→`__name__` 变 `"wrapper"`,wraps 把原名抄回(类比 React HOC `displayName`)。**装饰器装不上 ToolNode**(它是 Runnable 非函数)→ 内置 `stream_mode` 才覆盖 prebuilt 节点。`stream_mode` 五选 `values/updates/messages/custom/debug`;`invoke`→`stream`,每 chunk=`{节点名: 更新}`。**stream 计时**:循环掐表(近似)/`stream_mode="debug"` 的 `task`+`task_result` 时间戳配对(精确)。**生产不手搓**:用 tracing 平台 **LangSmith**(env var `LANGSMITH_TRACING`/`_API_KEY`,零改动,已装)/OpenTelemetry/Langfuse;structlog(扁平日志)vs tracing(树状 span+延迟+token) |

### 可选机动(我的增量,原计划没有;时间紧可后置)

| Step | 主题 | 内容 | 产出 |
|---|---|---|---|
| **10** ✅ | 收官:RAG-as-tool | 把 rag-service 的检索封成一个 `@tool`,让 agent 自己决定何时检索 —— 串起整个课程(Agent 调 RAG) | `11_demo_rag_agent.py`:`@tool search_knowledge_base` 调 rag-service `POST /query`,**只取 `sources`、丢弃 `answer`**(`/query` 把 retrieve+generate 捆死,生成那步 Qwen3.5-4B 经硅基流动慢/带思考链/偶回"没找到";检索 sources 又快又准)→ `create_agent` 挂工具。**学习点验收**:同一 agent,算术题 `tool_calls=[]` 直接答、知识库题调 `search_knowledge_base` 再综合 → 检索从"必走流程"变"按需调用"。看 stream:`stream_mode="updates"` 每 chunk=`{节点:{messages}}`;自写 `show_update` 能截断长 chunk / 内置 `msg.pretty_print()` 一行出框线(不截断)。踩坑:rag-service redis 在 **6380**(容器避让本机 6379)是对的,报 `6380 refused` 是没起 redis 容器、别改端口 |
| **11** ✅ | 流式输出 | `astream(stream_mode=...)`:`values`/`updates`/`messages`。对照 rag-service 的 SSE token 流 | `12_streaming_by_claude.py`。**两种粒度**:`messages`=逐 token(打字机)/ `updates`=整段(节点跑完才给一块)。messages 的 chunk 是二元组 `(AIMessageChunk, metadata)`,过滤掉空块/非 AI 块;打字机靠 `print(content, end="", flush=True)`。**astream vs stream**:数据完全一样,只差同步/异步——`astream` 是异步生成器(`async for`+`asyncio.run()`)。脚本自己跑 sync `stream` 够用,只有做高并发 SSE 服务才必须 async(对照 rag-service 的 FastAPI) |
| **12** ✅ | 多 Agent / 子图 | `subgraph` 或 supervisor 模式:最简多 agent handoff | `13_multi_agent_by_claude.py`。**核心:agent 就是张编译好的图,图能当节点**——`add_node("tech_agent", tech_agent)` 直接塞编译好的 agent(不是函数),一个节点内部跑完自己的 `model⇄tool` 循环。结构同 Step 2 条件分支,只是分支终点从函数换成 agent、路由从关键字换成 supervisor 的 LLM 判断(写进 `state["next"]`,条件边读它)。能插进去靠 **state 形状对上**:agent 吃/吐 `{"messages"}`,大图用 `MessagesState` 就严丝合缝。验证:算术题→general_agent 直答 / 知识库题→tech_agent 调 RAG |

---

## 每周验收(能讲清 / 能交付什么)

- **Week 9 末(06-12)**:能从零搭带条件分支的图;能解释"为什么 Agent 是 LLM 决定调工具,而多轮对话不是";手写过一遍 agent loop,知道 `create_agent` 替你做了什么;agent 状态能存 SQLite 并恢复。
- **Week 10 末(06-18)**:agent 能在关键步骤暂停等人批准、能在 API 失败时重试/降级、能输出每步 JSON 日志并导出流程图。

## 可写的技术博客选题(呼应 rag-service 的博客线)

- **LangGraph 1.0 迁移避坑**:`create_react_agent` → `create_agent`、`interrupt_before` → `interrupt()`、checkpointer 拆独立包,以及为什么核心 graph API 反而稳定(版本判断方法论)
- **多轮对话 ≠ Agent**:从 rag-service 的服务端历史,到 LLM 自主调工具的分水岭在哪
- **reducer 是 LangGraph 的状态合并契约**:对照 React 的 `useReducer`(前端类比向)
- **Agent 的人类介入**:`interrupt()` + `Command(resume=)` 怎么把"等人批准"做成可恢复的中断
- **给 Agent 加可观测性**:节点级 JSON 日志 + mermaid 流程图,复用 RAG 服务的 structlog 经验
- **把 RAG 接成 Agent 的一个工具**:检索从"必走流程"变成"LLM 按需调用"的设计转变

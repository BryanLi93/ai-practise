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
| **3** ✅ | 接 LLM 节点 + 多轮 | `ChatOpenAI` 接中转站(复用 rag-service 的 `.env`);`MessagesState` + `add_messages` | 全部完成:`llm.py` 单例封装(SecretStr)+ `02_conditional.py` 的 `node_chat` 接真 LLM;`03_chatbot.py` 用 `MessagesState` 做多轮,亲手验证"带历史 vs 不带历史"——LLM 无状态,记忆靠每轮传历史 |
| **4** ✅ | 工具调用 | `@tool` → `bind_tools` → 观察 `tool_calls`;`ToolNode`(必须在图里跑)执行工具。**Agent vs 多轮对话的分水岭** | `04_tools.py`(看 tool_calls)+ `04_tool_agent.py`(LLM→ToolNode→LLM 一次往返,线性版)。踩了死循环坑(回头边)+ 学了 `print_ascii()`/`draw_mermaid()` 可视化。条件路由的循环版留 Step 5 |
| **5** | Agent loop | 先**手写** `LLM → ToolNode → LLM` 循环(条件边判断是否还有 tool_call);再用 `create_agent` 一行替换,对比 | **练习:"搜索 + 计算器" Agent** → `react_manual.py` / `react_prebuilt.py` |
| **6** | 持久化 Checkpointer | **先装包** `pip install langgraph-checkpoint-sqlite`;`SqliteSaver` + `thread_id` 多会话;中断后从 checkpoint 恢复执行(你 rag-service 有 Postgres,也可换 `PostgresSaver`)。对照「服务端持有历史」 | **练习:可中断 → 恢复执行**的工作流(「人工确认」那步衔接 W10 Step 7) → `checkpoint.py` |

## Week 10 — 人类介入 / 容错 / 可观测(截止 📅 2026-06-18)

> 主线:让 agent 能被人打断、能扛住失败、能看清每步在干什么。多处对照 rag-service 已实现的工程能力。

| Step | 主题 | 内容 | 练习 / 产出 |
|---|---|---|---|
| **7** | Human-in-the-loop | `interrupt()` 暂停 + `Command(resume=...)` 恢复(**1.x 动态写法**,需配 Step 6 的 checkpointer);审批节点设计。⚠️ 老教程的 `interrupt_before/after` 见速查表 | **练习:危险操作前暂停等人确认** → `human_in_loop.py` |
| **8** | 失败重试 + Fallback | 节点级重试 `add_node(..., retry_policy=RetryPolicy(...))`(参数名是 `retry_policy`,不是 `retry`);模型降级 `llm.with_fallbacks([backup_llm])`(Fallback 到备选模型/策略) | **练习:模拟 API 失败**,验证重试 + 切到备选 → `retry_fallback.py` |
| **9** | 步骤日志 + 可视化 | 记录每节点的输入/输出/耗时(复用 rag-service 的 structlog 经验,JSON 输出);`graph.get_graph().draw_mermaid_png()` 生成执行流程图(`draw_mermaid()` 出 mermaid 源码) | **练习:为 Agent 加完整执行日志(JSON)+ 导出流程图** → `observability.py` |

### 可选机动(我的增量,原计划没有;时间紧可后置)

| Step | 主题 | 内容 | 产出 |
|---|---|---|---|
| **10**(建议保留) | 收官:RAG-as-tool | 把 rag-service 的检索封成一个 `@tool`,让 agent 自己决定何时检索 —— 串起整个课程(Agent 调 RAG) | `rag_agent.py` |
| **11**(可选) | 流式输出 | `astream(stream_mode=...)`:`values`/`updates`/`messages`。对照 rag-service 的 SSE token 流 | `streaming.py` |
| **12**(可选) | 多 Agent / 子图 | `subgraph` 或 supervisor 模式:最简多 agent handoff | `multi_agent.py` |

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

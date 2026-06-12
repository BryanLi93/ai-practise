# LangGraph 学习 — 面试要点速记

> 从每个 Step 的踩坑里提炼,**只收面试适用**的概念(一般性踩坑不收)。每个 Step 结束在此追加。
> 进度:截至 **Step 4(工具调用)**。

---

## 一、LLM 与对话的本质(高频)

### Q1　多轮对话怎么实现的?LLM 怎么"记住"上下文?
**一句话**:LLM 本身**无状态**,"记忆"是应用层每轮把**完整历史**一起传出去制造的。
- 每次 API 调用相互独立,LLM 不记得上一次说过什么。
- 实现多轮:把全部历史消息(user/assistant 轮流)作为 `messages` 列表一起发给 LLM,它看到历史才能接上。
- 反证:问"我是谁?",带历史 → 答得出名字;不带历史 → 只能瞎猜。
- **工程延伸**:历史越积越长 → 撑爆 context + 烧 token → 需滑动窗口 / 摘要压缩(rag-service 做过)。
- 来源:Step 3。

### Q2　Function Calling / Tool Calling 的原理?
**一句话**:LLM 不执行工具,只**决定**调哪个、传什么参数;执行是应用层的事,结果回喂给 LLM 出最终答案。
- LLM 输出结构化的 `tool_calls`(工具名 + 参数),放在它返回的 `AIMessage` 里;此时 `content` 通常为空。
- 应用层执行工具 → 结果包成 `ToolMessage` → 加回 messages → 再调一次 LLM → 出人话答案。
- 完整往返:`用户问 → LLM(出 tool_calls) → 执行工具 → ToolMessage(结果) → LLM(出答案)`。
- 工具靠 **docstring + 参数类型注解** 让 LLM 理解"干嘛的、怎么调"。
- 来源:Step 4。

## 二、Agent 的本质(高频)

### Q3　Agent 和普通多轮对话有什么区别?
**一句话**:多轮对话只是 LLM"回话"、流程固定;Agent 是 **LLM 自己决定下一步做什么**(调哪个工具、要不要继续)的多步任务。
- 分水岭就在 `tool_calls`:LLM 能自主决定调用外部能力。
- **Agent Loop**:`LLM → 工具 → LLM → 工具 → …` 直到 LLM 判断不再需要工具才结束。
- 来源:Step 4。

## 三、LangGraph 核心机制(中高频)

### Q4　LangGraph 怎么管理 / 更新状态?
- State 是个 TypedDict;节点只 `return` "要更新的字段",框架**合并**进 state。
- 合并规则由 **reducer** 决定:**默认覆盖**;给字段挂 `Annotated[type, reducer]` 可改成累加等。
- 例:`messages: Annotated[list, add_messages]` → 消息**追加**;`Annotated[list, operator.add]` → 列表拼接。
- 来源:Step 1 / Step 3。

### Q5　怎么实现条件分支 / Agent 的决策?
- `add_edge` 固定边:A 后必去 B。`add_conditional_edges` 条件边:**路由函数**读 state、返回标签,决定走哪条。
- 职责划分:**节点**干活、写 state;**路由函数**只读 state 做决定、不写 state、本身不是节点。
- **权衡**:要留给后面用的中间结果,必须由**节点 `return` 进 state**(路由函数的返回只选路、不进 state)。Agent loop 里 route 读的是 LLM 节点写进 state 的 `tool_calls`,绝不在 route 里重调 LLM。
- 来源:Step 2。

### Q6　LangGraph 的图是怎么执行的?(执行模型)
- 执行由**边构成的图结构**决定,**不按**代码里 add_node/add_edge 的书写顺序。
- 一个节点的多条**无条件**出边是**全部并行走**(fan-out),不是二选一;要二选一必须用**条件边**。
- **回头边**(指回上游)会导致循环;`recursion_limit`(默认 25)兜底,超了抛 `GraphRecursionError`。
- 调试:`graph.get_graph().print_ascii()` / `.draw_mermaid()` 把图画出来看(`draw_mermaid()` 文本可贴 mermaid.live 渲染)。
- 来源:Step 4(死循环)。

## 四、工程细节(加分项,非高频)

- **接 OpenAI 兼容中转站**:`ChatOpenAI` 不传 `api_key`/`base_url` 也能用——`OPENAI_API_KEY`/`OPENAI_BASE_URL` 是 langchain / openai SDK 源码里写死的标准环境变量名,会自动读取(同 rag-service 的中转站方案)。
- **LangGraph 1.0 版本变更**(2025-10 GA):造 agent 用 `langchain.agents.create_agent`(旧 `langgraph.prebuilt.create_react_agent` 已弃用);人类介入用 `interrupt()` + `Command(resume=)`(旧 `interrupt_before/after`);checkpointer 拆成独立包。
- 来源:环境搭建 / Step 3。

---

_每 Step 结束在此追加新条目。_

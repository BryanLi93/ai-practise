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

### Q3.5　LangChain 和 LangGraph 什么区别?用哪个?(高频)
**一句话**:LangGraph 是**底层图编排引擎**(精确控制流程);LangChain 是**组件库 + 高层封装**(`create_agent` 开箱即用)。不对立,是**分层**——`create_agent` 底层就是用 langgraph 跑的(返回 `CompiledStateGraph`),两者共享 `langchain-core`(消息/工具/模型接口)。
- **用哪个**:默认 `create_agent`(一行);当需要**精确控制**(拦截/改中间步、加人类审批、自定义循环/分支、多 agent、自定义 state)时,落到 langgraph 手搭图。
- 亲历(Step 5):手写 agent loop(langgraph) == `create_agent`(langchain)一行,结果完全一样。
- 三层:`langchain`(封装) → `langgraph`(引擎) → `langchain-core`(共享底座)。
- 来源:Step 5。

### Q3.6　Agent Loop 具体怎么手写实现?
- 两个节点:`model`(调 LLM)+ `tools`(`ToolNode` 执行工具)。
- **条件边**:路由函数读最后一条 `AIMessage`,有 `tool_calls` → 去 `tools`,没有 → END。
- `tools → model` **回边**形成循环;**为什么不死循环**:出边是条件边(二选一),LLM 不再出 `tool_calls` 时走 END(`recursion_limit` 默认 25 兜底)。
- `create_agent` 一行 = 这整套的封装(亲测内部图同构:`model ⇄ tools` + 条件边)。
- 来源:Step 5。

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

### Q7　LangGraph 怎么做持久化 / 多会话记忆?(中高频)
- **Checkpointer**:自动保存每一步的 state,按 `thread_id` 存取;下次同 `thread_id` invoke **自动恢复历史**(只需传新消息,不用手动拼)。
- **后端选择**:`InMemorySaver`(内存,重启丢,base 包免装)/ `SqliteSaver`·`PostgresSaver`(落盘,重启不丢,**需装独立包** `langgraph-checkpoint-sqlite`/`-postgres`)。
- `thread_id` = **会话隔离**:多用户 / 多会话各自独立。
- 对比手动传历史(Step 3):checkpointer 自动恢复,`invoke` 只传新消息。
- 这也是 **HITL(人类介入)的基础**——状态能存盘,才能"暂停 → 等人 → 恢复"。
- 来源:Step 6。

## 四、工程细节(加分项,非高频)

- **接 OpenAI 兼容中转站**:`ChatOpenAI` 不传 `api_key`/`base_url` 也能用——`OPENAI_API_KEY`/`OPENAI_BASE_URL` 是 langchain / openai SDK 源码里写死的标准环境变量名,会自动读取(同 rag-service 的中转站方案)。
- **LangGraph 1.0 版本变更**(2025-10 GA):造 agent 用 `langchain.agents.create_agent`(旧 `langgraph.prebuilt.create_react_agent` 已弃用);人类介入用 `interrupt()` + `Command(resume=)`(旧 `interrupt_before/after`);checkpointer 拆成独立包。
- 来源:环境搭建 / Step 3。

---

_每 Step 结束在此追加新条目。_

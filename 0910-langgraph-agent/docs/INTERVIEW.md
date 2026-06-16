# LangGraph 学习 — 面试要点速记

> 从每个 Step 的踩坑里提炼,**只收面试适用**的概念(一般性踩坑不收)。每个 Step 结束在此追加。
> 进度:截至 **Step 9(步骤日志 + 可视化 / 可观测)**。

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

### Q8　LangGraph 怎么实现 Human-in-the-loop?(中频)
- **`interrupt(问题)`**:在节点里调用,图**当场暂停**,把"问题"放进返回的 `__interrupt__` 抛给人。
- **`Command(resume=答案)`**:人决定后 invoke 恢复,`interrupt()` 返回那个答案,节点接着跑。
- **必须配 checkpointer + thread_id**(暂停状态存盘、恢复读回)——HITL 建在持久化之上。
- **版本**:1.x 主推 `interrupt()`(runtime 动态);旧 `interrupt_before`/`interrupt_after`(compile 静态)是老写法。
- **反直觉坑**:resume 时节点**从头重跑**,`interrupt()` 之前别放副作用(发邮件/写库会重复执行);正确模式是审批节点只问、副作用放批准后的独立节点。
- 来源:Step 7。

### Q8.5　生产环境的 HITL 异步审批怎么做?(高频·进阶)
- 核心:**interrupt 的"暂停"不是阻塞等待,而是"状态持久化 → 请求结束释放进程 → 未来独立请求恢复"**。人隔几小时/几天批准都行。
- 两个端点:`/start`(invoke → 命中 `__interrupt__` → 存待审批表 + 返回 `thread_id`,**请求即结束**)、`/resume`(用户批准时带 `thread_id` + `Command(resume=)` → 从 checkpointer 读回状态续跑)。
- 别混两种异步:`async/await`(`ainvoke`)是单次请求内的 IO 并发;**人类异步决策靠"持久化 + 两次独立请求",不能用 `await` 干等用户**(会占满连接)。
- 硬要求:checkpointer 必须**持久化**(Postgres,非 InMemory)——两次请求间进程可能重启或落在不同实例。
- 一句话:把"等人"从**进程阻塞**转化成**数据库里一条待恢复记录**,所以能扛海量待审批。
- 来源:Step 7 延伸。

### Q9　Agent 的容错怎么做?重试和 Fallback 什么区别?(中高频)
**一句话**:两层、互补——**重试**赌"同一个再试一次就好"(瞬时抖动);**Fallback**赌"这个彻底不行,换一个"(整体不可用)。
- **节点级重试**:`add_node(name, fn, retry_policy=RetryPolicy(max_attempts=3))`。`max_attempts` 是**总执行次数**(容忍 `n-1` 个异常,不是 n 个)。
- **关键坑**:默认 `default_retry_on` **不重试** `ValueError`/`TypeError`/`RuntimeError` 这类——它们被当成**确定性 bug**(重试也是同样的错);只重试 `ConnectionError`/HTTP 5xx/未知异常(像瞬时故障的)。要自定义就传 `retry_on=(异常类元组)` 或 callable。
- **重试会从节点顶部重跑** → 节点要**幂等**,副作用(写库/扣款)放可失败点之后或用幂等键。**和 HITL 的 resume 重跑是同一条规律**:重新执行的最小单位是"节点"不是"行"。
- **模型降级**:`主LLM.with_fallbacks([备选LLM])`,在 **Runnable 层、跟图无关**;主失败→拿**同样输入**调备选。用途:限流(429)/超时/5xx 切 provider、成本优化(小模型失败降级大模型)。
- **生产怎么做 fallback**(高频追问):① **网关层**(LiteLLM/OpenRouter/Portkey)配置 fallback,应用只调一个 model 名,代码最干净、资源集中可观测——**最主流**;② 代码内 `with_fallbacks`(注意它返回 `RunnableWithFallbacks` 不是 `BaseChatModel`,传给 `create_agent` 会报类型,需压制);③ 需精细控制就手写图。
- 来源:Step 8。

### Q10　Agent 的可观测性怎么做?生产怎么追踪?(中高频)
**一句话**:学习期可手写(装饰器记每节点输入/输出/耗时);**生产不手搓**,开 tracing 平台把每个节点/LLM/工具自动记成带父子结构的 span。
- **可视化**:`graph.get_graph().draw_mermaid()`(出 mermaid 源码,无依赖)/ `draw_mermaid_png(output_file_path=...)`(默认联网 mermaid.ink 渲染落盘)。
- **手写日志**:装饰器包节点函数,`time.perf_counter()` 计时 + `json.dumps`。**坑**:① state 里若是消息对象不能直接 `json.dumps`,要 `default=str`;② 装饰器**装不上 `ToolNode`**(它是 Runnable 非函数),只能盖你自己的函数节点。
- **`functools.wraps`**:装饰器把函数换成内层 `wrapper`,被装饰函数 `__name__` 变 `"wrapper"`(所有节点都变一样,traceback 分不清);`wraps(fn)` 把原函数名/元信息抄回 wrapper。= React HOC 的 `displayName` 问题。
- **内置观测**:`graph.stream(input, stream_mode=...)`,五选 `values`(全量 state)/`updates`(每节点的增量,最常用)/`messages`(token 流)/`custom`/`debug`(带 `task`/`task_result` 时间戳,可算精确 per-node 耗时)。**它覆盖 ToolNode 等 prebuilt 节点**,补上手写装饰器的盲区。
- **生产 tracing(高频追问)**:① **LangSmith**(LangChain 一方,设 `LANGSMITH_TRACING`/`LANGSMITH_API_KEY` env var,零代码,自动记 trace+延迟+token+错误树);② **OpenTelemetry**(中立标准,导进 Datadog/Grafana);③ **Langfuse**(开源自托管)。
- **structlog vs tracing(高频,要能举例)**:同一次 agent 运行——
  - **structlog = 扁平事件流**:一条条独立 JSON 日志行(`node.start`/`llm.response`/`tool.exec`…),要自己按 `thread_id`+时间戳串起来;**结构没被记下来**。
  - **tracing(LangSmith)= 调用树 + 自动聚合**:`agent → model → tools → model …` 嵌套成树,带每步延迟瀑布、总 token / 总成本,点开任意 span 看那步完整 prompt/响应。
  - 一眼能答的事(树才给得了):循环跑了几轮 model、延迟全在哪步、总共花多少钱。agent 会循环嵌套,所以需要树。
  - **类比**:structlog ≈ 散落的 `console.log` 行;tracing/LangSmith ≈ Chrome DevTools 的 **Network 瀑布 / Performance 火焰图**。两者生产并用。
- 来源:Step 9。

## 四、工程细节(加分项,非高频)

- **接 OpenAI 兼容中转站**:`ChatOpenAI` 不传 `api_key`/`base_url` 也能用——`OPENAI_API_KEY`/`OPENAI_BASE_URL` 是 langchain / openai SDK 源码里写死的标准环境变量名,会自动读取(同 rag-service 的中转站方案)。
- **LangGraph 1.0 版本变更**(2025-10 GA):造 agent 用 `langchain.agents.create_agent`(旧 `langgraph.prebuilt.create_react_agent` 已弃用);人类介入用 `interrupt()` + `Command(resume=)`(旧 `interrupt_before/after`);checkpointer 拆成独立包。
- 来源:环境搭建 / Step 3。

---

_每 Step 结束在此追加新条目。_

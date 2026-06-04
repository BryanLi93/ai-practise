# 易错问题复习

> 按 Week/Day 累积。每条结构:**现象 → 原因 → 正解 → 复习点**。
> 用途:复盘自己踩过的坑,面试时这些"我怎么发现并修的"比"我知道某概念"更有说服力。

---

## Week 7 Day 2 — 多轮对话(Query Rewriting + 历史注入)

### P1. "取最近 N 条"写成了 `ORDER BY id ASC LIMIT N`

- **现象**:短对话正常,对话超过 N 条后,历史永远停在最开头几句,新消息进不来。
- **原因**:`ASC + LIMIT N` 取的是 **id 最小的 N 条(最旧)**;想要的是最新 N 条。短对话(≤N 条)时 ASC 正好返回全部,所以早期测不出来,是隐藏 bug。
- **正解**:
  ```python
  .order_by(Message.id.desc())   # 先倒序,LIMIT 砍掉旧的、留最新 N 条
  .limit(limit)
  # ...
  return list(reversed(result.scalars().all()))  # 再翻成正序给 prompt 用
  ```
- **复习点**:"取哪几条"由 `DESC/ASC + LIMIT` 决定,"按什么顺序摆"由 `reversed` 决定,是两件独立的事,别想一步到位。

### P2. 改了函数签名加必填参数,但调用方没接线

- **现象**:每个请求 `TypeError: query() missing 1 required keyword-only argument: 'recent_messages'`;而且 retrieval 里整套历史注入逻辑全程不执行(死代码),功能看似实现实则不通。
- **原因**:`run_query` 加了必填 `recent_messages`,router 里算出了 `recent_messages` 变量,却没传给 `run_query`。
- **复习点**:改公共函数签名后,grep 所有调用点逐个对齐。"加了参数没接线"是重构里最常见的断点。

### P3. 三引号字符串的源码缩进会进入内容

- **现象**:历史块发给 LLM 时,每行都带一堆前导空格。
- **原因**:写在函数体内的多行 `"""..."""` 会**原样保留源码缩进**,Python 不会自动去掉。
- **正解**:把 prompt 模板提到模块顶层顶格写(本项目做法),或用 `textwrap.dedent`。
- **复习点**:prompt 模板对空白敏感(浪费 token + 干扰模型对结构的判断),别在缩进的代码块里直接写多行模板。

### P4. 注入历史与"只用上下文回答"的 system prompt 冲突,引用编号会串

- **现象**:模型可能引用历史里的旧 `[1][2]`,而它们与当前上下文的 `[1][2]` 指向**不同的来源**,引用与实际来源对不上。
- **原因**:历史里 assistant 的旧答案带着旧编号 `[1][2]`,当前 prompt 的上下文又有一套全新的 `[1][2]`,两套编号撞车。
- **正解**:
  1. 拼历史时去掉旧编号:`history = re.sub(r"\[\d+\]", "", history)`;
  2. system prompt 补一条规则:历史聊天记录仅用于理解当前问题的背景,**不是事实来源、不能作为引用对象**,事实和引用编号只能来自"上下文"。
- **复习点**:RAG 多轮里,"历史"和"当前引用源"是两类东西,编号体系不能混。这正是引用正确性(faithfulness)难点的一个具体来源。

### P5. 抽 service 时把 HTTP 关注点漏进了 service

- **现象**:`handle_chat`(service 层)里直接 `raise HTTPException(status_code=404/502)`。
- **问题**:service 被 FastAPI 绑死,无法脱离 HTTP 单独测试;违背分层(service 不该认识 HTTP 状态码)。
- **正解**:service 抛**领域异常** `ConversationNotFound`;router 负责翻译:
  ```python
  except ConversationNotFound:
      raise HTTPException(status_code=404, ...)
  except Exception:
      raise HTTPException(status_code=502, ...)
  ```
- **复习点**:状态码是协议层(router)的事;service 只表达"发生了什么"(领域异常),不表达"该返回几"。

### P6. 事务边界:RAG 失败留空会话 + 两次 commit

- **现象(旧)**:router 先 `create_conversation`(内部立即 commit),再跑 RAG。RAG 失败时,空会话已经留在库里;新会话和消息还是两次独立 commit。
- **正解**:把**所有写库操作挪到 RAG 成功之后**,并合成一个事务:
  ```python
  # 取历史(只读)→ 改写 → 检索生成(都不写库)
  # 成功后才写:
  conv = await create_conversation(db, ..., commit=False)  # 只 flush 拿 id
  await add_message(..., commit=False)  # user
  await add_message(..., commit=False)  # assistant
  await db.commit()                     # 一次提交
  ```
  RAG 中途失败直接抛出,`get_db` 的 `async with` 关闭 session 时回滚未提交的 INSERT,**一个字都不写**。
- **复习点**:
  1. 顺序:先只读(取历史)→ 跑外部慢调用(LLM)→ 最后集中写库;
  2. 一个逻辑操作 = 一个事务一次 commit;
  3. 为什么不用"先建会话、失败再回滚":那样会把数据库事务挂在几秒的 LLM 调用上,占着连接,且代码更绕。

### P7. 抽出来的 `handle_chat` 写完忘了 `return`

- **现象**:函数体最后是 `pass`,路由拿到 `None`,`response_model` 校验失败 → 500。
- **复习点**:抽函数后,确认返回值真的接上了(这里返回 `QueryResponse`)。

### P8. 代理 `ConnectError` 是环境问题,不是代码问题

- **现象**:`httpcore.ConnectError`,traceback 里出现 `http_proxy.py ... start_tls`。
- **原因**:本地代理(`127.0.0.1:7897`)那一刻不可用。中国大陆访问 Gemini 必须走代理,代理一断,所有 LLM/embedding 调用都连不上。
- **排查**:
  ```bash
  nc -z 127.0.0.1 7897        # 端口在不在
  curl -x http://127.0.0.1:7897 https://generativelanguage.googleapis.com/  # 经代理能否连通
  ```
- **复习点**:traceback 最深处落在 httpx/httpcore 传输层、且出现 `proxy`/`start_tls` 字样 = 网络/代理问题,先查环境,别改代码。

### P9. 用 `flush` 就能拿到会话 id(因为 UUID 是 python 端默认值)

- **细节**:`id = mapped_column(Uuid, default=uuid.uuid4)` 是 **python 端默认值**,`flush` 时就生成,不需要 commit;而 `created_at = mapped_column(..., server_default=func.now())` 是**数据库端默认值**,要 commit/refresh 之后才有值。本次只需要 id,所以 `flush` 足够。
- **复习点**:`default`(python 端)vs `server_default`(DB 端),拿到值的时机不同。需要自增 int 主键时同理——靠 flush 拿。

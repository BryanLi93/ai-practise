# RAG 评测体系：快速复习版

> 复习时先看前 3 节，忘记具体文件和运行条件时再看最后的“项目事实备查”。环境与依赖问题见 [README](../README.md)。

## 1. 一分钟回忆

### 一句话说明

准备一套带参考答案的问题，先从真实 RAG 采集回答和检索片段，再用 Ragas 评估回答与检索质量，同时记录时延、token 和成本，最后用同一套题比较不同 Prompt。

### 五个脚本只记这五件事

```text
01 跑通：用 1 道题确认 Ragas 能正常打分
02 采集：调用真实 RAG，保存回答和检索片段
03 打分：读取采集结果，计算 4 个质量指标
04 测性能：重新调用 RAG，记录时延、token、成本
05 比 Prompt：分别采集和评测 v1、v2，比较结果
```

### 主流程

```text
标准题库 Golden Dataset
question + reference
        │
        ▼
02 调用 /query
        │
        ▼
评测数据集
user_input + reference + response + retrieved_contexts
        │
        ▼
03 Ragas 打分 ──> 质量报告

Golden Dataset + 质量报告
        │
        ▼
04 再调 /query ──> 时延、token、成本 ──> 统一面板

Prompt v1 / v2 + 同一套 Golden Dataset
        │
        ▼
05 各自采集、打分 ──> Prompt 对比记录
```

这套评测回答两类问题：

- 质量：检索有没有漏、准不准，回答有没有编、切不切题。
- 运营：一次回答需要多久、消耗多少 token、成本多少。

## 2. 四个字段如何变成四个指标

一条评测数据由两部分组成：

```text
人工准备：question（映射为 user_input） + reference
RAG 返回：answer（映射为 response）      + sources[].content（映射为 retrieved_contexts）
```

四个质量指标就是在这些内容之间做比较：

| 指标 | 比较什么 | 快速理解 |
|---|---|---|
| `faithfulness` | 回答 ↔ 检索片段 | 回答有没有脱离材料自己编 |
| `answer_relevancy` | 回答 ↔ 问题 | 回答有没有答非所问 |
| `context_recall` | 检索片段 ↔ 参考答案 | 参考答案需要的信息有没有漏检 |
| `context_precision` | 检索片段 ↔ 参考答案 | 检索内容是否相关，相关内容是否排在前面 |

最容易混淆的是 Recall 和 Precision：

- Recall 看“该找的是否找全了”。
- Precision 看“找回来的是否准确、排序是否合理”。

还要记住一个例外：`in_kb=false` 表示问题不在知识库中。这类题用于检查 RAG 能否正确拒答，不参加 4 个指标的自动汇总，而是单独人工确认。因为 Ragas 可能把正确拒答误判为低分。

## 3. 五个必须能解释的问题

### 3.1 为什么必须准备参考答案？

因为 `context_recall` 和 `context_precision` 需要知道“正确答案需要哪些信息”，才能判断检索是否漏掉内容、是否检索准确。没有 `reference`，只能评回答，无法完整评检索。

### 3.2 为什么采集和打分要拆开？

两者的重跑原因不同：

- RAG 改了，例如更换 embedding、调整检索、修改 `top_k` 或默认 Prompt，要重新采集。
- 只改评测，例如更换裁判模型、增加指标或修改汇总方式，只需重新打分。

拆开后，`eval_dataset.json` 就是一份固定的回答快照。修改评测逻辑时，可以反复用同一批回答计算，不必重新调用 RAG，也不会被每次生成结果的变化干扰。

### 3.3 为什么性能评测要再次调用 RAG？

保存下来的回答只能用于质量打分，不能反映当前请求实际用了多久、消耗了多少 token。`04_perf.py` 必须重新调用 `/query`，在调用前后读取时间和 token 计数。

运行前要清空答案缓存，否则缓存命中会让时延和 token 结果失真。

### 3.4 为什么知识库外的问题要人工确认？

正确行为应该是明确拒答，但 Ragas 主要判断回答与参考答案、检索片段之间的关系，可能把正确拒答打成低分。因此这类题不混入平均分，只检查是否真的拒绝编造。

### 3.5 为什么 Prompt A/B 不能看所有指标？

Prompt 改的是生成回答，不是检索结果，因此它理论上只能直接影响：

- `faithfulness`
- `answer_relevancy`

`context_recall` 和 `context_precision` 评的是检索。它们如果在 Prompt A/B 中发生变化，不能直接说是 Prompt 带来的提升，还要先排查裁判波动或检索结果是否真的变化。

## 4. 一道题如何走完全程

以 `python-pydantic-vs-orm` 为例：

```text
① Golden Dataset
问题：为什么 Pydantic schema 不应该直接替代 ORM model？
参考答案：Pydantic 负责接口校验和序列化，ORM 负责数据库映射和持久化。

② 02_collect.py
把问题发给 /query，得到：
- response：RAG 的回答
- retrieved_contexts：RAG 找到的 3 个片段

③ 03_eval.py
- 回答 vs 片段    → faithfulness
- 回答 vs 问题    → answer_relevancy
- 片段 vs 参考答案 → context_recall / context_precision

④ 04_perf.py
重新请求并记录 latency、prompt_tokens、completion_tokens、cost。
最后与质量分合并到 panel.csv。
```

当前报告中，这道题的质量分约为 `1.0 / 0.95 / 1.0 / 1.0`，时延为 `1156ms`，token 为 `905 + 99`。复习时重点记住数据怎么流，不需要背这些历史数字。

## 5. Prompt A/B 实验的关键结论

`v2` 只比 `v1` 多了一条规则：只回答问题所问的内容，不做无关延伸。

2026-06-26 各运行一次后的变化：

```text
faithfulness      -0.0085
answer_relevancy  -0.0049
context_recall     0
context_precision +0.0555
```

结论不是“v2 更好”，而是“这次实验不足以下结论”：

1. 真正可能受 Prompt 影响的两个回答指标都没有明显提高。
2. 两版检索片段相同，但 `context_precision` 仍相差约 0.056，说明 LLM 裁判的单次分数会波动。
3. 只运行一次，无法区分 Prompt 效果和裁判波动。

更可靠的做法：

- 每个版本运行 2–3 次，比较均值。
- 增加更容易出现跑题的测试问题。
- 只根据与本次改动有关的指标判断效果。

这里最该记住的是：做 A/B 不能只看哪个数字更高，要先判断这个改动本来能影响哪些指标。

## 6. 30 秒复述版

我给 RAG 服务做了一套黑盒评测，不需要改服务内部代码，只通过 `/query` 采集回答和检索片段。题库里先准备问题和参考答案，采集后组成 Ragas 需要的四个字段，再分别评回答是否忠于材料、是否切题，以及检索有没有漏、准不准。质量评测和性能评测分开，性能部分另外统计时延、token 和成本。最后我还用同一套题做 Prompt A/B，但单次 LLM 裁判分数会波动，所以不能只跑一次就判断哪个版本更好。

## 7. 合上文档后自测

1. Golden Dataset 和 `eval_dataset.json` 各包含什么？后者多了什么？
2. 四个质量指标各自在比较什么？
3. 为什么 `02_collect.py` 和 `03_eval.py` 要分开？
4. RAG 改了与裁判模型改了，分别需要重跑哪些脚本？
5. 为什么 `04_perf.py` 运行前要清空答案缓存？
6. 为什么知识库外问题不参加自动汇总？
7. Prompt 改动应该重点观察哪两个指标？
8. 为什么当前 v1/v2 的结果不能证明 v2 更好？

如果这 8 个问题能不看文档回答出来，这一部分就已经复习到位。

## 8. 项目事实备查

### 接口约定

- 被测服务：`http://127.0.0.1:8000/query`
- 请求字段：`question`、`top_k=3`；Prompt A/B 时额外传 `system_prompt`
- 响应字段：`answer`、`sources[].content`
- 评测方式：黑盒 HTTP 调用，不 import RAG 内部代码

### 脚本与产物

| 脚本 | 输入 | 输出 |
|---|---|---|
| [`01_first_score.py`](../scripts/01_first_score.py) | 一条硬编码样本 | 控制台中的 4 指标结果 |
| [`02_collect.py`](../scripts/02_collect.py) | `data/golden.json` | `data/eval_dataset.json` |
| [`03_eval.py`](../scripts/03_eval.py) | `data/eval_dataset.json` | `reports/report.csv`、`reports/summary.json` |
| [`04_perf.py`](../scripts/04_perf.py) | `data/golden.json`、`reports/report.csv`、RAG `/metrics` | `reports/panel.csv`、`reports/perf_summary.json` |
| [`05_prompt_ab.py`](../scripts/05_prompt_ab.py) | `prompts/<version>.json`、`data/golden.json` | `reports/prompt_runs.json` |

`05_prompt_ab.py` 不复用 `eval_dataset.json`，因为每个 Prompt 版本都需要重新生成回答。同一版本再次运行时，会覆盖台账中的旧记录。

### 当前能力边界

当前项目实现的是离线黑盒评测和基础性能统计。生产环境可以进一步记录线上请求数据，再异步抽样评测和人工复核，但这些不是当前项目已经实现的能力。

### 什么时候重跑

| 变化 | 需要运行 |
|---|---|
| 首次搭建或升级 Ragas | `01_first_score.py` |
| RAG 回答或检索发生变化 | `02_collect.py` → `03_eval.py` |
| 只修改指标、裁判或汇总逻辑 | `03_eval.py` |
| 重新测量时延、token、成本 | 清空答案缓存后运行 `04_perf.py` |
| 新增或修改 Prompt 版本 | `05_prompt_ab.py <version>` |

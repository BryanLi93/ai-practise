# 评测体系总览(运行逻辑)

> 这台"给 RAG 打分的机器"的整体逻辑。配合 `scripts/` 下 4 个脚本看。
> 完整脚本职责与复用方法见 README;本文聚焦"为什么这样跑、数据怎么流"。

## 一、定位 + 心智模型

**这个项目是一台「给 RAG 打分的机器」。** 它**黑盒**对待被测 RAG——只通过 HTTP 调 `/query`,从不 import RAG 的代码。所以它能评测**任何**有类似接口的 RAG。

打的分分两类:

```
质量(用 ragas,LLM 当裁判)         运营(自己测)
├─ 检索层: recall  该捞的漏没漏     ├─ latency  多快
│          precision 捞的准不准    ├─ tokens   烧多少
└─ 生成层: faithfulness 有没有编    └─ cost     多贵(token × 单价)
           relevancy   切不切题
```

- 质量 = "答得好不好",运营 = "答得多快多贵",两者合起来才是完整评测。
- 4 个质量指标的本质都是"拿两样东西对比",区别只在比哪两样(见第三节)。

## 二、流水线:4 个脚本 + 中间文件串起来

```
你手写
  golden.json ───────────────┐  (question + reference + in_kb)
  (题库)                      │
                              ▼
  02_collect.py ── 调 /query ──> eval_dataset.json
  (黑盒采集)                    (补上 response + retrieved_contexts,4 字段齐)
                              │
                              ▼
  03_eval.py ── ragas 4 指标 ──> report.csv(每题)+ summary.json(汇总)
  (质量打分)
                              
  04_perf.py ── 再调 /query 测时延/token ──> panel.csv + perf_summary.json
  (运营 + 合并质量分成统一面板)
```

### 关键设计:采集(02)和打分(03)分开

两步**重跑的频率和原因不同**,所以拆开:

- 采集重跑 = RAG 改了(换 embedding / 调 prompt / 改 top_k);RAG 没动就不该重采。
- 打分重跑 = 评测改了(加指标 / 换裁判 / 改聚合);这时 RAG 答案一个字没变。

耦在一起的话,只想"重算个分"也得把几十~几百次 RAG 调用、真金白银的 token 全重跑一遍。拆开后两个好处:

1. **改评测不必重烧 RAG**:对着冻结的 `eval_dataset.json` 重跑 03 即可。(本项目修聚合逻辑那次,就是直接拿 `report.csv` 重算 summary、没碰 RAG。)
2. **可复现对比**:`/query` 不确定(LLM 每次答得略不同),冻结快照才能让"裁判 A vs B""指标 v1 vs v2"跑在同一批答案上,公平对照。

类比:就是**录 HTTP fixture**(nock / msw)——`eval_dataset.json` 是录像,02 录制、03 对着录像跑断言。

**生产里更要分,且会进化成**:采集 → "记录线上 trace"(服务副产品,落 LangSmith/Langfuse);打分 → "异步评测作业"(事后批量+抽样+人工复核)。因为在线回答用户要秒级返回,不可能卡着等 LLM 裁判跑几分钟——评测必须从主链路剥离、跑在存下来的数据上。

`01_first_score.py` 不在这条正式流水线里——它是**学习脚手架**:一条硬编码数据跑通 4 指标,验证"引擎能转"。真正跑数据集是 02 → 03 → 04。

### 一条评测数据的 4 个字段(SingleTurnSample)

```
你写的(golden):   user_input(问题)        reference(标准答案)
服务采集的(/query): response(答案)          retrieved_contexts(检索片段 list[str])
```

`/query` 响应映射:`answer → response`、`[s["content"] for s in sources] → retrieved_contexts`。

## 三、一条问题走完全程(以 `python-pydantic-vs-orm` 为例)

```
① golden.json 里你写好两样:
   user_input = "为什么 Pydantic schema 不应该直接替代 ORM model?"
   reference  = "Pydantic schema 面向接口边界…ORM model 面向数据库表…职责不同…"

② 02_collect.py 拿 user_input 调 POST /query,RAG 返回:
   answer  → response           = "Pydantic 负责校验序列化,ORM 负责持久化…"
   sources → retrieved_contexts = ["Pydantic schema 面向接口边界…", …3 段]
   → 四样拼成一条存进 eval_dataset.json

③ 03_eval.py 把这条喂 ragas,4 个指标各挑两样对比:
   faithfulness: response ↔ contexts   → 1.0  (没编)
   relevancy   : response ↔ user_input → 0.95 (切题)
   recall      : contexts ↔ reference  → 1.0  (没漏)
   precision   : contexts ↔ reference  → 1.0  (准)
   → 写进 report.csv

④ 04_perf.py 再调一次 /query,掐表 + 抓 /metrics token 差:
   latency 1156ms, prompt 905, completion 99
   → 和 report.csv 合并 → panel.csv 里这一行:质量分 + 运营指标全有
```

每个指标"比哪两样":

| 指标 | 对比的两样 | 量什么 |
|---|---|---|
| `faithfulness` | response ↔ retrieved_contexts | 答案有没有编(忠于检索内容) |
| `answer_relevancy` | response ↔ user_input | 答案切不切题(需 embeddings) |
| `context_recall` | retrieved_contexts ↔ reference | 该检索的有没有漏 |
| `context_precision` | retrieved_contexts ↔ reference | 检索的准不准 / 排序 |

## 四、Prompt A/B(05_prompt_ab.py)与一个关键教训

把 prompt 版本化(`prompts/v1.json`/`v2.json`),用 `/query` 的 `system_prompt` 覆盖跑评测,分数挂到版本上对比。这是整套评测的"目的":改 prompt 用数字证明好坏。

**v1 vs v2 的区别**:只差规则 5 加的一句——v2 多了"只回答问题所问的那一点,不要扯到无关概念"(治跑题)。其余一字不差。

**实跑结果(各 1 次)**:

```
        faithfulness  relevancy  recall  precision
v1        0.9722       0.8143     1.0     0.8704
v2        0.9637       0.8094     1.0     0.9259   ← precision +0.056
```

**教训(比"谁赢"更重要):**

1. **prompt 只改答案(response),不碰检索**。所以它只可能动含 response 的指标:`faithfulness`、`relevancy`。`recall`/`precision` 是 检索片段↔reference、不含 response → **prompt 动不了它们**,两版检索片段一模一样。
2. 所以 v2 那个 **precision +0.056 不是 prompt 的功劳,是裁判噪声**(同样输入、不同次打分会飘)。`recall` 顶在 1.0 飘不动,正好当对照组。
3. **拿这 0.056 当噪声尺子**:v2 真正能影响的 faithfulness(-0.008)、relevancy(-0.005)都比噪声小一个量级 → 等于没动。**单跑一次不能证明 v2 更好。**
4. 严谨做法:① 改 prompt 只看 `faithfulness`/`relevancy`;② 每版跑 2-3 次取均值压过噪声,或用更难、跑题更吃亏的题。

> 一句话:A/B 的真功课是**挑对指标 + 知道自己的噪声底**,别被一次跑分骗了。

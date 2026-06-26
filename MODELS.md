# 切换模型 / 模型挂了怎么办(全项目检查清单)

当某个模型不可用(硅基流动限流、下线、报错),或你想统一换模型时,照这份清单改。
**关键认知:模型配置散在多个项目的 `.env` 和少量代码里,漏一个就会出现"有的服务用新模型、有的还用旧的"。**

---

## 0. 先判断:是"模型挂了/限流"还是别的问题

调用一直超时,先确认是不是模型侧的问题(而不是你代码):

```bash
# 宿主机直连一次 chat;再在容器里直连一次。两边都 APITimeoutError = 模型限流/下线
cd 1314-eval
.venv/bin/python -c "
import os; from dotenv import load_dotenv; from openai import OpenAI
load_dotenv('.env'); c=OpenAI(api_key=os.environ['OPENAI_API_KEY'], base_url=os.environ['OPENAI_BASE_URL'])
print(c.chat.completions.create(model=os.environ['CHAT_MODEL'],
  messages=[{'role':'user','content':'回复:好'}], max_tokens=10, timeout=30,
  extra_body={'enable_thinking': False}).choices[0].message.content)
"
```

- **超时**:硅基流动限流(我一个 session 打太多会触发)或模型下线 → 停 15-20 分钟,或按下面换模型。
- **正常返回**:模型没事,问题在别处。

---

## 1. 所有模型配置在哪(改之前对着这张表)

| 类型 | 文件 | 字段 | 用途 |
|---|---|---|---|
| **chat** | `0607-rag-service/.env` | `CHAT_MODEL` | RAG 生成答案 |
| **chat** | `0910-langgraph-agent/.env` | `CHAT_MODEL` | Agent |
| **chat** | `1314-eval/.env` | `CHAT_MODEL` | 评测裁判 |
| **chat** | `0607-rag-service/app/metrics.py` | `MODEL_PRICES` | 成本单价(加新模型一行,否则 cost=0) |
| **chat** | `1314-eval/scripts/04_perf.py` | `MODEL` 常量 | 必须等于 RAG 的 CHAT_MODEL(按它读 /metrics token) |
| **embedding** | `0607-rag-service/.env` | `EMBEDDING_MODEL` `EMBEDDING_DIM` | 向量化(换它要清库重灌,见 §3) |
| **embedding** | `1314-eval/.env` | `EMBEDDING_MODEL` | 评测的语义相似度 |
| **rerank** | `0607-rag-service/.env` | `RERANK_MODEL` | 重排 |
| **provider** | 各 `.env` | `OPENAI_BASE_URL` `OPENAI_API_KEY` | 整个服务商(硅基流动) |

> 注:`config.py` / `llm.py` / `rerank.py` / 前端 `think.ts` 里出现的模型名都是**注释示例**,不影响运行,可不改。

---

## 2. 换 chat 模型(最常见、最轻)

1. 改这 3 个 `.env` 的 `CHAT_MODEL` 成新模型名(三处要一致):
   `0607-rag-service/.env`、`0910-langgraph-agent/.env`、`1314-eval/.env`
2. `0607-rag-service/app/metrics.py` 的 `MODEL_PRICES` 加一行新模型单价(元/1K tokens):
   ```python
   "新模型名": {"prompt": 0.0005, "completion": 0.004},
   ```
3. `1314-eval/scripts/04_perf.py` 顶部 `MODEL = "新模型名"`(要和 RAG 的 CHAT_MODEL 一样)
4. **重建 RAG 容器**(改了 .env 和 metrics.py 代码都要;一条命令覆盖):
   ```bash
   cd 0607-rag-service && docker compose up -d --build app
   docker exec rag-app sh -c 'echo $CHAT_MODEL'   # 确认已是新模型
   ```
5. **清答案缓存**(缓存键含模型名,旧答案别留着混淆):
   ```bash
   docker exec rag-redis redis-cli --scan --pattern "ans:*" | xargs -r -I{} docker exec rag-redis redis-cli DEL "{}"
   ```
6. (Qwen3 等"思考模型")代码里已统一传 `extra_body={"enable_thinking": False}`,无需改。换成**非思考/非 Qwen** 模型时,确认该模型不会因这个参数报错。

> embedding、rerank **不用动**,数据库**不用清**——换 chat 不影响向量。

---

## 3. 换 embedding 模型(重!必须清库重灌)

⚠️ **向量跨模型不可比**:换了 embedding,库里所有旧向量作废,不重灌会检索全乱。

1. 改 `0607-rag-service/.env` 的 `EMBEDDING_MODEL`;**维度变了**还要改 `EMBEDDING_DIM`,并改 `app/models.py` 里 `embedding HALFVEC(1024)` 的维度
2. 改 `1314-eval/.env` 的 `EMBEDDING_MODEL`(评测也要用同款)
3. 清向量库 + 清 embedding 缓存:
   ```bash
   docker exec rag-postgres psql -U rag -d rag -c "TRUNCATE documents, conversations RESTART IDENTITY CASCADE;"
   docker exec rag-redis redis-cli --scan --pattern "emb:*" | xargs -r -I{} docker exec rag-redis redis-cli DEL "{}"
   ```
   (维度变了:先 `docker compose down -v` 清表,改完 models.py 后重建表)
4. 重建容器:`cd 0607-rag-service && docker compose up -d --build app`
5. **重新入库那 4 篇文档**(`scripts/test_data/documents/` 下),用 `/upload` 接口或入库脚本
6. 评测侧重新采集:`cd 1314-eval && .venv/bin/python scripts/02_collect.py`(旧 eval_dataset.json 作废)

---

## 4. 换 rerank 模型

只改 `0607-rag-service/.env` 的 `RERANK_MODEL` → 重建容器。rerank 是无状态 API 调用,不涉及缓存和库。

---

## 5. 整个 provider 挂了(硅基流动整体不可用)

换服务商:改各 `.env` 的 `OPENAI_BASE_URL` + `OPENAI_API_KEY`,并把 `CHAT_MODEL`/`EMBEDDING_MODEL`/`RERANK_MODEL` 换成新服务商上有的型号。embedding 模型若变 → 按 §3 清库重灌。

---

## 改完自检(任何改动后跑一遍)

```bash
# 1. RAG 还能正常答(用新 chat 模型)
curl -s -X POST http://127.0.0.1:8000/query -H "Content-Type: application/json" \
  -d '{"question":"什么是 chunk_overlap?","top_k":3}' | head -c 200

# 2. 评测裁判能连通
cd 1314-eval && .venv/bin/python scripts/01_first_score.py
```

> docker 与本地两种运行方式的区别:容器跑 = 改完要 `docker compose up -d --build app`;
> 本地 `fastapi dev` 跑 = 改 .py 自动重载,但**改 .env 不重载,要手动重启进程**。

# 学习路线图 & 博客选题

> 从 CLAUDE.md 抽出的中长期规划。近期 Week 7 的逐 Day 任务仍在 CLAUDE.md 第 6 节。

## 24 周课程后续 Week

- **Week 8**:RAG 工程化(Redis 缓存、日志配置、Docker 多服务、成本/token 监控)
- **Week 9-10**:LangGraph Agent(注意:Week 7 的多轮对话 ≠ Agent;Agent 是 LLM 决定调工具的多步任务)
- **Week 11-12**:Next.js + Vercel AI SDK 产品级前端(流式渲染、Tool 可视化、引用 UI)+ **开始投简历**
- **Week 13-14**:评测体系(Ragas:Context Recall / Faithfulness,用现成的 10 个 golden questions)
- **Week 15-18**:项目 2(业务 Workflow Agent)
- **Week 19**:MCP 基础(flagged 为前瞻必学)
- **Week 20-21**:ML 补课(scikit-learn / PyTorch 最小闭环 / Transformer 概念 / LoRA 直觉)
- **Week 22-24**:作品集包装 + 技术博客 + 面试冲刺

## 可写的技术博客选题(Week 23 用)

- pgvector 维度上限 / HALFVEC workaround(3072→1536 的来龙去脉)
- Gemini embedding SDK 不兼容 OpenAI 层(task_type 缺失)
- 中文文本用 RecursiveCharacterTextSplitter 的坑(需显式中文标点分隔符)
- 前端工程师如何构建生产级 RAG 系统(综述向)
- RRF vs 加权求和:为什么混合检索用排名而非分数
- Bi-encoder vs Cross-encoder:RAG 为什么必须召回+精排两段

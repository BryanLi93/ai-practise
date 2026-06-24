"""
Agent HTTP 端点:把 LangGraph agent 的「工具事件 + 答案 token」吐成 SSE。
给 1112-frontend 的 BFF 适配器消费(对照 rag-service 的 /query/stream)。

前置:RAG 服务要在 :8000 起着(工具会去调它)。

跑:.venv/bin/python -m uvicorn 15_agent_server:app --host 127.0.0.1 --port 8100
测:curl -N -X POST http://127.0.0.1:8100/agent/stream \
      -H "Content-Type: application/json" \
      -d '{"question":"pgvector 用什么距离度量?"}'
"""
from __future__ import annotations

import json

import requests
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk, ToolMessage
from langchain.agents import create_agent

from llm import get_chat_client


# ---------- 工具:RAG 作为 agent 的一个工具(抄 11_demo_rag_agent.py)----------
@tool
def search_knowledge_base(query: str) -> str:
    """内部技术知识库,涵盖 FastAPI 后端 / RAG pipeline / pgvector 运维 / Java 并发;遇到这类问题时调用"""
    resp = requests.post(
        "http://127.0.0.1:8000/query",
        json={"question": query, "top_k": 3},
        timeout=30,
    )
    resp.raise_for_status()
    sources = resp.json()["sources"]
    parts = [f"文档名：{s['document_filename']} / 内容：{s['content']}" for s in sources]
    return "\n\n".join(parts)


agent = create_agent(
    get_chat_client(),
    tools=[search_knowledge_base],
    system_prompt="知识库问题用工具查、查到再答;通用问题直接答,别瞎调工具",
)


# ---------- 应用 ----------
app = FastAPI(title="Agent Stream Service")


class AgentQuery(BaseModel):
    question: str


def _sse(frame: dict) -> str:
    """一个语义帧 → 一条 SSE 消息(抄 rag-service/query.py 的 _sse)。"""
    return f"data: {json.dumps(frame, ensure_ascii=False)}\n\n"


@app.post("/agent/stream")
async def agent_stream(req: AgentQuery):
    """
    两个 stream 模式一起开,把 LangGraph 的事件翻译成前端要的帧:
      updates 模式 → 节点级整条消息,工具调用/结果在这 → step 帧
      messages 模式 → 逐 token → token 帧
    帧顺序:step(running) → step(done) → token×N → done。
    """
    async def event_stream():
        try:
            async for mode, payload in agent.astream(
                {"messages": [HumanMessage(req.question)]},
                stream_mode=["updates", "messages"],
            ):
                if mode == "updates":
                    # payload = {节点名: {"messages": [整条消息]}}
                    for _node, data in payload.items():
                        for msg in data.get("messages", []):
                            # LLM 决定调工具 → step running(带入参)
                            if isinstance(msg, AIMessage) and msg.tool_calls:
                                for tc in msg.tool_calls:
                                    yield _sse({
                                        "type": "step",
                                        "id": tc["id"],
                                        "tool": tc["name"],
                                        "status": "running",
                                        "input": tc["args"],
                                    })
                            # 工具返回 → step done(带结果),靠 tool_call_id 跟上面配对
                            elif isinstance(msg, ToolMessage):
                                yield _sse({
                                    "type": "step",
                                    "id": msg.tool_call_id,
                                    "tool": msg.name,
                                    "status": "done",
                                    "output": msg.content,
                                })
                            # 没有 tool_calls 的 AIMessage = 最终答案整条,token 已从 messages 来,这里跳过

                elif mode == "messages":
                    chunk, _meta = payload
                    # ⚠️ 只认 AIMessageChunk:messages 模式也会吐一条 ToolMessage(工具结果整段),
                    #    不挡掉的话那一大段会被当成答案 token 喷给前端(探查脚本里亲眼见过)
                    if isinstance(chunk, AIMessageChunk) and chunk.content:
                        yield _sse({"type": "token", "content": chunk.content})

            yield _sse({"type": "done"})
        except Exception as e:
            # 已经开流,HTTP 状态码改不了,只能把错误当一条数据帧发出去(同 rag-service)
            yield _sse({"type": "error", "message": type(e).__name__})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

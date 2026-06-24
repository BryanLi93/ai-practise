"""
探查脚本:看清 LangGraph 双模式流到底吐出什么形状。
不写端点之前,先用真数据确认:工具调用(入参)和工具结果各长什么样、答案 token 在哪。

跑(需先起 RAG 服务 :8000):.venv/bin/python 14_inspect_stream.py
"""
import asyncio

import requests
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain.agents import create_agent

from llm import get_chat_client


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

QUESTION = "pgvector 用什么距离度量?"


async def main():
    # 两个模式一起开:每个 item 多包一层,变成 (mode, payload)
    async for item in agent.astream(
        {"messages": [HumanMessage(QUESTION)]},
        stream_mode=["updates", "messages"],
    ):
        mode, payload = item

        if mode == "updates":
            # payload = {节点名: {"messages": [整条消息]}}
            for node, data in payload.items():
                for msg in data.get("messages", []):
                    kind = type(msg).__name__
                    extra = ""
                    if isinstance(msg, AIMessage) and msg.tool_calls:
                        extra = f" tool_calls={msg.tool_calls}"
                    if isinstance(msg, ToolMessage):
                        extra = f" name={msg.name} tool_call_id={msg.tool_call_id}"
                    print(f"[updates] node={node} {kind}{extra} content={str(msg.content)[:80]!r}")

        elif mode == "messages":
            # payload = (AIMessageChunk, metadata)
            chunk, _meta = payload
            if getattr(chunk, "content", ""):
                print(f"[messages] {type(chunk).__name__} content={chunk.content!r}")


if __name__ == "__main__":
    asyncio.run(main())

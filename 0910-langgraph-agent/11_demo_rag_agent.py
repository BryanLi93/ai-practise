from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
import requests
from langchain.agents import create_agent

from llm import get_chat_client

@tool
def search_knowledge_base(query: str) -> str:
    """这是一个内部技术知识库,涵盖 FastAPI 后端 / RAG pipeline / pgvector 运维 / Java 并发;遇到这类问题时调用""" # ← 名字 + docstring 一起被 LLM 读去判断"要不要调我"
    resp = requests.post(
        "http://127.0.0.1:8000/query",
        json={
            "question": query,
            "top_k": 3,
        },
        timeout=30
    )
    resp.raise_for_status() # 非 2xx 直接抛异常,别让坏响应往下走
    sources = resp.json()["sources"]

    parts = []
    for s in sources:
        # 内层用单引号,避免和外层 f-string 的双引号打架(也兼容 3.11)
        parts.append(f"文档名：{s['document_filename']} / 相关性：{s['similarity']} / 内容：{s['content']}")
    return "\n\n".join(parts)


if __name__ == "__main__":
    agent = create_agent(
        get_chat_client(),
        tools=[search_knowledge_base],
        system_prompt="知识库问题用工具查、查到再答;通用问题(算术、闲聊)直接答,别瞎调工具",
    )

    for q in ["3加5的结果乘以3等于多少?", "pgvector 用什么距离度量?"]:
        print(f"\n===== Question: {q} =====")
        for update in agent.stream({"messages": [HumanMessage(q)]}, stream_mode="updates"):
            for payload in update.values():        # update = {节点名: {"messages": [...]}},只关心值
                for msg in payload["messages"]:
                    msg.pretty_print()             # LangChain 内置:一行出框线格式

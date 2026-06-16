"""
Step 12:多 Agent / 子图 —— supervisor 路由 + 专家 agent 当节点
结构同 Step 2 条件分支,只是分支终点从「函数」换成「一整个 agent」。

跑:.venv/bin/python 13_multi_agent.py(技术那条要 rag-service 起在 :8000)
"""
import requests
from langgraph.graph import StateGraph, START, END, MessagesState
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage

from llm import get_chat_client


# ---- 工具(从 11_demo_rag_agent.py 抄来,给技术 agent 用)----
@tool
def search_knowledge_base(query: str) -> str:
    """内部技术知识库,涵盖 FastAPI / RAG / pgvector / Java 并发;遇到这类问题时调用"""
    resp = requests.post(
        "http://127.0.0.1:8000/query",
        json={"question": query, "top_k": 3},
        timeout=30,
    )
    resp.raise_for_status()
    sources = resp.json()["sources"]
    return "\n\n".join(
        f"文档名：{s['document_filename']} / 相关性：{s['similarity']} / 内容：{s['content']}"
        for s in sources
    )


# ---- 两个专家 agent:各自的图,待会儿直接当节点插进大图 ----
tech_agent = create_agent(
    get_chat_client(),
    tools=[search_knowledge_base],
    system_prompt="你是技术支持,用知识库工具查到再答",
)
general_agent = create_agent(
    get_chat_client(),
    tools=[],
    system_prompt="你是通用助手,算术/闲聊直接答",
)


# ---- 大图的 state:MessagesState 多挂一个 next 存路由决定 ----
class MultiAgentState(MessagesState):
    next: str


# ---- supervisor:一个 LLM 调用,只判类型,把决定写进 next ----
def supervisor(state: MultiAgentState) -> dict:
    question = state["messages"][-1].content
    decision = get_chat_client().invoke([
        SystemMessage(
            "判断用户问题属于哪类,只回一个词:"
            "技术知识库问题(FastAPI/RAG/pgvector/Java 并发)回 tech,"
            "其它(算术、闲聊)回 general。除这一个词外什么都别输出。"
        ),
        HumanMessage(question),
    ]).content
    next_node = "tech" if "tech" in decision.lower() else "general"  # 兜底:不含 tech 一律 general
    print(f"[supervisor] 问题={question!r} → 路由={next_node}")
    return {"next": next_node}


def route(state: MultiAgentState) -> str:
    return state["next"]


# ---- 搭图:START → supervisor →(条件)→ 某个 agent → END ----
builder = StateGraph(MultiAgentState)
builder.add_node("supervisor", supervisor)
builder.add_node("tech_agent", tech_agent)        # 传编译好的 agent 本身,不是函数
builder.add_node("general_agent", general_agent)

builder.add_edge(START, "supervisor")
builder.add_conditional_edges(
    "supervisor",
    route,
    {"tech": "tech_agent", "general": "general_agent"},
)
builder.add_edge("tech_agent", END)
builder.add_edge("general_agent", END)

graph = builder.compile()


def run(question: str):
    print(f"\n===== 问题:{question} =====")
    for update in graph.stream({"messages": [HumanMessage(question)]}, stream_mode="updates"):
        for node_name, payload in update.items():
            for msg in payload.get("messages", []):  # supervisor 只更新 next,没 messages,跳过
                msg.pretty_print()


if __name__ == "__main__":
    run("3加5等于几?")                 # → general_agent 直接答
    run("pgvector 用什么距离度量?")    # → tech_agent 调知识库

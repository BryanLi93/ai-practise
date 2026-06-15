from langgraph.types import interrupt, Command
from typing import TypedDict, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.runnables import RunnableConfig

class State(TypedDict):
    decision: str

def node_ask(state):
    decision = interrupt("要执行删除操作,批准吗?(yes/no)")
    return { "decision": decision }

def node_execute(state):
    print("已执行")

def node_cancel(state):
    print("已取消")

def should_continue(state: State) -> str:
    return state["decision"]


if __name__ == "__main__":
    builder = StateGraph(State)

    builder.add_node("node_ask", node_ask)
    builder.add_node("node_execute", node_execute)
    builder.add_node("node_cancel", node_cancel)

    builder.add_edge(START, "node_ask")
    builder.add_conditional_edges("node_ask", should_continue, {
        "yes": "node_execute",
        "no": "node_cancel"
    })
    builder.add_edge("node_execute", END)
    builder.add_edge("node_cancel", END)

    graph = builder.compile(checkpointer=InMemorySaver())

    # 复制到 mermaid.live
    print(graph.get_graph().draw_mermaid())

    # 批准
    config1: RunnableConfig = { "configurable": { "thread_id": "1" }}
    result1 = graph.invoke({"decision": ""}, config=config1)
    print("result1---", result1)
    result2 = graph.invoke(Command(resume="yes"), config=config1)
    print("result2---", result2)

    # 拒绝
    config2: RunnableConfig = { "configurable": { "thread_id": "2" }}
    result3 = graph.invoke({"decision": ""}, config=config2)
    print("result3---", result3)
    result4 = graph.invoke(Command(resume="no"), config=config2)
    print("result4---", result4)
